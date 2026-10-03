from django.core.management.base import BaseCommand
from django.db.models import Q

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta
from ventas.services import resumen_por_ejecutivo_actual


SUPERVISORES_CONFIRMADOS = {
    "17480807-4": "CHARLY",
    "16440386-6": "JORGE",
    "17790237-3": "PATRICIO",
    "22186549-9": "VICENTE",
}


class Command(BaseCommand):
    help = "Valida integridad UAT: ESACOM maestro, dotación vigente y focos KPI estrictos."

    def handle(self, *args, **options):
        errores = []
        alertas = []

        self.stdout.write(self.style.MIGRATE_HEADING("ESACOM · VALIDACIÓN INTEGRIDAD UAT"))

        ultima = (
            CargaExcel.objects.filter(tipo_base=CargaExcel.TipoBase.REPORTE_KPI)
            .order_by("-fecha_corte", "-creado_en")
            .first()
        )
        if not ultima:
            errores.append("No existe snapshot KPI cargado.")
            focos = {"B1": "", "B2": "", "B3": ""}
            metas = {"B1": None, "B2": None, "B3": None}
        else:
            focos = {"B1": ultima.foco_b1, "B2": ultima.foco_b2, "B3": ultima.foco_b3}
            metas = {"B1": ultima.meta_b1, "B2": ultima.meta_b2, "B3": ultima.meta_b3}
            self.stdout.write(
                f"Snapshot KPI: #{ultima.id} · {ultima.archivo_nombre} · corte {ultima.fecha_corte} · "
                f"B1 {focos['B1']} · B2 {focos['B2']} · B3 {focos['B3']}"
            )

        # RBAC: solo los cuatro supervisores comerciales confirmados deben estar
        # con rol SUPERVISOR dentro de la dotación comercial UAT.
        supervisores_activos = Ejecutivo.objects.filter(
            cargo=Ejecutivo.Cargo.SUPERVISOR, is_active=True
        ).order_by("nombre")
        ruts_actuales = set(supervisores_activos.values_list("rut", flat=True))
        extras = sorted(ruts_actuales - set(SUPERVISORES_CONFIRMADOS))
        faltantes = sorted(set(SUPERVISORES_CONFIRMADOS) - ruts_actuales)
        if extras:
            errores.append(f"Supervisores CRM no confirmados: {', '.join(extras)}")
        if faltantes:
            errores.append(f"Supervisores CRM confirmados faltantes: {', '.join(faltantes)}")
        if not extras and not faltantes:
            self.stdout.write(self.style.SUCCESS("[OK] Supervisores CRM confirmados: 4/4"))

        # La dotación visible al Supervisor usa únicamente EJECUTIVO + activo.
        for rut, alias in SUPERVISORES_CONFIRMADOS.items():
            sup = Ejecutivo.objects.filter(rut=rut).first()
            if not sup:
                continue
            equipo = Ejecutivo.objects.filter(
                supervisor=sup, cargo=Ejecutivo.Cargo.EJECUTIVO, is_active=True
            )
            reg = equipo.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR).count()
            hon = equipo.filter(tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"[OK] {alias}: {equipo.count()} vigentes · {reg} Regular · {hon} Honorarios"
                )
            )

            # El KPI regular usa Venta.ejecutivo de ESACOM y solo focos oficiales.
            ventas_instaladas = Venta.objects.filter(
                ejecutivo__in=equipo.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR),
                estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
            )
            cortes = Corte.objects.filter(carga_kpi=ultima, venta__in=ventas_instaladas).select_related(
                "venta", "venta__ejecutivo", "venta__ejecutivo__supervisor", "venta__promocion"
            )
            resumen = resumen_por_ejecutivo_actual(cortes, focos=focos, metas=metas)
            for fila in resumen:
                for corte in fila["cortes"]:
                    foco = focos.get(corte["boleta"])
                    if foco and corte["mes_ano"] != foco:
                        errores.append(
                            f"{alias}/{fila['ejecutivo']['rut']}: {corte['boleta']} "
                            f"muestra {corte['mes_ano']} y foco oficial es {foco}."
                        )

        # Dotación ESACOM manda sobre REGULAR/HONORARIOS para toda persona
        # sincronizada desde la hoja Dotación.
        dotacion_activa = Ejecutivo.objects.filter(
            ultima_sync_dotacion__isnull=False,
            cargo=Ejecutivo.Cargo.EJECUTIVO,
            is_active=True,
        )
        inconsistentes_tipo = []
        for e in dotacion_activa.only(
            "rut", "nombre", "tipo_contrato", "estado_contrato_fuente", "tipo_kpi"
        ):
            texto = f"{e.tipo_contrato} {e.estado_contrato_fuente}".upper()
            esperado = (
                Ejecutivo.TipoKPI.HONORARIOS if "HONORARIO" in texto else Ejecutivo.TipoKPI.REGULAR
            )
            if e.tipo_kpi != esperado:
                inconsistentes_tipo.append(f"{e.rut} {e.nombre}: {e.tipo_kpi} -> {esperado}")
        if inconsistentes_tipo:
            errores.append(
                "REGULAR/HONORARIOS no coincide con Dotación: " + "; ".join(inconsistentes_tipo[:12])
            )
        else:
            self.stdout.write(self.style.SUCCESS("[OK] REGULAR/HONORARIOS coincide con Dotación ESACOM vigente"))

        # Los usuarios vigentes sin supervisor no se asignan por semejanza de texto.
        sin_supervisor = dotacion_activa.filter(supervisor__isnull=True)
        if sin_supervisor.exists():
            alias = sorted(set(sin_supervisor.exclude(supervisor_fuente="").values_list("supervisor_fuente", flat=True)))
            alertas.append(
                f"{sin_supervisor.count()} ejecutivos vigentes sin supervisor resuelto"
                + (f" (alias: {', '.join(alias)})" if alias else "")
            )

        self.stdout.write(
            f"Fuente ESACOM: {Venta.objects.count()} ventas · "
            f"{Venta.objects.filter(estado_instalacion=Venta.EstadoInstalacion.INSTALADO).count()} instaladas"
        )

        for alerta in alertas:
            self.stdout.write(self.style.WARNING(f"[ALERTA] {alerta}"))
        if errores:
            for error in errores:
                self.stdout.write(self.style.ERROR(f"[ERROR] {error}"))
            self.stdout.write(self.style.ERROR(f"RESULTADO: {len(errores)} error(es) de integridad."))
        else:
            self.stdout.write(self.style.SUCCESS("RESULTADO: integridad UAT OK. ESACOM manda; KPI solo mide."))

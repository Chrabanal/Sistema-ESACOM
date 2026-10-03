from django.core.management.base import BaseCommand, CommandError

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta
from ventas.services import filtrar_cortes_kpi_operativos, resumen_cortes_actuales


class Command(BaseCommand):
    help = "Valida el Dashboard Supervisor y compara KPI de sus ejecutivos contra la misma regla del Portal Ejecutivo."

    def add_arguments(self, parser):
        parser.add_argument("--rut", required=True, help="RUT del supervisor")
        parser.add_argument("--ejecutivo-rut", help="Opcional: valida además un ejecutivo específico de su equipo")

    def handle(self, *args, **options):
        supervisor = Ejecutivo.objects.filter(rut=options["rut"].strip()).first()
        if not supervisor:
            raise CommandError(f"No existe usuario ESACOM con RUT {options['rut']}")
        if not supervisor.es_supervisor:
            raise CommandError(f"{supervisor.nombre} existe, pero su cargo es {supervisor.cargo}, no SUPERVISOR")

        ultima = (
            CargaExcel.objects.filter(tipo_base=CargaExcel.TipoBase.REPORTE_KPI)
            .order_by("-fecha_corte", "-creado_en")
            .first()
        )
        if not ultima:
            raise CommandError("No hay reportes KPI cargados.")

        focos = {"B1": ultima.foco_b1, "B2": ultima.foco_b2, "B3": ultima.foco_b3}
        metas = {"B1": ultima.meta_b1, "B2": ultima.meta_b2, "B3": ultima.meta_b3}

        equipo = Ejecutivo.objects.filter(
            supervisor=supervisor,
            cargo=Ejecutivo.Cargo.EJECUTIVO,
            is_active=True,
        ).order_by("nombre")
        regulares = equipo.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR)
        honorarios = equipo.filter(tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS)

        self.stdout.write(self.style.SUCCESS(f"Supervisor: {supervisor.nombre} · {supervisor.rut}"))
        self.stdout.write(
            f"Equipo asignado: {equipo.count()} · Regulares: {regulares.count()} · Honorarios: {honorarios.count()}"
        )
        self.stdout.write(
            f"Snapshot activo: #{ultima.id} · {ultima.archivo_nombre} · corte {ultima.fecha_corte} · {ultima.dia_reporte}"
        )

        # Las tarjetas B1/B2/B3 usan exclusivamente la población REGULAR del equipo.
        # Honorarios permanece separado hasta contar con su fórmula oficial.
        cortes_equipo_regular = filtrar_cortes_kpi_operativos(
            Corte.objects.filter(
                carga_kpi=ultima,
                venta__ejecutivo__supervisor=supervisor,
                venta__ejecutivo__is_active=True,
                venta__ejecutivo__tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
            )
        )
        resumen_equipo_regular = resumen_cortes_actuales(
            cortes_equipo_regular, focos=focos, metas=metas
        )
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("CONSOLIDADO KPI REGULAR DEL EQUIPO"))
        if not resumen_equipo_regular:
            self.stdout.write("  Sin KPI regular vigente.")
        else:
            for r in resumen_equipo_regular:
                self.stdout.write(
                    f"  {r['boleta']} {r['mes_ano']}: KPI {r['pct_cumplimiento']:.2f}% · "
                    f"Pago {r['pagadas']} · Pendiente {r['pendientes']} · No Pago {r['no_pago']} · "
                    f"Fuera Plazo {r['fuera_plazo']} · S/B {r['sin_boleta']} · "
                    f"Meta {r['meta_pct']:.1f}% · Q meta {r['faltan_para_meta']} RGU"
                )

        objetivo_rut = (options.get("ejecutivo_rut") or "").strip()
        if objetivo_rut:
            objetivo = equipo.filter(rut=objetivo_rut).first()
            if not objetivo:
                raise CommandError(f"El RUT {objetivo_rut} no pertenece al equipo de {supervisor.nombre}.")
            objetivos = [objetivo]
        else:
            objetivos = list(regulares)

        for ejecutivo in objetivos:
            cortes = filtrar_cortes_kpi_operativos(
                Corte.objects.filter(carga_kpi=ultima, venta__ejecutivo=ejecutivo)
            ).select_related("venta", "venta__promocion")
            resumen = resumen_cortes_actuales(cortes, focos=focos, metas=metas)
            self.stdout.write("")
            self.stdout.write(self.style.HTTP_INFO(f"{ejecutivo.nombre} · {ejecutivo.rut}"))
            if not resumen:
                self.stdout.write("  Sin KPI vigente.")
                continue
            for r in resumen:
                self.stdout.write(
                    f"  {r['boleta']} {r['mes_ano']}: KPI {r['pct_cumplimiento']:.2f}% · "
                    f"Pago {r['pagadas']} · Pendiente {r['pendientes']} · No Pago {r['no_pago']} · "
                    f"Fuera Plazo {r['fuera_plazo']} · S/B {r['sin_boleta']} · "
                    f"Meta {r['meta_pct']:.1f}% · Q meta {r['faltan_para_meta']} RGU"
                )

        if honorarios.exists():
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Honorarios del equipo no se mezclan con B1/B2/B3 regular; su KPI queda pendiente de parametrización específica."
            ))
            for e in honorarios:
                self.stdout.write(f"  - {e.nombre} · {e.rut}")

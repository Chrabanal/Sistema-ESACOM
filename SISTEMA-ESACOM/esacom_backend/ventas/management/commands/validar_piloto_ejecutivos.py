from django.core.management.base import BaseCommand, CommandError

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta
from ventas.services import (
    filtrar_cortes_kpi_operativos,
    resumen_accionables,
    resumen_cortes_actuales,
)


class Command(BaseCommand):
    help = "Valida invariantes críticas del Portal Ejecutivo antes de marcha blanca."

    def handle(self, *args, **options):
        ultima = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI
        ).order_by("-fecha_corte", "-creado_en").first()
        if not ultima:
            raise CommandError("No existe snapshot KPI activo.")

        focos = {"B1": ultima.foco_b1, "B2": ultima.foco_b2, "B3": ultima.foco_b3}
        metas = {"B1": ultima.meta_b1, "B2": ultima.meta_b2, "B3": ultima.meta_b3}
        ejecutivos = Ejecutivo.objects.filter(
            cargo=Ejecutivo.Cargo.EJECUTIVO, is_active=True
        ).order_by("nombre")

        errores = []
        advertencias = []
        regulares = 0
        honorarios = 0

        self.stdout.write("ESACOM · VALIDACIÓN PILOTO EJECUTIVOS")
        self.stdout.write(
            f"Snapshot: #{ultima.id} · {ultima.archivo_nombre} · corte {ultima.fecha_corte} · "
            f"B1 {focos['B1']} · B2 {focos['B2']} · B3 {focos['B3']}"
        )

        for e in ejecutivos:
            ventas = Venta.objects.filter(ejecutivo=e)
            total = ventas.count()
            instaladas = ventas.filter(estado_instalacion=Venta.EstadoInstalacion.INSTALADO).count()
            pendientes_i = ventas.filter(estado_instalacion=Venta.EstadoInstalacion.PENDIENTE_INSTALACION).count()
            pendientes_c = ventas.filter(estado_instalacion=Venta.EstadoInstalacion.PENDIENTE_COMERCIAL).count()
            anuladas = ventas.filter(estado_instalacion=Venta.EstadoInstalacion.ANULADO).count()
            suma_estados = instaladas + pendientes_i + pendientes_c + anuladas
            if suma_estados != total:
                errores.append(f"{e.rut} {e.nombre}: estados ventas {suma_estados} != total {total}")

            if e.tipo_kpi == Ejecutivo.TipoKPI.HONORARIOS:
                honorarios += 1
                continue
            regulares += 1

            cortes = filtrar_cortes_kpi_operativos(
                Corte.objects.filter(carga_kpi=ultima, venta__ejecutivo=e)
            )
            kpis = resumen_cortes_actuales(cortes, focos=focos, metas=metas)
            for k in kpis:
                esperado = focos.get(k.get("boleta"))
                if esperado and k.get("mes_ano") != esperado:
                    errores.append(
                        f"{e.rut} {e.nombre}: {k.get('boleta')} {k.get('mes_ano')} fuera del foco {esperado}"
                    )

            accionables = resumen_accionables(cortes, focos=focos)
            ids_accionables = []
            for clave in ("vencidos", "hoy", "manana", "prox_3d"):
                ids_accionables.extend(i["corte_id"] for i in accionables.get(clave, {}).get("items", []))
            if ids_accionables:
                no_instalados = Corte.objects.filter(id__in=ids_accionables).exclude(
                    venta__estado_instalacion=Venta.EstadoInstalacion.INSTALADO
                ).count()
                if no_instalados:
                    errores.append(f"{e.rut} {e.nombre}: {no_instalados} accionables no instalados")

            if total == 0:
                advertencias.append(f"{e.rut} {e.nombre}: activo sin ventas ESACOM")

        self.stdout.write(
            f"Ejecutivos activos: {ejecutivos.count()} · Regular: {regulares} · Honorarios: {honorarios}"
        )
        for a in advertencias[:20]:
            self.stdout.write(self.style.WARNING(f"[ALERTA] {a}"))
        if len(advertencias) > 20:
            self.stdout.write(self.style.WARNING(f"[ALERTA] ... y {len(advertencias)-20} alertas adicionales"))

        if errores:
            for e in errores:
                self.stdout.write(self.style.ERROR(f"[ERROR] {e}"))
            raise CommandError(f"Piloto NO aprobado: {len(errores)} error(es) de integridad.")

        self.stdout.write(self.style.SUCCESS(
            "[OK] Portal Ejecutivo apto para UAT: ventas ESACOM consistentes, focos KPI válidos y accionables solo sobre ventas instaladas."
        ))

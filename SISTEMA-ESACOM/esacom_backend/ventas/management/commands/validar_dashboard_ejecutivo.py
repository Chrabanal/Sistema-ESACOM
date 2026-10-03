from django.core.management.base import BaseCommand, CommandError

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta
from ventas.services import filtrar_cortes_kpi_operativos, resumen_cortes_actuales


class Command(BaseCommand):
    help = "Valida el Dashboard Ejecutivo contra la fuente maestra ESACOM (RUT EVT)."

    def add_arguments(self, parser):
        parser.add_argument("--rut", required=True, help="RUT del ejecutivo, p.ej. 19776727-8")

    def handle(self, *args, **options):
        rut = options["rut"].strip()
        ejecutivo = Ejecutivo.objects.filter(rut=rut).first()
        if not ejecutivo:
            raise CommandError(f"No existe ejecutivo ESACOM con RUT {rut}")

        ventas = Venta.objects.filter(ejecutivo=ejecutivo)
        instaladas = ventas.filter(estado_instalacion=Venta.EstadoInstalacion.INSTALADO)
        anuladas = ventas.filter(estado_instalacion=Venta.EstadoInstalacion.ANULADO)

        ultima = (
            CargaExcel.objects.filter(tipo_base=CargaExcel.TipoBase.REPORTE_KPI)
            .order_by("-fecha_corte", "-creado_en")
            .first()
        )
        if not ultima:
            raise CommandError("No hay reportes KPI cargados.")

        focos = {"B1": ultima.foco_b1, "B2": ultima.foco_b2, "B3": ultima.foco_b3}
        metas = {"B1": ultima.meta_b1, "B2": ultima.meta_b2, "B3": ultima.meta_b3}
        # Debe reproducir exactamente el universo del Portal: snapshot KPI activo
        # + ventas ESACOM instaladas. No mezclar Corte residuales de cargas anteriores.
        cortes = filtrar_cortes_kpi_operativos(
            Corte.objects.filter(carga_kpi=ultima, venta__ejecutivo=ejecutivo)
        ).select_related("venta", "venta__promocion")
        resumen = resumen_cortes_actuales(cortes, focos=focos, metas=metas)

        self.stdout.write(self.style.SUCCESS(f"Ejecutivo: {ejecutivo.nombre} · {ejecutivo.rut}"))
        self.stdout.write(
            f"Ventas ESACOM: {ventas.count()} · Instaladas: {instaladas.count()} · Anuladas: {anuladas.count()}"
        )
        self.stdout.write(
            f"Snapshot activo: #{ultima.id} · {ultima.archivo_nombre} · corte {ultima.fecha_corte} · {ultima.dia_reporte}"
        )
        for r in resumen:
            self.stdout.write(
                f"{r['boleta']} {r['mes_ano']}: KPI {r['pct_cumplimiento']:.2f}% · "
                f"Pago {r['pagadas']} · Pendiente {r['pendientes']} · No Pago {r['no_pago']} · "
                f"Fuera Plazo {r['fuera_plazo']} · S/B {r['sin_boleta']} · "
                f"Meta {r['meta_pct']:.1f}% · Q meta {r['faltan_para_meta']} RGU"
            )

from django.core.management.base import BaseCommand, CommandError
from usuarios.models import Ejecutivo
from ventas.models import Corte
from ventas.services import resumen_accionables, filtrar_cortes_kpi_operativos
from integraciones.models import CargaExcel


class Command(BaseCommand):
    help = "Valida los accionables de un ejecutivo Regular (vencidos, hoy, mañana y próximos 3 días)."

    def add_arguments(self, parser):
        parser.add_argument("--rut", required=True)

    def handle(self, *args, **options):
        rut = options["rut"]
        try:
            ejecutivo = Ejecutivo.objects.get(rut=rut)
        except Ejecutivo.DoesNotExist as exc:
            raise CommandError(f"No existe ejecutivo con RUT {rut}") from exc

        ultima = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI
        ).order_by("-fecha_corte", "-creado_en").first()
        if not ultima:
            raise CommandError("No existe snapshot KPI activo para determinar B1/B2/B3.")
        focos = {"B1": ultima.foco_b1, "B2": ultima.foco_b2, "B3": ultima.foco_b3}
        cortes = filtrar_cortes_kpi_operativos(
            Corte.objects.filter(carga_kpi=ultima, venta__ejecutivo=ejecutivo)
        )
        data = resumen_accionables(cortes, focos=focos)
        self.stdout.write(f"Ejecutivo: {ejecutivo.nombre} · {ejecutivo.rut} · {ejecutivo.tipo_kpi}")
        self.stdout.write(
            f"Snapshot: #{ultima.id} · {ultima.archivo_nombre} · corte {ultima.fecha_corte} · "
            f"Focos B1 {focos['B1']} · B2 {focos['B2']} · B3 {focos['B3']}"
        )
        total = 0
        for clave, titulo in (("vencidos", "VENCIDOS"), ("hoy", "HOY"), ("manana", "MAÑANA"), ("prox_3d", "PRÓX. 3 DÍAS")):
            bucket = data.get(clave, {})
            total += int(bucket.get("casos", 0))
            self.stdout.write(
                f"{titulo}: {bucket.get('rgu', 0)} RGU · {bucket.get('clientes', 0)} clientes · {bucket.get('casos', 0)} casos"
            )
            for camada in bucket.get("camadas", []):
                self.stdout.write(
                    f"  - {camada['nombre']}: {camada['rgu']} RGU · {camada['clientes']} clientes · {camada['casos']} casos"
                )
        self.stdout.write(self.style.SUCCESS(f"[OK] Accionables calculados: {total} casos visibles."))

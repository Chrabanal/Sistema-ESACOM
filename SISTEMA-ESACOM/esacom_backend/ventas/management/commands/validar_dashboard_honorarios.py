from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Ejecutivo
from ventas.models import Venta
from ventas.services import resumen_honorarios


class Command(BaseCommand):
    help = (
        "Valida un Ejecutivo con perfil HONORARIOS usando exclusivamente la fuente ESACOM. "
        "No calcula B1/B2/B3 ni presenta un KPI oficial mientras la fórmula de Gerencia no esté parametrizada."
    )

    def add_arguments(self, parser):
        parser.add_argument("--rut", required=True, help="RUT del Ejecutivo Honorarios")

    def handle(self, *args, **options):
        rut = (options["rut"] or "").strip()
        try:
            ejecutivo = Ejecutivo.objects.get(rut=rut)
        except Ejecutivo.DoesNotExist as exc:
            raise CommandError(f"No existe un usuario con RUT {rut}.") from exc

        if ejecutivo.cargo != Ejecutivo.Cargo.EJECUTIVO:
            raise CommandError(f"{ejecutivo.nombre} no tiene cargo EJECUTIVO.")
        if ejecutivo.tipo_kpi != Ejecutivo.TipoKPI.HONORARIOS:
            raise CommandError(
                f"{ejecutivo.nombre} tiene perfil KPI {ejecutivo.tipo_kpi}; se esperaba HONORARIOS."
            )

        ventas = Venta.objects.filter(
            ejecutivo=ejecutivo,
            origen_venta=Venta.OrigenVenta.HONORARIOS,
        )
        resumen = resumen_honorarios(ventas)

        self.stdout.write(self.style.SUCCESS(f"Ejecutivo Honorarios: {ejecutivo.nombre} · {ejecutivo.rut}"))
        self.stdout.write(f"Supervisor: {ejecutivo.supervisor or 'Sin supervisor'} · Equipo: {ejecutivo.equipo or 'Sin equipo'}")
        self.stdout.write(
            "Ventas ESACOM Honorarios: {total_ventas} · RGU: {total_rgu} · "
            "Ventas con pago: {ventas_con_pago} · RGU con pago: {rgu_con_pago} · "
            "Ventas sin pago: {ventas_sin_pago} · RGU sin pago: {rgu_sin_pago}".format(**resumen)
        )
        self.stdout.write(
            f"Indicador referencial de pago por RGU: {resumen['pct_pago_referencial']:.1f}% "
            "(NO es KPI oficial)"
        )
        self.stdout.write(self.style.WARNING(
            "B1/B2/B3 y metas regulares NO se aplican a Honorarios. "
            "Falta la fórmula oficial de Gerencia para cerrar este perfil."
        ))

        if resumen["camadas"]:
            self.stdout.write("Últimas camadas disponibles:")
            for camada in resumen["camadas"]:
                self.stdout.write(
                    f"  {camada['camada'] or 'Sin camada'}: "
                    f"{camada['ventas']} ventas · {camada['rgu']} RGU · "
                    f"{camada['pagadas_rgu']} RGU con pago · "
                    f"{camada['pendientes_rgu']} RGU sin pago · "
                    f"{camada['pct_pago_referencial']:.1f}% referencial"
                )

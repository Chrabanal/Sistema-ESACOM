from django.core.management.base import BaseCommand
from django.db import transaction

from integraciones.models import KPIRegistro


def snapshot_desde_registro(registro):
    venta = registro.venta
    if not venta:
        return {
            "venta_id": None,
            "estado_instalacion": "",
            "conflicto_fuente": False,
            "rgu": None,
            "rut_evt": "",
            "nombre_evt": "",
            "supervisor_fuente": "",
            "ejecutivo_id": None,
            "ejecutivo_rut": "",
            "ejecutivo_nombre": "",
            "tipo_kpi": "",
            "cargo": "",
            "ejecutivo_activo": False,
            "supervisor_id": None,
            "supervisor_rut": "",
            "supervisor_nombre": "",
        }

    ejecutivo = venta.ejecutivo
    supervisor = ejecutivo.supervisor if ejecutivo and ejecutivo.supervisor_id else None
    return {
        "venta_id": venta.id,
        "estado_instalacion": venta.estado_instalacion or "",
        "conflicto_fuente": bool(venta.conflicto_fuente),
        "rgu": venta.rgu_base,
        "rut_evt": venta.rut_evt or "",
        "nombre_evt": venta.nombre_evt or "",
        "supervisor_fuente": venta.supervisor_fuente or "",
        "ejecutivo_id": ejecutivo.id if ejecutivo else None,
        "ejecutivo_rut": ejecutivo.rut if ejecutivo else "",
        "ejecutivo_nombre": ejecutivo.nombre if ejecutivo else "",
        "tipo_kpi": ejecutivo.tipo_kpi if ejecutivo else "",
        "cargo": ejecutivo.cargo if ejecutivo else "",
        "ejecutivo_activo": bool(ejecutivo and ejecutivo.is_active),
        "supervisor_id": supervisor.id if supervisor else None,
        "supervisor_rut": supervisor.rut if supervisor else "",
        "supervisor_nombre": supervisor.nombre if supervisor else "",
    }


class Command(BaseCommand):
    help = (
        "Congela la población ESACOM ya asociada a cada KPIRegistro. "
        "Ejecutar una sola vez sobre la base PRE-SYNC, antes de volver a sincronizar Google Sheets."
    )

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--forzar", action="store_true")

    def handle(self, *args, **options):
        batch_size = max(50, int(options["batch_size"] or 500))
        qs = KPIRegistro.objects.select_related(
            "venta",
            "venta__ejecutivo",
            "venta__ejecutivo__supervisor",
        ).order_by("id")
        if not options["forzar"]:
            qs = qs.filter(snapshot_esacom__isnull=True)

        total = qs.count()
        if not total:
            self.stdout.write(self.style.SUCCESS("SNAPSHOT ESACOM: no hay filas pendientes."))
            return

        buffer = []
        procesadas = 0
        for registro in qs.iterator(chunk_size=batch_size):
            registro.snapshot_esacom = snapshot_desde_registro(registro)
            buffer.append(registro)
            if len(buffer) >= batch_size:
                with transaction.atomic():
                    KPIRegistro.objects.bulk_update(buffer, ["snapshot_esacom"], batch_size=batch_size)
                procesadas += len(buffer)
                self.stdout.write(f"Sembradas: {procesadas}/{total}")
                buffer.clear()

        if buffer:
            with transaction.atomic():
                KPIRegistro.objects.bulk_update(buffer, ["snapshot_esacom"], batch_size=batch_size)
            procesadas += len(buffer)
            self.stdout.write(f"Sembradas: {procesadas}/{total}")

        self.stdout.write(self.style.SUCCESS(f"SNAPSHOT ESACOM OK: {procesadas} filas sembradas"))

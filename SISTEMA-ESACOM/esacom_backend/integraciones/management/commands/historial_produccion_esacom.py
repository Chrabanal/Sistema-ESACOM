from django.core.management.base import BaseCommand

from integraciones.models import CargaExcel


class Command(BaseCommand):
    help = "Muestra snapshots de producción guardados en cada sincronización ESACOM."

    def add_arguments(self, parser):
        parser.add_argument("--ultimos", type=int, default=10, help="Cantidad de snapshots a mostrar (1-50).")

    def handle(self, *args, **options):
        limite = min(max(int(options.get("ultimos") or 10), 1), 50)
        qs = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.BASE_MATRIZ,
        ).exclude(resumen_produccion={}).order_by("-creado_en")[:limite]

        self.stdout.write(self.style.SUCCESS("ESACOM · HISTORIAL DE PRODUCCIÓN POR SINCRONIZACIÓN"))
        if not qs:
            self.stdout.write(
                "Aún no hay snapshots con la nueva build. Ejecuta verificar_sync_esacom --sincronizar."
            )
            return

        anterior = None
        for carga in reversed(list(qs)):
            r = carga.resumen_produccion or {}
            fija = r.get("fija") or {}
            movil = r.get("movil") or {}
            total = int(r.get("total_produccion") or 0)
            delta = ""
            if anterior is not None:
                delta = f" · Δ total {total - anterior:+d}"
            alineacion = r.get("alineacion_fuente_crm")
            marca = " · ATÓMICO OK" if alineacion is True else " · ATÓMICO DIF" if alineacion is False else ""
            self.stdout.write(
                f"#{carga.id} · fuente {carga.fuente_modificada_en or '-'} · "
                f"F {fija.get('completadas', 0)}/{fija.get('pendiente_instalacion', 0)}="
                f"{fija.get('total_control', 0)} · "
                f"M Pr{movil.get('principal', 0)} A{movil.get('adicional', 0)} "
                f"PPM{movil.get('ppm', 0)}={movil.get('total', 0)} · TOTAL {total}{delta}{marca}"
            )
            anterior = total

        self.stdout.write("\nF = completadas/pendiente instalación en RGU; M = líneas móviles efectivas.")
        self.stdout.write("Cada fila queda ligada al modifiedTime y SHA-256 del XLSX importado.")

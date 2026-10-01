from django.core.management.base import BaseCommand, CommandError

from integraciones.services.google_sheets import obtener_hojas_spreadsheet, obtener_metadata_spreadsheet


class Command(BaseCommand):
    help = "Lista metadata de hojas Google Sheets ESACOM; con --todas incluye pestañas ocultas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--todas",
            action="store_true",
            help="Incluye hojas ocultas. Sin esta opción se muestran solo hojas visibles.",
        )

    def handle(self, *args, **options):
        try:
            metadata = obtener_metadata_spreadsheet()
            hojas = obtener_hojas_spreadsheet()
        except Exception as exc:
            raise CommandError(f"No fue posible consultar Google Sheets ESACOM: {exc}") from exc

        if not options.get("todas"):
            hojas = [h for h in hojas if not h["hidden"]]

        self.stdout.write(self.style.SUCCESS("ESACOM · HOJAS GOOGLE SHEETS"))
        self.stdout.write(f"Spreadsheet: {metadata.get('name', '-')} · ID {metadata.get('id', '-')}")
        metodo = hojas[0].get("metadata_source", "-") if hojas else "-"
        self.stdout.write(f"Hojas mostradas: {len(hojas)} · método: {metodo}")
        self.stdout.write("")
        for hoja in hojas:
            estado = "OCULTA" if hoja["hidden"] else "VISIBLE"
            self.stdout.write(
                f"{estado:<8} · idx {hoja['index']:>2} · id {hoja['sheet_id']!s:<10} · "
                f"{hoja['row_count']:>6}x{hoja['column_count']:<4} · {hoja['title']}"
            )

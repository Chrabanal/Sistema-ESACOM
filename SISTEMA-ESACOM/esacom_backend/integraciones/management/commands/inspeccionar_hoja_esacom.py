import unicodedata

from django.core.management.base import BaseCommand, CommandError

from integraciones.services.google_sheets import (
    escapar_titulo_hoja,
    leer_valores,
    obtener_hoja_por_titulo,
)


SENSIBLES = (
    "RUT",
    "NOMBRE",
    "TELEFONO",
    "NUMERO CLIENTE",
    "DIRECCION",
    "DOMICILIO",
    "EMAIL",
    "CORREO",
    "PCS",
    "CLAVE",
    "PASSWORD",
)


def _norm(texto):
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def _columna_excel(numero: int) -> str:
    resultado = ""
    n = max(1, int(numero))
    while n:
        n, resto = divmod(n - 1, 26)
        resultado = chr(65 + resto) + resultado
    return resultado


def _es_sensible(encabezado: str) -> bool:
    h = _norm(encabezado)
    return any(token in h for token in SENSIBLES)


def _redactar(valor):
    if valor in (None, ""):
        return ""
    texto = str(valor)
    if len(texto) <= 4:
        return "***"
    return f"{texto[:2]}***{texto[-2:]}"


class Command(BaseCommand):
    help = (
        "Inspecciona encabezados y primeras filas de una hoja ESACOM. "
        "Los campos potencialmente sensibles se redactan por defecto."
    )

    def add_arguments(self, parser):
        parser.add_argument("--hoja", required=True, help="Título exacto de la pestaña a inspeccionar.")
        parser.add_argument("--filas", type=int, default=5, help="Filas de datos a mostrar (1-20).")
        parser.add_argument("--columnas", type=int, default=60, help="Máximo de columnas a leer (1-100).")
        parser.add_argument(
            "--mostrar-datos-sensibles",
            action="store_true",
            help="Desactiva redacción. Usar solo en un entorno controlado.",
        )

    def handle(self, *args, **options):
        titulo = str(options["hoja"] or "").strip()
        filas = min(max(int(options.get("filas") or 5), 1), 20)
        columnas = min(max(int(options.get("columnas") or 60), 1), 100)
        mostrar_sensibles = bool(options.get("mostrar_datos_sensibles"))

        try:
            hoja = obtener_hoja_por_titulo(titulo)
            if not hoja:
                raise CommandError(f"No existe una hoja con título exacto: {titulo}")
            fin_col = _columna_excel(columnas)
            rango = f"{escapar_titulo_hoja(hoja['title'])}!A1:{fin_col}{filas + 1}"
            valores = leer_valores(rango)
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f"No fue posible inspeccionar la hoja ESACOM: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("ESACOM · INSPECCIÓN DE HOJA"))
        self.stdout.write(
            f"{('OCULTA' if hoja['hidden'] else 'VISIBLE')} · id {hoja['sheet_id']} · "
            f"{hoja['row_count']}x{hoja['column_count']} · {hoja['title']}"
        )
        if not valores:
            self.stdout.write("Sin valores en el rango consultado.")
            return

        encabezados = [str(v or "").strip() for v in valores[0]]
        self.stdout.write("\nENCABEZADOS")
        for i, encabezado in enumerate(encabezados, start=1):
            if encabezado:
                marca = " [SENSIBLE]" if _es_sensible(encabezado) else ""
                self.stdout.write(f"  {_columna_excel(i):>3} · {encabezado}{marca}")

        if len(valores) <= 1:
            return

        self.stdout.write("\nMUESTRA")
        for numero_fila, fila in enumerate(valores[1:filas + 1], start=2):
            pares = []
            for i, encabezado in enumerate(encabezados):
                if not encabezado or i >= len(fila):
                    continue
                valor = fila[i]
                if valor in (None, ""):
                    continue
                if _es_sensible(encabezado) and not mostrar_sensibles:
                    valor = _redactar(valor)
                pares.append(f"{encabezado}={valor}")
            self.stdout.write(f"  fila {numero_fila}: " + (" · ".join(pares) if pares else "(vacía)"))

        if not mostrar_sensibles:
            self.stdout.write(self.style.WARNING(
                "\nCampos sensibles redactados. Usa --mostrar-datos-sensibles solo si realmente es necesario."
            ))

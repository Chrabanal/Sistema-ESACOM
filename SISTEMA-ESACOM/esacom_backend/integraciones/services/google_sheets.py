"""IntegraciÃ³n ESACOM â†” Google Sheets.

La Google Sheet ESACOM es la fuente operativa maestra. Este mÃ³dulo permite:

* descargar una copia XLSX para reutilizar el importador oficial;
* leer rangos concretos para diagnÃ³stico;
* consultar la metadata nativa de todas las pestaÃ±as, incluidas las ocultas.

Importante: las hojas de Claro presentes en la matriz NO se importan desde
esta sincronizaciÃ³n. Claro solo complementa el CRM mediante los archivos KPI
cargados por separado (lunes/miÃ©rcoles).
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings



XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _spreadsheet_id() -> str:
    spreadsheet_id = str(settings.GOOGLE_SHEETS_SPREADSHEET_ID or "").strip()
    if not spreadsheet_id:
        raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID no estÃ¡ configurado en .env")
    return spreadsheet_id


def _credential_path() -> Path:
    raw = str(settings.GOOGLE_SERVICE_ACCOUNT_FILE or "").strip()
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_FILE no estÃ¡ configurado. "
            "Guarda el JSON de la cuenta de servicio y define su ruta en .env."
        )
    path = Path(raw)
    if not path.is_absolute():
        path = Path(settings.BASE_DIR) / path
    if not path.exists():
        raise RuntimeError(f"No existe el archivo de credenciales Google: {path}")
    return path


def _credentials():
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_file(
        str(_credential_path()),
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/spreadsheets.readonly",
        ],
    )


def _drive_service():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_credentials(), cache_discovery=False)


def _sheets_service():
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=_credentials(), cache_discovery=False)


def obtener_metadata_spreadsheet() -> dict:
    """Valida acceso y devuelve metadata de archivo desde Google Drive."""
    return _drive_service().files().get(
        fileId=_spreadsheet_id(),
        fields="id,name,modifiedTime,mimeType,webViewLink",
        supportsAllDrives=True,
    ).execute()


def _hojas_desde_xlsx(path: str | os.PathLike) -> list[dict]:
    """Lee metadata de pestaÃ±as desde una exportaciÃ³n XLSX de Drive.

    Esta ruta es el fallback oficial cuando la API de Google Sheets no estÃ¡
    habilitada. La exportaciÃ³n XLSX conserva las pestaÃ±as ocultas, por lo que
    no necesitamos exigir una segunda API para auditar la matriz ESACOM.
    """
    from openpyxl import load_workbook

    # Para metadata preferimos modo normal. Algunas pestaÃ±as auxiliares/pivot
    # exportadas por Google (p. ej. "TD Dot") pueden carecer de una dimensiÃ³n
    # vÃ¡lida y openpyxl read_only falla con UnboundLocalError al intentar
    # calcularla. En modo normal max_row/max_column es robusto para este XLSX
    # (~pocos MB) y no modifica el archivo.
    wb = load_workbook(path, read_only=False, data_only=True)
    try:
        hojas = []
        for index, ws in enumerate(wb.worksheets):
            try:
                row_count = int(ws.max_row or 0)
                column_count = int(ws.max_column or 0)
            except Exception:
                # La existencia/visibilidad de la hoja es mÃ¡s importante que
                # una dimensiÃ³n defectuosa; mantenemos la pestaÃ±a auditable.
                row_count = 0
                column_count = 0
            hojas.append({
                "sheet_id": f"XLSX-{index}",
                "title": ws.title,
                "index": index,
                "hidden": ws.sheet_state != "visible",
                "row_count": row_count,
                "column_count": column_count,
                "metadata_source": "DRIVE_XLSX",
            })
        return hojas
    finally:
        wb.close()


def obtener_hojas_spreadsheet() -> list[dict]:
    """Devuelve metadata de TODAS las hojas, incluso ocultas.

    Intenta primero la API nativa de Sheets. Si esa API estÃ¡ deshabilitada
    pero la cuenta de servicio sÃ­ puede exportar el archivo mediante Drive
    (el caso real de ESACOM), usa automÃ¡ticamente la copia XLSX.
    """
    try:
        resultado = _sheets_service().spreadsheets().get(
            spreadsheetId=_spreadsheet_id(),
            includeGridData=False,
            fields=(
                "properties(title),"
                "sheets(properties(sheetId,title,index,hidden,gridProperties(rowCount,columnCount)))"
            ),
        ).execute()
    except Exception:
        tmp = tempfile.NamedTemporaryFile(prefix="esacom_hojas_", suffix=".xlsx", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            descargar_spreadsheet_xlsx(tmp_path)
            return _hojas_desde_xlsx(tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    hojas = []
    for item in resultado.get("sheets", []):
        props = item.get("properties", {})
        grid = props.get("gridProperties", {})
        hojas.append({
            "sheet_id": props.get("sheetId"),
            "title": props.get("title", ""),
            "index": props.get("index", 0),
            "hidden": bool(props.get("hidden", False)),
            "row_count": grid.get("rowCount", 0),
            "column_count": grid.get("columnCount", 0),
            "metadata_source": "SHEETS_API",
        })
    return sorted(hojas, key=lambda h: h["index"])


def obtener_hoja_por_titulo(titulo: str) -> dict | None:
    buscado = str(titulo or "").strip().casefold()
    for hoja in obtener_hojas_spreadsheet():
        if hoja["title"].strip().casefold() == buscado:
            return hoja
    return None


def _separar_rango_a1(rango: str) -> tuple[str, str]:
    if "!" not in rango:
        raise ValueError(f"Rango A1 sin tÃ­tulo de hoja: {rango}")
    titulo, celdas = rango.split("!", 1)
    titulo = titulo.strip()
    if titulo.startswith("'") and titulo.endswith("'"):
        titulo = titulo[1:-1].replace("''", "'")
    return titulo, celdas.strip()


def _leer_valores_desde_xlsx(path: str | os.PathLike, rango: str) -> list[list]:
    """Lee un rango A1 desde la exportaciÃ³n XLSX usando valores calculados."""
    from openpyxl import load_workbook
    from openpyxl.utils.cell import column_index_from_string, range_boundaries

    titulo, celdas = _separar_rango_a1(rango)
    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if titulo not in wb.sheetnames:
            return []
        ws = wb[titulo]
        if ws.max_row is None or ws.max_column is None:
            ws.calculate_dimension(force=True)

        # Soporta rangos por columnas completas (A:BD) y rangos normales
        # (A1:BH6), que son los usados por los comandos de diagnÃ³stico.
        m = re.fullmatch(r"([A-Za-z]+):([A-Za-z]+)", celdas)
        if m:
            min_col = column_index_from_string(m.group(1))
            max_col = column_index_from_string(m.group(2))
            min_row, max_row = 1, int(ws.max_row or 1)
        else:
            min_col, min_row, max_col, max_row = range_boundaries(celdas)
            max_row = min(max_row, int(ws.max_row or max_row))
            max_col = min(max_col, int(ws.max_column or max_col))

        filas = []
        for row in ws.iter_rows(
            min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col,
            values_only=True,
        ):
            valores = list(row)
            while valores and valores[-1] is None:
                valores.pop()
            filas.append(valores)
        while filas and not filas[-1]:
            filas.pop()
        return filas
    finally:
        wb.close()


def leer_valores(rango: str) -> list[list]:
    """Lectura de diagnÃ³stico con fallback automÃ¡tico a Drive/XLSX."""
    try:
        resultado = _sheets_service().spreadsheets().values().get(
            spreadsheetId=_spreadsheet_id(),
            range=rango,
            valueRenderOption="UNFORMATTED_VALUE",
            dateTimeRenderOption="FORMATTED_STRING",
        ).execute()
        return resultado.get("values", [])
    except Exception:
        tmp = tempfile.NamedTemporaryFile(prefix="esacom_rango_", suffix=".xlsx", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            descargar_spreadsheet_xlsx(tmp_path)
            return _leer_valores_desde_xlsx(tmp_path, rango)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def leer_valores_multiples(rangos: list[str]) -> dict[str, list[list]]:
    """Lee varios rangos intentando una sola exportaciÃ³n XLSX si Sheets falla."""
    try:
        return {rango: leer_valores_sheets(rango) for rango in rangos}
    except Exception:
        tmp = tempfile.NamedTemporaryFile(prefix="esacom_rangos_", suffix=".xlsx", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            descargar_spreadsheet_xlsx(tmp_path)
            return {rango: _leer_valores_desde_xlsx(tmp_path, rango) for rango in rangos}
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def leer_valores_sheets(rango: str) -> list[list]:
    """Lectura estricta por Sheets API; Ãºtil para agrupar fallbacks."""
    resultado = _sheets_service().spreadsheets().values().get(
        spreadsheetId=_spreadsheet_id(),
        range=rango,
        valueRenderOption="UNFORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING",
    ).execute()
    return resultado.get("values", [])


def escapar_titulo_hoja(titulo: str) -> str:
    """Escapa un nombre de pestaÃ±a para usarlo en notaciÃ³n A1."""
    return "'" + str(titulo).replace("'", "''") + "'"


def descargar_spreadsheet_xlsx(destino: str | os.PathLike) -> dict:
    """Exporta la Sheet nativa completa a XLSX para reutilizar el importador."""
    from googleapiclient.http import MediaIoBaseDownload

    metadata = obtener_metadata_spreadsheet()
    request = _drive_service().files().export_media(
        fileId=_spreadsheet_id(),
        mimeType=XLSX_MIME,
    )
    with open(destino, "wb") as fh:
        downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return metadata



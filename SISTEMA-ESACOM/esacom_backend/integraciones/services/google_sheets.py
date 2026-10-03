"""Integración ESACOM ↔ Google Sheets.

La Google Sheet ESACOM es la fuente operativa maestra. Este módulo permite:

* descargar una copia XLSX para reutilizar el importador oficial;
* leer rangos concretos para diagnóstico;
* consultar la metadata nativa de todas las pestañas, incluidas las ocultas.

Importante: las hojas de Claro presentes en la matriz NO se importan desde
esta sincronización. Claro solo complementa el CRM mediante los archivos KPI
cargados por separado (lunes/miércoles).
"""
from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path

from django.conf import settings
from django.db import transaction

from integraciones.models import CargaExcel


XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _spreadsheet_id() -> str:
    spreadsheet_id = str(settings.GOOGLE_SHEETS_SPREADSHEET_ID or "").strip()
    if not spreadsheet_id:
        raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID no está configurado en .env")
    return spreadsheet_id


def _credential_path() -> Path:
    raw = str(settings.GOOGLE_SERVICE_ACCOUNT_FILE or "").strip()
    if not raw:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_FILE no está configurado. "
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
    """Lee metadata de pestañas desde una exportación XLSX de Drive.

    Esta ruta es el fallback oficial cuando la API de Google Sheets no está
    habilitada. La exportación XLSX conserva las pestañas ocultas, por lo que
    no necesitamos exigir una segunda API para auditar la matriz ESACOM.
    """
    from openpyxl import load_workbook

    # Para metadata preferimos modo normal. Algunas pestañas auxiliares/pivot
    # exportadas por Google (p. ej. "TD Dot") pueden carecer de una dimensión
    # válida y openpyxl read_only falla con UnboundLocalError al intentar
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
                # La existencia/visibilidad de la hoja es más importante que
                # una dimensión defectuosa; mantenemos la pestaña auditable.
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

    Intenta primero la API nativa de Sheets. Si esa API está deshabilitada
    pero la cuenta de servicio sí puede exportar el archivo mediante Drive
    (el caso real de ESACOM), usa automáticamente la copia XLSX.
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
        raise ValueError(f"Rango A1 sin título de hoja: {rango}")
    titulo, celdas = rango.split("!", 1)
    titulo = titulo.strip()
    if titulo.startswith("'") and titulo.endswith("'"):
        titulo = titulo[1:-1].replace("''", "'")
    return titulo, celdas.strip()


def _leer_valores_desde_xlsx(path: str | os.PathLike, rango: str) -> list[list]:
    """Lee un rango A1 desde la exportación XLSX usando valores calculados."""
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
        # (A1:BH6), que son los usados por los comandos de diagnóstico.
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
    """Lectura de diagnóstico con fallback automático a Drive/XLSX."""
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
    """Lee varios rangos intentando una sola exportación XLSX si Sheets falla."""
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
    """Lectura estricta por Sheets API; útil para agrupar fallbacks."""
    resultado = _sheets_service().spreadsheets().values().get(
        spreadsheetId=_spreadsheet_id(),
        range=rango,
        valueRenderOption="UNFORMATTED_VALUE",
        dateTimeRenderOption="FORMATTED_STRING",
    ).execute()
    return resultado.get("values", [])


def escapar_titulo_hoja(titulo: str) -> str:
    """Escapa un nombre de pestaña para usarlo en notación A1."""
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


def sincronizar_base_matriz(*, creado_por=None) -> dict:
    """Sincroniza la Google Sheet ESACOM hacia la base Django.

    Se importan exclusivamente fuentes ESACOM:
      - Dotación
      - Honorarios
      - Comunas
      - Apoyo/promociones
      - Base de Ventas + históricos BV/BDVentas
      - Ventas Móvil + históricos Móvil/BV Móvil

    NO se importan Base Claro ni Móvil Claro. Los KPI de Claro se cargan por
    el flujo REPORTE_KPI y se cruzan contra las ventas ESACOM por N° pedido.
    """
    from integraciones.management.commands.importar_excel import Command as ImportarExcelCommand

    _spreadsheet_id()  # valida configuración antes de crear temporales

    tmp = tempfile.NamedTemporaryFile(prefix="esacom_sheets_", suffix=".xlsx", delete=False)
    tmp_path = tmp.name
    tmp.close()
    try:
        metadata = descargar_spreadsheet_xlsx(tmp_path)

        # Auditoría atómica: calculamos la producción DIRECTAMENTE desde el
        # mismo XLSX exacto que se importará a continuación. Esto elimina los
        # falsos DIF cuando la matriz cambia entre dos descargas consecutivas.
        from integraciones.services.produccion_fuente import calcular_produccion_desde_xlsx, campos
        fuente_directa = calcular_produccion_desde_xlsx(tmp_path)

        with transaction.atomic():
            command = ImportarExcelCommand()
            # Invocación directa para poder recuperar command.resumen.
            command.handle(
                archivo=tmp_path,
                solo="dotacion,honorarios,comunas,apoyo,ventas,movil",
                dry_run=False,
                usuario_rut=getattr(creado_por, "rut", "") if creado_por else "",
            )
            resumen = getattr(command, "resumen", {}) or {}
    
            # Huella del archivo exacto que acabamos de importar.
            sha256 = hashlib.sha256()
            with open(tmp_path, "rb") as fh:
                for bloque in iter(lambda: fh.read(1024 * 1024), b""):
                    sha256.update(bloque)
    
            # Snapshot posterior al import del MISMO XLSX. No sustituye la
            # auditoría directa de fuente, pero deja historia para explicar cómo
            # evoluciona la producción entre sincronizaciones.
            from ventas.produccion import resumen_produccion_actual
            produccion = resumen_produccion_actual()
            fuente_global = fuente_directa["global"]
            fuente_resumen = {
                "fija": {
                    "completadas": fuente_global["fija"]["completadas"],
                    "pendiente_instalacion": fuente_global["fija"]["pendiente_instalacion"],
                    "total_control": fuente_global["fija"]["total_control"],
                },
                "movil": {
                    "principal": fuente_global["movil"]["principal"],
                    "adicional": fuente_global["movil"]["adicional"],
                    "ppm": fuente_global["movil"]["ppm"],
                    "total": fuente_global["movil"]["total"],
                    "pendiente_activacion": fuente_global["movil"]["pendientes"],
                },
                "total_produccion": fuente_global["total_produccion"],
                "trazabilidad": fuente_directa["trazabilidad"],
            }
            crm_resumen = {
                "fija": {
                    "completadas": produccion["fija"]["completadas"],
                    "pendiente_instalacion": produccion["fija"]["pendiente_instalacion"],
                    "total_control": produccion["fija"]["total_control"],
                    "ventas_vigentes": produccion["fija"]["total_base_vigente"],
                    "rgu_total_vigente": produccion["fija"]["rgu_total_base_vigente"],
                },
                "movil": {
                    "principal": produccion["movil"]["principal"],
                    "adicional": produccion["movil"]["adicional"],
                    "ppm": produccion["movil"]["ppm"],
                    "total": produccion["movil"]["total"],
                    "pendiente_activacion": produccion["movil"]["pendiente_activacion"],
                    "lineas_vigentes": produccion["movil"]["total_base_vigente"],
                },
                "total_produccion": produccion["total_produccion"],
            }
            crm_campos = (
                int(produccion["fija"]["completadas"]),
                int(produccion["fija"]["pendiente_instalacion"]),
                int(produccion["movil"]["principal"]),
                int(produccion["movil"]["adicional"]),
                int(produccion["movil"]["ppm"]),
            )
            fuente_campos = campos(fuente_global)
            alineado = fuente_campos == crm_campos
            diferencias = {
                nombre: {"fuente": fuente, "crm": crm, "delta": crm - fuente}
                for nombre, fuente, crm in zip(
                    ("fija_completadas", "fija_pendiente_instalacion", "movil_principal", "movil_adicional", "movil_ppm"),
                    fuente_campos,
                    crm_campos,
                )
                if fuente != crm
            }

            # La sincronización diaria no se bloquea por diferencias agregadas de auditoría.
            # El XLSX descargado se importa dentro de la misma transacción y cualquier error
            # real del importador sigue provocando rollback automático. La comparación queda
            # registrada para revisión sin impedir que la base ESACOM avance con su corte vigente.
            resumen_produccion = dict(crm_resumen)
            resumen_produccion.update({
                "fuente_directa": fuente_resumen,
                "crm_post_import": crm_resumen,
                "alineacion_fuente_crm": bool(alineado),
                "auditoria_operacional": {
                    "estado": "OK" if alineado else "ADVERTENCIA",
                    "diferencias": diferencias,
                },
            })
    
            def contar(d):
                total = 0
                if isinstance(d, dict):
                    for k, v in d.items():
                        if isinstance(v, dict):
                            total += contar(v)
                        elif isinstance(v, int) and k in {
                            "creados", "creadas", "actualizados", "actualizadas",
                            "ventas_creadas", "ventas_actualizadas", "moviles_creadas",
                            "moviles_actualizadas", "filas_importadas",
                        }:
                            total += max(v, 0)
                return total
    
            from django.utils.dateparse import parse_datetime
            modificada = parse_datetime(str(metadata.get("modifiedTime") or ""))
            carga = CargaExcel.objects.create(
                origen=CargaExcel.Origen.AUTOMATICO_SHEETS,
                tipo_base=CargaExcel.TipoBase.BASE_MATRIZ,
                archivo_nombre=f"Google Sheets ESACOM · {metadata.get('name', 'Base ESACOM')}",
                filas_totales=contar(resumen),
                fuente_modificada_en=modificada,
                fuente_sha256=sha256.hexdigest(),
                resumen_produccion=resumen_produccion,
                creado_por=creado_por,
            )
            return {
                "ok": True,
                "carga_id": carga.id,
                "spreadsheet": metadata.get("name"),
                "modified_time": metadata.get("modifiedTime"),
                "fuente_sha256": sha256.hexdigest(),
                "resumen_produccion": resumen_produccion,
                "fuente_directa": fuente_resumen,
                "alineacion_fuente_crm": bool(alineado),
                "auditoria_operacional": resumen_produccion.get("auditoria_operacional", {}),
                "resumen": resumen,
            }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

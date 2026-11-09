from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from pathlib import Path


def norm(valor):
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def cabecera(valor):
    return re.sub(r"[^A-Z0-9]+", " ", norm(valor)).strip()


def mapa(headers):
    return {cabecera(valor): idx for idx, valor in enumerate(headers)}


def valor(row, m, nombre, default=""):
    idx = m.get(cabecera(nombre))
    if idx is None or idx >= len(row):
        return default
    item = row[idx]
    return default if item is None else item


def valor_alias(row, m, *nombres, default=""):
    """Devuelve el primer encabezado alternativo presente en la fuente."""
    for nombre in nombres:
        idx = m.get(cabecera(nombre))
        if idx is not None and idx < len(row):
            item = row[idx]
            return default if item is None else item
    return default


def tiene_alias(m, *nombres):
    return any(cabecera(nombre) in m for nombre in nombres)


def rgu(valor_):
    if valor_ in (None, ""):
        return 0
    try:
        return max(int(float(str(valor_).replace(",", "."))), 0)
    except (TypeError, ValueError):
        return 0


def estado_fijo(valor_):
    estado = norm(valor_)
    if "COMPLETAD" in estado or "INSTALAD" in estado:
        return "completadas"
    if "PENDIENTE" in estado and "INSTAL" in estado:
        return "pendiente_instalacion"
    return "fuera_control"


def tipo_movil(valor_):
    tipo = norm(valor_)
    if "PRINC" in tipo:
        return "principal"
    if "ADIC" in tipo:
        return "adicional"
    if tipo == "PPM" or " PPM" in f" {tipo}":
        return "ppm"
    return "otros"


ESTADOS_POSITIVOS = (
    "PORTADO", "ACTIVADO", "ACTIVADA", "ACTIVO", "ACTIVA", "COMPLETADO", "COMPLETADA",
)
ESTADOS_BLOQUEADOS = (
    "ANULAD", "CANCEL", "RECHAZ", "NO PORTAD", "PENDIENT", "POR PORTAR", "MANDATO",
)


def movil_efectiva(estado, fecha_activacion):
    estado = norm(estado)
    if estado and any(token in estado for token in ESTADOS_BLOQUEADOS):
        return False
    if fecha_activacion not in (None, "", 0):
        return True
    return bool(estado and any(token in estado for token in ESTADOS_POSITIVOS))


def bucket():
    return {
        "fija": {"completadas": 0, "pendiente_instalacion": 0, "total_control": 0},
        "movil": {"principal": 0, "adicional": 0, "ppm": 0, "otros": 0, "total": 0, "pendientes": 0},
        "total_produccion": 0,
    }


def cerrar(b):
    b["fija"]["total_control"] = b["fija"]["completadas"] + b["fija"]["pendiente_instalacion"]
    b["movil"]["total"] = (
        b["movil"]["principal"] + b["movil"]["adicional"] + b["movil"]["ppm"] + b["movil"]["otros"]
    )
    b["total_produccion"] = b["fija"]["total_control"] + b["movil"]["total"]
    return b


def campos(b):
    return (
        int(b["fija"]["completadas"]),
        int(b["fija"]["pendiente_instalacion"]),
        int(b["movil"]["principal"]),
        int(b["movil"]["adicional"]),
        int(b["movil"]["ppm"]),
    )


def _rows_hoja(ws, max_col=None):
    # En exportaciones Google, las dimensiones cacheadas pueden venir vacías
    # en modo read_only (max_row/max_column = None). No dependemos de ellas:
    # openpyxl itera hasta el final real del XML y limitamos solo columnas.
    kwargs = {"min_row": 1, "min_col": 1, "values_only": True}
    if max_col:
        kwargs["max_col"] = int(max_col)
    for row in ws.iter_rows(**kwargs):
        valores = list(row)
        while valores and valores[-1] is None:
            valores.pop()
        yield valores



def leer_resumen_gerencia_desde_xlsx(path: str | Path) -> dict:
    """Lee el control manual vigente de la hoja ``Resumen`` de ESACOM.

    La portada de Gerencia debe poder reproducir la misma tabla dinámica que
    Operaciones actualiza diariamente. Se localizan los bloques por sus rótulos
    (no por coordenadas fijas) para tolerar filas/columnas insertadas.
    """
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        if "Resumen" not in wb.sheetnames:
            return {"disponible": False, "motivo": "SIN_HOJA_RESUMEN"}

        rows = list(_rows_hoja(wb["Resumen"], max_col=30))

        def cell(row, idx):
            return row[idx] if idx < len(row) else None

        def buscar(texto):
            objetivo = cabecera(texto)
            for r_idx, row in enumerate(rows):
                for c_idx, item in enumerate(row):
                    if cabecera(item) == objetivo:
                        return r_idx, c_idx
            return None

        estados = {
            "ANULADO": "anulado",
            "COMPLETADA": "completada",
            "DERIVADO REDES": "derivado_redes",
            "PENDIENTE COMERCIAL": "pendiente_comercial",
            "PENDIENTE INSTALACION": "pendiente_instalacion",
        }
        ventas_fijas = {k: 0 for k in estados.values()}
        ventas_fijas["total_rgu"] = 0

        pos = buscar("VENTAS FIJAS")
        if pos:
            r0, c0 = pos
            for row in rows[r0 + 1 : r0 + 20]:
                etiqueta = cabecera(cell(row, c0))
                if not etiqueta:
                    continue
                if etiqueta == "SUMA TOTAL":
                    ventas_fijas["total_rgu"] = rgu(cell(row, c0 + 1))
                    break
                clave = estados.get(etiqueta)
                if clave:
                    ventas_fijas[clave] = rgu(cell(row, c0 + 1))

        completada_por_supervisor = {}
        for r_idx, row in enumerate(rows):
            dia_col = None
            for c_idx, item in enumerate(row):
                if cabecera(item) == "DIA FIN":
                    dia_col = c_idx
                    break
            if dia_col is None:
                continue
            headers = []
            total_col = None
            for c_idx in range(dia_col + 1, len(row)):
                texto = str(cell(row, c_idx) or "").strip()
                if cabecera(texto) == "SUMA TOTAL":
                    total_col = c_idx
                    break
                if texto:
                    headers.append((c_idx, texto))
            if total_col is None or not headers:
                continue
            for total_row in rows[r_idx + 1 : r_idx + 40]:
                if cabecera(cell(total_row, dia_col)) != "SUMA TOTAL":
                    continue
                completada_por_supervisor = {
                    nombre: rgu(cell(total_row, col)) for col, nombre in headers
                }
                break
            if completada_por_supervisor:
                break

        cruce_claro = {"total": 0, "por_supervisor": {}}
        pos_cruce = buscar("CRUCE CLARO")
        if pos_cruce:
            r0, c0 = pos_cruce
            # Normalmente la fila siguiente contiene SUPERVISOR / Suma total.
            header_row_idx = None
            sup_col = None
            val_col = None
            for rr in range(r0, min(r0 + 5, len(rows))):
                row = rows[rr]
                for cc, item in enumerate(row):
                    if cabecera(item) == "SUPERVISOR":
                        sup_col = cc
                        header_row_idx = rr
                    if cabecera(item) == "SUMA TOTAL" and header_row_idx == rr:
                        val_col = cc
                if header_row_idx is not None and val_col is not None:
                    break
            if header_row_idx is not None and sup_col is not None and val_col is not None:
                por_sup = {}
                for row in rows[header_row_idx + 1 : header_row_idx + 30]:
                    nombre = str(cell(row, sup_col) or "").strip()
                    etiqueta = cabecera(nombre)
                    if not etiqueta:
                        continue
                    valor_total = rgu(cell(row, val_col))
                    if etiqueta == "SUMA TOTAL":
                        cruce_claro["total"] = valor_total
                        break
                    por_sup[nombre] = valor_total
                cruce_claro["por_supervisor"] = por_sup

        disponible = bool(ventas_fijas["total_rgu"] or completada_por_supervisor)
        return {
            "disponible": disponible,
            "ventas_fijas": ventas_fijas,
            "completada_por_supervisor": completada_por_supervisor,
            "cruce_claro": cruce_claro,
        }
    finally:
        wb.close()

def calcular_produccion_desde_xlsx(path: str | Path) -> dict:
    """Calcula producción DIRECTAMENTE desde el XLSX exacto exportado de ESACOM.

    No usa la BD Django. Sirve para validar que el importador reprodujo el
    mismo archivo byte-a-byte que fue descargado durante la sincronización.
    """
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        for requerida in ("Base de Ventas", "Ventas Móvil"):
            if requerida not in wb.sheetnames:
                raise RuntimeError(f"No existe la hoja requerida '{requerida}' en el XLSX exportado.")

        fija_rows = list(_rows_hoja(wb["Base de Ventas"], max_col=56))
        movil_rows = list(_rows_hoja(wb["Ventas Móvil"], max_col=34))
        if not fija_rows:
            raise RuntimeError("La hoja 'Base de Ventas' no devolvió filas.")
        if not movil_rows:
            raise RuntimeError("La hoja 'Ventas Móvil' no devolvió filas.")

        global_ = bucket()
        por_sup = defaultdict(bucket)
        por_sup_evt = defaultdict(lambda: defaultdict(bucket))

        fmap = mapa(fija_rows[0])
        requeridos_fija = ["SUPERVISOR", "NOMBRE EVT", "RGU", "ESTADO DE INSTALACION"]
        faltantes = [h for h in requeridos_fija if cabecera(h) not in fmap]
        if faltantes:
            raise RuntimeError(f"Faltan columnas en Base de Ventas: {', '.join(faltantes)}")

        fija_filas_control = 0
        fija_sin_rgu = 0
        pedidos_control = defaultdict(int)
        for row in fija_rows[1:]:
            estado = estado_fijo(valor(row, fmap, "ESTADO DE INSTALACION"))
            if estado == "fuera_control":
                continue
            cantidad = rgu(valor(row, fmap, "RGU"))
            if cantidad <= 0:
                fija_sin_rgu += 1
            pedido = str(valor(row, fmap, "N° PEDIDO") or "").strip()
            if pedido:
                pedidos_control[pedido] += 1
            sup = str(valor(row, fmap, "SUPERVISOR") or "SIN SUPERVISOR").strip()
            evt = str(valor(row, fmap, "NOMBRE EVT") or "SIN EJECUTIVO").strip()
            for b in (global_, por_sup[sup], por_sup_evt[sup][evt]):
                b["fija"][estado] += cantidad
            fija_filas_control += 1

        mmap = mapa(movil_rows[0])
        requeridos_movil = ["SUPERVISOR", "PPAL/ADICI.", "FECHA ACTIVACIÓN", "ESTADO"]
        faltantes = [h for h in requeridos_movil if cabecera(h) not in mmap]
        if not tiene_alias(mmap, "NOMBRE EVT", "NOMBRE EJECUTIVO"):
            faltantes.append("NOMBRE EVT/NOMBRE EJECUTIVO")
        if faltantes:
            raise RuntimeError(f"Faltan columnas en Ventas Móvil: {', '.join(faltantes)}")

        movil_filas = movil_efectivas = movil_pendientes = 0
        for row in movil_rows[1:]:
            tipo = tipo_movil(valor(row, mmap, "PPAL/ADICI."))
            evt_fuente = valor_alias(row, mmap, "NOMBRE EVT", "NOMBRE EJECUTIVO")
            if tipo == "otros" and not any(
                str(x or "").strip() for x in (valor(row, mmap, "SUPERVISOR"), evt_fuente)
            ):
                continue
            movil_filas += 1
            estado = valor(row, mmap, "ESTADO")
            fecha_activacion = valor(row, mmap, "FECHA ACTIVACIÓN")
            sup = str(valor(row, mmap, "SUPERVISOR") or "SIN SUPERVISOR").strip()
            evt = str(evt_fuente or "SIN EJECUTIVO").strip()
            if not movil_efectiva(estado, fecha_activacion):
                movil_pendientes += 1
                for b in (global_, por_sup[sup], por_sup_evt[sup][evt]):
                    b["movil"]["pendientes"] += 1
                continue
            movil_efectivas += 1
            for b in (global_, por_sup[sup], por_sup_evt[sup][evt]):
                b["movil"][tipo] += 1

        cerrar(global_)
        for b in por_sup.values():
            cerrar(b)
        for ejecutivos in por_sup_evt.values():
            for b in ejecutivos.values():
                cerrar(b)

        return {
            "global": global_,
            "supervisores": dict(por_sup),
            "ejecutivos_por_supervisor": {k: dict(v) for k, v in por_sup_evt.items()},
            "trazabilidad": {
                "filas_fija_control": fija_filas_control,
                "fija_sin_rgu": fija_sin_rgu,
                "pedidos_fija_control_unicos": len(pedidos_control),
                "duplicados_n_pedido_fija_control": sum(max(cantidad - 1, 0) for cantidad in pedidos_control.values()),
                "filas_movil": movil_filas,
                "movil_efectivas": movil_efectivas,
                "movil_pendientes": movil_pendientes,
            },
        }
    finally:
        wb.close()

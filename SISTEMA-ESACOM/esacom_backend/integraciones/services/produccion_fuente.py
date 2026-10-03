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
        nombre_evt_movil = "NOMBRE EVT" if cabecera("NOMBRE EVT") in mmap else "NOMBRE EJECUTIVO"
        requeridos_movil = ["SUPERVISOR", nombre_evt_movil, "PPAL/ADICI.", "FECHA ACTIVACIÓN", "ESTADO"]
        faltantes = [h for h in requeridos_movil if cabecera(h) not in mmap]
        if faltantes:
            raise RuntimeError(f"Faltan columnas en Ventas Móvil: {', '.join(faltantes)}")

        movil_filas = movil_efectivas = movil_pendientes = 0
        for row in movil_rows[1:]:
            tipo = tipo_movil(valor(row, mmap, "PPAL/ADICI."))
            if tipo == "otros" and not any(
                str(valor(row, mmap, h) or "").strip() for h in ("SUPERVISOR", nombre_evt_movil)
            ):
                continue
            movil_filas += 1
            estado = valor(row, mmap, "ESTADO")
            fecha_activacion = valor(row, mmap, "FECHA ACTIVACIÓN")
            sup = str(valor(row, mmap, "SUPERVISOR") or "SIN SUPERVISOR").strip()
            evt = str(valor(row, mmap, nombre_evt_movil) or "SIN EJECUTIVO").strip()
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

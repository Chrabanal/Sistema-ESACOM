from __future__ import annotations

import datetime
import re
import unicodedata
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from integraciones.models import CargaExcel, KPICierreResumen
from usuarios.models import Ejecutivo


MESES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
    "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
    "SEPTIEMBRE": 9, "SETIEMBRE": 9, "OCTUBRE": 10,
    "NOVIEMBRE": 11, "DICIEMBRE": 12,
}

ESTADO_MAP = {
    "PAGO": "PAGO",
    "NO PAGO": "NO_PAGO",
    "PENDIENTE": "PENDIENTE",
    "S/B": "SIN_BOLETA",
    "PAGADO FUERA DE PLAZO": "FUERA_PLAZO",
}

BOLETA_MAP = {1: "B1", 2: "B2", 3: "B3"}


def normalizar(texto) -> str:
    texto = str(texto) if texto is not None else ""
    texto = texto.strip().upper().replace("_", " ").replace("°", "")
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def normalizar_rut(v) -> str:
    if v in (None, ""):
        return ""
    s = re.sub(r"[^0-9K]", "", str(v).upper().strip())
    if len(s) < 2:
        return s
    cuerpo, dv = s[:-1].lstrip("0") or "0", s[-1]
    return f"{cuerpo}-{dv}"


def a_entero(v, default=0):
    if v in (None, ""):
        return default
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def a_pct(v):
    if v in (None, ""):
        return None
    if isinstance(v, str):
        s = v.strip().replace("%", "").replace(",", ".")
        try:
            d = Decimal(s)
        except Exception:
            return None
    else:
        try:
            d = Decimal(str(v))
        except Exception:
            return None
    if d <= 1:
        d *= 100
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def mes_camada(nombre_mes, fecha_corte: datetime.date) -> str:
    mes = MESES.get(normalizar(nombre_mes))
    if not mes:
        raise CommandError(f"Camada mensual no reconocida en reporte móvil: {nombre_mes!r}")
    anio = fecha_corte.year if mes <= fecha_corte.month else fecha_corte.year - 1
    return f"{anio:04d}-{mes:02d}"


def _bloques_resumen(ws, fecha_corte: datetime.date):
    """Extrae B1/B2/B3 y totales oficiales de RESUMEN GESTION RGU."""
    marcadores = []
    max_scan_row = min(ws.max_row, 30)
    for row in ws.iter_rows(min_row=1, max_row=max_scan_row):
        for cell in row:
            if normalizar(cell.value) == "NUMERO BOLETA":
                numero = a_entero(ws.cell(cell.row, cell.column + 1).value, None)
                if numero in BOLETA_MAP:
                    marcadores.append((cell.column, numero))
    if not marcadores:
        raise CommandError("No se encontraron bloques NUMERO_BOLETA en RESUMEN GESTION RGU.")
    marcadores = sorted(dict(marcadores).items())

    resultado = {}
    for pos, (inicio, numero) in enumerate(marcadores):
        fin = (marcadores[pos + 1][0] - 1) if pos + 1 < len(marcadores) else ws.max_column
        boleta = BOLETA_MAP[numero]
        camada_txt = None
        header_row = None
        headers = {}
        for r in range(1, max_scan_row + 1):
            for c in range(inicio, fin + 1):
                txt = normalizar(ws.cell(r, c).value)
                if txt == "CAMADA" and c + 1 <= fin:
                    camada_txt = ws.cell(r, c + 1).value
            fila_headers = {normalizar(ws.cell(r, c).value): c for c in range(inicio, fin + 1)}
            if "EMPRESADASH" in fila_headers and "KPI" in fila_headers and "RGU TOTAL" in fila_headers:
                header_row = r
                headers = fila_headers
                break
        if not camada_txt or not header_row:
            raise CommandError(f"No se pudo leer CAMADA/cabecera para {boleta} en RESUMEN GESTION RGU.")

        fila_esacom = None
        for r in range(header_row + 1, min(ws.max_row, header_row + 80) + 1):
            empresa = normalizar(ws.cell(r, headers["EMPRESADASH"]).value)
            if empresa == "ESACOM":
                fila_esacom = r
                break
        if not fila_esacom:
            raise CommandError(f"No se encontró fila ESACOM para {boleta} en RESUMEN GESTION RGU.")

        def hv(nombre):
            col = headers.get(nombre)
            return ws.cell(fila_esacom, col).value if col else None

        resultado[boleta] = {
            "camada_texto": normalizar(camada_txt),
            "camada": mes_camada(camada_txt, fecha_corte),
            "pago": a_entero(hv("PAGO")),
            "total": a_entero(hv("RGU TOTAL")),
            "kpi_pct": a_pct(hv("KPI")),
            "meta_claro_pct": a_pct(hv("META")),
            "q_meta_claro": a_entero(hv("Q PARA META")),
        }
    faltan = [b for b in ("B1", "B2", "B3") if b not in resultado]
    if faltan:
        raise CommandError(f"El reporte móvil no contiene los tres bloques B1/B2/B3: {', '.join(faltan)}")
    return resultado


def _agregar_base(ws, focos):
    headers = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not headers:
        raise CommandError("La hoja BASE está vacía.")
    idx = {normalizar(h): i for i, h in enumerate(headers) if h not in (None, "")}
    requeridas = ["CAMADA", "EMPRESADASH", "REP PCS", "N BOLETA", "RUT VENDEDOR", "KPI", "MARCA MES NP8"]
    faltantes = [h for h in requeridas if h not in idx]
    if faltantes:
        raise CommandError("Faltan columnas obligatorias para reporte móvil en BASE: " + ", ".join(faltantes))

    def campo(row, nombre):
        i = idx[nombre]
        return row[i] if i < len(row) else None

    foco_texto = {b: normalizar(info["camada_texto"]) for b, info in focos.items()}
    # (rut normalizado, boleta) -> estados RGU
    por_vendedor = defaultdict(lambda: defaultdict(int))
    filas_incluidas = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if normalizar(campo(row, "EMPRESADASH")) != "ESACOM":
            continue
        numero = a_entero(campo(row, "N BOLETA"), None)
        boleta = BOLETA_MAP.get(numero)
        if not boleta:
            continue
        if normalizar(campo(row, "CAMADA")) != foco_texto[boleta]:
            continue
        if a_entero(campo(row, "MARCA MES NP8"), 0) != 1:
            continue
        estado = ESTADO_MAP.get(normalizar(campo(row, "KPI")))
        if not estado:
            continue
        rgu = max(0, a_entero(campo(row, "REP PCS"), 0))
        rut = normalizar_rut(campo(row, "RUT VENDEDOR"))
        if not rut:
            # La fila aporta al total del archivo, pero no se puede atribuir a un Ejecutivo.
            rut = "SIN_RUT"
        por_vendedor[(rut, boleta)][estado] += rgu
        filas_incluidas += 1
    if not filas_incluidas:
        raise CommandError("No se encontraron filas ESACOM medibles para los focos B1/B2/B3 del reporte móvil.")
    return por_vendedor, filas_incluidas


def _pct(pago, total):
    if not total:
        return Decimal("0.00")
    return (Decimal(pago) / Decimal(total) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class Command(BaseCommand):
    help = "Importa un AVANCE o CIERRE Claro Móvil agregado sin exigir NUM_PEDIDO."

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str)
        parser.add_argument("--carga-id", type=int, required=True)
        parser.add_argument("--fecha-corte", type=str, required=True)

    def handle(self, *args, **options):
        try:
            fecha_corte = datetime.date.fromisoformat(options["fecha_corte"])
        except ValueError:
            raise CommandError("fecha_corte debe tener formato AAAA-MM-DD.")
        try:
            wb = openpyxl.load_workbook(options["archivo"], data_only=True, read_only=True)
        except Exception as exc:
            raise CommandError(f"No se pudo abrir el reporte móvil: {exc}")
        if "RESUMEN GESTION RGU" not in wb.sheetnames or "BASE" not in wb.sheetnames:
            raise CommandError("El reporte Claro Móvil debe contener 'RESUMEN GESTION RGU' y 'BASE'.")

        carga = CargaExcel.objects.get(pk=options["carga_id"])
        formatos_validos = {CargaExcel.FormatoKPI.AVANCE_MOVIL, CargaExcel.FormatoKPI.CIERRE_MOVIL}
        if carga.formato_kpi not in formatos_validos:
            raise CommandError("El importador Móvil requiere formato AVANCE_MOVIL o CIERRE_MOVIL.")
        if carga.formato_kpi == CargaExcel.FormatoKPI.AVANCE_MOVIL and carga.estado_reporte != CargaExcel.EstadoReporte.AVANCE:
            raise CommandError("El formato AVANCE_MOVIL debe cargarse como AVANCE.")
        if carga.formato_kpi == CargaExcel.FormatoKPI.CIERRE_MOVIL and carga.estado_reporte != CargaExcel.EstadoReporte.CIERRE:
            raise CommandError("El formato CIERRE_MOVIL debe cargarse como CIERRE oficial.")

        focos = _bloques_resumen(wb["RESUMEN GESTION RGU"], fecha_corte)
        agregados, filas_incluidas = _agregar_base(wb["BASE"], focos)

        ejecutivos = {normalizar_rut(e.rut): e for e in Ejecutivo.objects.all()}
        por_boleta_global = defaultdict(lambda: defaultdict(int))
        resumen_por_boleta = {}

        with transaction.atomic():
            KPICierreResumen.objects.filter(carga=carga).delete()
            objetos = []
            sin_resolver = 0
            for (rut, boleta), estados in agregados.items():
                info = focos[boleta]
                pago = estados.get("PAGO", 0)
                pendiente = estados.get("PENDIENTE", 0)
                no_pago = estados.get("NO_PAGO", 0)
                fuera = estados.get("FUERA_PLAZO", 0)
                sin_boleta = estados.get("SIN_BOLETA", 0)
                total = pago + pendiente + no_pago + fuera
                for k, v in estados.items():
                    por_boleta_global[boleta][k] += v
                ejecutivo = ejecutivos.get(rut)
                if rut not in ("SIN_RUT",) and ejecutivo is None:
                    sin_resolver += 1
                objetos.append(KPICierreResumen(
                    carga=carga,
                    ejecutivo=ejecutivo,
                    rut_vendedor_fuente=rut,
                    camada=info["camada"],
                    boleta=boleta,
                    pagadas=pago,
                    pendientes=pendiente,
                    no_pago=no_pago,
                    fuera_plazo=fuera,
                    sin_boleta=sin_boleta,
                    total_medible=total,
                    kpi_pago_pct=_pct(pago, total),
                    meta_claro_pct=getattr(carga, f"meta_{boleta.lower()}") or info["meta_claro_pct"],
                    cierre_claro_pct=getattr(carga, f"avance_{boleta.lower()}") or None,
                ))

            # Total oficial del archivo, útil para comprobar que la lectura de BASE
            # reproduce el RESUMEN GESTION RGU antes de aceptar el cierre.
            for boleta in ("B1", "B2", "B3"):
                estados = por_boleta_global[boleta]
                info = focos[boleta]
                pago = estados.get("PAGO", 0)
                pendiente = estados.get("PENDIENTE", 0)
                no_pago = estados.get("NO_PAGO", 0)
                fuera = estados.get("FUERA_PLAZO", 0)
                sin_boleta = estados.get("SIN_BOLETA", 0)
                total = pago + pendiente + no_pago + fuera
                kpi = _pct(pago, total)
                if info["total"] and total != info["total"]:
                    raise CommandError(
                        f"El reporte Móvil {boleta} no reproduce RGU TOTAL del resumen: BASE={total}, RESUMEN={info['total']}."
                    )
                if info["pago"] and pago != info["pago"]:
                    raise CommandError(
                        f"El reporte Móvil {boleta} no reproduce Pago del resumen: BASE={pago}, RESUMEN={info['pago']}."
                    )
                if info["kpi_pct"] is not None and abs(kpi - info["kpi_pct"]) > Decimal("0.02"):
                    raise CommandError(
                        f"El reporte Móvil {boleta} no reproduce KPI del resumen: BASE={kpi}%, RESUMEN={info['kpi_pct']}%."
                    )
                cierre_oficial = getattr(carga, f"avance_{boleta.lower()}")
                meta_claro = getattr(carga, f"meta_{boleta.lower()}") or info["meta_claro_pct"]
                if cierre_oficial is not None and meta_claro:
                    calculado = (kpi / Decimal(str(meta_claro)) * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                    if abs(calculado - Decimal(str(cierre_oficial))) > Decimal("0.10"):
                        raise CommandError(
                            f"Avance/cierre informado {boleta} ({cierre_oficial}%) no cuadra con KPI/Meta del archivo ({calculado}%)."
                        )
                objetos.append(KPICierreResumen(
                    carga=carga,
                    ejecutivo=None,
                    rut_vendedor_fuente="GLOBAL",
                    camada=info["camada"],
                    boleta=boleta,
                    pagadas=pago,
                    pendientes=pendiente,
                    no_pago=no_pago,
                    fuera_plazo=fuera,
                    sin_boleta=sin_boleta,
                    total_medible=total,
                    kpi_pago_pct=kpi,
                    meta_claro_pct=meta_claro,
                    cierre_claro_pct=cierre_oficial,
                ))
                resumen_por_boleta[boleta] = {
                    "camada": info["camada"],
                    "pago": pago,
                    "pendiente": pendiente,
                    "no_pago": no_pago,
                    "fuera_plazo": fuera,
                    "sin_boleta": sin_boleta,
                    "total_rgu": total,
                    "kpi_pago_pct": float(kpi),
                    "meta_claro_pct": float(meta_claro) if meta_claro is not None else None,
                    "cierre_claro_pct": float(cierre_oficial) if cierre_oficial is not None else None,
                }

            KPICierreResumen.objects.bulk_create(objetos, batch_size=500)
            # Conserva el canal/tipo seleccionado: AVANCE_MOVIL o CIERRE_MOVIL.
            carga.foco_b1 = focos["B1"]["camada"]
            carga.foco_b2 = focos["B2"]["camada"]
            carga.foco_b3 = focos["B3"]["camada"]
            for boleta in ("B1", "B2", "B3"):
                campo_meta = f"meta_{boleta.lower()}"
                if getattr(carga, campo_meta) is None and focos[boleta]["meta_claro_pct"] is not None:
                    setattr(carga, campo_meta, focos[boleta]["meta_claro_pct"])
            carga.filas_totales = filas_incluidas
            carga.filas_sin_cruce = sin_resolver
            carga.save(update_fields=[
                "foco_b1", "foco_b2", "foco_b3",
                "meta_b1", "meta_b2", "meta_b3",
                "filas_totales", "filas_sin_cruce",
            ])

        es_cierre = carga.formato_kpi == CargaExcel.FormatoKPI.CIERRE_MOVIL
        self.resumen = {
            "formato": carga.formato_kpi,
            "estado": carga.estado_reporte,
            "filas_base_incluidas": filas_incluidas,
            "vendedores_no_resueltos": sin_resolver,
            "cierres" if es_cierre else "avances": resumen_por_boleta,
            "resumen_boletas": resumen_por_boleta,
            "nota": (
                "Cierre Móvil agregado guardado sin NUM_PEDIDO; no modifica accionables ni la ventana de AVANCE Fijo."
                if es_cierre
                else "Avance Móvil agregado guardado sin NUM_PEDIDO; queda separado del AVANCE Fijo y no modifica sus accionables."
            ),
        }
        etiqueta = "Cierre" if es_cierre else "Avance"
        self.stdout.write(self.style.SUCCESS(f"{etiqueta} Claro Móvil importado: {self.resumen}"))

"""
Importa la hoja BASE del reporte KPI de Claro (lunes/miércoles).

Clave de negocio confirmada con los archivos reales de ESACOM:
    NUM_PEDIDO + CAMADA + N_BOLETA

Los reportes son snapshots acumulativos: una misma boleta vuelve a llegar
con cambios de estado. La importación hace dos cosas en paralelo:

1. UPSERT del estado vigente en ventas.Corte (sin duplicar).
2. Snapshot inmutable en integraciones.KPIRegistro por cada carga, para
   auditar qué dijo Claro en cada archivo y detectar diferencias.

Uso:
    python manage.py importar_kpi archivo.xlsx
    python manage.py importar_kpi archivo.xlsx --dry-run
    python manage.py importar_kpi archivo.xlsx --limite 1000
"""
from __future__ import annotations

import datetime
import os
import re
import unicodedata
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from integraciones.models import CargaExcel, KPIRegistro, KPICierreFijoFila
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta


KPI_A_ESTADO = {
    "PAGO": Corte.EstadoPago.PAGADO,
    "NO PAGO": Corte.EstadoPago.NO_PAGO,
    "PENDIENTE": Corte.EstadoPago.PENDIENTE,
    "S/B": Corte.EstadoPago.SIN_BOLETA,
    "PAGADO FUERA DE PLAZO": Corte.EstadoPago.FUERA_PLAZO,
}

N_BOLETA_A_CORTE = {1: Corte.Boleta.B1, 2: Corte.Boleta.B2, 3: Corte.Boleta.B3}

# El Sistema ESACOM comenzó su histórico KPI operativo en julio 2026.
# Los reportes de Claro son acumulativos y pueden seguir trayendo meses
# anteriores; un AVANCE no debe reabrirlos ni mostrarlos como vigentes.
MES_INICIO_KPI = "2026-07"


def camadas_cerradas_fijo() -> set[tuple[str, str]]:
    """Protege únicamente las combinaciones CAMADA + BOLETA
    que cuentan con un cierre fijo oficial.
    """
    cierres = CargaExcel.objects.filter(
        tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
        estado_reporte=CargaExcel.EstadoReporte.CIERRE,
        formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
    )

    cerradas: set[tuple[str, str]] = set()

    for b1, b2, b3 in cierres.values_list(
        "foco_b1", "foco_b2", "foco_b3"
    ):
        for boleta, camada in (
            ("B1", b1), ("B2", b2), ("B3", b3)
        ):
            if camada and str(camada).strip():
                cerradas.add((str(camada).strip(), boleta))

    filas = KPICierreFijoFila.objects.filter(
        carga__in=cierres
    ).exclude(camada="").values_list(
        "camada", "boleta"
    ).distinct()

    for camada, boleta in filas:
        if camada and boleta:
            cerradas.add((str(camada).strip(), str(boleta).strip()))

    return cerradas


def normalizar(texto) -> str:
    texto = str(texto) if texto is not None else ""
    texto = texto.strip().upper().replace("_", " ").replace("°", "")
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def normalizar_rut(v) -> str:
    """
    Forma comparable de RUT chileno: cuerpo sin ceros a la izquierda + DV.

    El KPI real de Claro trae varios RUT con padding (ej. ``013425831-4``)
    mientras la base ESACOM guarda ``13425831-4``. Ambos representan el
    mismo RUT y deben comparar iguales. No valida el dígito verificador;
    solo normaliza el formato para auditoría.
    """
    if v in (None, ""):
        return ""
    s = str(v).upper().strip()
    if s.endswith(".0") and s[:-2].isdigit():
        s = s[:-2]
    s = re.sub(r"[^0-9K]", "", s)
    if len(s) < 2:
        return s
    cuerpo, dv = s[:-1], s[-1]
    cuerpo = cuerpo.lstrip("0") or "0"
    return f"{cuerpo}{dv}"


def a_fecha(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    return None


def a_entero(v):
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def a_decimal(v):
    if v in (None, ""):
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError):
        return None


def camada_a_mes_ano(camada) -> str | None:
    """202605 (int/float/str) -> '2026-05'. También acepta '2026-05'."""
    if camada in (None, ""):
        return None
    s = str(camada).strip()
    if re.fullmatch(r"\d{4}-\d{2}", s):
        return s
    try:
        s = str(int(float(s)))
    except (TypeError, ValueError):
        return None
    if len(s) != 6:
        return None
    mes = int(s[4:])
    if not 1 <= mes <= 12:
        return None
    return f"{s[:4]}-{s[4:]}"


def json_seguro(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def fecha_iso(v):
    if not v:
        return None
    if isinstance(v, datetime.date):
        return v
    try:
        return datetime.date.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None


def fin_mes(fecha: datetime.date | None):
    """Último día del mes del reporte. Claro excluye cuando vencimiento + 8
    cae en el mes siguiente, aunque el corte de pagos sea un día intermedio.
    """
    if not fecha:
        return None
    if fecha.month == 12:
        siguiente = datetime.date(fecha.year + 1, 1, 1)
    else:
        siguiente = datetime.date(fecha.year, fecha.month + 1, 1)
    return siguiente - datetime.timedelta(days=1)


def calcular_estado_esacom(*, estado_claro, boleta, fecha_venc, fecha_pago, fecha_corte, estados_fuente, clave_base):
    """
    Valida el estado sin modificar lo que informó Claro.

    Reglas confirmadas por correos de agosto 2026:
    - La fecha de corte limita qué PAGOS se consideran en el snapshot.
    - Una boleta queda fuera de medición si vencimiento + 8 días cae en el
      mes siguiente al mes del reporte (ej. corte 09/08 -> excluye septiembre).
    - Si hay pago dentro de los 8 días: PAGADO. Después: FUERA_PLAZO.
    - En B3 sin boleta: si B1 y B2 registran algún pago, queda S/B;
      si no hubo pago en las primeras boletas, se mide como NO_PAGO.
    """
    fecha_limite = fecha_venc + datetime.timedelta(days=8) if fecha_venc else None
    limite_mes = fin_mes(fecha_corte)
    es_medible = not (limite_mes and fecha_limite and fecha_limite > limite_mes)

    if not es_medible:
        return Corte.EstadoCalculado.FUERA_MEDICION, fecha_limite, False

    if fecha_pago and (not fecha_corte or fecha_pago <= fecha_corte):
        if fecha_limite and fecha_pago > fecha_limite:
            return Corte.EstadoCalculado.FUERA_PLAZO, fecha_limite, True
        return Corte.EstadoCalculado.PAGADO, fecha_limite, True

    # El correo indica que el reporte solo contempla pagos hasta la fecha
    # de corte. Un pago posterior no puede rescatar la medición de ese snapshot.
    if fecha_pago and fecha_corte and fecha_pago > fecha_corte:
        return Corte.EstadoCalculado.NO_PAGO, fecha_limite, True

    if boleta == Corte.Boleta.B3 and estado_claro == Corte.EstadoPago.SIN_BOLETA:
        pagados = {Corte.EstadoPago.PAGADO, Corte.EstadoPago.FUERA_PLAZO}
        b1 = estados_fuente.get((*clave_base, Corte.Boleta.B1))
        b2 = estados_fuente.get((*clave_base, Corte.Boleta.B2))
        if b1 is None or b2 is None:
            # Si el snapshot no trae las boletas previas, no inventamos el
            # historial: conservamos S/B y dejamos la fuente auditable.
            return Corte.EstadoCalculado.SIN_BOLETA, fecha_limite, True
        if b1 in pagados and b2 in pagados:
            return Corte.EstadoCalculado.SIN_BOLETA, fecha_limite, True
        return Corte.EstadoCalculado.NO_PAGO, fecha_limite, True

    equivalencia = {
        Corte.EstadoPago.PAGADO: Corte.EstadoCalculado.PAGADO,
        Corte.EstadoPago.PENDIENTE: Corte.EstadoCalculado.PENDIENTE,
        Corte.EstadoPago.NO_PAGO: Corte.EstadoCalculado.NO_PAGO,
        Corte.EstadoPago.FUERA_PLAZO: Corte.EstadoCalculado.FUERA_PLAZO,
        Corte.EstadoPago.SIN_BOLETA: Corte.EstadoCalculado.SIN_BOLETA,
    }
    return equivalencia.get(estado_claro, Corte.EstadoCalculado.PENDIENTE), fecha_limite, True


class Command(BaseCommand):
    help = "Importa la hoja BASE del reporte KPI de Claro y cruza contra ESACOM."

    def add_arguments(self, parser):
        parser.add_argument("archivo", type=str)
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limite", type=int, default=None, help="Máximo de filas a leer (pruebas).")
        parser.add_argument("--hoja", type=str, default="BASE")
        parser.add_argument("--carga-id", type=int, default=None, help="CargaExcel ya creada por la API.")
        parser.add_argument("--usuario-rut", type=str, default="")
        parser.add_argument("--archivo-nombre", type=str, default="")
        parser.add_argument("--fecha-corte", type=str, default="", help="Fecha de corte Claro, AAAA-MM-DD.")
        parser.add_argument("--dia-reporte", type=str, default="", help="LUNES / MIERCOLES / JUEVES / OTRO.")

    def handle(self, *args, **options):
        path = options["archivo"]
        dry_run = options["dry_run"]
        limite = options["limite"]
        nombre_hoja = options["hoja"]

        try:
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        except FileNotFoundError:
            raise CommandError(f"No existe el archivo: {path}")
        except Exception as exc:
            raise CommandError(f"No se pudo abrir el Excel: {exc}")

        if nombre_hoja not in wb.sheetnames:
            raise CommandError(f"La hoja '{nombre_hoja}' no existe. Disponibles: {wb.sheetnames}")
        ws = wb[nombre_hoja]

        try:
            headers = next(ws.iter_rows(min_row=1, max_row=1, values_only=True))
        except StopIteration:
            raise CommandError("La hoja BASE está vacía.")

        idx = {normalizar(h): i for i, h in enumerate(headers) if h}

        requeridas = ["NUM PEDIDO", "CAMADA", "N BOLETA", "KPI"]
        faltantes = [h for h in requeridas if h not in idx]
        if faltantes:
            raise CommandError(f"Faltan columnas obligatorias en BASE: {', '.join(faltantes)}")

        def campo(row, nombre):
            i = idx.get(normalizar(nombre))
            return row[i] if i is not None and i < len(row) else None

        # El reporte tiene solo unos pocos miles de filas. Lo materializamos
        # para poder validar B3 contra B1/B2 sin depender del orden del Excel.
        # El archivo real de Claro puede tener formato/fórmulas arrastradas
        # hasta cientos de miles de filas vacías. La fila de negocio existe
        # solo cuando trae NUM_PEDIDO; filtrar por esa clave evita contar
        # basura visual como "filas malformadas" y reduce muchísimo memoria.
        filas = [
            row for row in ws.iter_rows(min_row=2, values_only=True)
            if str(campo(row, "NUM_PEDIDO") or "").strip()
        ]
        estados_fuente = {}
        for row in filas:
            pedido = str(campo(row, "NUM_PEDIDO") or "").strip()
            camada_pre = camada_a_mes_ano(campo(row, "CAMADA"))
            nb = a_entero(campo(row, "N_BOLETA"))
            bol = N_BOLETA_A_CORTE.get(nb)
            est = KPI_A_ESTADO.get(normalizar(campo(row, "kpi")))
            if pedido and camada_pre and bol and est:
                estados_fuente[(pedido, camada_pre, bol)] = est

        # Cargamos las ventas una sola vez: el cruce fuerte es NUM_PEDIDO.
        ventas = {
            str(v["n_pedido"]).strip(): v
            for v in Venta.objects.values(
                "id",
                "n_pedido",
                "rut_cliente",
                "camada",
                "rgu_base",
                "codigo_ce",
                "rut_ce",
                "ejecutivo_id",
                "ejecutivo_ce_id",
                "conflicto_fuente",
                "estado_instalacion",
                "rut_evt",
                "nombre_evt",
                "supervisor_fuente",
                "ejecutivo__rut",
                "ejecutivo__nombre",
                "ejecutivo__tipo_kpi",
                "ejecutivo__cargo",
                "ejecutivo__is_active",
                "ejecutivo__supervisor_id",
                "ejecutivo__supervisor__rut",
                "ejecutivo__supervisor__nombre",
            )
        }

        # PROPIETARIO_FINAL suele coincidir con CODIGO CE/CODIGO ANDES.
        ejecutivos_por_codigo = {}
        for e in Ejecutivo.objects.values("id", "codigo_andes", "codigo_fijo", "codigo_movil"):
            for campo_codigo in ("codigo_andes", "codigo_fijo", "codigo_movil"):
                codigo = normalizar(e[campo_codigo])
                if codigo:
                    ejecutivos_por_codigo.setdefault(codigo, e["id"])

        cortes_existentes = {
            (venta_id, mes_ano, boleta): {
                "id": corte_id,
                "verificado": verificado,
                "meta_pct": meta_pct,
            }
            for corte_id, venta_id, mes_ano, boleta, verificado, meta_pct in Corte.objects.values_list(
                "id", "venta_id", "mes_ano", "boleta", "verificado_en_andes", "meta_pct"
            )
        }

        # ``filas_archivo`` conserva cuántas filas de negocio venían en el XLSX.
        # ``total_leidas`` pasa a representar solo las filas que el CRM permitió
        # procesar después de aplicar la protección automática de históricos.
        filas_archivo = len(filas)
        total_leidas = 0
        filas_ignoradas_cierre = 0
        filas_ignoradas_fuera_alcance = 0
        ignoradas_cierre_por_camada: dict[str, int] = {}
        coincidencias = 0
        creados = 0
        actualizados = 0
        sin_venta = 0
        filas_malformadas = 0
        duplicadas_archivo = 0
        diferencias_rut = 0
        diferencias_rgu = 0
        diferencias_propietario = 0
        ejecutivos_no_resueltos = 0
        estados_desconocidos = 0
        fuera_medicion = 0
        diferencias_estado = 0
        filas_con_inconsistencia = 0
        marca_mes_uno = 0
        marca_mes_cero = 0
        marca_mes_ausente = 0
        pedidos_conflicto_fuente: set[str] = set()

        vistos_archivo = set()
        buffer_crear: list[Corte] = []
        buffer_actualizar_con_estado: list[Corte] = []
        buffer_actualizar_sin_estado: list[Corte] = []
        buffer_kpi: list[KPIRegistro] = []

        carga = None
        usuario = None
        if options.get("usuario_rut"):
            usuario = Ejecutivo.objects.filter(rut=options["usuario_rut"]).first()

        fecha_corte = fecha_iso(options.get("fecha_corte"))
        dia_reporte = str(options.get("dia_reporte") or "").upper()

        with transaction.atomic():
            if options.get("carga_id"):
                carga = CargaExcel.objects.get(pk=options["carga_id"])
                fecha_corte = fecha_corte or carga.fecha_corte
                dia_reporte = dia_reporte or carga.dia_reporte
            elif not dry_run:
                carga = CargaExcel.objects.create(
                    origen=CargaExcel.Origen.MANUAL,
                    tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
                    archivo_nombre=options.get("archivo_nombre") or os.path.basename(path),
                    creado_por=usuario,
                    fecha_corte=fecha_corte,
                    dia_reporte=dia_reporte if dia_reporte in CargaExcel.DiaReporte.values else "",
                )

            proteger_historico = bool(
                (dry_run and carga is None)
                or (
                    carga
                    and carga.estado_reporte == CargaExcel.EstadoReporte.AVANCE
                    and carga.formato_kpi == CargaExcel.FormatoKPI.DETALLADO
                )
            )
            camadas_cerradas = camadas_cerradas_fijo() if proteger_historico else set()

            meta_por_boleta = {
                "B1": getattr(carga, "meta_b1", None) if carga else None,
                "B2": getattr(carga, "meta_b2", None) if carga else None,
                "B3": getattr(carga, "meta_b3", None) if carga else None,
            }
            # La meta del correo corresponde al foco vigente de cada boleta,
            # no a todas las camadas históricas arrastradas por el snapshot.
            # Detectamos la camada medible más reciente por B1/B2/B3 para no
            # contaminar metas históricas al importar un archivo acumulativo.
            camadas_medibles = {"B1": set(), "B2": set(), "B3": set()}
            camadas_todas = {"B1": set(), "B2": set(), "B3": set()}
            for row_meta in filas:
                camada_meta = camada_a_mes_ano(campo(row_meta, "CAMADA"))
                bol_meta = N_BOLETA_A_CORTE.get(a_entero(campo(row_meta, "N_BOLETA")))
                if not camada_meta or not bol_meta:
                    continue
                camadas_todas[bol_meta].add(camada_meta)
                marca_meta = a_entero(campo(row_meta, "Marca de mes"))
                if marca_meta is not None:
                    if marca_meta == 1:
                        camadas_medibles[bol_meta].add(camada_meta)
                    continue
                venc_meta = a_fecha(campo(row_meta, "FECHA_VENCIMIENTO"))
                limite_meta = venc_meta + datetime.timedelta(days=8) if venc_meta else None
                limite_mes_meta = fin_mes(fecha_corte)
                if not (limite_mes_meta and limite_meta and limite_meta > limite_mes_meta):
                    camadas_medibles[bol_meta].add(camada_meta)
            focos_carga = {
                "B1": getattr(carga, "foco_b1", "") if carga else "",
                "B2": getattr(carga, "foco_b2", "") if carga else "",
                "B3": getattr(carga, "foco_b3", "") if carga else "",
            }
            mes_meta_por_boleta = {
                b: (
                    focos_carga.get(b)
                    or (max(camadas_medibles[b]) if camadas_medibles[b] else None)
                    or (max(camadas_todas[b]) if camadas_todas[b] else None)
                )
                for b in ("B1", "B2", "B3")
            }

            for row in filas:
                num_pedido = str(campo(row, "NUM_PEDIDO") or "").strip()
                camada = camada_a_mes_ano(campo(row, "CAMADA"))
                n_boleta = a_entero(campo(row, "N_BOLETA"))
                boleta = N_BOLETA_A_CORTE.get(n_boleta)

                if not num_pedido or not camada or not boleta:
                    total_leidas += 1
                    filas_malformadas += 1
                    continue

                # Protección automática para los XLSX acumulativos de Claro.
                # Un AVANCE puede traer nuevamente B1/B2/B3 de meses antiguos:
                # - antes de julio 2026 quedan fuera del alcance ESACOM;
                # - una camada con CIERRE_FIJO nunca se vuelve a escribir.
                # Los meses todavía abiertos sí continúan actualizándose aunque
                # ya no sean el foco principal del correo/reporte.
                if proteger_historico:
                    if camada < MES_INICIO_KPI:
                        filas_ignoradas_fuera_alcance += 1
                        continue
                    if (camada, boleta) in camadas_cerradas:
                        filas_ignoradas_cierre += 1
                        ignoradas_cierre_por_camada[camada] = (
                            ignoradas_cierre_por_camada.get(camada, 0) + 1
                        )
                        continue

                total_leidas += 1
                if limite and total_leidas > limite:
                    total_leidas -= 1
                    break

                clave_archivo = (num_pedido, camada, boleta)
                if clave_archivo in vistos_archivo:
                    duplicadas_archivo += 1
                    continue
                vistos_archivo.add(clave_archivo)

                venta = ventas.get(num_pedido)
                venta_id = venta["id"] if venta else None

                kpi_txt_original = str(campo(row, "kpi") or "").strip()
                kpi_norm = normalizar(kpi_txt_original)
                estado_claro = KPI_A_ESTADO.get(kpi_norm)
                if estado_claro is None:
                    estados_desconocidos += 1
                    estado_claro = Corte.EstadoPago.PENDIENTE

                rut_kpi = str(campo(row, "RUT") or "").strip()
                propietario = str(campo(row, "PROPIETARIO_FINAL") or "").strip()
                rut_propietario = str(campo(row, "RUT_PROPIETARIO_FINAL") or "").strip()
                rgu = a_entero(campo(row, "RGU"))
                fecha_venc = a_fecha(campo(row, "FECHA_VENCIMIENTO"))
                fecha_pago = a_fecha(campo(row, "FECHA_EFECTIVA_PAGO"))
                dias_pago = a_entero(campo(row, "DiasPago"))
                rango_pago = str(campo(row, "RangoPago") or "")[:40]
                apelacion_claro = a_entero(campo(row, "apelacion"))
                bill_no = str(campo(row, "BILL_NO") or "").strip()[:50]
                monto_boleta = a_decimal(campo(row, "MONTO_BOLETA"))
                monto_pago = a_decimal(campo(row, "MONTO_PAGO"))
                marca_mes_kpi = a_entero(campo(row, "Marca de mes"))
                if marca_mes_kpi == 1:
                    marca_mes_uno += 1
                elif marca_mes_kpi == 0:
                    marca_mes_cero += 1
                else:
                    marca_mes_ausente += 1

                estado_calculado, fecha_limite_medicion, es_medible = calcular_estado_esacom(
                    estado_claro=estado_claro,
                    boleta=boleta,
                    fecha_venc=fecha_venc,
                    fecha_pago=fecha_pago,
                    fecha_corte=fecha_corte,
                    estados_fuente=estados_fuente,
                    clave_base=(num_pedido, camada),
                )
                # ``Marca de mes`` es la bandera oficial que usa el reporte Claro
                # para decidir qué filas pertenecen al foco KPI. La regla local
                # de vencimiento sigue funcionando como control, pero nunca
                # debemos incluir una fila que el propio snapshot marcó con 0.
                if marca_mes_kpi is not None and marca_mes_kpi != 1:
                    es_medible = False
                    estado_calculado = Corte.EstadoCalculado.FUERA_MEDICION

                dif_estado = bool(
                    es_medible
                    and estado_calculado != estado_claro
                )
                fuera_medicion += int(not es_medible)
                diferencias_estado += int(dif_estado)

                dif_rut = False
                dif_rgu = False
                dif_propietario = False
                ejecutivo_kpi_id = None
                ejecutivo_no_resuelto = False

                if venta:
                    coincidencias += 1
                    if venta.get("conflicto_fuente"):
                        # El corte se conserva para el KPI global, pero las
                        # capas por Ejecutivo/Supervisor lo excluirán hasta
                        # resolver la propiedad ESACOM. Nunca adjudicamos este
                        # caso usando PROPIETARIO_FINAL de Claro.
                        pedidos_conflicto_fuente.add(num_pedido)

                    if rut_kpi and venta["rut_cliente"]:
                        dif_rut = normalizar_rut(rut_kpi) != normalizar_rut(venta["rut_cliente"])
                    if rgu is not None and venta["rgu_base"] is not None:
                        dif_rgu = int(rgu) != int(venta["rgu_base"])
                    if propietario and venta["codigo_ce"]:
                        dif_propietario = normalizar(propietario) != normalizar(venta["codigo_ce"])

                    if propietario:
                        ejecutivo_kpi_id = ejecutivos_por_codigo.get(normalizar(propietario))
                    if not ejecutivo_kpi_id:
                        ejecutivo_kpi_id = venta["ejecutivo_ce_id"]
                    ejecutivo_no_resuelto = bool(propietario and not ejecutivo_kpi_id)

                    diferencias_rut += int(dif_rut)
                    diferencias_rgu += int(dif_rgu)
                    diferencias_propietario += int(dif_propietario)
                    ejecutivos_no_resueltos += int(ejecutivo_no_resuelto)
                    filas_con_inconsistencia += int(
                        dif_rut or dif_rgu or dif_propietario or dif_estado or ejecutivo_no_resuelto
                    )

                    clave_corte = (venta_id, camada, boleta)
                    existente = cortes_existentes.get(clave_corte)
                    meta_carga = meta_por_boleta.get(boleta) if camada == mes_meta_por_boleta.get(boleta) else None
                    meta_vigente = meta_carga if meta_carga is not None else (existente.get("meta_pct") if existente else 0)

                    datos_corte = dict(
                        venta_id=venta_id,
                        carga_kpi_id=carga.id if carga is not None else None,
                        meta_pct=meta_vigente or 0,
                        mes_ano=camada,
                        boleta=boleta,
                        estado_claro=estado_claro,
                        fecha_vencimiento=fecha_venc,
                        fecha_pago=fecha_pago,
                        fecha_limite_medicion=fecha_limite_medicion,
                        es_medible=es_medible,
                        marca_mes_kpi=marca_mes_kpi,
                        estado_calculado=estado_calculado,
                        dias_diferencia=dias_pago,
                        rango_pago=rango_pago,
                        apelacion_claro=apelacion_claro,
                        rgu_kpi=rgu,
                        propietario_final=propietario[:50],
                        rut_propietario_final=rut_propietario[:20],
                        ejecutivo_kpi_id=ejecutivo_kpi_id,
                        bill_no=bill_no,
                        monto_boleta=monto_boleta,
                        monto_pago=monto_pago,
                    )

                    if existente:
                        obj = Corte(id=existente["id"], **datos_corte)
                        if existente["verificado"]:
                            buffer_actualizar_sin_estado.append(obj)
                        else:
                            obj.estado_pago = estado_claro
                            buffer_actualizar_con_estado.append(obj)
                        actualizados += 1
                    else:
                        obj = Corte(estado_pago=estado_claro, **datos_corte)
                        buffer_crear.append(obj)
                        # Evita crear dos veces si el archivo trae la clave repetida
                        # antes de que se ejecute el bulk_create.
                        cortes_existentes[clave_corte] = {"id": None, "verificado": False, "meta_pct": meta_vigente or 0}
                        creados += 1
                else:
                    sin_venta += 1

                if carga is not None:
                    raw = {
                        str(headers[i]): json_seguro(row[i])
                        for i in range(min(len(headers), len(row)))
                        if headers[i]
                    }
                    snapshot_esacom = None
                    if venta:
                        snapshot_esacom = {
                            "venta_id": venta.get("id"),
                            "estado_instalacion": venta.get("estado_instalacion") or "",
                            "conflicto_fuente": bool(venta.get("conflicto_fuente")),
                            "rgu": venta.get("rgu_base"),
                            "rut_evt": venta.get("rut_evt") or "",
                            "nombre_evt": venta.get("nombre_evt") or "",
                            "supervisor_fuente": venta.get("supervisor_fuente") or "",
                            "ejecutivo_id": venta.get("ejecutivo_id"),
                            "ejecutivo_rut": venta.get("ejecutivo__rut") or "",
                            "ejecutivo_nombre": venta.get("ejecutivo__nombre") or "",
                            "tipo_kpi": venta.get("ejecutivo__tipo_kpi") or "",
                            "cargo": venta.get("ejecutivo__cargo") or "",
                            "ejecutivo_activo": bool(venta.get("ejecutivo__is_active")),
                            "supervisor_id": venta.get("ejecutivo__supervisor_id"),
                            "supervisor_rut": venta.get("ejecutivo__supervisor__rut") or "",
                            "supervisor_nombre": venta.get("ejecutivo__supervisor__nombre") or "",
                        }
                    buffer_kpi.append(
                        KPIRegistro(
                            carga_id=carga.id,
                            venta_id=venta_id,
                            num_pedido=num_pedido,
                            camada=camada,
                            boleta=boleta,
                            rut_cliente=rut_kpi[:20],
                            propietario_final=propietario[:50],
                            rut_propietario_final=rut_propietario[:20],
                            supervisor_fuente=str(campo(row, "SUPERVISOR") or "")[:100],
                            ingresador=str(campo(row, "INGRESADOR") or "")[:100],
                            comuna=str(campo(row, "COMUNA") or "")[:100],
                            rgu=rgu,
                            kpi_texto=kpi_txt_original[:40],
                            estado_normalizado=estado_claro,
                            bill_no=bill_no,
                            fecha_pago=fecha_pago,
                            fecha_vencimiento=fecha_venc,
                            fecha_limite_medicion=fecha_limite_medicion,
                            es_medible=es_medible,
                            marca_mes_kpi=marca_mes_kpi,
                            estado_calculado=estado_calculado,
                            diferencia_estado=dif_estado,
                            monto_boleta=monto_boleta,
                            monto_pago=monto_pago,
                            rango_pago=rango_pago,
                            apelacion_claro=apelacion_claro,
                            cruce_ok=bool(venta),
                            diferencia_rut=dif_rut,
                            diferencia_rgu=dif_rgu,
                            diferencia_propietario=dif_propietario,
                            ejecutivo_kpi_no_resuelto=ejecutivo_no_resuelto,
                            snapshot_esacom=snapshot_esacom,
                            raw_data=raw,
                        )
                    )

                if len(buffer_crear) >= 1000:
                    self._flush_crear(buffer_crear, dry_run)
                if len(buffer_actualizar_con_estado) >= 1000:
                    self._flush_actualizar(buffer_actualizar_con_estado, incluir_estado_pago=True, dry_run=dry_run)
                if len(buffer_actualizar_sin_estado) >= 1000:
                    self._flush_actualizar(buffer_actualizar_sin_estado, incluir_estado_pago=False, dry_run=dry_run)
                if len(buffer_kpi) >= 1000:
                    self._flush_kpi(buffer_kpi, dry_run)

            self._flush_crear(buffer_crear, dry_run)
            self._flush_actualizar(buffer_actualizar_con_estado, incluir_estado_pago=True, dry_run=dry_run)
            self._flush_actualizar(buffer_actualizar_sin_estado, incluir_estado_pago=False, dry_run=dry_run)
            self._flush_kpi(buffer_kpi, dry_run)

            if carga is not None:
                # filas_con_error cuenta filas con alguna diferencia, no la suma
                # de banderas (una fila puede tener más de una).
                filas_inconsistentes = KPIRegistro.objects.filter(carga=carga).filter(
                    # OR explícito para contar cada fila una sola vez.
                    Q(diferencia_rut=True)
                    | Q(diferencia_rgu=True)
                    | Q(diferencia_propietario=True)
                    | Q(diferencia_estado=True)
                    | Q(ejecutivo_kpi_no_resuelto=True)
                ).count()
                # El total persistido representa lo que realmente quedó
                # importado en esta carga, no las filas acumulativas que el
                # sistema protegió/ignoró.
                carga.filas_totales = KPIRegistro.objects.filter(carga=carga).count()
                carga.filas_sin_cruce = sin_venta
                carga.filas_con_error = filas_inconsistentes + filas_malformadas
                carga.save(update_fields=["filas_totales", "filas_sin_cruce", "filas_con_error"])

                # Un CIERRE Fijo congela también la población de la planilla
                # Gerencia (filas ESACOM instaladas + estado original Claro).
                # Así una sincronización posterior no puede alterar el cierre.
                if (
                    carga.estado_reporte == CargaExcel.EstadoReporte.CIERRE
                    and carga.formato_kpi == CargaExcel.FormatoKPI.CIERRE_FIJO
                ):
                    from integraciones.cierre_fijo_snapshot import asegurar_snapshot_cierre_fijo

                    for boleta_snap, campo_foco in (("B1", "foco_b1"), ("B2", "foco_b2"), ("B3", "foco_b3")):
                        camada_snap = str(getattr(carga, campo_foco, "") or "").strip()
                        if camada_snap:
                            asegurar_snapshot_cierre_fijo(carga, boleta_snap, camada_snap)

            if dry_run:
                self.stdout.write(self.style.WARNING("DRY-RUN: se revierte la transacción, no se guardó nada."))
                transaction.set_rollback(True)

        wb.close()

        filas_importadas = (
            KPIRegistro.objects.filter(carga=carga).count()
            if carga is not None and not dry_run
            else max(0, total_leidas - filas_malformadas - duplicadas_archivo)
        )

        resumen = {
            "filas_archivo": filas_archivo,
            "filas_leidas": total_leidas,
            "filas_importadas": filas_importadas,
            "proteccion_cierres": bool(proteger_historico),
            "filas_ignoradas_cierre": filas_ignoradas_cierre,
            "filas_ignoradas_fuera_alcance": filas_ignoradas_fuera_alcance,
            "camadas_cerradas_protegidas": [f"{m}/{b}" for m, b in sorted(camadas_cerradas)],
            "ignoradas_cierre_por_camada": dict(sorted(ignoradas_cierre_por_camada.items())),
            "mes_inicio_kpi": MES_INICIO_KPI,
            "coincidencias": coincidencias,
            "cortes_creados": creados,
            "cortes_actualizados": actualizados,
            "sin_venta_propia": sin_venta,
            "filas_malformadas": filas_malformadas,
            "duplicadas_en_archivo": duplicadas_archivo,
            "diferencias_rut": diferencias_rut,
            "diferencias_rgu": diferencias_rgu,
            "diferencias_propietario": diferencias_propietario,
            "ejecutivos_kpi_no_resueltos": ejecutivos_no_resueltos,
            "estados_kpi_desconocidos": estados_desconocidos,
            "fecha_corte": fecha_corte.isoformat() if fecha_corte else None,
            "dia_reporte": dia_reporte or None,
            "fuera_medicion": fuera_medicion,
            "diferencias_estado": diferencias_estado,
            "filas_con_inconsistencia": filas_con_inconsistencia,
            "marca_mes_1": marca_mes_uno,
            "marca_mes_0": marca_mes_cero,
            "marca_mes_ausente": marca_mes_ausente,
            "pedidos_conflicto_fuente": len(pedidos_conflicto_fuente),
            "muestra_pedidos_conflicto_fuente": sorted(pedidos_conflicto_fuente)[:20],
            "regla_atribucion": "Propiedad por RUT EVT ESACOM; pedidos conflicto_fuente no se adjudican a Ejecutivo/Supervisor",
            "regla_medicion": "Marca de mes del snapshot manda cuando existe; FECHA_VENCIMIENTO + 8 dias queda como control/fallback; pagos considerados hasta FECHA_CORTE",
            "clave_upsert": "NUM_PEDIDO + CAMADA + N_BOLETA",
        }

        self.stdout.write(self.style.SUCCESS(
            f"Archivo: {filas_archivo} | Procesadas: {total_leidas} | Cruces: {coincidencias} | "
            f"Ignoradas cierre: {filas_ignoradas_cierre} | Fuera alcance: {filas_ignoradas_fuera_alcance} | "
            f"Cortes +{creados}/~{actualizados} | Sin venta: {sin_venta} | "
            f"Dif RUT/RGU/CE: {diferencias_rut}/{diferencias_rgu}/{diferencias_propietario}"
        ))
        self.resumen = resumen
        self.carga = carga

    @staticmethod
    def _flush_crear(buffer: list[Corte], dry_run: bool):
        if not buffer:
            return
        if not dry_run:
            Corte.objects.bulk_create(buffer, batch_size=1000)
        buffer.clear()

    @staticmethod
    def _flush_actualizar(buffer: list[Corte], incluir_estado_pago: bool, dry_run: bool):
        if not buffer:
            return
        if not dry_run:
            campos = [
                "carga_kpi",
                "meta_pct",
                "estado_claro",
                "fecha_vencimiento",
                "fecha_pago",
                "fecha_limite_medicion",
                "es_medible",
                "marca_mes_kpi",
                "estado_calculado",
                "dias_diferencia",
                "rango_pago",
                "apelacion_claro",
                "rgu_kpi",
                "propietario_final",
                "rut_propietario_final",
                "ejecutivo_kpi",
                "bill_no",
                "monto_boleta",
                "monto_pago",
            ]
            if incluir_estado_pago:
                campos.append("estado_pago")
            Corte.objects.bulk_update(buffer, campos, batch_size=1000)
        buffer.clear()

    @staticmethod
    def _flush_kpi(buffer: list[KPIRegistro], dry_run: bool):
        if not buffer:
            return
        if not dry_run:
            KPIRegistro.objects.bulk_create(buffer, batch_size=1000)
        buffer.clear()

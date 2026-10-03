"""
Cálculo de KPI para ESACOM.

La regla se ajustó al archivo KPI real recibido de Claro: el indicador
se mide por RGU y el estado Pendiente permanece en el denominador del KPI
actual. Los S/B quedan fuera hasta que exista boleta.
"""
from __future__ import annotations

from collections import Counter
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q, QuerySet

from .models import Corte, Venta


def _pct(numerador: int, denominador: int) -> Decimal:
    if denominador == 0:
        return Decimal("0.0")
    return (Decimal(numerador) / Decimal(denominador) * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _rgu_corte(corte: Corte) -> int:
    """RGU de medición KPI.

    ESACOM sigue siendo la fuente maestra de la venta, su RUT EVT y su
    propiedad comercial. Pero el KPI oficial de Claro se pondera con el RGU
    que trae el snapshot KPI (``Corte.rgu_kpi``). Usar ``Venta.rgu_base``
    primero puede hacer que el porcentaje local difiera del Excel oficial.

    Para cortes históricos antiguos que no guardaron ``rgu_kpi`` mantenemos
    un fallback seguro a ESACOM y, por último, a la promoción.
    """
    if corte.rgu_kpi is not None:
        return int(corte.rgu_kpi)
    if corte.venta.rgu_base is not None:
        return int(corte.venta.rgu_base)
    return int(corte.venta.promocion.rgu or 1)


def _pct_kpi(numerador: Decimal | int, denominador: Decimal | int) -> Decimal:
    """Porcentaje KPI oficial con dos decimales, igual al reporte Claro."""
    if denominador == 0:
        return Decimal("0.00")
    return (Decimal(numerador) / Decimal(denominador) * 100).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _bucket_gestion(rango: str, estado: str) -> str:
    """Normaliza las categorías operativas que Claro muestra en sus tablas."""
    txt = (rango or "").strip().lower().replace("á", "a").replace("é", "e")
    if estado == Corte.EstadoPago.PAGADO or "pago" == txt:
        return "pago"
    if "vencido" in txt and ("mas de 8" in txt or ">8" in txt or "+8" in txt):
        return "vencido_mas_8"
    if "vencido" in txt and ("0-8" in txt or "0 a 8" in txt):
        return "vencido_0_8"
    if "gestionar" in txt and ("0-7" in txt or "0 a 7" in txt):
        return "gestionar_0_7"
    if "gestionar" in txt and ("8 o mas" in txt or "8 o más" in rango.lower() or "+8" in txt):
        return "gestionar_8_mas"
    return "otros"


def resumen_kpi(cortes: QuerySet[Corte]) -> dict:
    """
    KPI real de Claro medido por RGU, no por cantidad de pedidos/boletas.

    Validado contra KPI24082026 ESACOM: el denominador actual incluye
    Pago + Pendiente + No Pago + Pagado Fuera de Plazo. S/B queda fuera.

    La proyección replica la fórmula oficial del Excel:
        (Pago + (KPI actual × Pendiente)) / RGU total
    Es decir, aplica a los RGU pendientes la tasa de pago observada actual;
    NO supone que todos los pendientes terminan pagados.
    """
    fuera_medicion_rgu = 0
    fuera_medicion_boletas = 0

    acumulado = {
        Corte.EstadoPago.PAGADO: 0,
        Corte.EstadoPago.PENDIENTE: 0,
        Corte.EstadoPago.NO_PAGO: 0,
        Corte.EstadoPago.FUERA_PLAZO: 0,
        Corte.EstadoPago.SIN_BOLETA: 0,
    }
    boletas = Counter()
    gestion = Counter()

    for c in cortes.select_related("venta", "venta__promocion"):
        rgu = _rgu_corte(c)
        if not c.es_medible:
            fuera_medicion_rgu += rgu
            fuera_medicion_boletas += 1
            continue
        acumulado[c.estado_pago] = acumulado.get(c.estado_pago, 0) + rgu
        boletas[c.estado_pago] += 1
        gestion[_bucket_gestion(c.rango_pago, c.estado_pago)] += rgu

    pagadas = acumulado[Corte.EstadoPago.PAGADO]
    pendientes = acumulado[Corte.EstadoPago.PENDIENTE]
    no_pago = acumulado[Corte.EstadoPago.NO_PAGO]
    fuera_plazo = acumulado[Corte.EstadoPago.FUERA_PLAZO]
    sin_boleta = acumulado[Corte.EstadoPago.SIN_BOLETA]

    total_kpi = pagadas + pendientes + no_pago + fuera_plazo
    pct_cumplimiento_exacto = (
        Decimal(pagadas) / Decimal(total_kpi) * 100 if total_kpi else Decimal("0")
    )
    pct_cumplimiento = _pct_kpi(pagadas, total_kpi)

    # Fórmula oficial del XLSX: ((KPI_actual * Pendiente) + Pago) / Total.
    # KPI_actual se usa sin redondearlo previamente para no introducir deriva.
    if total_kpi:
        tasa_actual = Decimal(pagadas) / Decimal(total_kpi)
        pago_proyectado = Decimal(pagadas) + (tasa_actual * Decimal(pendientes))
        pct_proyectado = _pct_kpi(pago_proyectado, total_kpi)
    else:
        pct_proyectado = Decimal("0.00")

    metas = list(cortes.exclude(meta_pct=0).values_list("meta_pct", flat=True))
    meta_pct = max(metas) if metas else Decimal("0")
    cumplimiento_meta = (pct_cumplimiento_exacto / meta_pct * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP) if meta_pct else Decimal("0")

    if total_kpi == 0 or meta_pct == 0:
        semaforo = "sin_datos"
    elif pct_cumplimiento_exacto >= meta_pct:
        semaforo = "verde"
    elif pct_cumplimiento_exacto >= meta_pct - 10:
        semaforo = "amarillo"
    else:
        semaforo = "rojo"

    return {
        # Estas claves expresan RGU.
        "pagadas": pagadas,
        "pendientes": pendientes,
        "no_pago": no_pago,
        "fuera_plazo": fuera_plazo,
        "sin_boleta": sin_boleta,
        "total": total_kpi,
        "total_con_sin_boleta": total_kpi + sin_boleta,
        "fuera_medicion": fuera_medicion_rgu,
        "unidad": "RGU",
        "boletas_total": sum(boletas.values()),
        "boletas_fuera_medicion": fuera_medicion_boletas,
        "meta_pct": float(meta_pct),
        "pct_cumplimiento": float(pct_cumplimiento),
        "pct_proyectado": float(pct_proyectado),
        "cumplimiento_meta_pct": float(cumplimiento_meta),
        "faltan_para_meta": max(0, _faltan_para_meta(pagadas, total_kpi, meta_pct)),
        "gestion": {
            "pago": gestion.get("pago", 0),
            "vencido_mas_8": gestion.get("vencido_mas_8", 0),
            "vencido_0_8": gestion.get("vencido_0_8", 0),
            "gestionar_0_7": gestion.get("gestionar_0_7", 0),
            "gestionar_8_mas": gestion.get("gestionar_8_mas", 0),
            "otros": gestion.get("otros", 0),
        },
        "semaforo": semaforo,
    }


def _faltan_para_meta(pagadas: int, total_kpi: int, meta_pct: Decimal) -> int:
    """RGU adicionales que deben pasar a Pago para alcanzar la meta."""
    if total_kpi == 0 or meta_pct == 0:
        return 0
    objetivo = (meta_pct / 100) * total_kpi
    faltan = objetivo - pagadas
    if faltan <= 0:
        return 0
    # ROUND_HALF_UP puede subestimar 0.4; para una meta hay que llegar al
    # entero siguiente. Decimal.to_integral_value con ROUND_CEILING.
    from decimal import ROUND_CEILING
    return int(faltan.to_integral_value(rounding=ROUND_CEILING))


def _aplicar_meta_resumen(resumen: dict, meta_valor) -> dict:
    """Aplica una meta sin redondear el KPI antes de calcular cumplimiento."""
    if meta_valor is None:
        return resumen
    meta = Decimal(str(meta_valor))
    total = int(resumen.get("total", 0) or 0)
    pagadas = int(resumen.get("pagadas", 0) or 0)
    pct_exacto = (Decimal(pagadas) / Decimal(total) * 100) if total else Decimal("0")
    resumen["meta_pct"] = float(meta)
    resumen["cumplimiento_meta_pct"] = float(
        (pct_exacto / meta * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if meta else Decimal("0")
    )
    resumen["faltan_para_meta"] = max(0, _faltan_para_meta(pagadas, total, meta))
    if total == 0 or meta == 0:
        resumen["semaforo"] = "sin_datos"
    elif pct_exacto >= meta:
        resumen["semaforo"] = "verde"
    elif pct_exacto >= meta - 10:
        resumen["semaforo"] = "amarillo"
    else:
        resumen["semaforo"] = "rojo"
    return resumen



def aplicar_meta_resumen(resumen: dict, meta_valor) -> dict:
    """API pública para aplicar una meta ESACOM a un resumen KPI."""
    return _aplicar_meta_resumen(resumen, meta_valor)

def resumen_por_corte(cortes: QuerySet[Corte]) -> list[dict]:
    """
    Igual que resumen_kpi, pero desglosado por (mes_ano, boleta) --
    para pintar las 3 tarjetas del dashboard ('Junio B1 · Mayo B2 · Abril B3').
    """
    combinaciones = cortes.values_list("mes_ano", "boleta").distinct().order_by("-mes_ano", "boleta")
    resultado = []
    for mes_ano, boleta in combinaciones:
        subset = cortes.filter(mes_ano=mes_ano, boleta=boleta)
        r = resumen_kpi(subset)
        r["mes_ano"] = mes_ano
        r["boleta"] = boleta
        resultado.append(r)
    return resultado


def resumen_por_ejecutivo(cortes: QuerySet[Corte]) -> list[dict]:
    """
    Matriz Ejecutivo × Camada × Boleta usando el dueño definido por ESACOM.
    El RUT EVT resuelto en Venta.ejecutivo manda; Claro solo aporta KPI.
    """
    from collections import defaultdict

    cortes = cortes.select_related(
        "ejecutivo_kpi", "venta", "venta__ejecutivo", "venta__ejecutivo_ce", "venta__promocion"
    )
    ids_por_ejecutivo: dict[int, dict] = {}
    cortes_por_grupo: dict[tuple[int, str, str], list[int]] = defaultdict(list)

    for c in cortes:
        e = c.venta.ejecutivo
        if not e or getattr(c.venta, "conflicto_fuente", False):
            # Un pedido con propiedad ESACOM conflictiva puede formar parte
            # del total global de Claro, pero no se adjudica arbitrariamente
            # a un Ejecutivo.
            continue
        ids_por_ejecutivo[e.id] = {"id": e.id, "rut": e.rut, "nombre": e.nombre, "equipo": e.equipo}
        cortes_por_grupo[(e.id, c.mes_ano, c.boleta)].append(c.id)

    por_ejecutivo: dict[int, list] = defaultdict(list)
    for (eid, mes_ano, boleta), ids in cortes_por_grupo.items():
        r = resumen_kpi(Corte.objects.filter(id__in=ids))
        r["mes_ano"] = mes_ano
        r["boleta"] = boleta
        por_ejecutivo[eid].append(r)

    resultado = []
    for eid, info in ids_por_ejecutivo.items():
        cortes_ejecutivo = sorted(
            por_ejecutivo[eid], key=lambda r: (r["mes_ano"], r["boleta"]), reverse=True
        )
        resultado.append({"ejecutivo": info, "cortes": cortes_ejecutivo})

    resultado.sort(key=lambda r: r["ejecutivo"]["nombre"])
    return resultado



def resumen_por_ejecutivo_actual(
    cortes: QuerySet[Corte],
    focos: dict[str, str] | None = None,
    metas: dict[str, float | None] | None = None,
) -> list[dict]:
    """KPI vigente B1/B2/B3 por Ejecutivo usando la propiedad ESACOM.

    Esta función es la contraparte por vendedor de ``resumen_cortes_actuales``:
    usa exactamente los focos del snapshot KPI activo y el dueño de la venta
    resuelto por ``Venta.ejecutivo`` (RUT EVT ESACOM). De esta forma el KPI que
    ve un Supervisor para un vendedor coincide con el Portal Ejecutivo.
    """
    from collections import defaultdict

    focos = focos or {}
    metas = metas or {}
    cortes = cortes.select_related(
        "venta", "venta__ejecutivo", "venta__ejecutivo__supervisor", "venta__promocion", "ejecutivo_kpi"
    )

    ids_por_ejecutivo: dict[int, dict] = {}
    ids_por_foco: dict[tuple[int, str], list[int]] = defaultdict(list)

    for c in cortes:
        e = c.venta.ejecutivo
        if not e or getattr(c.venta, "conflicto_fuente", False):
            # Un pedido con propiedad ESACOM conflictiva puede formar parte
            # del total global de Claro, pero no se adjudica arbitrariamente
            # a un Ejecutivo.
            continue
        # Honorarios posee una medición distinta y no debe mezclarse con
        # B1/B2/B3 regular hasta que su fórmula oficial esté parametrizada.
        if getattr(e, "tipo_kpi", "REGULAR") == "HONORARIOS":
            continue
        # Solo el foco vigente de cada boleta entra al dashboard supervisor.
        foco_mes = focos.get(c.boleta)
        if foco_mes and c.mes_ano != foco_mes:
            continue
        if c.boleta not in ("B1", "B2", "B3"):
            continue
        ids_por_ejecutivo[e.id] = {
            "id": e.id,
            "rut": e.rut,
            "nombre": e.nombre,
            "equipo": e.equipo,
            "tipo_kpi": getattr(e, "tipo_kpi", "REGULAR"),
            "supervisor_id": e.supervisor_id,
            "supervisor_nombre": e.supervisor.nombre if e.supervisor_id else "",
        }
        ids_por_foco[(e.id, c.boleta)].append(c.id)

    resultado = []
    for eid, info in ids_por_ejecutivo.items():
        cortes_actuales = []
        for boleta in ("B1", "B2", "B3"):
            ids = ids_por_foco.get((eid, boleta), [])
            if not ids:
                continue
            subset = Corte.objects.filter(id__in=ids)
            r = resumen_kpi(subset)
            r["boleta"] = boleta
            r["mes_ano"] = focos.get(boleta, "")
            _aplicar_meta_resumen(r, metas.get(boleta))
            cortes_actuales.append(r)

        if cortes_actuales:
            # promedio simple de los tres focos disponibles: útil para ordenar
            # el riesgo sin ocultar los KPI individuales B1/B2/B3.
            promedio = sum(x["pct_cumplimiento"] for x in cortes_actuales) / len(cortes_actuales)
            resultado.append({
                "ejecutivo": info,
                "cortes": cortes_actuales,
                "promedio_focos": round(promedio, 1),
            })

    resultado.sort(key=lambda r: (r["promedio_focos"], r["ejecutivo"]["nombre"]))
    return resultado



def resumen_por_supervisor_actual(
    cortes: QuerySet[Corte],
    focos: dict[str, str] | None = None,
    metas: dict[str, float | None] | None = None,
) -> list[dict]:
    """KPI vigente agregado por Supervisor usando propiedad ESACOM por RUT EVT.

    Honorarios se mantienen fuera del KPI regular. Cada supervisor recibe los
    mismos B1/B2/B3 que el dashboard global y los portales de sus ejecutivos.
    """
    from collections import defaultdict

    focos = focos or {}
    metas = metas or {}
    cortes = cortes.select_related(
        "venta", "venta__ejecutivo", "venta__ejecutivo__supervisor", "venta__promocion"
    )

    info_supervisor: dict[int, dict] = {}
    ids_por_foco: dict[tuple[int, str], list[int]] = defaultdict(list)
    ejecutivos_por_supervisor: dict[int, set[int]] = defaultdict(set)

    for c in cortes:
        ejecutivo = c.venta.ejecutivo
        if (
            not ejecutivo
            or getattr(c.venta, "conflicto_fuente", False)
            or getattr(ejecutivo, "tipo_kpi", "REGULAR") == "HONORARIOS"
        ):
            continue
        supervisor = ejecutivo.supervisor
        if not supervisor:
            continue
        foco_mes = focos.get(c.boleta)
        if foco_mes and c.mes_ano != foco_mes:
            continue
        if c.boleta not in ("B1", "B2", "B3"):
            continue
        info_supervisor[supervisor.id] = {
            "id": supervisor.id,
            "rut": supervisor.rut,
            "nombre": supervisor.nombre,
            "equipo": supervisor.equipo or ejecutivo.equipo,
        }
        ejecutivos_por_supervisor[supervisor.id].add(ejecutivo.id)
        ids_por_foco[(supervisor.id, c.boleta)].append(c.id)

    resultado = []
    for sid, info in info_supervisor.items():
        cortes_actuales = []
        for boleta in ("B1", "B2", "B3"):
            ids = ids_por_foco.get((sid, boleta), [])
            if not ids:
                continue
            r = resumen_kpi(Corte.objects.filter(id__in=ids))
            r["boleta"] = boleta
            r["mes_ano"] = focos.get(boleta, "")
            _aplicar_meta_resumen(r, metas.get(boleta))
            cortes_actuales.append(r)

        if cortes_actuales:
            promedio = sum(c["pct_cumplimiento"] for c in cortes_actuales) / len(cortes_actuales)
            resultado.append({
                "supervisor": info,
                "ejecutivos": len(ejecutivos_por_supervisor[sid]),
                "cortes": cortes_actuales,
                "promedio_focos": round(promedio, 1),
                "q_para_meta_total": sum(c.get("faltan_para_meta", 0) for c in cortes_actuales),
            })

    resultado.sort(key=lambda r: (r["promedio_focos"], r["supervisor"]["nombre"]))
    return resultado

def filtrar_cortes_kpi_operativos(cortes: QuerySet[Corte]) -> QuerySet[Corte]:
    """Aplica la regla maestra ESACOM para el KPI operativo.

    Un corte de Claro puede existir históricamente aunque la venta ESACOM no
    esté instalada. Para Mi KPI y Accionables solo se consideran ventas que
    ESACOM marca actualmente como INSTALADO. Claro mide; ESACOM define el
    universo comercial operativo.

    Centralizar este filtro evita que comandos de validación, API y frontend
    terminen usando poblaciones distintas.
    """
    return cortes.filter(venta__estado_instalacion=Venta.EstadoInstalacion.INSTALADO)


def resumen_accionables(cortes: QuerySet[Corte], focos: dict[str, str] | None = None) -> dict:
    """
    Accionables del vendedor/equipo: agrupa cortes PENDIENTES y medibles en
    VENCIDOS, HOY, MAÑANA y PRÓXIMOS 3 DÍAS.

    Cuando se informan ``focos`` limita estrictamente los casos a los tres
    focos oficiales del snapshot KPI activo (B1/B2/B3). Así Mi Portal y
    Accionables trabajan sobre la misma población y el histórico antiguo no
    contamina la gestión diaria del vendedor.
    """
    from collections import defaultdict
    from django.utils import timezone

    hoy = timezone.localdate()
    buckets: dict[str, list[Corte]] = {
        "vencidos": [],
        "hoy": [],
        "manana": [],
        "prox_3d": [],
    }

    focos = focos or {}
    cortes = cortes.filter(
        estado_pago=Corte.EstadoPago.PENDIENTE,
        fecha_vencimiento__isnull=False,
        es_medible=True,
    ).exclude(venta__conflicto_fuente=True)

    # Si existe snapshot activo, solo son accionables los focos oficiales.
    foco_q = None
    for boleta in (Corte.Boleta.B1, Corte.Boleta.B2, Corte.Boleta.B3):
        mes = focos.get(boleta)
        if not mes:
            continue
        q = Q(boleta=boleta, mes_ano=mes)
        foco_q = q if foco_q is None else foco_q | q
    if foco_q is not None:
        cortes = cortes.filter(foco_q)

    cortes = cortes.select_related(
        "venta", "venta__promocion", "venta__ejecutivo", "venta__ejecutivo_ce", "ejecutivo_kpi"
    )

    for c in cortes:
        dias = (c.fecha_vencimiento - hoy).days
        if dias < 0:
            buckets["vencidos"].append(c)
        elif dias == 0:
            buckets["hoy"].append(c)
        elif dias == 1:
            buckets["manana"].append(c)
        elif 2 <= dias <= 3:
            buckets["prox_3d"].append(c)

    resultado = {}
    for clave, lista in buckets.items():
        camadas = defaultdict(lambda: {"rgu": 0, "clientes": set(), "casos": 0})
        items = []
        for c in sorted(lista, key=lambda x: (x.fecha_vencimiento, x.venta.n_pedido)):
            etiqueta = f"{c.mes_ano} · {c.get_boleta_display()}"
            rgu = _rgu_corte(c)
            camadas[etiqueta]["rgu"] += rgu
            camadas[etiqueta]["clientes"].add(c.venta.rut_cliente)
            camadas[etiqueta]["casos"] += 1
            propietario = c.venta.ejecutivo
            dias = (c.fecha_vencimiento - hoy).days
            if dias < 0:
                estado_vencimiento = f"Vencido hace {abs(dias)} día{'s' if abs(dias) != 1 else ''}"
            elif dias == 0:
                estado_vencimiento = "Vence hoy"
            elif dias == 1:
                estado_vencimiento = "Vence mañana"
            else:
                estado_vencimiento = f"Vence en {dias} días"
            items.append({
                "corte_id": c.id,
                "venta_id": c.venta_id,
                "pedido": c.venta.n_pedido,
                "rut_cliente": c.venta.rut_cliente,
                "nombre_cliente": c.venta.nombre_cliente,
                "telefono_cliente": c.venta.telefono_cliente,
                "camada": c.mes_ano,
                "boleta": c.boleta,
                "fecha_vencimiento": c.fecha_vencimiento.isoformat(),
                "dias_para_vencer": dias,
                "estado_vencimiento": estado_vencimiento,
                "rgu": rgu,
                "ejecutivo": propietario.nombre if propietario else "",
            })

        todos_los_clientes = set()
        for v in camadas.values():
            todos_los_clientes |= v["clientes"]

        resultado[clave] = {
            "rgu": sum(v["rgu"] for v in camadas.values()),
            "clientes": len(todos_los_clientes),
            "casos": len(items),
            "camadas": [
                {"nombre": nombre, "rgu": v["rgu"], "clientes": len(v["clientes"]), "casos": v["casos"]}
                for nombre, v in sorted(camadas.items())
            ],
            "items": items,
        }
    return resultado


def resumen_equipo(ventas: QuerySet[Venta]) -> dict:
    """
    Estadísticas de cabecera del Portal Supervisor
    ('37 Clientes · 57 RGU · 9 Ejecutivos · 23 Pte. Inst. · 5 Pte. Com.').
    """
    ventas = ventas.select_related("ejecutivo", "promocion")

    clientes = set()
    ejecutivos = set()
    rgu_total = 0
    pendiente_instalacion = 0
    pendiente_comercial = 0
    anulados = 0

    for v in ventas:
        clientes.add(v.rut_cliente)
        if v.ejecutivo_id:
            ejecutivos.add(v.ejecutivo_id)
        rgu_total += int(v.rgu_base if v.rgu_base is not None else v.promocion.rgu)
        if v.estado_instalacion == Venta.EstadoInstalacion.PENDIENTE_INSTALACION:
            pendiente_instalacion += 1
        elif v.estado_instalacion == Venta.EstadoInstalacion.PENDIENTE_COMERCIAL:
            pendiente_comercial += 1
        elif v.estado_instalacion == Venta.EstadoInstalacion.ANULADO:
            anulados += 1

    return {
        "clientes": len(clientes),
        "rgu": rgu_total,
        "ejecutivos": len(ejecutivos),
        "pendiente_instalacion": pendiente_instalacion,
        "pendiente_comercial": pendiente_comercial,
        "anulados": anulados,
    }


def resumen_historico_camadas(ventas: QuerySet[Venta]) -> list[dict]:
    """
    Comparativo mes a mes -- 'este mes vs. el anterior, vs. el anterior' --
    para la pantalla 'Histórico'. Agrupa por camada de VENTA (mes en que
    se vendió, no el mes del corte de boleta) y trae, para cada mes:
    cuántas ventas entraron, cuántos RGU, y el desglose de estado de
    pago de todos sus Corte asociados.
    """
    from collections import defaultdict

    ventas = ventas.select_related("promocion").prefetch_related("cortes")
    por_camada = defaultdict(lambda: {
        "ventas": 0, "rgu": 0, "clientes": set(),
        "pagadas": 0, "pendientes": 0, "no_pago": 0, "fuera_plazo": 0, "sin_boleta": 0, "fuera_medicion": 0,
    })

    for v in ventas:
        d = por_camada[v.camada]
        d["ventas"] += 1
        d["rgu"] += int(v.rgu_base if v.rgu_base is not None else v.promocion.rgu)
        d["clientes"].add(v.rut_cliente)
        for c in v.cortes.all():
            rgu_corte = _rgu_corte(c)
            if not c.es_medible:
                d["fuera_medicion"] += rgu_corte
                continue
            if c.estado_pago == Corte.EstadoPago.PAGADO:
                d["pagadas"] += rgu_corte
            elif c.estado_pago == Corte.EstadoPago.PENDIENTE:
                d["pendientes"] += rgu_corte
            elif c.estado_pago == Corte.EstadoPago.NO_PAGO:
                d["no_pago"] += rgu_corte
            elif c.estado_pago == Corte.EstadoPago.FUERA_PLAZO:
                d["fuera_plazo"] += rgu_corte
            elif c.estado_pago == Corte.EstadoPago.SIN_BOLETA:
                d["sin_boleta"] += rgu_corte

    resultado = []
    for camada in sorted(por_camada.keys()):
        d = por_camada[camada]
        total_medible = d["pagadas"] + d["pendientes"] + d["no_pago"] + d["fuera_plazo"]
        pct = _pct(d["pagadas"], total_medible)
        resultado.append({
            "camada": camada,
            "ventas": d["ventas"],
            "rgu": d["rgu"],
            "clientes": len(d["clientes"]),
            "pagadas": d["pagadas"],
            "pendientes": d["pendientes"],
            "no_pago": d["no_pago"],
            "fuera_plazo": d["fuera_plazo"],
            "sin_boleta": d["sin_boleta"],
            "fuera_medicion": d["fuera_medicion"],
            "pct_cumplimiento": float(pct),
        })
    return resultado


def resumen_cortes_actuales(
    cortes: QuerySet[Corte],
    focos: dict[str, str] | None = None,
    metas: dict[str, Decimal | float | int | None] | None = None,
) -> list[dict]:
    """Devuelve siempre la ventana oficial B1/B2/B3 del snapshot activo.

    Cuando el snapshot declara una camada y el usuario no tiene registros para
    ese foco, se devuelve una tarjeta "sin datos" en vez de ocultar la
    boleta. Así la interfaz conserva siempre las tres boletas mensuales
    vigentes sin inventar datos ni hacer fallback a otra camada.
    """
    focos = focos or {}
    metas = metas or {}
    resultado = []
    for boleta in (Corte.Boleta.B1, Corte.Boleta.B2, Corte.Boleta.B3):
        base = cortes.filter(boleta=boleta)
        mes = focos.get(boleta)

        if not mes:
            if not base.exists():
                continue
            mes = (
                base.filter(es_medible=True)
                .order_by("-mes_ano")
                .values_list("mes_ano", flat=True)
                .first()
            )
            if mes is None:
                mes = base.order_by("-mes_ano").values_list("mes_ano", flat=True).first()
        if not mes:
            continue

        subset = base.filter(mes_ano=mes)
        r = resumen_kpi(subset)
        _aplicar_meta_resumen(r, metas.get(boleta))
        r["mes_ano"] = mes
        r["boleta"] = boleta
        r["tiene_datos"] = bool(r.get("total") or r.get("sin_boleta") or r.get("fuera_medicion"))
        resultado.append(r)
    return resultado

def resumen_honorarios(ventas: QuerySet[Venta]) -> dict:
    """Resumen operativo separado para vendedores a honorarios.

    No reutiliza las metas del KPI regular de Claro. Este resumen corresponde
    únicamente a la producción/registro ESACOM de Honorarios; el KPI de Calidad
    se calcula por separado desde los snapshots de Claro.
    """
    ventas = ventas.filter(origen_venta=Venta.OrigenVenta.HONORARIOS).select_related("promocion")
    total_ventas = 0
    total_rgu = 0
    pagadas_ventas = 0
    pagadas_rgu = 0
    pendientes_ventas = 0
    pendientes_rgu = 0
    por_camada: dict[str, dict] = {}

    for v in ventas:
        rgu = int(v.rgu_base if v.rgu_base is not None else (v.promocion.rgu or 1))
        total_ventas += 1
        total_rgu += rgu
        pagada = bool(v.fecha_pago_honorarios)
        if pagada:
            pagadas_ventas += 1
            pagadas_rgu += rgu
        else:
            pendientes_ventas += 1
            pendientes_rgu += rgu

        d = por_camada.setdefault(v.camada, {
            "camada": v.camada, "ventas": 0, "rgu": 0,
            "pagadas": 0, "pagadas_rgu": 0, "pendientes": 0, "pendientes_rgu": 0,
        })
        d["ventas"] += 1
        d["rgu"] += rgu
        if pagada:
            d["pagadas"] += 1
            d["pagadas_rgu"] += rgu
        else:
            d["pendientes"] += 1
            d["pendientes_rgu"] += rgu

    pct_referencial = _pct(pagadas_rgu, total_rgu)
    camadas = []
    for _, d in sorted(por_camada.items(), reverse=True):
        d["pct_pago_referencial"] = float(_pct(d["pagadas_rgu"], d["rgu"]))
        camadas.append(d)

    return {
        "tipo": "HONORARIOS",
        "regla_kpi_configurada": False,
        "mensaje": "Producción ESACOM Honorarios separada del KPI Regular. La meta de Calidad para Honorarios permanece pendiente de definición por Gerencia.",
        "total_ventas": total_ventas,
        "total_rgu": total_rgu,
        "ventas_con_pago": pagadas_ventas,
        "rgu_con_pago": pagadas_rgu,
        "ventas_sin_pago": pendientes_ventas,
        "rgu_sin_pago": pendientes_rgu,
        "pct_pago_referencial": float(pct_referencial),
        "camadas": camadas[:6],
    }


def resumen_kpi_honorarios_registros(registros) -> dict:
    """KPI de pago para Honorarios usando el universo real del snapshot Claro.

    Honorarios comparte la medición de *calidad de pago* (Pago / RGU del
    universo informado), pero NO hereda la meta ESACOM de vendedores Regular.
    Por eso el porcentaje se informa sin ``Cumple/No cumple`` ni ``Q para meta``.

    Para reproducir los cierres manuales de Honorarios, el denominador conserva
    todos los RGU del snapshot del vendedor, incluidos S/B y filas fuera de
    medición/#N-D. Ejemplo validado: Max Negri julio = 111 / 126 = 88,10%.
    """
    acumulado = {
        Corte.EstadoPago.PAGADO: 0,
        Corte.EstadoPago.PENDIENTE: 0,
        Corte.EstadoPago.NO_PAGO: 0,
        Corte.EstadoPago.FUERA_PLAZO: 0,
        Corte.EstadoPago.SIN_BOLETA: 0,
    }
    gestion = Counter()
    fuera_medicion = 0
    boletas_total = 0
    boletas_fuera_medicion = 0

    iterable = (
        registros.select_related("venta", "venta__promocion")
        if hasattr(registros, "select_related")
        else registros
    )
    for registro in iterable:
        rgu = registro.rgu
        if rgu is None and registro.venta_id:
            rgu = registro.venta.rgu_base
        if rgu is None and registro.venta_id:
            rgu = getattr(registro.venta.promocion, "rgu", None)
        rgu = int(rgu or 1)

        if not registro.es_medible:
            fuera_medicion += rgu
            boletas_fuera_medicion += 1
            continue

        estado = registro.estado_normalizado or Corte.EstadoPago.PENDIENTE
        acumulado[estado] = acumulado.get(estado, 0) + rgu
        boletas_total += 1
        gestion[_bucket_gestion(registro.rango_pago, estado)] += rgu

    pagadas = acumulado[Corte.EstadoPago.PAGADO]
    pendientes = acumulado[Corte.EstadoPago.PENDIENTE]
    no_pago = acumulado[Corte.EstadoPago.NO_PAGO]
    fuera_plazo = acumulado[Corte.EstadoPago.FUERA_PLAZO]
    sin_boleta = acumulado[Corte.EstadoPago.SIN_BOLETA]
    total_medible = pagadas + pendientes + no_pago + fuera_plazo
    total_universo = total_medible + sin_boleta + fuera_medicion
    pct = _pct_kpi(pagadas, total_universo) if total_universo else Decimal("0.00")

    return {
        "pagadas": pagadas,
        "pendientes": pendientes,
        "no_pago": no_pago,
        "fuera_plazo": fuera_plazo,
        "sin_boleta": sin_boleta,
        "fuera_medicion": fuera_medicion,
        "total": total_universo,
        "total_medible": total_medible,
        "total_con_sin_boleta": total_universo,
        "unidad": "RGU",
        "boletas_total": boletas_total,
        "boletas_fuera_medicion": boletas_fuera_medicion,
        "meta_pct": 0.0,
        "meta_definida": False,
        "pct_cumplimiento": float(pct),
        "pct_proyectado": None,
        "cumplimiento_meta_pct": None,
        "faltan_para_meta": None,
        "gestion": {
            "pago": gestion.get("pago", 0),
            "vencido_mas_8": gestion.get("vencido_mas_8", 0),
            "vencido_0_8": gestion.get("vencido_0_8", 0),
            "gestionar_0_7": gestion.get("gestionar_0_7", 0),
            "gestionar_8_mas": gestion.get("gestionar_8_mas", 0),
            "otros": gestion.get("otros", 0),
        },
        "semaforo": "informativo",
    }


def resumen_kpi_registros(registros, meta_pct=0) -> dict:
    """Resume un snapshot inmutable de KPIRegistro con la misma regla del KPI operativo.

    Se usa para comparar reportes semanales y cierres sin depender de ``Corte``,
    ya que ``Corte`` representa el último estado operativo y puede seguir
    actualizándose con cargas posteriores. ``KPIRegistro`` conserva cada carga.
    """
    acumulado = {
        Corte.EstadoPago.PAGADO: 0,
        Corte.EstadoPago.PENDIENTE: 0,
        Corte.EstadoPago.NO_PAGO: 0,
        Corte.EstadoPago.FUERA_PLAZO: 0,
        Corte.EstadoPago.SIN_BOLETA: 0,
    }
    gestion = Counter()
    fuera_medicion = 0
    boletas_total = 0
    boletas_fuera_medicion = 0

    iterable = (
        registros.select_related("venta", "venta__promocion")
        if hasattr(registros, "select_related")
        else registros
    )
    for registro in iterable:
        rgu = registro.rgu
        if rgu is None and registro.venta_id:
            rgu = registro.venta.rgu_base
        if rgu is None and registro.venta_id:
            rgu = getattr(registro.venta.promocion, "rgu", None)
        rgu = int(rgu or 1)
        if not registro.es_medible:
            fuera_medicion += rgu
            boletas_fuera_medicion += 1
            continue
        estado = registro.estado_normalizado or Corte.EstadoPago.PENDIENTE
        acumulado[estado] = acumulado.get(estado, 0) + rgu
        boletas_total += 1
        gestion[_bucket_gestion(registro.rango_pago, estado)] += rgu

    pagadas = acumulado[Corte.EstadoPago.PAGADO]
    pendientes = acumulado[Corte.EstadoPago.PENDIENTE]
    no_pago = acumulado[Corte.EstadoPago.NO_PAGO]
    fuera_plazo = acumulado[Corte.EstadoPago.FUERA_PLAZO]
    sin_boleta = acumulado[Corte.EstadoPago.SIN_BOLETA]
    total = pagadas + pendientes + no_pago + fuera_plazo
    pct_exacto = Decimal(pagadas) / Decimal(total) * 100 if total else Decimal("0")
    pct = _pct_kpi(pagadas, total)

    if total:
        tasa_actual = Decimal(pagadas) / Decimal(total)
        pago_proyectado = Decimal(pagadas) + (tasa_actual * Decimal(pendientes))
        pct_proyectado = _pct_kpi(pago_proyectado, total)
    else:
        pct_proyectado = Decimal("0.00")

    meta = Decimal(str(meta_pct or 0))
    cumplimiento = (
        (pct_exacto / meta * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if meta else Decimal("0")
    )
    if total == 0 or meta == 0:
        semaforo = "sin_datos"
    elif pct_exacto >= meta:
        semaforo = "verde"
    elif pct_exacto >= meta - 10:
        semaforo = "amarillo"
    else:
        semaforo = "rojo"

    return {
        "pagadas": pagadas,
        "pendientes": pendientes,
        "no_pago": no_pago,
        "fuera_plazo": fuera_plazo,
        "sin_boleta": sin_boleta,
        "total": total,
        "total_con_sin_boleta": total + sin_boleta,
        "fuera_medicion": fuera_medicion,
        "unidad": "RGU",
        "boletas_total": boletas_total,
        "boletas_fuera_medicion": boletas_fuera_medicion,
        "meta_pct": float(meta),
        "pct_cumplimiento": float(pct),
        "pct_proyectado": float(pct_proyectado),
        "cumplimiento_meta_pct": float(cumplimiento),
        "faltan_para_meta": max(0, _faltan_para_meta(pagadas, total, meta)),
        "gestion": {
            "pago": gestion.get("pago", 0),
            "vencido_mas_8": gestion.get("vencido_mas_8", 0),
            "vencido_0_8": gestion.get("vencido_0_8", 0),
            "gestionar_0_7": gestion.get("gestionar_0_7", 0),
            "gestionar_8_mas": gestion.get("gestionar_8_mas", 0),
            "otros": gestion.get("otros", 0),
        },
        "semaforo": semaforo,
    }

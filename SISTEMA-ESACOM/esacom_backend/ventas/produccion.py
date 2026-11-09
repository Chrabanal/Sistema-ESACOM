"""Producción operacional ESACOM (fija + móvil).

Esta capa es independiente del KPI Claro. Su objetivo es reproducir el
universo que Gerencia ve en los controles operacionales de las hojas vigentes.

Reglas de negocio:

* ``Base de Ventas``: la producción fija se mide en **RGU**, no en cantidad de
  filas. Solo ``Completada`` + ``Pendiente Instalación`` forman el total del
  control. Las filas siguen contabilizándose por separado para auditoría.
* ``Ventas Móvil``: la unidad es la línea/PCS. Una línea solo entra en
  producción efectiva cuando existe evidencia de activación/portabilidad. Las
  filas aún no efectivas permanecen en base como ``pendiente_activacion``.
* ESACOM es la fuente operacional. Ningún campo de Claro reasigna propiedad ni
  participa en este cálculo.

Los históricos permanecen en base, pero no participan en la producción
"actual" salvo que una consulta explícita los pida en otra capa.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict

from ventas.models import Venta, VentaFijaFuente, VentaMovil


def _norm(texto) -> str:
    texto = str(texto or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(texto.split())


def _estado_fijo_control(venta) -> str:
    """Clasificación compatible con la columna fuente de Base de Ventas."""
    fuente = _norm(venta.estado_instalacion_fuente)
    if fuente:
        if "COMPLETAD" in fuente or "INSTALAD" in fuente:
            return "COMPLETADA"
        if "PENDIENTE" in fuente and "INSTAL" in fuente:
            return "PENDIENTE_INSTALACION"
        if "PENDIENTE" in fuente and "COMERCIAL" in fuente:
            return "PENDIENTE_COMERCIAL"
        if "ANULAD" in fuente:
            return "ANULADA"
        if "DERIVADO" in fuente and "RED" in fuente:
            return "DERIVADO_REDES"
        return "OTRO"

    mapa = {
        Venta.EstadoInstalacion.INSTALADO: "COMPLETADA",
        Venta.EstadoInstalacion.PENDIENTE_INSTALACION: "PENDIENTE_INSTALACION",
        Venta.EstadoInstalacion.PENDIENTE_COMERCIAL: "PENDIENTE_COMERCIAL",
        Venta.EstadoInstalacion.ANULADO: "ANULADA",
    }
    estado_modelo = getattr(venta, "estado_instalacion", None)
    if not estado_modelo:
        venta_maestra = getattr(venta, "venta", None)
        estado_modelo = getattr(venta_maestra, "estado_instalacion", None)
    return mapa.get(estado_modelo, "OTRO")


def _rgu_fijo(venta) -> int:
    """RGU operacional informado por ESACOM.

    No se inventa un RGU desde Claro ni desde otra fuente. Si la hoja vigente
    no trae RGU, la venta queda trazada como ``ventas_sin_rgu`` y aporta cero
    hasta el siguiente sync/corrección de datos.
    """
    try:
        valor = int(venta.rgu_base or 0)
    except (TypeError, ValueError):
        return 0
    return max(valor, 0)


def _nombre_supervisor_fijo(venta) -> str:
    if venta.supervisor_fuente:
        return venta.supervisor_fuente.strip()
    if venta.ejecutivo and venta.ejecutivo.supervisor:
        return venta.ejecutivo.supervisor.nombre
    return "SIN SUPERVISOR"


def _nombre_supervisor_movil(venta: VentaMovil) -> str:
    if venta.supervisor_fuente:
        return venta.supervisor_fuente.strip()
    if venta.ejecutivo and venta.ejecutivo.supervisor:
        return venta.ejecutivo.supervisor.nombre
    return "SIN SUPERVISOR"


def _nombre_ejecutivo_fijo(venta) -> str:
    return (venta.nombre_evt or (venta.ejecutivo.nombre if venta.ejecutivo else "") or "SIN EJECUTIVO").strip()


def _nombre_ejecutivo_movil(venta: VentaMovil) -> str:
    return (venta.nombre_evt or (venta.ejecutivo.nombre if venta.ejecutivo else "") or "SIN EJECUTIVO").strip()


def _supervisor_fuente_coincide(valor_fuente: str, supervisor) -> bool:
    """Indica si la etiqueta SUPERVISOR de ESACOM corresponde al usuario CRM.

    La fuente suele abreviar el nombre (por ejemplo ``Charly Estay`` frente a
    ``CHARLY FABIAN ESTAY LAZO``). Para el control operativo la propiedad la
    define la hoja vigente, por lo que aceptamos cuando todos los tokens de la
    etiqueta fuente están contenidos en el nombre del Supervisor CRM.
    """
    fuente = set(_norm(valor_fuente).split())
    nombre = set(_norm(getattr(supervisor, "nombre", "")).split())
    return bool(fuente and nombre and (fuente.issubset(nombre) or nombre.issubset(fuente)))


def _filtrar_equipo_por_supervisor_fuente(qs, supervisor):
    """Aplica al control operativo el agrupamiento de SUPERVISOR de ESACOM.

    No depende de ``ejecutivo__is_active``: si la matriz vigente conserva una
    fila bajo el Supervisor, esa fila debe seguir visible en el control diario.
    La producción propia del Supervisor se excluye aquí porque el portal la
    consulta por separado con ``ejecutivo=supervisor``.
    """
    etiquetas = [
        valor
        for valor in qs.exclude(supervisor_fuente__isnull=True)
        .exclude(supervisor_fuente="")
        .values_list("supervisor_fuente", flat=True)
        .distinct()
        if _supervisor_fuente_coincide(valor, supervisor)
    ]
    if etiquetas:
        return qs.filter(supervisor_fuente__in=etiquetas).exclude(ejecutivo=supervisor)

    # Compatibilidad para bases antiguas todavía sin supervisor_fuente.
    return qs.filter(ejecutivo__supervisor=supervisor).exclude(ejecutivo=supervisor)


def _bucket_fijo():
    # Estas claves representan RGU; las cantidades de filas usan el prefijo ``ventas_``.
    return {
        "unidad": "RGU",
        "completadas": 0,
        "pendiente_instalacion": 0,
        "pendiente_comercial": 0,
        "anuladas": 0,
        "derivado_redes": 0,
        "otros": 0,
        "total_control": 0,
        "rgu_total_base_vigente": 0,
        "total_base_vigente": 0,  # cantidad de filas/ventas, se conserva por compatibilidad
        "ventas_completadas": 0,
        "ventas_pendiente_instalacion": 0,
        "ventas_pendiente_comercial": 0,
        "ventas_anuladas": 0,
        "ventas_derivado_redes": 0,
        "ventas_otros": 0,
        "total_control_ventas": 0,
        "ventas_sin_rgu": 0,
    }


def _bucket_movil():
    return {
        "unidad": "LINEAS",
        # Producción efectiva.
        "principal": 0,
        "adicional": 0,
        "ppm": 0,
        "otros": 0,
        "total": 0,
        "portadas": 0,  # Principal + Adicional; KPI Móvil solicitado por ESACOM.
        # Universo bruto y exclusiones auditables.
        "total_base_vigente": 0,
        "pendiente_activacion": 0,
        "pendiente_principal": 0,
        "pendiente_adicional": 0,
        "pendiente_ppm": 0,
        "pendiente_otros": 0,
        "pendiente_sin_evidencia": 0,
        "pendiente_estado_bloqueado": 0,
    }


def _sumar_fijo(bucket: dict, venta):
    bucket["total_base_vigente"] += 1
    rgu = _rgu_fijo(venta)
    bucket["rgu_total_base_vigente"] += rgu
    if rgu <= 0:
        bucket["ventas_sin_rgu"] += 1

    estado = _estado_fijo_control(venta)
    if estado == "COMPLETADA":
        bucket["ventas_completadas"] += 1
        bucket["completadas"] += rgu
        bucket["total_control"] += rgu
        bucket["total_control_ventas"] += 1
    elif estado == "PENDIENTE_INSTALACION":
        bucket["ventas_pendiente_instalacion"] += 1
        bucket["pendiente_instalacion"] += rgu
        bucket["total_control"] += rgu
        bucket["total_control_ventas"] += 1
    elif estado == "PENDIENTE_COMERCIAL":
        bucket["ventas_pendiente_comercial"] += 1
        bucket["pendiente_comercial"] += rgu
    elif estado == "ANULADA":
        bucket["ventas_anuladas"] += 1
        bucket["anuladas"] += rgu
    elif estado == "DERIVADO_REDES":
        bucket["ventas_derivado_redes"] += 1
        bucket["derivado_redes"] += rgu
    else:
        bucket["ventas_otros"] += 1
        bucket["otros"] += rgu


_ESTADOS_MOVIL_POSITIVOS = (
    "PORTADO",
    "ACTIVADO",
    "ACTIVADA",
    "ACTIVO",
    "ACTIVA",
    "COMPLETADO",
    "COMPLETADA",
)

_ESTADOS_MOVIL_BLOQUEADOS = (
    "ANULAD",
    "CANCEL",
    "RECHAZ",
    "NO PORTAD",
    "PENDIENT",
    "POR PORTAR",
    "MANDATO",
)


def clasificar_movil_produccion(venta: VentaMovil) -> tuple[bool, str]:
    """Determina si una línea móvil forma parte de producción efectiva.

    Se acepta como evidencia positiva una fecha de activación o un estado
    explícito de portabilidad/activación. Estados negativos/bloqueados tienen
    prioridad aunque exista información parcial. Si no hay evidencia, la fila
    permanece en la base pero se clasifica como pendiente de activación.
    """
    estado = _norm(venta.estado)

    if estado and any(token in estado for token in _ESTADOS_MOVIL_BLOQUEADOS):
        return False, "ESTADO_BLOQUEADO"

    if venta.fecha_activacion is not None:
        return True, "FECHA_ACTIVACION"

    if estado and any(token in estado for token in _ESTADOS_MOVIL_POSITIVOS):
        return True, "ESTADO_CONFIRMADO"

    return False, "SIN_EVIDENCIA_ACTIVACION"


def _sumar_tipo_movil(bucket: dict, venta: VentaMovil, *, prefijo: str = ""):
    if venta.tipo_linea == VentaMovil.TipoLinea.PRINCIPAL:
        bucket[f"{prefijo}principal"] += 1
    elif venta.tipo_linea == VentaMovil.TipoLinea.ADICIONAL:
        bucket[f"{prefijo}adicional"] += 1
    elif venta.tipo_linea == VentaMovil.TipoLinea.PPM:
        bucket[f"{prefijo}ppm"] += 1
    else:
        bucket[f"{prefijo}otros"] += 1


def _sumar_movil(bucket: dict, venta: VentaMovil):
    bucket["total_base_vigente"] += 1
    efectiva, motivo = clasificar_movil_produccion(venta)
    if efectiva:
        bucket["total"] += 1
        _sumar_tipo_movil(bucket, venta)
        if venta.tipo_linea in (VentaMovil.TipoLinea.PRINCIPAL, VentaMovil.TipoLinea.ADICIONAL):
            bucket["portadas"] += 1
        return

    bucket["pendiente_activacion"] += 1
    _sumar_tipo_movil(bucket, venta, prefijo="pendiente_")
    if motivo == "ESTADO_BLOQUEADO":
        bucket["pendiente_estado_bloqueado"] += 1
    else:
        bucket["pendiente_sin_evidencia"] += 1


def resumen_produccion_actual(*, ejecutivo=None, supervisor=None) -> dict:
    """Resumen operativo de las hojas ESACOM vigentes.

    Sin filtros devuelve el control global. ``ejecutivo`` limita a la producción
    propia de una persona y ``supervisor`` reproduce el equipo informado por
    ``SUPERVISOR`` en la fuente ESACOM vigente, incluso si un ejecutivo ya está
    inactivo en el login. La producción propia del Supervisor se consulta
    por separado pasando ``ejecutivo=supervisor`` para no mezclarla con su equipo.
    """
    # La producción fija se calcula desde la granularidad real de la hoja
    # ``Base de Ventas``. Un mismo N° PEDIDO puede ocupar más de una fila y
    # cada fila aporta su propio RGU/estado, exactamente como el pivot de
    # Gerencia. ``Venta`` continúa siendo el pedido maestro único para KPI.
    fijas_fuente = VentaFijaFuente.objects.filter(en_base_vigente=True)
    if fijas_fuente.exists():
        fijas = fijas_fuente.select_related("ejecutivo", "ejecutivo__supervisor")
    else:
        # Fallback si la BD migrada todavía no ha realizado el primer sync.
        fijas = Venta.objects.filter(
            origen_venta=Venta.OrigenVenta.BASE_VENTAS,
            en_base_vigente=True,
        ).select_related("ejecutivo", "ejecutivo__supervisor")

    moviles = VentaMovil.objects.filter(en_base_vigente=True).select_related("ejecutivo", "ejecutivo__supervisor")
    if ejecutivo is not None and supervisor is not None:
        raise ValueError("Use ejecutivo o supervisor, no ambos")
    if ejecutivo is not None:
        fijas = fijas.filter(ejecutivo=ejecutivo)
        moviles = moviles.filter(ejecutivo=ejecutivo)
    elif supervisor is not None:
        # El control operativo reproduce la propiedad informada en la fuente
        # ESACOM vigente, no la dotación activa del login. Esto evita perder
        # ventas vigentes de un ejecutivo que hoy figure inactivo. La producción
        # propia del Supervisor permanece separada y se consulta con
        # ``ejecutivo=supervisor``.
        fijas = _filtrar_equipo_por_supervisor_fuente(fijas, supervisor)
        moviles = _filtrar_equipo_por_supervisor_fuente(moviles, supervisor)

    fija = _bucket_fijo()
    for venta in fijas.iterator():
        _sumar_fijo(fija, venta)

    movil = _bucket_movil()
    for venta in moviles.iterator():
        _sumar_movil(movil, venta)

    return {
        "fuente": "ESACOM",
        "corte": "BASE_VIGENTE",
        "fija": fija,
        "movil": movil,
        # Claves explícitas para UI: no mezclar RGU Fijo con líneas Móvil en un
        # mismo número. ``total_produccion`` se conserva solo por compatibilidad.
        "rgu_fijo_control": fija["total_control"],
        "rgu_fijo_completados": fija["completadas"],
        "rgu_fijo_pendiente_instalacion": fija["pendiente_instalacion"],
        "rgu_fijo_pendiente_comercial": fija["pendiente_comercial"],
        "rgu_fijo_anulados": fija["anuladas"],
        "kpi_movil_portadas": movil["portadas"],
        "movil_principal": movil["principal"],
        "movil_adicional": movil["adicional"],
        "movil_pendiente_activacion": movil["pendiente_activacion"],
        "total_produccion": fija["total_control"] + movil["total"],
        "disponible": bool(fija["total_base_vigente"] or movil["total_base_vigente"]),
    }



def resumen_movil_vigente_por_supervisor() -> dict[str, dict]:
    """Distribución de portadas móviles efectivas según SUPERVISOR fuente.

    Reproduce el agrupamiento del control diario de Gerencia. Es importante
    usar ``supervisor_fuente`` porque una venta propia de un usuario con cargo
    SUPERVISOR no tiene ``ejecutivo.supervisor_id`` (ni debe tenerlo).
    """
    resultado = defaultdict(lambda: {"principal": 0, "adicional": 0, "total": 0})
    qs = VentaMovil.objects.filter(en_base_vigente=True).select_related(
        "ejecutivo", "ejecutivo__supervisor"
    )
    for venta in qs.iterator():
        efectiva, _ = clasificar_movil_produccion(venta)
        if not efectiva or venta.tipo_linea not in (
            VentaMovil.TipoLinea.PRINCIPAL,
            VentaMovil.TipoLinea.ADICIONAL,
        ):
            continue
        supervisor = _nombre_supervisor_movil(venta)
        if venta.tipo_linea == VentaMovil.TipoLinea.PRINCIPAL:
            resultado[supervisor]["principal"] += 1
        else:
            resultado[supervisor]["adicional"] += 1
        resultado[supervisor]["total"] += 1
    return dict(resultado)


def resumen_produccion_mes(*, mes: str, ejecutivo=None, supervisor=None, movil_vigente_actual: bool = False) -> dict:
    """Producción ESACOM para el período operativo solicitado.

    Fijo se mantiene estrictamente en la camada calendario ``mes``. Para Móvil
    existen dos lecturas explícitas:

    * ``movil_vigente_actual=False``: respeta la camada/fecha del mes pedido.
    * ``movil_vigente_actual=True``: usa toda la hoja móvil vigente y aplica la
      clasificación de línea efectiva (PORTADO/activado). Esta es la lectura
      operacional del control diario de Gerencia y puede incluir portadas
      vendidas a fines del mes anterior que siguen vigentes/efectivas hoy.

    ESACOM continúa siendo la única fuente operacional; Claro no participa en
    esta selección.
    """
    import re
    from django.db.models import Q

    if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", str(mes or "")):
        raise ValueError("mes debe usar formato YYYY-MM")
    anio, numero_mes = [int(x) for x in mes.split("-")]

    hay_fuente_fija = VentaFijaFuente.objects.filter(en_base_vigente=True).exists()
    if hay_fuente_fija:
        fijas = VentaFijaFuente.objects.filter(
            en_base_vigente=True,
            fecha_venta__year=anio,
            fecha_venta__month=numero_mes,
        ).select_related("ejecutivo", "ejecutivo__supervisor")
    else:
        fijas = Venta.objects.filter(
            origen_venta=Venta.OrigenVenta.BASE_VENTAS,
            en_base_vigente=True,
            camada=mes,
        ).select_related("ejecutivo", "ejecutivo__supervisor")

    moviles = VentaMovil.objects.filter(en_base_vigente=True)
    if not movil_vigente_actual:
        moviles = moviles.filter(
            Q(camada=mes)
            | Q(camada="", fecha_venta__year=anio, fecha_venta__month=numero_mes)
        )
    moviles = moviles.select_related("ejecutivo", "ejecutivo__supervisor")

    if ejecutivo is not None and supervisor is not None:
        raise ValueError("Use ejecutivo o supervisor, no ambos")
    if ejecutivo is not None:
        fijas = fijas.filter(ejecutivo=ejecutivo)
        moviles = moviles.filter(ejecutivo=ejecutivo)
    elif supervisor is not None:
        fijas = fijas.filter(ejecutivo__supervisor=supervisor, ejecutivo__is_active=True)
        moviles = moviles.filter(ejecutivo__supervisor=supervisor, ejecutivo__is_active=True)

    fija = _bucket_fijo()
    pedidos_fijo = set()
    for venta in fijas.iterator():
        _sumar_fijo(fija, venta)
        pedido = str(getattr(venta, "n_pedido", "") or "").strip()
        if pedido:
            pedidos_fijo.add(pedido)

    # La hoja Honorarios es también fuente ESACOM y puede contener ventas que
    # no existen en ``VentaFijaFuente`` (Base de Ventas). Se incorporan al mes
    # solicitado sin duplicar pedidos ya presentes en la fuente fija principal.
    honorarios = Venta.objects.filter(
        origen_venta=Venta.OrigenVenta.HONORARIOS,
        camada=mes,
    ).select_related("ejecutivo", "ejecutivo__supervisor", "promocion")
    if ejecutivo is not None:
        honorarios = honorarios.filter(ejecutivo=ejecutivo)
    elif supervisor is not None:
        honorarios = honorarios.filter(ejecutivo__supervisor=supervisor, ejecutivo__is_active=True)
    for venta in honorarios.iterator():
        pedido = str(getattr(venta, "n_pedido", "") or "").strip()
        if pedido and pedido in pedidos_fijo:
            continue
        _sumar_fijo(fija, venta)
        if pedido:
            pedidos_fijo.add(pedido)

    movil = _bucket_movil()
    for venta in moviles.distinct().iterator():
        _sumar_movil(movil, venta)

    # Para el KPI comercial Fijo del mes, ESACOM es la fuente oficial de la
    # cantidad vendida: se muestran TODOS los RGU presentes en la Base de
    # Ventas vigente del período, incluso si después quedaron anulados. El
    # antiguo ``total_control`` se conserva como indicador operacional
    # secundario (RGU gestionables = completados + pendiente instalación).
    rgu_vendidos = fija["rgu_total_base_vigente"]
    rgu_gestionables = fija["total_control"]

    return {
        "fuente": "ESACOM",
        "corte": "MES",
        "mes": mes,
        "fija": fija,
        "movil": movil,
        # KPI Ventas Fijo: RGU vendidos según la fuente oficial ESACOM.
        "kpi_fijo_rgu": rgu_vendidos,
        "rgu_fijo_vendidos": rgu_vendidos,
        "rgu_fijo_gestionables": rgu_gestionables,
        "ventas_fijo": len(pedidos_fijo) if pedidos_fijo else fija["total_base_vigente"],
        "filas_fijo_fuente": fija["total_base_vigente"],
        "rgu_fijo_anulados": fija["anuladas"],
        "rgu_fijo_completados": fija["completadas"],
        "rgu_fijo_pendiente_instalacion": fija["pendiente_instalacion"],
        "kpi_movil_portadas": movil["portadas"],
        "movil_modo": "BASE_VIGENTE_EFECTIVA" if movil_vigente_actual else "MES",
        "movil_vigente_actual": bool(movil_vigente_actual),
        "total_produccion": rgu_vendidos + movil["portadas"],
        "disponible": bool(fija["total_base_vigente"] or movil["total_base_vigente"]),
    }

def detalle_produccion_actual() -> dict:
    """Consolidado global, por supervisor y por ejecutivo para auditoría."""
    global_fija = _bucket_fijo()
    global_movil = _bucket_movil()
    supervisores = defaultdict(lambda: {"fija": _bucket_fijo(), "movil": _bucket_movil()})
    ejecutivos = defaultdict(lambda: {"fija": _bucket_fijo(), "movil": _bucket_movil()})
    # Conserva la misma jerarquía que usa la tabla dinámica manual de Gerencia:
    # SUPERVISOR fuente -> NOMBRE EVT fuente. Esto es importante porque un mismo
    # ejecutivo puede aparecer bajo supervisores distintos dentro del corte.
    ejecutivos_por_supervisor = defaultdict(
        lambda: defaultdict(lambda: {"fija": _bucket_fijo(), "movil": _bucket_movil()})
    )

    fijas_fuente = VentaFijaFuente.objects.filter(en_base_vigente=True)
    if fijas_fuente.exists():
        fijas = fijas_fuente.select_related("ejecutivo", "ejecutivo__supervisor")
    else:
        fijas = Venta.objects.filter(
            origen_venta=Venta.OrigenVenta.BASE_VENTAS,
            en_base_vigente=True,
        ).select_related("ejecutivo", "ejecutivo__supervisor")
    for venta in fijas.iterator():
        supervisor = _nombre_supervisor_fijo(venta)
        ejecutivo = _nombre_ejecutivo_fijo(venta)
        _sumar_fijo(global_fija, venta)
        _sumar_fijo(supervisores[supervisor]["fija"], venta)
        _sumar_fijo(ejecutivos[ejecutivo]["fija"], venta)
        _sumar_fijo(ejecutivos_por_supervisor[supervisor][ejecutivo]["fija"], venta)

    moviles = VentaMovil.objects.filter(en_base_vigente=True).select_related("ejecutivo", "ejecutivo__supervisor")
    for venta in moviles.iterator():
        supervisor = _nombre_supervisor_movil(venta)
        ejecutivo = _nombre_ejecutivo_movil(venta)
        _sumar_movil(global_movil, venta)
        _sumar_movil(supervisores[supervisor]["movil"], venta)
        _sumar_movil(ejecutivos[ejecutivo]["movil"], venta)
        _sumar_movil(ejecutivos_por_supervisor[supervisor][ejecutivo]["movil"], venta)

    for grupo in (supervisores, ejecutivos):
        for datos in grupo.values():
            datos["total_produccion"] = datos["fija"]["total_control"] + datos["movil"]["total"]
    for ejecutivos_supervisor in ejecutivos_por_supervisor.values():
        for datos in ejecutivos_supervisor.values():
            datos["total_produccion"] = datos["fija"]["total_control"] + datos["movil"]["total"]

    return {
        "global": {
            "fija": global_fija,
            "movil": global_movil,
            "total_produccion": global_fija["total_control"] + global_movil["total"],
        },
        "supervisores": dict(supervisores),
        "ejecutivos": dict(ejecutivos),
        "ejecutivos_por_supervisor": {
            supervisor: dict(datos)
            for supervisor, datos in ejecutivos_por_supervisor.items()
        },
    }

from __future__ import annotations

import unicodedata
from collections import Counter, defaultdict

from django.db import transaction

from integraciones.models import KPIRegistro, KPICierreFijoFila
from ventas.models import Venta, VentaFijaFuente
from usuarios.models import Ejecutivo


def _normalizar(texto) -> str:
    txt = str(texto or "").strip().upper().replace("_", " ")
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode("ascii")
    return " ".join(txt.split())




def _tokens_nombre_persona(texto) -> set[str]:
    """Tokens estables para resolver alias de supervisor sin usar el equipo actual.

    ESACOM historico puede guardar etiquetas cortas como ``Charly Estay`` o
    ``Patricio Guerra`` mientras Usuarios conserva el nombre legal completo.
    La resolucion solo se usa para CANONIZAR esa etiqueta historica; nunca para
    reasignar directamente a un ejecutivo segun su supervisor actual.
    """
    stop = {"DE", "DEL", "LA", "LAS", "LOS", "Y"}
    return {t for t in _normalizar(texto).split() if t and t not in stop}


def _personas_para_alias():
    return list(
        Ejecutivo.objects.select_related("supervisor")
        .only("id", "nombre", "cargo", "supervisor_id", "supervisor__nombre")
        .order_by("id")
    )


def _buscar_persona_por_alias(nombre_fuente: str, personas) -> Ejecutivo | None:
    """Busca una persona de CRM que explique una etiqueta historica ESACOM.

    Se exige una coincidencia conservadora por tokens (minimo dos). Ejemplos:
    ``Charly Estay`` -> ``CHARLY FABIAN ESTAY LAZO``;
    ``Claudio Torres`` -> ``CLAUDIO ANTONIO TORRES ASTUDILLO``.
    Si hay empate real, no se adivina.
    """
    original = _normalizar(nombre_fuente)
    if not original:
        return None

    exactos = [p for p in personas if _normalizar(p.nombre) == original]
    if len(exactos) == 1:
        return exactos[0]

    tokens = _tokens_nombre_persona(nombre_fuente)
    if len(tokens) < 2:
        return None

    candidatos = []
    for persona in personas:
        pt = _tokens_nombre_persona(persona.nombre)
        if tokens.issubset(pt):
            candidatos.append((len(pt - tokens), len(pt), persona.id, persona))

    if not candidatos:
        return None
    candidatos.sort(key=lambda x: (x[0], x[1], x[2]))
    mejor = candidatos[0]
    # Si dos personas tienen exactamente el mismo nivel de coincidencia, no
    # hacemos una asignacion silenciosa.
    if len(candidatos) > 1 and candidatos[1][:2] == mejor[:2]:
        return None
    return mejor[3]


def _supervisor_historico_canonico(nombre_fuente: str, *, ejecutivo=None, personas=None) -> str:
    """Canoniza el supervisor historico sin reescribir la historia del equipo.

    Regla R2.8:
    1) manda la etiqueta de supervisor guardada en la venta ESACOM historica;
    2) si esa etiqueta corresponde a un SUPERVISOR CRM, se usa su nombre
       canonico completo;
    3) si la etiqueta corresponde a un EJECUTIVO/intermedio (caso historico
       ``Claudio Torres``), se sube a SU supervisor CRM;
    4) solo si la venta no trae supervisor se usa el supervisor del ejecutivo
       como respaldo.

    Esto evita el error R2.7 de mover retroactivamente a Claudia/Lorena por su
    relacion CRM actual, y a la vez permite consolidar una jefatura intermedia
    antigua bajo el supervisor real del cierre.
    """
    personas = personas if personas is not None else _personas_para_alias()
    fuente = str(nombre_fuente or "").strip()

    if fuente:
        persona = _buscar_persona_por_alias(fuente, personas)
        if persona is not None:
            if persona.cargo == Ejecutivo.Cargo.SUPERVISOR:
                return str(persona.nombre or fuente).strip()
            if persona.supervisor_id and getattr(persona, "supervisor", None):
                return str(persona.supervisor.nombre or fuente).strip()
        return fuente

    if ejecutivo is not None:
        sup = getattr(ejecutivo, "supervisor", None)
        if sup is not None:
            return str(getattr(sup, "nombre", "") or "").strip()
        fuente_ej = str(getattr(ejecutivo, "supervisor_fuente", "") or "").strip()
        if fuente_ej:
            return _supervisor_historico_canonico(fuente_ej, personas=personas)
    return ""


def categoria_estado_kpi(texto) -> str:
    txt = _normalizar(texto)
    mapa = {
        "PAGO": KPICierreFijoFila.Categoria.PAGO,
        "NO PAGO": KPICierreFijoFila.Categoria.NO_PAGO,
        "PENDIENTE": KPICierreFijoFila.Categoria.PENDIENTE,
        "S/B": KPICierreFijoFila.Categoria.SIN_BOLETA,
        "S B": KPICierreFijoFila.Categoria.SIN_BOLETA,
        "SIN BOLETA": KPICierreFijoFila.Categoria.SIN_BOLETA,
        "PAGADO FUERA DE PLAZO": KPICierreFijoFila.Categoria.FUERA_PLAZO,
        "FUERA DE PLAZO": KPICierreFijoFila.Categoria.FUERA_PLAZO,
    }
    return mapa.get(txt, KPICierreFijoFila.Categoria.N_D)


def _estado_completado_fuente(texto) -> bool:
    """Replica la población de la planilla de Gerencia desde ESACOM.

    El cierre manual usa el estado original de la Base de Ventas. No basta con
    que ``Venta.estado_instalacion`` haya quedado normalizado como INSTALADO:
    filas con estado fuente vacío pueden terminar normalizadas y agregar RGU
    que no pertenecían al cierre manual.
    """
    txt = _normalizar(texto)
    return txt.startswith("COMPLETADA")


def _partes_mes(camada: str) -> tuple[int, int]:
    try:
        y, m = str(camada).split("-", 1)
        year, month = int(y), int(m)
    except (TypeError, ValueError):
        raise ValueError(f"Camada inválida para cierre: {camada!r}")
    if not (1 <= month <= 12):
        raise ValueError(f"Mes inválido para cierre: {camada!r}")
    return year, month


def _estado_registro(registro: KPIRegistro | None) -> str:
    if registro is None:
        return "#N/D"
    original = str(registro.kpi_texto or "").strip()
    if original:
        return original
    fallback = {
        "PAGADO": "Pago",
        "NO_PAGO": "No Pago",
        "PENDIENTE": "Pendiente",
        "SIN_BOLETA": "S/B",
        "FUERA_PLAZO": "Pagado Fuera de Plazo",
    }
    return fallback.get(str(registro.estado_normalizado or ""), "#N/D")


def asegurar_snapshot_cierre_fijo(carga, boleta: str, camada: str, *, force: bool = False) -> int:
    """Congela la población usada por la planilla Gerencia para un CIERRE Fijo.

    Regla replicada del archivo manual ``Cierre KPI jul 2026``:
    - población: filas ESACOM cuyo estado fuente es ``Completada``
      (incluye variantes como ``Completada Scott``) y cuyo FECHA CIERRE cae
      en el mes evaluado;
    - RGU: RGU de la fila ESACOM (no RGU Claro);
    - estado KPI: texto original del CIERRE Claro unido por N° PEDIDO;
    - supervisor: Base de Ventas ESACOM/CRM al momento del cierre, nunca Claro;
    - sin cruce con Claro: #N/D;
    - no se filtra por usuario activo, rol actual, REGULAR/HONORARIOS ni
      ``es_medible``: es una auditoría paralela a KPI CRM.

    Una vez creado, no se recalcula automáticamente: futuras sincronizaciones
    ESACOM no pueden alterar un cierre histórico.
    """
    fuente_version = "VENTA_FIJA_FUENTE_R28"
    historica_version = "VENTA_HIST_COMPLETADA_R28"
    qs_existente = KPICierreFijoFila.objects.filter(carga=carga, camada=camada, boleta=boleta)
    if qs_existente.exists() and not force:
        # Las revisiones previas fueron snapshots de prueba local. R2.8 corrige
        # exclusivamente la identidad historica del supervisor: la venta historica
        # manda y CRM solo canoniza aliases/jefaturas intermedias. Se regenera una vez
        # y luego vuelve a quedar congelado.
        fuentes = set(qs_existente.values_list("fuente_poblacion", flat=True).distinct())
        if fuentes and fuentes.issubset({fuente_version, historica_version}):
            return qs_existente.count()
        force = True

    year, month = _partes_mes(camada)
    registros = {
        str(r.num_pedido or "").strip(): r
        for r in KPIRegistro.objects.filter(carga=carga, camada=camada, boleta=boleta)
        .only("num_pedido", "kpi_texto", "estado_normalizado", "supervisor_fuente")
    }

    # La fila operacional aporta RGU y FECHA CIERRE. La R2.4 deduplica por
    # N° PEDIDO porque el cierre manual historico contiene una sola fila por
    # pedido, aunque la base operacional vigente pueda conservar reingresos.
    lineas = list(
        VentaFijaFuente.objects.filter(
            en_base_vigente=True,
            venta__fecha_cierre__year=year,
            venta__fecha_cierre__month=month,
        )
        .select_related("ejecutivo", "venta")
        .order_by("fila_fuente")
    )

    fuente = fuente_version
    filas_snapshot = []
    personas_alias = _personas_para_alias()

    # El archivo manual de cierre contiene un pedido una sola vez. La fuente
    # operacional vigente puede conservar filas duplicadas del mismo pedido
    # (por ejemplo, por reingresos o cambios posteriores al cierre). Para un
    # histórico oficial se conserva una sola fila canónica por N° PEDIDO.
    lineas_unicas = []
    por_pedido = {}
    for linea in lineas:
        if not _estado_completado_fuente(linea.estado_instalacion_fuente):
            continue
        pedido = str(linea.n_pedido or "").strip()
        if pedido:
            if pedido in por_pedido:
                continue
            por_pedido[pedido] = linea
        lineas_unicas.append(linea)

    for linea in lineas_unicas:
        pedido = str(linea.n_pedido or "").strip()
        reg = registros.get(pedido)
        estado = _estado_registro(reg)
        # El supervisor de la planilla Gerencia proviene de ESACOM, no de
        # Claro. El reporte KPI puede traer SUPERDASH vacío/N-D o incluso una
        # jerarquía distinta. Por eso congelamos el supervisor de la Base de
        # Ventas vigente al momento de recibir el CIERRE y, si faltara, usamos
        # la relación CRM del Ejecutivo como respaldo.
        supervisor_cierre = _supervisor_historico_canonico(
            linea.supervisor_fuente,
            ejecutivo=getattr(linea, "ejecutivo", None),
            personas=personas_alias,
        )
        filas_snapshot.append(
            KPICierreFijoFila(
                carga=carga,
                camada=camada,
                boleta=boleta,
                fila_fuente=int(linea.fila_fuente),
                n_pedido=pedido,
                rut_evt=str(linea.rut_evt or "")[:20],
                nombre_evt=str(linea.nombre_evt or "")[:150],
                supervisor_fuente=supervisor_cierre[:150],
                tipo_kpi=str(getattr(linea.ejecutivo, "tipo_kpi", "") or "")[:20],
                rgu=int(linea.rgu_base or 0),
                estado_kpi=estado[:40],
                categoria=categoria_estado_kpi(estado),
                fuente_poblacion=fuente,
            )
        )

    # Reconstrucción histórica para cierres anteriores a VentaFijaFuente.
    # ``Venta`` conserva las hojas BVD/BDVentas mensuales importadas. La clave
    # es usar el ESTADO DE INSTALACION original de ESACOM (Completada*) y no
    # el estado normalizado INSTALADO: en Julio existía una fila con fuente
    # vacía que estaba normalizada como instalada y agregaba 1 RGU de más.
    if not filas_snapshot:
        fuente = historica_version
        ventas = list(
            Venta.objects.filter(
                fecha_cierre__year=year,
                fecha_cierre__month=month,
            )
            .select_related("ejecutivo", "ejecutivo__supervisor")
            .order_by("id")
        )

        # Una fila histórica por pedido normalizado. Los respaldos antiguos
        # pueden contener el mismo pedido con espacios o reingresos técnicos.
        ventas_unicas = []
        por_pedido_hist = {}
        for venta in ventas:
            if not _estado_completado_fuente(venta.estado_instalacion_fuente):
                continue
            pedido = str(venta.n_pedido or "").strip()
            if pedido:
                if pedido in por_pedido_hist:
                    # Preferir una fila proveniente de la hoja histórica real
                    # antes que una fila sin trazabilidad de hoja.
                    anterior = por_pedido_hist[pedido]
                    if (not str(anterior.hoja_fuente or "").strip()) and str(venta.hoja_fuente or "").strip():
                        ventas_unicas.remove(anterior)
                        por_pedido_hist[pedido] = venta
                        ventas_unicas.append(venta)
                    continue
                por_pedido_hist[pedido] = venta
            ventas_unicas.append(venta)

        for venta in ventas_unicas:
            pedido = str(venta.n_pedido or "").strip()
            reg = registros.get(pedido)
            estado = _estado_registro(reg)

            # Reconstruccion retroactiva: manda el supervisor grabado en la
            # venta historica. CRM se usa solo para canonizar el nombre o para
            # resolver una jefatura intermedia que no es un rol SUPERVISOR.
            # Nunca se reemplaza el supervisor historico por el supervisor
            # actual del Ejecutivo (eso fue el error de R2.7).
            ejecutivo = getattr(venta, "ejecutivo", None)
            supervisor_cierre = _supervisor_historico_canonico(
                venta.supervisor_fuente,
                ejecutivo=ejecutivo,
                personas=personas_alias,
            )

            filas_snapshot.append(
                KPICierreFijoFila(
                    carga=carga,
                    camada=camada,
                    boleta=boleta,
                    fila_fuente=int(venta.id),
                    n_pedido=pedido,
                    rut_evt=str(venta.rut_evt or "")[:20],
                    nombre_evt=str(venta.nombre_evt or "")[:150],
                    supervisor_fuente=supervisor_cierre[:150],
                    tipo_kpi=str(getattr(ejecutivo, "tipo_kpi", "") or "")[:20],
                    rgu=int(venta.rgu_base or 0),
                    estado_kpi=estado[:40],
                    categoria=categoria_estado_kpi(estado),
                    fuente_poblacion=fuente,
                )
            )

    with transaction.atomic():
        if force:
            qs_existente.delete()
        elif KPICierreFijoFila.objects.filter(carga=carga, camada=camada, boleta=boleta).exists():
            return KPICierreFijoFila.objects.filter(carga=carga, camada=camada, boleta=boleta).count()
        KPICierreFijoFila.objects.bulk_create(filas_snapshot, batch_size=1000)

    return len(filas_snapshot)


def resumen_filas_cierre(filas) -> dict:
    acumulado = {
        "no_pago": 0,
        "fuera_plazo": 0,
        "pagadas": 0,
        "pendientes": 0,
        "sin_boleta": 0,
        "n_d": 0,
    }
    campo = {
        KPICierreFijoFila.Categoria.PAGO: "pagadas",
        KPICierreFijoFila.Categoria.NO_PAGO: "no_pago",
        KPICierreFijoFila.Categoria.FUERA_PLAZO: "fuera_plazo",
        KPICierreFijoFila.Categoria.PENDIENTE: "pendientes",
        KPICierreFijoFila.Categoria.SIN_BOLETA: "sin_boleta",
        KPICierreFijoFila.Categoria.N_D: "n_d",
    }
    for fila in filas:
        acumulado[campo.get(fila.categoria, "n_d")] += int(fila.rgu or 0)
    total = sum(acumulado.values())
    kpi = round(acumulado["pagadas"] / total * 100, 2) if total else 0.0
    return {**acumulado, "total_general": total, "kpi_pct": kpi}


def desglose_snapshot_cierre_fijo(carga, boleta: str, camada: str):
    asegurar_snapshot_cierre_fijo(carga, boleta, camada)
    filas = list(
        KPICierreFijoFila.objects.filter(carga=carga, camada=camada, boleta=boleta)
        .order_by("supervisor_fuente", "nombre_evt", "fila_fuente")
    )

    # Un Ejecutivo debe aparecer una sola vez en un cierre historico. Si una
    # fila sin cruce conserva un supervisor distinto al resto, no se parte la
    # persona entre equipos: se usa el supervisor historico dominante por RGU.
    por_ejecutivo = defaultdict(list)
    identidad = {}
    for fila in filas:
        rut = str(fila.rut_evt or "").strip()
        nombre = str(fila.nombre_evt or "Sin nombre").strip() or "Sin nombre"
        clave = (rut or _normalizar(nombre), nombre)
        por_ejecutivo[clave].append(fila)
        identidad[clave] = {"rut": rut, "nombre": nombre}

    por_supervisor = defaultdict(list)
    ejecutivos = []
    for clave, regs in por_ejecutivo.items():
        peso_supervisor = Counter()
        tipos = Counter()
        for fila in regs:
            sup = str(fila.supervisor_fuente or "").strip() or "Sin supervisor"
            peso_supervisor[sup] += max(int(fila.rgu or 0), 1)
            tipo = str(fila.tipo_kpi or "").strip()
            if tipo:
                tipos[tipo] += max(int(fila.rgu or 0), 1)
        supervisor = sorted(peso_supervisor.items(), key=lambda x: (-x[1], x[0]))[0][0]
        tipo_kpi = sorted(tipos.items(), key=lambda x: (-x[1], x[0]))[0][0] if tipos else ""
        por_supervisor[supervisor].extend(regs)
        item = dict(identidad[clave])
        item.update({
            "id": None,
            "supervisor": supervisor,
            "tipo_kpi": tipo_kpi,
            "planilla_cierre": resumen_filas_cierre(regs),
        })
        ejecutivos.append(item)

    ejecutivos.sort(key=lambda x: (x["supervisor"], x["nombre"]))
    supervisores = [
        {"id": None, "nombre": sup, "planilla_cierre": resumen_filas_cierre(regs)}
        for sup, regs in sorted(por_supervisor.items(), key=lambda x: x[0])
    ]

    return supervisores, ejecutivos, resumen_filas_cierre(filas), filas

"""
Motor de detección automática de apelaciones.

Regla del corte de plazo actualizada en la reunión del 14/08/26,
que reemplaza (para efectos de apelabilidad) la extensión NP8+2/+3
del documento 'Criterios de Apelación — KPI Calidad de Ventas'
(vigente jul-2026): esa extensión resultó no aplicar a este caso, o
quedó obsoleta -- el corte real es el día 8, sin extensión. Ver
`Corte.extension_np8` (deprecada) y `Corte.esta_muerto`.

Reglas implementadas (las que se pueden derivar con los datos que
tenemos hoy en Corte/Venta -- ver notas de alcance al final):

Regla A -- "Corrección de estado" (equivale al 'NP→F.Plazo' del mockup):
    Claro informa No Pago o Fuera de Plazo, pero el cliente SÍ pagó
    dentro de los 8 días del vencimiento -> apelable, se pide
    reclasificar a 'Pagado en Plazo'. Se verifica en Andes (manual o
    Pago Exprés) antes de enviar la apelación.
    Si el pago ocurrió DESPUÉS del día 8, la boleta queda "muerta":
    no se genera apelación, no hay corrección posible.

Regla B -- "Sin Boleta con boletas previas pagadas" (PDF, sección 3.2):
    Corte en estado SIN_BOLETA para la 2ª o 3ª boleta, con todas las
    boletas anteriores de esa misma venta en estado PAGADO. Es
    apelable como error de aprovisionamiento/facturación.

Fuera de alcance de esta primera versión (se necesita información que
hoy no capturamos, ej. notas de crédito, motivo de suspensión, SS de
regularización):
    - Apelaciones por acreditación de campaña (3.1)
    - Apelaciones por cliente suspendido/desconectado (3.3)
Esas dos quedan disponibles como carga MANUAL de una Apelacion desde
el Admin o la API, con motivo elegido a mano -- el motor no las genera
solo todavía.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.db.models import QuerySet

from .models import Apelacion, Corte

ORDEN_BOLETAS = ["B1", "B2", "B3"]


@dataclass
class ResultadoDeteccion:
    creadas: int = 0
    ya_existian: int = 0
    revisadas: int = 0


def detectar_apelaciones(cortes: QuerySet[Corte]) -> ResultadoDeteccion:
    """
    Recorre el queryset de Corte recibido (ya filtrado por rol/camada
    según corresponda) y crea Apelacion para los casos que cumplan la
    Regla A o la Regla B y que todavía no tengan una apelación asociada.
    """
    resultado = ResultadoDeteccion()
    cortes = cortes.select_related("venta").prefetch_related("venta__cortes")

    for corte in cortes:
        resultado.revisadas += 1
        if Apelacion.objects.filter(corte=corte).exists():
            resultado.ya_existian += 1
            continue

        deteccion = _regla_a_correccion_estado(corte) or _regla_b_sin_boleta(corte)
        if deteccion:
            motivo, observacion = deteccion
            Apelacion.objects.create(
                corte=corte,
                motivo=motivo,
                estado=Apelacion.Estado.DETECTADA,
                observacion=observacion,
            )
            resultado.creadas += 1

    return resultado


def _regla_a_correccion_estado(corte: Corte) -> tuple[str, str] | None:
    """
    Regla A -- 'corrección de estado' (confirmada en reunión 14/08/26,
    reemplaza la lógica NP8+2/+3 del documento de criterios que resultó
    obsoleta):

    Se compara `estado_claro` (lo que Claro reportó, tal cual, nunca se
    pisa) contra la evidencia real que maneja ESACOM. Dos formas de
    disparar la apelación, de mayor a menor certeza:

      1. Cobranza ya verificó el caso a mano en Andes/portal de pago y
         corrigió `estado_pago` a PAGADO -- máxima certeza, se apela sí o sí.
      2. Todavía nadie lo verificó a mano, pero `fecha_pago` (la que trae
         el propio reporte de Claro) cae dentro de los 8 días del
         vencimiento -- contradice el estado que Claro está informando.

    Si el pago (real o declarado) ocurrió DESPUÉS del día 8, la boleta
    queda "muerta": ya no es apelable bajo ninguna forma.
    """
    estado_referencia = corte.estado_claro or corte.estado_pago
    if estado_referencia not in (Corte.EstadoPago.NO_PAGO, Corte.EstadoPago.FUERA_PLAZO):
        return None

    # Caso 1: Cobranza ya lo verificó en Andes y dice que SÍ está pagado.
    if corte.verificado_en_andes and corte.estado_pago == Corte.EstadoPago.PAGADO:
        return (
            Apelacion.Motivo.ACREDITACION,
            f"Cobranza verificó en Andes/portal de pago el "
            f"{corte.fecha_verificacion_andes:%d/%m/%Y} que la boleta SÍ está pagada, "
            f"pero Claro la reporta como '{corte.get_estado_claro_display() if corte.estado_claro else estado_referencia}'. "
            f"Corresponde apelar para que corrijan el estado.",
        )

    # Caso 2: todavía sin verificar a mano, pero la fecha de pago que
    # trae el propio reporte de Claro contradice su estado declarado.
    if not corte.fecha_pago or not corte.fecha_vencimiento:
        return None

    dias_reales = (corte.fecha_pago - corte.fecha_vencimiento).days
    if dias_reales <= 8:
        return (
            Apelacion.Motivo.ACREDITACION,
            f"Estado informado por Claro como '{estado_referencia}', sin embargo su propio reporte "
            f"registra pago el {corte.fecha_pago:%d/%m/%Y}, dentro del plazo de 8 días "
            f"(límite {corte.limite_pago:%d/%m/%Y}). Verificar en Andes (manual o Pago Exprés) "
            f"antes de enviar la apelación.",
        )
    return None  # pagado después del día 8: no apelable, queda como No Pago.


def _regla_b_sin_boleta(corte: Corte) -> tuple[str, str] | None:
    if corte.estado_pago != Corte.EstadoPago.SIN_BOLETA:
        return None
    idx = ORDEN_BOLETAS.index(corte.boleta)
    if idx == 0:
        return None  # la 1ra boleta no tiene "previas" que exigir

    previas = [c for c in corte.venta.cortes.all() if c.mes_ano == corte.mes_ano and c.boleta in ORDEN_BOLETAS[:idx]]
    if len(previas) < idx:
        return None  # todavía no existen todas las boletas previas
    if not all(c.estado_pago == Corte.EstadoPago.PAGADO for c in previas):
        return None

    return (
        Apelacion.Motivo.APROVISIONAMIENTO,
        f"Cliente sin {corte.get_boleta_display()} generada (S/B), con las boletas previas "
        f"pagadas en plazo. Corresponde informar como S/B mientras se resuelve el error de "
        f"aprovisionamiento/facturación, según sección 3.2 de los criterios de apelación.",
    )

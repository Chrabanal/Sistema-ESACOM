import logging

from celery import shared_task
from django.utils import timezone

from .apelaciones import detectar_apelaciones
from .emails import enviar_apelaciones_por_correo
from .models import Apelacion, Corte

logger = logging.getLogger(__name__)


@shared_task
def detectar_apelaciones_task():
    """Corre el motor de detección sobre todos los Corte -- ver ventas/apelaciones.py."""
    resultado = detectar_apelaciones(Corte.objects.all())
    logger.info(
        "Detección automática: %s cortes revisados, %s apelaciones nuevas",
        resultado.revisadas, resultado.creadas,
    )
    return {"revisadas": resultado.revisadas, "creadas": resultado.creadas}


@shared_task
def enviar_apelaciones_pendientes_task():
    """
    Envía por correo, en un solo Excel, todas las apelaciones que
    siguen en estado DETECTADA (nadie las excluyó ni las envió a mano
    todavía) -- reemplaza el envío manual por correo que hace hoy el
    equipo, dos veces por semana, igual que el reporte de Claro.
    """
    pendientes = list(
        Apelacion.objects.filter(estado=Apelacion.Estado.DETECTADA)
        .select_related("corte", "corte__venta", "corte__venta__ejecutivo")
    )
    if not pendientes:
        logger.info("Envío automático de apelaciones: no había pendientes.")
        return {"enviadas": 0}

    enviar_apelaciones_por_correo(pendientes)

    ahora = timezone.now()
    ids = [a.id for a in pendientes]
    Apelacion.objects.filter(id__in=ids).update(estado=Apelacion.Estado.ENVIADA, fecha_envio=ahora)

    logger.info("Envío automático de apelaciones: %s apelación(es) enviada(s).", len(pendientes))
    return {"enviadas": len(pendientes)}

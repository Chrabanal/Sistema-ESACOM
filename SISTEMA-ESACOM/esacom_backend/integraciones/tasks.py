import logging

from celery import shared_task

from .locks import adquirir_lock_operacion_datos, liberar_lock_operacion_datos
from .services.google_sheets import sincronizar_base_matriz

logger = logging.getLogger(__name__)


@shared_task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def sincronizar_google_sheets_task():
    """Sincroniza ESACOM con un lock compartido con la carga KPI.

    Si Soporte está cargando KPI o ejecutando otra sincronización, Beat omite
    este ciclo en vez de competir por ventas/cortes y provocar un deadlock.
    """
    lock = adquirir_lock_operacion_datos()
    if lock is False:
        logger.warning("Sincronización Google Sheets omitida: otra operación de datos está activa")
        return {"estado": "omitida", "motivo": "operacion_datos_en_curso"}

    try:
        resultado = sincronizar_base_matriz()
        logger.info("Sincronización Google Sheets OK: %s", resultado)
        return resultado
    except Exception:
        logger.exception("Sincronización con Google Sheets falló")
        raise
    finally:
        liberar_lock_operacion_datos(lock)

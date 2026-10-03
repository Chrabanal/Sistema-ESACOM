import logging

from django.conf import settings

logger = logging.getLogger(__name__)

DATA_OPERATION_LOCK_KEY = "esacom:operacion_datos"
DATA_OPERATION_LOCK_SECONDS = 30 * 60


def adquirir_lock_operacion_datos():
    """Lock distribuido compartido por sync ESACOM y cargas KPI.

    En tests/eager no se requiere Redis. En producción evita que dos procesos
    escriban ventas/cortes al mismo tiempo y provoquen deadlocks PostgreSQL.
    Devuelve ``False`` si otra operación ya posee el lock.
    """
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return None

    import redis

    cliente = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    lock = cliente.lock(
        DATA_OPERATION_LOCK_KEY,
        timeout=DATA_OPERATION_LOCK_SECONDS,
        blocking=False,
        thread_local=False,
    )
    if not lock.acquire(blocking=False):
        return False
    return lock


def liberar_lock_operacion_datos(lock):
    if lock in (None, False):
        return
    try:
        lock.release()
    except Exception:
        logger.exception("No se pudo liberar el lock compartido de operaciones ESACOM/KPI")

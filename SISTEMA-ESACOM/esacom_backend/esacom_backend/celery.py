import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "esacom_backend.settings")

app = Celery("esacom_backend")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

# Cadencia real, tomada del correo de directrices ('el reporte se envía
# 2 veces a la semana: lunes/miércoles' para calidad, 'diario' para
# pendiente comercial). Se deja como valor por defecto editable vía
# settings -- no hace falta tocar este archivo para ajustar horarios.
app.conf.beat_schedule = {
    "sincronizar-google-sheets": {
        "task": "integraciones.tasks.sincronizar_google_sheets_task",
        "schedule": crontab(minute=f"*/{settings.GOOGLE_SHEETS_SYNC_MINUTES}"),  # configurable; por defecto cada 5 min
    },
    "enviar-apelaciones-pendientes": {
        "task": "ventas.tasks.enviar_apelaciones_pendientes_task",
        "schedule": crontab(hour=9, minute=0, day_of_week="mon,wed"),  # lunes y miércoles, como el reporte de Claro
    },
    "detectar-apelaciones-diario": {
        "task": "ventas.tasks.detectar_apelaciones_task",
        "schedule": crontab(hour=7, minute=30),  # antes del envío, todos los días
    },
}

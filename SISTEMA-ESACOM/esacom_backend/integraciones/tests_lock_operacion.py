from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from integraciones.locks import adquirir_lock_operacion_datos
from integraciones.tasks import sincronizar_google_sheets_task


class LockOperacionCompartidoTests(SimpleTestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_entorno_eager_no_requiere_redis(self):
        self.assertIsNone(adquirir_lock_operacion_datos())

    @patch("integraciones.tasks.sincronizar_base_matriz")
    @patch("integraciones.tasks.adquirir_lock_operacion_datos", return_value=False)
    def test_sync_beat_se_omite_si_otra_operacion_tiene_lock(self, _lock, sync):
        resultado = sincronizar_google_sheets_task.run()
        self.assertEqual(resultado["estado"], "omitida")
        self.assertEqual(resultado["motivo"], "operacion_datos_en_curso")
        sync.assert_not_called()

from django.test import SimpleTestCase

from integraciones.kpi_population import clave_poblacion, diferencias_poblacion


class KpiPopulationKeyTests(SimpleTestCase):
    def test_mismo_venta_id_es_misma_poblacion_aunque_texto_pedido_cambie(self):
        # La llave relacional no depende del texto NUM_PEDIDO.
        snapshot = {clave_poblacion(77, "2026-05", "B3")}
        corte = {clave_poblacion(77, "2026-05", "B3")}
        faltan, sobran = diferencias_poblacion(snapshot, corte)
        self.assertEqual(faltan, set())
        self.assertEqual(sobran, set())

    def test_detecta_venta_realmente_distinta(self):
        snapshot = {clave_poblacion(77, "2026-05", "B3")}
        corte = {clave_poblacion(88, "2026-05", "B3")}
        faltan, sobran = diferencias_poblacion(snapshot, corte)
        self.assertEqual(faltan, {(77, "2026-05", "B3")})
        self.assertEqual(sobran, {(88, "2026-05", "B3")})

import os
import tempfile

from django.test import SimpleTestCase
from openpyxl import Workbook

from integraciones.services.google_sheets import _hojas_desde_xlsx, _leer_valores_desde_xlsx


class GoogleSheetsDriveFallbackTests(SimpleTestCase):
    def _archivo(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        wb = Workbook()
        ws = wb.active
        ws.title = "Base de Ventas"
        ws.append(["SUPERVISOR", "NOMBRE EVT", "RGU", "ESTADO DE INSTALACION"])
        ws.append(["Charly Estay", "Ejecutivo Uno", 2, "Completada"])
        oculta = wb.create_sheet("Auxiliar Oculta")
        oculta.sheet_state = "hidden"
        oculta.append(["A", "B"])
        wb.save(tmp.name)
        return tmp.name

    def test_fallback_detecta_hojas_ocultas(self):
        path = self._archivo()
        try:
            hojas = _hojas_desde_xlsx(path)
            self.assertEqual(len(hojas), 2)
            self.assertFalse(hojas[0]["hidden"])
            self.assertTrue(hojas[1]["hidden"])
            self.assertEqual(hojas[0]["metadata_source"], "DRIVE_XLSX")
        finally:
            os.unlink(path)

    def test_fallback_lee_columnas_completas(self):
        path = self._archivo()
        try:
            rows = _leer_valores_desde_xlsx(path, "'Base de Ventas'!A:D")
            self.assertEqual(rows[0][2], "RGU")
            self.assertEqual(rows[1][2], 2)
            self.assertEqual(rows[1][3], "Completada")
        finally:
            os.unlink(path)

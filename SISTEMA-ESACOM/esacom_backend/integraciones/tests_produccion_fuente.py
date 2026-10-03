import os
import tempfile

from django.test import SimpleTestCase
from openpyxl import Workbook

from integraciones.services.produccion_fuente import calcular_produccion_desde_xlsx


class ProduccionFuenteAtomicaTests(SimpleTestCase):
    def _archivo(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        wb = Workbook()
        fija = wb.active
        fija.title = "Base de Ventas"
        fija.append(["SUPERVISOR", "NOMBRE EVT", "RGU", "ESTADO DE INSTALACION"])
        fija.append(["Charly Estay", "Ejecutivo A", 2, "Completada"])
        fija.append(["Charly Estay", "Ejecutivo A", 3, "Pendiente Instalación"])
        fija.append(["Charly Estay", "Ejecutivo A", 5, "Anulado"])

        movil = wb.create_sheet("Ventas Móvil")
        movil.append(["SUPERVISOR", "NOMBRE EVT", "PPAL/ADICI.", "FECHA ACTIVACIÓN", "ESTADO"])
        movil.append(["Charly Estay", "Ejecutivo A", "Principal", "2026-08-25", ""])
        movil.append(["Charly Estay", "Ejecutivo A", "Adicional", "", "ACTIVADO"])
        movil.append(["Charly Estay", "Ejecutivo A", "Adicional", "", "MANDATO"])
        wb.save(tmp.name)
        wb.close()
        return tmp.name

    def test_calcula_mismo_universo_operacional(self):
        path = self._archivo()
        try:
            r = calcular_produccion_desde_xlsx(path)
            self.assertEqual(r["global"]["fija"]["completadas"], 2)
            self.assertEqual(r["global"]["fija"]["pendiente_instalacion"], 3)
            self.assertEqual(r["global"]["fija"]["total_control"], 5)
            self.assertEqual(r["global"]["movil"]["principal"], 1)
            self.assertEqual(r["global"]["movil"]["adicional"], 1)
            self.assertEqual(r["global"]["movil"]["pendientes"], 1)
            self.assertEqual(r["global"]["movil"]["total"], 2)
            self.assertEqual(r["global"]["total_produccion"], 7)
        finally:
            os.unlink(path)

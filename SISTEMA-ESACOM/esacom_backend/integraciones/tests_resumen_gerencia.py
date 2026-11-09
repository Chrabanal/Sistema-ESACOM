import os
import tempfile

from django.test import SimpleTestCase
from openpyxl import Workbook

from integraciones.services.produccion_fuente import leer_resumen_gerencia_desde_xlsx


class ResumenGerenciaFuenteTests(SimpleTestCase):
    def test_lee_control_manual_resumen_por_rotulos(self):
        wb = Workbook()
        ws = wb.active
        ws.title = "Resumen"

        ws["A1"] = "*"
        ws["B1"] = "SUPERVISOR"
        ws["A2"] = "DIA FIN"
        for col, nombre in enumerate(
            ["Antonio Ochoa", "Charly Estay", "Enzo Morales", "Jorge Hernandez", "Patricio Guerra", "Suma total"],
            start=2,
        ):
            ws.cell(2, col, nombre)
        ws["A25"] = "Suma total"
        for col, valor in enumerate([25, 335, 22, 139, 63, 584], start=2):
            ws.cell(25, col, valor)

        ws["K1"] = "VENTAS FIJAS"
        ws["L1"] = "SUM de RGU"
        for row, (estado, total) in enumerate(
            [
                ("Anulado", 348),
                ("Completada", 584),
                ("Derivado Redes", 3),
                ("Pendiente Comercial", 23),
                ("Pendiente Instalación", 99),
                ("Suma total", 1057),
            ],
            start=3,
        ):
            ws.cell(row, 11, estado)
            ws.cell(row, 12, total)

        ws["K13"] = "COUNTA de SUPERVISOR"
        ws["L13"] = "Cruce Claro"
        ws["K14"] = "SUPERVISOR"
        ws["L14"] = "Suma total"
        for row, (supervisor, total) in enumerate(
            [
                ("Antonio Ochoa", 21),
                ("Charly Estay", 84),
                ("Enzo Morales", 7),
                ("Jorge Hernandez", 50),
                ("Patricio Guerra", 31),
                ("Suma total", 193),
            ],
            start=15,
        ):
            ws.cell(row, 11, supervisor)
            ws.cell(row, 12, total)

        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        try:
            wb.save(path)
            resultado = leer_resumen_gerencia_desde_xlsx(path)
        finally:
            os.remove(path)

        self.assertTrue(resultado["disponible"])
        self.assertEqual(resultado["ventas_fijas"]["total_rgu"], 1057)
        self.assertEqual(resultado["ventas_fijas"]["completada"], 584)
        self.assertEqual(resultado["ventas_fijas"]["pendiente_instalacion"], 99)
        self.assertEqual(resultado["ventas_fijas"]["pendiente_comercial"], 23)
        self.assertEqual(resultado["ventas_fijas"]["anulado"], 348)
        self.assertEqual(resultado["ventas_fijas"]["derivado_redes"], 3)
        self.assertEqual(resultado["completada_por_supervisor"]["Charly Estay"], 335)
        self.assertEqual(resultado["cruce_claro"]["total"], 193)

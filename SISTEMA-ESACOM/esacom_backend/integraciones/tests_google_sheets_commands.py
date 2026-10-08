from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class GoogleSheetsManagementCommandsTests(SimpleTestCase):

    @patch(
        "integraciones.management.commands.listar_hojas_esacom.obtener_metadata_spreadsheet"
    )
    @patch(
        "integraciones.management.commands.listar_hojas_esacom.obtener_hojas_spreadsheet"
    )
    def test_listar_hojas_oculta_pestanas_ocultas_por_defecto(
        self,
        mock_hojas,
        mock_metadata,
    ):
        mock_metadata.return_value = {
            "id": "sheet-123",
            "name": "Base ESACOM",
        }

        mock_hojas.return_value = [
            {
                "sheet_id": 1,
                "title": "Dotación",
                "index": 0,
                "hidden": False,
                "row_count": 90,
                "column_count": 10,
                "metadata_source": "SHEETS_API",
            },
            {
                "sheet_id": 2,
                "title": "Auxiliar Oculta",
                "index": 1,
                "hidden": True,
                "row_count": 10,
                "column_count": 5,
                "metadata_source": "SHEETS_API",
            },
        ]

        salida = StringIO()

        call_command(
            "listar_hojas_esacom",
            stdout=salida,
        )

        contenido = salida.getvalue()

        self.assertIn("Base ESACOM", contenido)
        self.assertIn("Dotación", contenido)
        self.assertNotIn("Auxiliar Oculta", contenido)

    @patch(
        "integraciones.management.commands.listar_hojas_esacom.obtener_metadata_spreadsheet"
    )
    @patch(
        "integraciones.management.commands.listar_hojas_esacom.obtener_hojas_spreadsheet"
    )
    def test_listar_hojas_muestra_ocultas_con_opcion_todas(
        self,
        mock_hojas,
        mock_metadata,
    ):
        mock_metadata.return_value = {
            "id": "sheet-123",
            "name": "Base ESACOM",
        }

        mock_hojas.return_value = [
            {
                "sheet_id": 1,
                "title": "Dotación",
                "index": 0,
                "hidden": False,
                "row_count": 90,
                "column_count": 10,
                "metadata_source": "SHEETS_API",
            },
            {
                "sheet_id": 2,
                "title": "Auxiliar Oculta",
                "index": 1,
                "hidden": True,
                "row_count": 10,
                "column_count": 5,
                "metadata_source": "SHEETS_API",
            },
        ]

        salida = StringIO()

        call_command(
            "listar_hojas_esacom",
            "--todas",
            stdout=salida,
        )

        contenido = salida.getvalue()

        self.assertIn("Dotación", contenido)
        self.assertIn("Auxiliar Oculta", contenido)
        self.assertIn("OCULTA", contenido)

    @patch(
        "integraciones.management.commands.inspeccionar_hoja_esacom.obtener_hoja_por_titulo"
    )
    @patch(
        "integraciones.management.commands.inspeccionar_hoja_esacom.leer_valores"
    )
    def test_inspeccionar_hoja_redacta_campos_sensibles(
        self,
        mock_leer_valores,
        mock_obtener_hoja,
    ):
        mock_obtener_hoja.return_value = {
            "sheet_id": 15,
            "title": "Dotación",
            "hidden": False,
            "row_count": 100,
            "column_count": 5,
        }

        mock_leer_valores.return_value = [
            ["RUT", "NOMBRE", "SUPERVISOR"],
            ["12345678-9", "Juan Perez", "Supervisor Uno"],
        ]

        salida = StringIO()

        call_command(
            "inspeccionar_hoja_esacom",
            "--hoja",
            "Dotación",
            "--filas",
            "1",
            stdout=salida,
        )

        contenido = salida.getvalue()

        self.assertIn("RUT [SENSIBLE]", contenido)
        self.assertIn("NOMBRE [SENSIBLE]", contenido)
        self.assertIn("12***-9", contenido)
        self.assertIn("Ju***ez", contenido)
        self.assertIn("Supervisor Uno", contenido)
        self.assertNotIn("12345678-9", contenido)
        self.assertNotIn("Juan Perez", contenido)

    @patch(
        "integraciones.management.commands.inspeccionar_hoja_esacom.obtener_hoja_por_titulo"
    )
    def test_inspeccionar_hoja_inexistente_lanza_error(
        self,
        mock_obtener_hoja,
    ):
        mock_obtener_hoja.return_value = None

        with self.assertRaises(CommandError):
            call_command(
                "inspeccionar_hoja_esacom",
                "--hoja",
                "No Existe",
            )
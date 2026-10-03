import datetime

from django.test import TestCase
from openpyxl import Workbook

from catalogos.models import Promocion
from integraciones.management.commands.importar_excel import Command
from usuarios.models import Ejecutivo
from ventas.models import Venta


class DuplicadosPedidoBaseVentasTests(TestCase):
    """La matriz puede repetir un pedido en más de una fila operacional."""

    def setUp(self):
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="11111111-1",
            nombre="EJECUTIVO PRUEBA",
            password="PruebaSegura2026!",
        )
        Promocion.objects.create(
            nombre="PROMO TEST",
            rgu=1,
            empresa=Promocion.Empresa.CLARO,
        )

    def _worksheet(self, estados=("Pendiente Instalación", "Pendiente Instalación"), rgus=(2, 1)):
        wb = Workbook()
        ws = wb.active
        ws.title = "Base de Ventas"
        ws.append([
            "N° PEDIDO", "RUT EVT", "NOMBRE EVT", "PROMOCION", "FECHA VENTA",
            "SUPERVISOR", "ESTADO DE INSTALACION", "RGU", "RUT CLIENTE",
        ])
        for estado, rgu in zip(estados, rgus):
            ws.append([
                "PED-DUP-1", "11111111-1", "EJECUTIVO PRUEBA", "PROMO TEST",
                datetime.date(2026, 8, 25), "Vicente Morales", estado, rgu, "22222222-2",
            ])
        return ws

    def test_dup_coherente_consolida_rgu_sin_romper_unicidad_de_pedido(self):
        resumen = Command()._importar_hoja_ventas(self._worksheet(), es_vigente=True)

        self.assertEqual(Venta.objects.count(), 1)
        venta = Venta.objects.get(n_pedido="PED-DUP-1")
        self.assertEqual(venta.rgu_base, 3)
        self.assertTrue(venta.en_base_vigente)
        self.assertEqual(venta.estado_instalacion_fuente, "Pendiente Instalación")
        self.assertEqual(resumen["filas_procesadas"], 2)
        self.assertEqual(resumen["pedidos_unicos"], 1)
        self.assertEqual(resumen["duplicados_consolidados"], 1)
        self.assertEqual(resumen["duplicados_conflictivos"], [])

    def test_dup_conflictivo_no_pierde_rgu_y_marca_pedido_maestro(self):
        ws = self._worksheet(estados=("Pendiente Instalación", "Completada"), rgus=(1, 1))
        resumen = Command()._importar_hoja_ventas(ws, es_vigente=True)

        self.assertEqual(Venta.objects.count(), 1)
        venta = Venta.objects.get(n_pedido="PED-DUP-1")
        self.assertEqual(venta.rgu_base, 2)
        self.assertTrue(venta.conflicto_fuente)
        self.assertEqual(venta.estado_instalacion_fuente, "CONFLICTO MULTILINEA")
        self.assertEqual(len(resumen["duplicados_conflictivos"]), 1)

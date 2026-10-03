from datetime import date

from django.test import TestCase

from catalogos.models import Promocion
from usuarios.models import Ejecutivo
from ventas.models import Venta, VentaFijaFuente
from ventas.produccion import resumen_produccion_actual, detalle_produccion_actual


class ProduccionFilaFuenteTests(TestCase):
    def setUp(self):
        self.ej = Ejecutivo.objects.create(
            rut="11111111-1", nombre="MAX PRUEBA", cargo=Ejecutivo.Cargo.EJECUTIVO
        )
        self.promo = Promocion.objects.create(
            nombre="PROMO TEST FILA", rgu=1, empresa=Promocion.Empresa.CLARO
        )
        self.venta = Venta.objects.create(
            n_pedido="PED-DUP", rut_cliente="1-9", nombre_cliente="Cliente",
            rut_evt=self.ej.rut, nombre_evt=self.ej.nombre, ejecutivo=self.ej,
            origen_venta=Venta.OrigenVenta.BASE_VENTAS, en_base_vigente=True,
            estado_instalacion=Venta.EstadoInstalacion.PENDIENTE_COMERCIAL,
            estado_instalacion_fuente="CONFLICTO MULTILINEA", rgu_base=3,
            promocion=self.promo, fecha_venta=date(2026, 8, 25), camada="2026-08",
        )

    def test_dos_filas_mismo_pedido_con_estados_distintos_se_suman_por_fila(self):
        VentaFijaFuente.objects.create(
            fila_fuente=720, n_pedido=self.venta.n_pedido, rut_evt=self.ej.rut,
            nombre_evt=self.ej.nombre, supervisor_fuente="Vicente Morales",
            estado_instalacion_fuente="Completada", rgu_base=1, ejecutivo=self.ej, venta=self.venta,
        )
        VentaFijaFuente.objects.create(
            fila_fuente=721, n_pedido=self.venta.n_pedido, rut_evt=self.ej.rut,
            nombre_evt=self.ej.nombre, supervisor_fuente="Vicente Morales",
            estado_instalacion_fuente="Pendiente Instalación", rgu_base=2, ejecutivo=self.ej, venta=self.venta,
        )
        r = resumen_produccion_actual()
        self.assertEqual(r["fija"]["completadas"], 1)
        self.assertEqual(r["fija"]["pendiente_instalacion"], 2)
        self.assertEqual(r["fija"]["total_control"], 3)
        self.assertEqual(r["fija"]["total_base_vigente"], 2)

    def test_detalle_conserva_supervisor_y_ejecutivo_de_cada_fila(self):
        VentaFijaFuente.objects.create(
            fila_fuente=720, n_pedido=self.venta.n_pedido, rut_evt=self.ej.rut,
            nombre_evt=self.ej.nombre, supervisor_fuente="Vicente Morales",
            estado_instalacion_fuente="Pendiente Instalación", rgu_base=1, ejecutivo=self.ej, venta=self.venta,
        )
        VentaFijaFuente.objects.create(
            fila_fuente=721, n_pedido=self.venta.n_pedido, rut_evt=self.ej.rut,
            nombre_evt=self.ej.nombre, supervisor_fuente="Charly Estay",
            estado_instalacion_fuente="Pendiente Instalación", rgu_base=2, ejecutivo=self.ej, venta=self.venta,
        )
        d = detalle_produccion_actual()
        self.assertEqual(d["supervisores"]["Vicente Morales"]["fija"]["pendiente_instalacion"], 1)
        self.assertEqual(d["supervisores"]["Charly Estay"]["fija"]["pendiente_instalacion"], 2)


class ImportacionFilaFuenteIntegracionTests(TestCase):
    """Prueba el flujo real Base de Ventas -> filas fuente -> pedido maestro."""

    def setUp(self):
        self.promo = Promocion.objects.create(
            nombre="PROMO FILA FUENTE", rgu=1, empresa=Promocion.Empresa.CLARO
        )

    def _workbook(self, *, rut="11111111-1"):
        import datetime
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Base de Ventas"
        ws.append([
            "RUT CLIENTE", "N° PEDIDO", "SUPERVISOR", "NOMBRE EVT", "RUT EVT",
            "PROMOCION", "RGU", "ESTADO DE INSTALACION", "FECHA VENTA",
        ])
        ws.append([
            "22222222-2", "PED-MULTI", "Vicente Morales", "MAX TEST", rut,
            self.promo.nombre, 1, "Completada", datetime.date(2026, 8, 25),
        ])
        ws.append([
            "22222222-2", "PED-MULTI", "Vicente Morales", "MAX TEST", rut,
            self.promo.nombre, 2, "Pendiente Instalación", datetime.date(2026, 8, 25),
        ])
        return wb

    def test_importacion_completa_preserva_dos_filas_y_un_pedido(self):
        from integraciones.management.commands.importar_excel import Command
        wb = self._workbook()
        try:
            resumen = Command()._importar_base_ventas(wb)
        finally:
            wb.close()

        self.assertEqual(Venta.objects.filter(n_pedido="PED-MULTI").count(), 1)
        venta = Venta.objects.get(n_pedido="PED-MULTI")
        self.assertEqual(venta.rgu_base, 3)
        self.assertTrue(venta.conflicto_fuente)
        self.assertEqual(VentaFijaFuente.objects.filter(n_pedido="PED-MULTI").count(), 2)
        self.assertEqual(VentaFijaFuente.objects.filter(n_pedido="PED-MULTI", venta=venta).count(), 2)

        prod = resumen_produccion_actual()
        self.assertEqual(prod["fija"]["completadas"], 1)
        self.assertEqual(prod["fija"]["pendiente_instalacion"], 2)
        self.assertEqual(prod["fija"]["total_control"], 3)
        self.assertEqual(resumen["lineas_fuente_vigente"]["pedidos_duplicados"], 1)

    def test_reimportar_mismo_xlsx_es_idempotente(self):
        from integraciones.management.commands.importar_excel import Command
        for _ in range(2):
            wb = self._workbook()
            try:
                Command()._importar_base_ventas(wb)
            finally:
                wb.close()

        venta = Venta.objects.get(n_pedido="PED-MULTI")
        self.assertEqual(venta.rgu_base, 3)
        self.assertEqual(VentaFijaFuente.objects.filter(n_pedido="PED-MULTI").count(), 2)
        prod = resumen_produccion_actual()
        self.assertEqual(prod["fija"]["total_control"], 3)

    def test_ejecutivo_creado_durante_import_queda_vinculado_a_fila_fuente(self):
        from integraciones.management.commands.importar_excel import Command
        wb = self._workbook(rut="33333333-3")
        try:
            Command()._importar_base_ventas(wb)
        finally:
            wb.close()

        ejecutivo = Ejecutivo.objects.get(rut="33333333-3")
        self.assertEqual(
            VentaFijaFuente.objects.filter(n_pedido="PED-MULTI", ejecutivo=ejecutivo).count(), 2
        )
        prod = resumen_produccion_actual(ejecutivo=ejecutivo)
        self.assertEqual(prod["fija"]["total_control"], 3)

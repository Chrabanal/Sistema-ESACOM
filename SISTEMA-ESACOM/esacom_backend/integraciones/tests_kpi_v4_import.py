import datetime
import os
import tempfile

import openpyxl
from django.test import TestCase

from catalogos.models import Promocion
from integraciones.management.commands.importar_kpi import Command as ImportarKpiCommand
from integraciones.models import CargaExcel, KPIRegistro
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta
from ventas.services import resumen_kpi


class ImportadorMarcaMesKpiV4Tests(TestCase):
    """La bandera oficial ``Marca de mes`` debe sobrevivir al import y mandar
    sobre la inclusión del snapshot. Este caso reproduce el patrón observado
    en KPI24082026: filas S/B sin fecha pueden venir con Marca de mes = 0.
    """

    def setUp(self):
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="11111111-1", password="test12345", nombre="Ejecutivo Marca KPI"
        )
        self.promo = Promocion.objects.create(
            nombre="Promo Marca KPI", rgu=1, empresa=Promocion.Empresa.CLARO
        )
        self.venta_pago = self._venta("KPI-MARCA-1", "12345678-5")
        self.venta_fuera = self._venta("KPI-MARCA-2", "87654321-4")

    def _venta(self, pedido, rut_cliente):
        return Venta.objects.create(
            rut_cliente=rut_cliente,
            n_pedido=pedido,
            rut_evt=self.ejecutivo.rut,
            nombre_evt=self.ejecutivo.nombre,
            ejecutivo=self.ejecutivo,
            promocion=self.promo,
            fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07",
            rgu_base=99,  # deliberadamente distinto del RGU KPI
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )

    def _xlsx(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "BASE"
        ws.append([
            "NUM_PEDIDO", "CAMADA", "N_BOLETA", "kpi", "RGU", "Marca de mes",
            "RUT", "PROPIETARIO_FINAL", "RUT_PROPIETARIO_FINAL", "SUPERVISOR",
            "INGRESADOR", "COMUNA", "FECHA_VENCIMIENTO", "FECHA_EFECTIVA_PAGO",
            "DiasPago", "RangoPago", "apelacion", "BILL_NO", "MONTO_BOLETA", "MONTO_PAGO",
        ])
        ws.append([
            self.venta_pago.n_pedido, 202607, 1, "Pago", 10, 1,
            self.venta_pago.rut_cliente, "", "", "SUP", "", "", None, None,
            None, "Pago", 0, "B1", 1000, 1000,
        ])
        # Sin FECHA_VENCIMIENTO: la regla local antigua la consideraba medible.
        # El XLSX oficial la excluye mediante Marca de mes = 0.
        ws.append([
            self.venta_fuera.n_pedido, 202607, 1, "S/B", 3, 0,
            self.venta_fuera.rut_cliente, "", "", "SUP", "", "", None, None,
            None, "", 0, "", None, None,
        ])
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        wb.save(tmp.name)
        wb.close()
        return tmp.name

    def test_marca_mes_cero_queda_fuera_y_se_audita(self):
        path = self._xlsx()
        try:
            carga = CargaExcel.objects.create(
                origen=CargaExcel.Origen.MANUAL,
                tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
                archivo_nombre="marca-mes.xlsx",
                fecha_corte=datetime.date(2026, 8, 24),
                dia_reporte=CargaExcel.DiaReporte.LUNES,
                foco_b1="2026-07",
                meta_b1=85,
            )
            cmd = ImportarKpiCommand()
            cmd.handle(
                archivo=path,
                dry_run=False,
                limite=None,
                hoja="BASE",
                carga_id=carga.id,
                usuario_rut="",
                archivo_nombre="marca-mes.xlsx",
                fecha_corte="2026-08-24",
                dia_reporte="LUNES",
            )

            pago = KPIRegistro.objects.get(carga=carga, num_pedido=self.venta_pago.n_pedido)
            fuera = KPIRegistro.objects.get(carga=carga, num_pedido=self.venta_fuera.n_pedido)
            self.assertEqual(pago.marca_mes_kpi, 1)
            self.assertTrue(pago.es_medible)
            self.assertEqual(fuera.marca_mes_kpi, 0)
            self.assertFalse(fuera.es_medible)
            self.assertEqual(fuera.estado_calculado, Corte.EstadoCalculado.FUERA_MEDICION)

            corte_pago = Corte.objects.get(venta=self.venta_pago, mes_ano="2026-07", boleta="B1")
            corte_fuera = Corte.objects.get(venta=self.venta_fuera, mes_ano="2026-07", boleta="B1")
            self.assertEqual(corte_pago.marca_mes_kpi, 1)
            self.assertEqual(corte_fuera.marca_mes_kpi, 0)
            self.assertEqual(corte_pago.carga_kpi_id, carga.id)
            self.assertEqual(corte_fuera.carga_kpi_id, carga.id)
            self.assertFalse(corte_fuera.es_medible)

            resumen = resumen_kpi(Corte.objects.filter(mes_ano="2026-07", boleta="B1"))
            self.assertEqual(resumen["pagadas"], 10)
            self.assertEqual(resumen["sin_boleta"], 0)
            self.assertEqual(resumen["fuera_medicion"], 3)
            self.assertEqual(resumen["total"], 10)
            self.assertEqual(resumen["pct_cumplimiento"], 100.0)
        finally:
            if os.path.exists(path):
                os.unlink(path)

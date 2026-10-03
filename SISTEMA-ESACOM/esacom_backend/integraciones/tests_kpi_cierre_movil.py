import datetime
import os
import tempfile
from decimal import Decimal

import openpyxl
from django.test import TestCase
from rest_framework.test import APIClient

from integraciones.management.commands.importar_kpi_movil_cierre import Command
from integraciones.models import CargaExcel, KPICierreResumen
from usuarios.models import Ejecutivo


class CierreMovilImportTests(TestCase):
    def setUp(self):
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="19784357-8", nombre="Ejecutivo Cierre", cargo=Ejecutivo.Cargo.EJECUTIVO,
            password="Clave12345!",
        )

    def _archivo(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "RESUMEN GESTION RGU"

        bloques = [
            (1, 3, "ABRIL", 37, 38, Decimal("0.9736842105263158"), Decimal("0.78")),
            (17, 2, "MAYO", 48, 50, Decimal("0.96"), Decimal("0.82")),
            (33, 1, "JUNIO", 92, 97, Decimal("0.9484536082474226"), Decimal("0.87")),
        ]
        for inicio, numero, camada, pago, total, kpi, meta in bloques:
            ws.cell(8, inicio, "NUMERO_BOLETA")
            ws.cell(8, inicio + 1, numero)
            ws.cell(10, inicio, "CAMADA")
            ws.cell(10, inicio + 1, camada)
            headers = ["EMPRESADASH", "EQUIPO DASH", "RUT_VENDEDOR", "VENCIDO --> MÁS 8", "VENCIDO --> 0 - 8", "GESTIONAR --> VENCE 8 O MÁS", "GESTIONAR --> VENCE 0 - 7", "Pagado Fuera de Plazo", "Pago", "RGU TOTAL", "KPI", "META", "Q PARA META"]
            for offset, h in enumerate(headers):
                ws.cell(14, inicio + offset, h)
            ws.cell(15, inicio, "ESACOM")
            ws.cell(15, inicio + 1, "ESACOM VINA DEL MAR")
            ws.cell(15, inicio + 8, pago)
            ws.cell(15, inicio + 9, total)
            ws.cell(15, inicio + 10, float(kpi))
            ws.cell(15, inicio + 11, float(meta))
            ws.cell(15, inicio + 12, 0)

        base = wb.create_sheet("BASE")
        headers = ["CAMADA", "EMPRESADASH", "EQUIPO DASH", "REP PCS", "N_BOLETA", "RUT_VENDEDOR", "kpi", "MARCA MES np8"]
        base.append(headers)
        rut = "019784357-8"
        base.append(["ABRIL", "ESACOM", "ESACOM VINA DEL MAR", 37, 3, rut, "PAGO", 1])
        base.append(["ABRIL", "ESACOM", "ESACOM VINA DEL MAR", 1, 3, rut, "NO PAGO", 1])
        base.append(["MAYO", "ESACOM", "ESACOM VINA DEL MAR", 48, 2, rut, "PAGO", 1])
        base.append(["MAYO", "ESACOM", "ESACOM VINA DEL MAR", 2, 2, rut, "NO PAGO", 1])
        base.append(["JUNIO", "ESACOM", "ESACOM VINA DEL MAR", 92, 1, rut, "PAGO", 1])
        base.append(["JUNIO", "ESACOM", "ESACOM VINA DEL MAR", 3, 1, rut, "PAGADO FUERA DE PLAZO", 1])
        base.append(["JUNIO", "ESACOM", "ESACOM VINA DEL MAR", 2, 1, rut, "NO PAGO", 1])

        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(path)
        return path

    def test_importa_cierre_sin_num_pedido_y_reproduce_resumen(self):
        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI MOVIL cierre.xlsx",
            fecha_corte=datetime.date(2026, 8, 31),
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=CargaExcel.EstadoReporte.CIERRE,
            formato_kpi=CargaExcel.FormatoKPI.CIERRE_MOVIL,
            avance_b1=Decimal("109.02"), avance_b2=Decimal("117.07"), avance_b3=Decimal("124.83"),
            meta_b1=Decimal("87"), meta_b2=Decimal("82"), meta_b3=Decimal("78"),
        )
        path = self._archivo()
        try:
            cmd = Command()
            cmd.handle(archivo=path, carga_id=carga.id, fecha_corte="2026-08-31")
        finally:
            os.remove(path)
        carga.refresh_from_db()
        self.assertEqual(carga.foco_b1, "2026-06")
        self.assertEqual(carga.foco_b2, "2026-05")
        self.assertEqual(carga.foco_b3, "2026-04")
        self.assertEqual(KPICierreResumen.objects.filter(carga=carga).count(), 6)
        global_b1 = KPICierreResumen.objects.get(carga=carga, rut_vendedor_fuente="GLOBAL", boleta="B1")
        self.assertEqual(global_b1.pagadas, 92)
        self.assertEqual(global_b1.total_medible, 97)
        self.assertEqual(global_b1.kpi_pago_pct, Decimal("94.85"))
        ejecutivo_b3 = KPICierreResumen.objects.get(carga=carga, ejecutivo=self.ejecutivo, boleta="B3")
        self.assertEqual(ejecutivo_b3.pagadas, 37)
        self.assertEqual(ejecutivo_b3.no_pago, 1)
        self.assertEqual(ejecutivo_b3.total_medible, 38)


    def test_importa_avance_movil_separado_del_cierre(self):
        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI MOVIL avance.xlsx",
            fecha_corte=datetime.date(2026, 9, 17),
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            formato_kpi=CargaExcel.FormatoKPI.AVANCE_MOVIL,
            avance_b1=Decimal("109.02"), avance_b2=Decimal("117.07"), avance_b3=Decimal("124.83"),
            meta_b1=Decimal("87"), meta_b2=Decimal("82"), meta_b3=Decimal("78"),
        )
        path = self._archivo()
        try:
            cmd = Command()
            cmd.handle(archivo=path, carga_id=carga.id, fecha_corte="2026-09-17")
        finally:
            os.remove(path)
        carga.refresh_from_db()
        self.assertEqual(carga.formato_kpi, CargaExcel.FormatoKPI.AVANCE_MOVIL)
        self.assertEqual(carga.estado_reporte, CargaExcel.EstadoReporte.AVANCE)
        self.assertIn("avances", cmd.resumen)
        self.assertNotIn("cierres", cmd.resumen)
        self.assertEqual(cmd.resumen["resumen_boletas"]["B1"]["pago"], 92)
        self.assertEqual(cmd.resumen["resumen_boletas"]["B1"]["total_rgu"], 97)
        self.assertEqual(KPICierreResumen.objects.filter(carga=carga).count(), 6)



class CargaDatosSoloSoporteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.soporte = Ejecutivo.objects.create_user(
            rut="11111111-1", nombre="Soporte", cargo=Ejecutivo.Cargo.SOPORTE, password="Clave12345!"
        )
        self.gerencia = Ejecutivo.objects.create_user(
            rut="22222222-2", nombre="Gerencia", cargo=Ejecutivo.Cargo.GERENCIA, password="Clave12345!"
        )
        self.url = "/api/integraciones/cargar-excel/"

    def test_gerencia_no_puede_cargar(self):
        self.client.force_authenticate(self.gerencia)
        self.assertEqual(self.client.post(self.url, {}, format="multipart").status_code, 403)

    def test_soporte_tiene_permiso_de_carga(self):
        self.assertTrue(self.soporte.tiene_permiso("cargar_datos"))
        self.client.force_authenticate(self.soporte)
        self.assertEqual(self.client.post(self.url, {}, format="multipart").status_code, 400)

import datetime
from decimal import Decimal

from django.test import TestCase

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.views import _carga_efectiva_par, _cierre_oficial_mes, _ultima_carga_kpi_activa


class AvanceCierreSnapshotTests(TestCase):
    def _carga(self, *, estado, corte, b1="", b2="", b3="", formato=CargaExcel.FormatoKPI.DETALLADO):
        return CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre=f"{estado}-{corte}.xlsx",
            fecha_corte=corte,
            dia_reporte=CargaExcel.DiaReporte.OTRO,
            estado_reporte=estado,
            formato_kpi=formato,
            foco_b1=b1,
            foco_b2=b2,
            foco_b3=b3,
        )

    def test_cierre_congela_par_aunque_llegue_avance_posterior(self):
        cierre = self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 8, 31),
            b1="2026-07",
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 9, 2),
            b1="2026-07",
        )
        self.assertEqual(_carga_efectiva_par("B1", "2026-07").id, cierre.id)

    def test_carga_activa_prefiere_ultimo_avance_y_no_cierre_historico(self):
        avance = self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 9, 1),
            b1="2026-08", b2="2026-07", b3="2026-06",
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 9, 2),
            b1="2026-06", b2="2026-05", b3="2026-04",
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
        )
        self.assertEqual(_ultima_carga_kpi_activa().id, avance.id)


    def test_avance_movil_no_desplaza_avance_fijo(self):
        avance_fijo = self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 9, 15),
            b1="2026-08", b2="2026-07", b3="2026-06",
            formato=CargaExcel.FormatoKPI.DETALLADO,
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 9, 17),
            b1="2026-07", b2="2026-06", b3="2026-05",
            formato=CargaExcel.FormatoKPI.AVANCE_MOVIL,
        )
        self.assertEqual(_ultima_carga_kpi_activa().id, avance_fijo.id)
        self.assertEqual(_carga_efectiva_par("B1", "2026-08").id, avance_fijo.id)

    def test_cierre_movil_no_se_convierte_en_snapshot_activo_fijo(self):
        self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 9, 2),
            b1="2026-08",
            formato=CargaExcel.FormatoKPI.CIERRE_MOVIL,
        )
        self.assertIsNone(_ultima_carga_kpi_activa())

    def test_cierre_movil_no_congela_kpi_fijo_del_mismo_mes(self):
        avance = self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 9, 1),
            b1="2026-08",
            formato=CargaExcel.FormatoKPI.DETALLADO,
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 9, 2),
            b1="2026-08",
            formato=CargaExcel.FormatoKPI.CIERRE_MOVIL,
        )
        self.assertEqual(_carga_efectiva_par("B1", "2026-08").id, avance.id)
        self.assertIsNone(_cierre_oficial_mes("2026-08"))

    def test_cierre_fijo_y_movil_pueden_coexistir_sin_mezclarse(self):
        self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 8, 31),
            b1="2026-07",
            formato=CargaExcel.FormatoKPI.CIERRE_MOVIL,
        )
        cierre_fijo = self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 9, 1),
            b1="2026-07",
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
        )
        self.assertEqual(_cierre_oficial_mes("2026-07").id, cierre_fijo.id)
        self.assertEqual(_carga_efectiva_par("B1", "2026-07").id, cierre_fijo.id)

class CierreMovilPortalTests(TestCase):
    def setUp(self):
        from integraciones.models import KPICierreResumen
        self.KPICierreResumen = KPICierreResumen
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="66666666-6", nombre="Ejecutivo Cierre Portal", cargo=Ejecutivo.Cargo.EJECUTIVO,
            password="Clave12345!",
        )

    def test_resumen_cierre_movil_usa_meta_movil_y_no_necesita_kpiregistro(self):
        from integraciones.models import CargaExcel
        from ventas.views import _resumen_par_snapshot_usuario

        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="cierre movil.xlsx",
            fecha_corte=datetime.date(2026, 8, 31),
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=CargaExcel.EstadoReporte.CIERRE,
            formato_kpi=CargaExcel.FormatoKPI.CIERRE_MOVIL,
            foco_b1="2026-06",
            avance_b1=Decimal("109.02"),
            meta_b1=Decimal("87"),
        )
        self.KPICierreResumen.objects.create(
            carga=carga, ejecutivo=self.ejecutivo, rut_vendedor_fuente=self.ejecutivo.rut,
            camada="2026-06", boleta="B1", pagadas=8, no_pago=2, total_medible=10,
            kpi_pago_pct=Decimal("80.00"), meta_claro_pct=Decimal("87"), cierre_claro_pct=Decimal("109.02"),
        )
        resumen = _resumen_par_snapshot_usuario(self.ejecutivo, "B1", "2026-06", carga=carga)
        self.assertTrue(resumen["cerrado"])
        self.assertEqual(resumen["fuente_formato"], "CIERRE_MOVIL")
        self.assertEqual(resumen["pct_cumplimiento"], 80.0)
        self.assertEqual(resumen["meta_pct"], 87.0)
        self.assertEqual(resumen["faltan_para_meta"], 1)

    def test_resumen_avance_movil_usa_meta_movil_y_permanece_abierto(self):
        from integraciones.models import CargaExcel
        from ventas.views import _resumen_par_snapshot_usuario

        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="avance movil.xlsx",
            fecha_corte=datetime.date(2026, 9, 17),
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            formato_kpi=CargaExcel.FormatoKPI.AVANCE_MOVIL,
            foco_b1="2026-07",
            avance_b1=Decimal("81.60"),
            meta_b1=Decimal("87"),
        )
        self.KPICierreResumen.objects.create(
            carga=carga, ejecutivo=self.ejecutivo, rut_vendedor_fuente=self.ejecutivo.rut,
            camada="2026-07", boleta="B1", pagadas=115, pendientes=47, total_medible=162,
            kpi_pago_pct=Decimal("70.99"), meta_claro_pct=Decimal("87"), cierre_claro_pct=Decimal("81.60"),
        )
        resumen = _resumen_par_snapshot_usuario(self.ejecutivo, "B1", "2026-07", carga=carga)
        self.assertFalse(resumen["cerrado"])
        self.assertEqual(resumen["fuente_formato"], "AVANCE_MOVIL")
        self.assertEqual(resumen["meta_pct"], 87.0)
        self.assertEqual(resumen["pct_cumplimiento"], 70.99)
        self.assertEqual(resumen["faltan_para_meta"], 26)
        self.assertEqual(resumen["valor_informado_claro"], 81.6)


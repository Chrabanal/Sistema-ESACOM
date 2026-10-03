import datetime

from django.test import TestCase

from integraciones.models import CargaExcel
from ventas.views import _cierre_oficial_mes, _ultimo_avance_b1_mes


class CierreMensualKPIRegressionTests(TestCase):
    def _carga(self, *, estado, corte, b1="", b2="", b3=""):
        return CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre=f"{estado}-{corte}.xlsx",
            fecha_corte=corte,
            dia_reporte=CargaExcel.DiaReporte.OTRO,
            estado_reporte=estado,
            foco_b1=b1,
            foco_b2=b2,
            foco_b3=b3,
        )

    def test_mes_no_cambia_por_aparecer_luego_como_b2(self):
        b1 = self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 8, 25),
            b1="2026-07",
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 9, 1),
            b1="2026-08",
            b2="2026-07",
        )
        self.assertEqual(_ultimo_avance_b1_mes("2026-07").id, b1.id)

    def test_primer_cierre_oficial_congela_mes_aunque_llegue_otro_reporte(self):
        cierre = self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 8, 31),
            b1="2026-06",
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 9, 1),
            b3="2026-06",
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            corte=datetime.date(2026, 9, 10),
            b2="2026-06",
        )
        self.assertEqual(_cierre_oficial_mes("2026-06").id, cierre.id)

    def test_mes_sin_cierre_oficial_no_inventa_cierre(self):
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            corte=datetime.date(2026, 8, 25),
            b1="2026-07",
        )
        self.assertIsNone(_cierre_oficial_mes("2026-07"))

import datetime
from decimal import Decimal

from django.test import TestCase

from integraciones.models import CargaExcel, KPIRegistro
from integraciones.report_dates import fecha_reporte_desde_nombre
from ventas.views import (
    _camadas_b1_abiertas,
    _carga_efectiva_par,
    _cierre_oficial_mes,
    _ultimo_avance_b1_mes,
    _valor_informado_claro_par,
)


class FlujoKpiCamadasAbiertasR214Tests(TestCase):
    def _avance(self, nombre, corte, *, foco_b1="2026-08", avance=Decimal("0")):
        return CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre=nombre,
            fecha_corte=corte,
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            formato_kpi=CargaExcel.FormatoKPI.DETALLADO,
            foco_b1=foco_b1,
            avance_b1=avance,
            meta_b1=Decimal("85"),
        )

    def _fila(self, carga, camada, pedido):
        return KPIRegistro.objects.create(
            carga=carga, num_pedido=pedido, camada=camada, boleta="B1",
            rgu=1, kpi_texto="Pendiente", estado_normalizado="PENDIENTE",
            es_medible=True, marca_mes_kpi=1, cruce_ok=False,
        )

    def test_fecha_reporte_separa_nombre_de_fecha_corte(self):
        self.assertEqual(
            fecha_reporte_desde_nombre("KPI23092026 ESACOM(1).xlsx"),
            datetime.date(2026, 9, 23),
        )

    def test_septiembre_existe_aunque_resumen_siga_focalizado_en_agosto(self):
        carga = self._avance(
            "KPI23092026 ESACOM.xlsx", datetime.date(2026, 9, 22),
            foco_b1="2026-08", avance=Decimal("90.85"),
        )
        self._fila(carga, "2026-09", "SEP-1")

        self.assertEqual(_ultimo_avance_b1_mes("2026-09").id, carga.id)
        self.assertIn("2026-09", _camadas_b1_abiertas())
        self.assertIn("2026-08", _camadas_b1_abiertas())
        self.assertIsNone(_valor_informado_claro_par(carga, "B1", "2026-09"))
        self.assertEqual(_valor_informado_claro_par(carga, "B1", "2026-08"), 90.85)

    def test_reporte_28_actualiza_septiembre_sin_cerrar_agosto(self):
        c23 = self._avance(
            "KPI23092026 ESACOM.xlsx", datetime.date(2026, 9, 22),
            avance=Decimal("90.85"),
        )
        self._fila(c23, "2026-09", "SEP-23")
        c28 = self._avance(
            "KPI28092026 ESACOM.xlsx", datetime.date(2026, 9, 28),
            avance=Decimal("97.81"),
        )
        self._fila(c28, "2026-09", "SEP-28")

        self.assertEqual(_ultimo_avance_b1_mes("2026-09").id, c28.id)
        self.assertIsNone(_cierre_oficial_mes("2026-08"))
        self.assertEqual(_camadas_b1_abiertas()[:2], ["2026-09", "2026-08"])

    def test_cierre_solo_es_oficial_si_formato_es_cierre_fijo(self):
        self._avance("KPI28092026 ESACOM.xlsx", datetime.date(2026, 9, 28), foco_b1="2026-08")
        CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL, tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="avance_mal_marcado.xlsx", fecha_corte=datetime.date(2026, 9, 30),
            estado_reporte=CargaExcel.EstadoReporte.CIERRE, formato_kpi=CargaExcel.FormatoKPI.DETALLADO,
            foco_b1="2026-08",
        )
        self.assertIsNone(_cierre_oficial_mes("2026-08"))

        cierre = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL, tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI01102026 CIERRE FIJO.xlsx", fecha_corte=datetime.date(2026, 9, 30),
            estado_reporte=CargaExcel.EstadoReporte.CIERRE, formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
            foco_b1="2026-08",
        )
        self.assertEqual(_cierre_oficial_mes("2026-08").id, cierre.id)
        self.assertNotIn("2026-08", _camadas_b1_abiertas())
        self.assertEqual(_carga_efectiva_par("B1", "2026-08").id, cierre.id)

    def test_fecha_reporte_manda_si_archivo_antiguo_se_carga_despues(self):
        nuevo = self._avance(
            "KPI09092026 ESACOM.xlsx", datetime.date(2026, 9, 8), foco_b1="2026-08"
        )
        # Se carga después, pero el reporte es del 08/09 y no debe desplazar al 09/09.
        self._avance(
            "KPI08092026 ESACOM.xlsx", datetime.date(2026, 9, 8), foco_b1="2026-08"
        )
        self.assertEqual(_ultimo_avance_b1_mes("2026-08").id, nuevo.id)

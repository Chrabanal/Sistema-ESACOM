from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from integraciones.models import MetaKPICalidad
from integraciones.services.metas_kpi import meta_calidad_para, metas_calidad_para_focos
from usuarios.models import Ejecutivo


class MetaKPICalidadResolverTests(TestCase):
    def test_metas_historicas_enero_a_junio_2026(self):
        # La migración 0010 fija la regla histórica anterior al cambio de B3:
        # B1 85%, B2 83%, B3 78% para camadas 2026-01 a 2026-06.
        self.assertEqual(Decimal(str(meta_calidad_para(boleta="B1", camada="2026-06", fallback=0))), Decimal("85.00"))
        self.assertEqual(Decimal(str(meta_calidad_para(boleta="B2", camada="2026-06", fallback=0))), Decimal("83.00"))
        self.assertEqual(Decimal(str(meta_calidad_para(boleta="B3", camada="2026-06", fallback=0))), Decimal("78.00"))

    def test_meta_confirmada_desde_julio_2026(self):
        # La migración 0009 crea 2026-07 = B1 85 / B2 83 / B3 80.
        self.assertEqual(Decimal(str(meta_calidad_para(boleta="B1", camada="2026-07", fallback=0))), Decimal("85.00"))
        self.assertEqual(Decimal(str(meta_calidad_para(boleta="B2", camada="2026-08", fallback=0))), Decimal("83.00"))
        self.assertEqual(Decimal(str(meta_calidad_para(boleta="B3", camada="2026-07", fallback=0))), Decimal("80.00"))

    def test_reporte_agosto_julio_junio_resuelve_meta_por_camada(self):
        # Caso real del KPI03092026: B1 Ago / B2 Jul / B3 Jun.
        # Aunque el formulario de carga haya guardado 80 como meta_b3 del reporte,
        # Junio debe conservar 78% porque la vigencia nueva empieza en Julio.
        metas = metas_calidad_para_focos(
            {"B1": "2026-08", "B2": "2026-07", "B3": "2026-06"},
            fallback={"B1": Decimal("85"), "B2": Decimal("83"), "B3": Decimal("80")},
        )
        self.assertEqual(Decimal(str(metas["B1"])), Decimal("85.00"))
        self.assertEqual(Decimal(str(metas["B2"])), Decimal("83.00"))
        self.assertEqual(Decimal(str(metas["B3"])), Decimal("78.00"))

    def test_nueva_vigencia_no_modifica_camadas_anteriores(self):
        MetaKPICalidad.objects.create(
            vigente_desde="2027-01", meta_b1=87, meta_b2=85, meta_b3=82,
            motivo="Cambio futuro aprobado por Gerencia",
        )
        metas_julio = metas_calidad_para_focos({"B1": "2026-07", "B2": "2026-07", "B3": "2026-07"})
        metas_enero = metas_calidad_para_focos({"B1": "2027-01", "B2": "2027-01", "B3": "2027-01"})
        self.assertEqual(Decimal(str(metas_julio["B3"])), Decimal("80.00"))
        self.assertEqual(Decimal(str(metas_enero["B3"])), Decimal("82.00"))


class MetaKPICalidadPermisosTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.soporte = Ejecutivo.objects.create_user(
            rut="11111111-1", nombre="Soporte KPI", cargo=Ejecutivo.Cargo.SOPORTE, password="Clave12345!"
        )
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="22222222-2", nombre="Ejecutivo KPI", cargo=Ejecutivo.Cargo.EJECUTIVO, password="Clave12345!"
        )
        self.gerencia = Ejecutivo.objects.create_user(
            rut="33333333-3", nombre="Gerencia KPI", cargo=Ejecutivo.Cargo.GERENCIA, password="Clave12345!"
        )
        self.url = "/api/soporte/metas-kpi-calidad/"

    def test_soporte_puede_listar_y_crear(self):
        self.client.force_authenticate(self.soporte)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        response = self.client.post(self.url, {
            "vigente_desde": "2027-02",
            "meta_b1": "86.00", "meta_b2": "84.00", "meta_b3": "81.00",
            "motivo": "Nueva meta aprobada por Gerencia",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        creada = MetaKPICalidad.objects.get(vigente_desde="2027-02")
        self.assertEqual(creada.creado_por, self.soporte)

    def test_ejecutivo_y_gerencia_no_pueden_administrar_metas(self):
        for usuario in (self.ejecutivo, self.gerencia):
            self.client.force_authenticate(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, {
                "vigente_desde": "2027-03", "meta_b1": 85, "meta_b2": 83, "meta_b3": 80,
                "motivo": "Intento no autorizado",
            }, format="json").status_code, 403)

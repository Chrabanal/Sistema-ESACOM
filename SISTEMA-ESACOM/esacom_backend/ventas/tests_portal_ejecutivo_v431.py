import datetime
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from catalogos.models import Promocion
from usuarios.models import Ejecutivo

from .models import Corte, Venta


class PortalEjecutivoHistoricoTests(TestCase):
    def setUp(self):
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="11111111-1", password="test12345", nombre="Ejecutivo Histórico"
        )
        self.promo = Promocion.objects.create(
            nombre="Promo Hist", rgu=1, empresa=Promocion.Empresa.CLARO
        )

    def _venta(self, pedido, camada):
        return Venta.objects.create(
            rut_cliente=f"{pedido[-6:]}-K",
            nombre_cliente=f"Cliente {pedido}",
            n_pedido=pedido,
            ejecutivo=self.ejecutivo,
            promocion=self.promo,
            fecha_venta=datetime.date(int(camada[:4]), int(camada[5:]), 1),
            camada=camada,
            rgu_base=1,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )

    def test_historico_solo_contiene_meses_anteriores_a_ventana_vigente(self):
        from .views import _historico_kpi_usuario

        datos = [
            ("1-AGO", "2026-08", Corte.Boleta.B1),  # futuro respecto a ventana: no histórico
            ("1-JUL", "2026-07", Corte.Boleta.B1),  # B1 activo
            ("1-JUN", "2026-06", Corte.Boleta.B2),  # B2 activo
            ("1-MAY", "2026-05", Corte.Boleta.B3),  # B3 activo
            ("1-ABR", "2026-04", Corte.Boleta.B3),  # histórico válido
        ]
        for pedido, mes, boleta in datos:
            venta = self._venta(pedido, mes)
            Corte.objects.create(
                venta=venta,
                mes_ano=mes,
                boleta=boleta,
                meta_pct=Decimal("80"),
                estado_pago=Corte.EstadoPago.PAGADO,
                es_medible=True,
                rgu_kpi=1,
            )

        historico = _historico_kpi_usuario(
            self.ejecutivo,
            {"B1": "2026-07", "B2": "2026-06", "B3": "2026-05"},
        )
        self.assertEqual([(x["mes_ano"], x["boleta"]) for x in historico], [("2026-04", "B3")])


class PortalEjecutivoClientesActivosTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="22222222-2", password="test12345", nombre="Ejecutivo Activos"
        )
        self.otro = Ejecutivo.objects.create_user(
            rut="33333333-3", password="test12345", nombre="Ejecutivo Otro"
        )
        self.promo = Promocion.objects.create(
            nombre="Promo Activos", rgu=1, empresa=Promocion.Empresa.CLARO
        )

    def _venta(self, pedido, ejecutivo, camada="2026-07"):
        return Venta.objects.create(
            rut_cliente=f"{pedido[-6:]}-K",
            nombre_cliente=f"Cliente {pedido}",
            n_pedido=pedido,
            ejecutivo=ejecutivo,
            promocion=self.promo,
            fecha_venta=datetime.date(2026, 7, 1),
            camada=camada,
            rgu_base=1,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )

    def test_activo_pago_mes_devuelve_solo_clientes_propios_que_pagaron(self):
        from .views import VentaViewSet

        pagado = self._venta("1-PAGADO", self.ejecutivo)
        no_pagado = self._venta("1-NOPAGO", self.ejecutivo)
        ajeno = self._venta("1-AJENO", self.otro)

        Corte.objects.create(
            venta=pagado, mes_ano="2026-08", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("85"), estado_pago=Corte.EstadoPago.PAGADO,
        )
        Corte.objects.create(
            venta=no_pagado, mes_ano="2026-08", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("85"), estado_pago=Corte.EstadoPago.PENDIENTE,
        )
        Corte.objects.create(
            venta=ajeno, mes_ano="2026-08", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("85"), estado_pago=Corte.EstadoPago.PAGADO,
        )

        request = self.factory.get("/api/ventas/", {"activo_pago_mes": "2026-08", "page_size": 1000})
        force_authenticate(request, user=self.ejecutivo)
        response = VentaViewSet.as_view({"get": "list"})(request)

        self.assertEqual(response.status_code, 200)
        resultados = response.data.get("results", response.data)
        self.assertEqual([x["id"] for x in resultados], [pagado.id])


    def test_activo_pago_mes_respeta_la_boleta_vigente(self):
        from .views import VentaViewSet

        venta = self._venta("1-ETAPA", self.ejecutivo)
        Corte.objects.create(
            venta=venta, mes_ano="2026-08", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("85"), estado_pago=Corte.EstadoPago.PAGADO,
        )
        Corte.objects.create(
            venta=venta, mes_ano="2026-08", boleta=Corte.Boleta.B2,
            meta_pct=Decimal("83"), estado_pago=Corte.EstadoPago.PENDIENTE,
        )

        request_b1 = self.factory.get("/api/ventas/", {
            "activo_pago_mes": "2026-08", "activo_pago_boleta": "B1",
        })
        force_authenticate(request_b1, user=self.ejecutivo)
        response_b1 = VentaViewSet.as_view({"get": "list"})(request_b1)
        resultados_b1 = response_b1.data.get("results", response_b1.data)
        self.assertEqual([x["id"] for x in resultados_b1], [venta.id])

        request_b2 = self.factory.get("/api/ventas/", {
            "activo_pago_mes": "2026-08", "activo_pago_boleta": "B2",
        })
        force_authenticate(request_b2, user=self.ejecutivo)
        response_b2 = VentaViewSet.as_view({"get": "list"})(request_b2)
        resultados_b2 = response_b2.data.get("results", response_b2.data)
        self.assertEqual(len(resultados_b2), 0)

    def test_activo_pago_mes_invalido_no_expone_cartera(self):
        from .views import VentaViewSet

        venta = self._venta("1-VALIDA", self.ejecutivo)
        Corte.objects.create(
            venta=venta, mes_ano="2026-08", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("85"), estado_pago=Corte.EstadoPago.PAGADO,
        )
        request = self.factory.get("/api/ventas/", {"activo_pago_mes": "agosto"})
        force_authenticate(request, user=self.ejecutivo)
        response = VentaViewSet.as_view({"get": "list"})(request)
        resultados = response.data.get("results", response.data)
        self.assertEqual(len(resultados), 0)

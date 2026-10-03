import datetime
from decimal import Decimal

from django.test import TestCase

from catalogos.models import Promocion
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta
from ventas.services import aplicar_meta_resumen, resumen_cortes_actuales, resumen_kpi


class VentanaBoletasV43Tests(TestCase):
    def setUp(self):
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="44444444-4", nombre="Ejecutivo Ventana", cargo=Ejecutivo.Cargo.EJECUTIVO, password="Clave12345!"
        )
        self.promo = Promocion.objects.create(nombre="Promo", rgu=1, empresa=Promocion.Empresa.CLARO)

    def test_devuelve_tres_boletas_aunque_usuario_no_tenga_datos(self):
        resumen = resumen_cortes_actuales(
            Corte.objects.none(),
            focos={"B1": "2026-08", "B2": "2026-07", "B3": "2026-06"},
            metas={"B1": 85, "B2": 83, "B3": 78},
        )
        self.assertEqual([(x["boleta"], x["mes_ano"]) for x in resumen], [
            ("B1", "2026-08"), ("B2", "2026-07"), ("B3", "2026-06")
        ])
        self.assertTrue(all(x["tiene_datos"] is False for x in resumen))

    def test_cumplimiento_meta_usa_precision_completa(self):
        ids = []
        for i in range(38):
            venta = Venta.objects.create(
                rut_cliente=f"100000{i:02d}-K", n_pedido=f"P-{i}", ejecutivo=self.ejecutivo,
                promocion=self.promo, fecha_venta=datetime.date(2026, 4, 1), camada="2026-04",
                rgu_base=1, estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
            )
            corte = Corte.objects.create(
                venta=venta, mes_ano="2026-04", boleta=Corte.Boleta.B3,
                meta_pct=Decimal("78"), estado_pago=Corte.EstadoPago.PAGADO if i < 37 else Corte.EstadoPago.NO_PAGO,
                rgu_kpi=1,
            )
            ids.append(corte.id)
        r = resumen_kpi(Corte.objects.filter(id__in=ids))
        aplicar_meta_resumen(r, Decimal("78"))
        self.assertEqual(r["pct_cumplimiento"], 97.37)
        self.assertEqual(r["cumplimiento_meta_pct"], 124.8)
        self.assertEqual(r["faltan_para_meta"], 0)


class EjecutivoSoloLecturaV43Tests(TestCase):
    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="55555555-5", nombre="Ejecutivo Solo Lectura", cargo=Ejecutivo.Cargo.EJECUTIVO, password="Clave12345!"
        )
        self.promo = Promocion.objects.create(nombre="Promo Solo Lectura", rgu=1, empresa=Promocion.Empresa.CLARO)
        self.venta = Venta.objects.create(
            rut_cliente="12345678-9", n_pedido="P-SOLO-LECTURA", ejecutivo=self.ejecutivo,
            promocion=self.promo, fecha_venta=datetime.date(2026, 9, 1), camada="2026-09",
            rgu_base=1, estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )

    def test_ejecutivo_puede_consultar_su_venta_pero_no_editarla(self):
        self.client.force_authenticate(self.ejecutivo)
        url = f"/api/ventas/{self.venta.pk}/"
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.patch(url, {"nombre_cliente": "Intento de edición"}, format="json")
        self.assertEqual(response.status_code, 403)
        self.venta.refresh_from_db()
        self.assertNotEqual(self.venta.nombre_cliente, "Intento de edición")

    def test_ejecutivo_no_puede_crear_ventas(self):
        self.client.force_authenticate(self.ejecutivo)
        response = self.client.post("/api/ventas/", {
            "rut_cliente": "87654321-0",
            "n_pedido": "P-CREADA-DESDE-PORTAL",
            "ejecutivo": self.ejecutivo.pk,
            "promocion": self.promo.pk,
            "fecha_venta": "2026-09-05",
            "camada": "2026-09",
            "rgu_base": 1,
            "estado_instalacion": Venta.EstadoInstalacion.INSTALADO,
        }, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Venta.objects.filter(n_pedido="P-CREADA-DESDE-PORTAL").exists())

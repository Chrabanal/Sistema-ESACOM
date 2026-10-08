import datetime
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from catalogos.models import Promocion
from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo

from .models import Corte, Venta
from .services import resumen_kpi


class KpiPorRguTests(TestCase):
    def setUp(self):
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="11111111-1", password="test12345", nombre="Ejecutivo Test"
        )
        self.promo = Promocion.objects.create(
            nombre="Promo Test", rgu=1, empresa=Promocion.Empresa.CLARO
        )

    def _venta(self, pedido, rgu):
        return Venta.objects.create(
            rut_cliente=f"{pedido[-7:]}-K",
            n_pedido=pedido,
            ejecutivo=self.ejecutivo,
            promocion=self.promo,
            fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07",
            rgu_base=rgu,
        )

    def test_kpi_incluye_pendientes_en_denominador_y_pondera_rgu(self):
        datos = [
            ("1-1", 3, Corte.EstadoPago.PAGADO),
            ("1-2", 2, Corte.EstadoPago.PENDIENTE),
            ("1-3", 1, Corte.EstadoPago.NO_PAGO),
            ("1-4", 1, Corte.EstadoPago.FUERA_PLAZO),
        ]
        corte_ids = []
        for pedido, rgu, estado in datos:
            v = self._venta(pedido, rgu)
            corte = Corte.objects.create(
                venta=v,
                mes_ano="2026-07",
                boleta=Corte.Boleta.B1,
                meta_pct=Decimal("0"),
                estado_pago=estado,
                rgu_kpi=rgu,
            )
            corte_ids.append(corte.id)

        # Aisla esta prueba de filas adicionales creadas por setUp de subclases.
        r = resumen_kpi(Corte.objects.filter(id__in=corte_ids))
        self.assertEqual(r["pagadas"], 3)
        self.assertEqual(r["pendientes"], 2)
        self.assertEqual(r["total"], 7)
        self.assertEqual(r["pct_cumplimiento"], 42.86)
        self.assertEqual(r["pct_proyectado"], 55.1)
        self.assertEqual(r["unidad"], "RGU")

    def test_mismo_pedido_y_boleta_puede_existir_en_otra_camada(self):
        v = self._venta("1-100", 1)
        Corte.objects.create(
            venta=v,
            mes_ano="2026-06",
            boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"),
        )
        Corte.objects.create(
            venta=v,
            mes_ano="2026-07",
            boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"),
        )
        self.assertEqual(v.cortes.filter(boleta=Corte.Boleta.B1).count(), 2)

    def test_no_duplica_misma_clave_pedido_camada_boleta(self):
        v = self._venta("1-200", 1)
        Corte.objects.create(
            venta=v,
            mes_ano="2026-07",
            boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Corte.objects.create(
                    venta=v,
                    mes_ano="2026-07",
                    boleta=Corte.Boleta.B1,
                    meta_pct=Decimal("0"),
                )


class CortesActualesTests(KpiPorRguTests):
    def test_dashboard_elige_ultima_camada_medible_por_boleta(self):
        from .services import resumen_cortes_actuales

        junio = self._venta("1-300", 2)
        julio = self._venta("1-301", 2)
        Corte.objects.create(
            venta=junio, mes_ano="2026-06", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=2, es_medible=True,
        )
        Corte.objects.create(
            venta=julio, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.PENDIENTE,
            rgu_kpi=2, es_medible=False,
        )

        cortes = resumen_cortes_actuales(Corte.objects.all())
        self.assertEqual(len(cortes), 1)
        self.assertEqual(cortes[0]["mes_ano"], "2026-06")
        self.assertEqual(cortes[0]["pagadas"], 2)

    def test_historico_excluye_fuera_medicion_del_kpi(self):
        from .services import resumen_historico_camadas

        v1 = self._venta("1-400", 2)
        v2 = self._venta("1-401", 3)
        Corte.objects.create(
            venta=v1, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=2, es_medible=True,
        )
        Corte.objects.create(
            venta=v2, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.NO_PAGO,
            rgu_kpi=3, es_medible=False,
        )
        r = resumen_historico_camadas(Venta.objects.filter(id__in=[v1.id, v2.id]))[0]
        self.assertEqual(r["pagadas"], 2)
        self.assertEqual(r["no_pago"], 0)
        self.assertEqual(r["fuera_medicion"], 3)
        self.assertEqual(r["pct_cumplimiento"], 100.0)


class GestionTrazabilidadTests(KpiPorRguTests):
    def test_gestion_guarda_resultado_y_proximo_contacto(self):
        from django.utils import timezone
        from .models import Gestion

        venta = self._venta("1-500", 1)
        proximo = timezone.now() + datetime.timedelta(days=1)
        g = Gestion.objects.create(
            venta=venta,
            ejecutivo=self.ejecutivo,
            tipo=Gestion.Tipo.LLAMADA,
            resultado=Gestion.Resultado.COMPROMISO_PAGO,
            nota="Cliente compromete pago mañana",
            proximo_contacto=proximo,
        )
        self.assertEqual(g.resultado, Gestion.Resultado.COMPROMISO_PAGO)
        self.assertIsNotNone(g.proximo_contacto)
        self.assertIn("compromete", g.nota)

class FocosOficialesDashboardTests(KpiPorRguTests):
    def test_dashboard_respeta_foco_oficial_y_meta_del_snapshot(self):
        from .services import resumen_cortes_actuales

        julio = self._venta("1-700", 3)
        agosto = self._venta("1-701", 6)
        Corte.objects.create(
            venta=julio, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=3, es_medible=True,
        )
        # Completa el total julio con 10 RGU pendientes en otra venta.
        julio_p = self._venta("1-702", 10)
        Corte.objects.create(
            venta=julio_p, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.PENDIENTE,
            rgu_kpi=10, es_medible=True,
        )
        Corte.objects.create(
            venta=agosto, mes_ano="2026-08", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.PENDIENTE,
            rgu_kpi=6, es_medible=True,
        )

        cortes = resumen_cortes_actuales(
            Corte.objects.all(), focos={"B1": "2026-07"}, metas={"B1": Decimal("85")}
        )
        self.assertEqual(cortes[0]["mes_ano"], "2026-07")
        self.assertEqual(cortes[0]["pagadas"], 3)
        self.assertEqual(cortes[0]["pendientes"], 10)
        self.assertEqual(cortes[0]["pct_cumplimiento"], 23.08)
        self.assertEqual(cortes[0]["meta_pct"], 85.0)
        self.assertEqual(cortes[0]["faltan_para_meta"], 9)

    def test_dashboard_no_hace_fallback_si_foco_oficial_no_existe(self):
        from .services import resumen_cortes_actuales

        agosto = self._venta("1-703", 2)
        Corte.objects.create(
            venta=agosto, mes_ano="2026-08", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("0"), estado_pago=Corte.EstadoPago.PENDIENTE,
            rgu_kpi=2, es_medible=True,
        )

        cortes = resumen_cortes_actuales(
            Corte.objects.all(), focos={"B1": "2026-07"}, metas={"B1": Decimal("85")}
        )
        # Regla vigente: el foco oficial se muestra aunque no tenga datos;
        # nunca hace fallback silencioso a otra camada.
        self.assertEqual(len(cortes), 1)
        self.assertEqual(cortes[0]["mes_ano"], "2026-07")
        self.assertEqual(cortes[0]["boleta"], Corte.Boleta.B1)
        self.assertEqual(cortes[0]["total"], 0)
        self.assertFalse(cortes[0]["tiene_datos"])

class AtribucionPorRutEsacomTests(KpiPorRguTests):
    def test_kpi_se_atribuye_al_evt_esacom_no_al_ce_claro(self):
        from .services import resumen_por_ejecutivo

        otro = Ejecutivo.objects.create_user(
            rut="22222222-2", password="test12345", nombre="CE Claro"
        )
        venta = self._venta("1-800", 2)
        venta.ejecutivo_ce = otro
        venta.rut_ce = otro.rut
        venta.save(update_fields=["ejecutivo_ce", "rut_ce"])
        Corte.objects.create(
            venta=venta,
            mes_ano="2026-07",
            boleta=Corte.Boleta.B1,
            meta_pct=Decimal("85"),
            estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=2,
            ejecutivo_kpi=otro,
        )

        resumen = resumen_por_ejecutivo(Corte.objects.all())
        self.assertEqual(len(resumen), 1)
        self.assertEqual(resumen[0]["ejecutivo"]["id"], self.ejecutivo.id)

    def test_resumen_honorarios_no_mezcla_b1_b2_b3(self):
        from .services import resumen_honorarios

        self.ejecutivo.tipo_kpi = Ejecutivo.TipoKPI.HONORARIOS
        self.ejecutivo.save(update_fields=["tipo_kpi"])
        v1 = self._venta("1-810", 2)
        v1.origen_venta = Venta.OrigenVenta.HONORARIOS
        v1.fecha_pago_honorarios = datetime.date(2026, 8, 10)
        v1.save(update_fields=["origen_venta", "fecha_pago_honorarios"])
        v2 = self._venta("1-811", 1)
        v2.origen_venta = Venta.OrigenVenta.HONORARIOS
        v2.save(update_fields=["origen_venta"])

        r = resumen_honorarios(Venta.objects.filter(ejecutivo=self.ejecutivo))
        self.assertEqual(r["tipo"], "HONORARIOS")
        self.assertFalse(r["regla_kpi_configurada"])
        self.assertEqual(r["total_rgu"], 3)
        self.assertEqual(r["rgu_con_pago"], 2)
        self.assertEqual(r["rgu_sin_pago"], 1)
        self.assertEqual(r["pct_pago_referencial"], 66.7)

class AlcancePorRutEvtTests(KpiPorRguTests):
    def test_scope_ejecutivo_ignora_ce_claro(self):
        from .views import _scope_ventas_qs, _scope_cortes_qs

        ce = Ejecutivo.objects.create_user(
            rut="44444444-4", password="test12345", nombre="CE distinto"
        )
        venta = self._venta("1-900", 1)
        venta.ejecutivo_ce = ce
        venta.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        venta.save(update_fields=["ejecutivo_ce", "estado_instalacion"])
        corte = Corte.objects.create(
            venta=venta, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            meta_pct=Decimal("85"), estado_pago=Corte.EstadoPago.PAGADO,
            ejecutivo_kpi=ce, rgu_kpi=1,
        )

        self.assertTrue(_scope_ventas_qs(Venta.objects.all(), self.ejecutivo).filter(pk=venta.pk).exists())
        self.assertFalse(_scope_ventas_qs(Venta.objects.all(), ce).filter(pk=venta.pk).exists())
        self.assertTrue(_scope_cortes_qs(Corte.objects.all(), self.ejecutivo).filter(pk=corte.pk).exists())
        self.assertFalse(_scope_cortes_qs(Corte.objects.all(), ce).filter(pk=corte.pk).exists())

class FuenteVerdadEsacomDashboardTests(KpiPorRguTests):
    """Regresiones: ESACOM define dueño, vigencia de venta y RGU operativo."""

    def test_kpi_crm_usa_rgu_del_snapshot_claro(self):
        from .services import resumen_kpi

        venta = self._venta("1-CLARO-RGU", 2)
        venta.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        venta.save(update_fields=["estado_instalacion"])
        Corte.objects.create(
            venta=venta,
            mes_ano="2026-07",
            boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=9,
            es_medible=True,
            meta_pct=Decimal("0"),
        )
        # KPI CRM replica la ponderacion del snapshot Claro. El cierre Gerencia
        # usa RGU ESACOM por separado y esta cubierto por tests_cierres_gerencia_v4311.
        r = resumen_kpi(Corte.objects.filter(venta=venta))
        self.assertEqual(r["pagadas"], 9)
        self.assertEqual(r["total"], 9)
        self.assertEqual(r["pct_cumplimiento"], 100.0)

    def test_dashboard_excluye_ventas_anuladas(self):
        from integraciones.models import KPIRegistro
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import dashboard_kpi

        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI_TEST_SNAPSHOT.xlsx",
            fecha_corte=datetime.date(2026, 8, 24),
            dia_reporte=CargaExcel.DiaReporte.LUNES,
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            foco_b1="2026-07", foco_b2="2026-06", foco_b3="2026-05",
            meta_b1=Decimal("85"), meta_b2=Decimal("83"), meta_b3=Decimal("78"),
        )

        instalada = self._venta("1-INSTALADA", 2)
        instalada.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        instalada.save(update_fields=["estado_instalacion"])
        KPIRegistro.objects.create(
            carga=carga, venta=instalada, num_pedido=instalada.n_pedido,
            camada="2026-07", boleta="B1", rgu=2,
            estado_normalizado=Corte.EstadoPago.PAGADO, es_medible=True, cruce_ok=True,
        )

        anulada = self._venta("1-ANULADA", 8)
        anulada.estado_instalacion = Venta.EstadoInstalacion.ANULADO
        anulada.save(update_fields=["estado_instalacion"])
        KPIRegistro.objects.create(
            carga=carga, venta=anulada, num_pedido=anulada.n_pedido,
            camada="2026-07", boleta="B1", rgu=8,
            estado_normalizado=Corte.EstadoPago.PENDIENTE, es_medible=True, cruce_ok=True,
        )

        factory = APIRequestFactory()
        request = factory.get('/api/dashboard/kpi/')
        force_authenticate(request, user=self.ejecutivo)
        response = dashboard_kpi(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['cortes'][0]['pagadas'], 2)
        self.assertEqual(response.data['cortes'][0]['pendientes'], 0)


class SupervisorConsistenciaTests(KpiPorRguTests):
    def setUp(self):
        super().setUp()
        self.supervisor = Ejecutivo.objects.create_user(
            rut="22222222-2", password="test12345", nombre="Supervisor Test",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.otro_supervisor = Ejecutivo.objects.create_user(
            rut="33333333-3", password="test12345", nombre="Otro Supervisor",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.ejecutivo.supervisor = self.supervisor
        self.ejecutivo.save(update_fields=["supervisor"])

    def test_supervisor_solo_ve_equipo_directo(self):
        from .views import _scope_ventas_qs, _scope_cortes_qs

        propia = self._venta("1-SUP-01", 2)
        propia.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        propia.save(update_fields=["estado_instalacion"])
        corte = Corte.objects.create(
            venta=propia, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.PAGADO, rgu_kpi=2, es_medible=True,
            meta_pct=Decimal("0"),
        )

        ajeno_ej = Ejecutivo.objects.create_user(
            rut="44444444-4", password="test12345", nombre="Ejecutivo Ajeno",
            supervisor=self.otro_supervisor,
        )
        ajena = Venta.objects.create(
            rut_cliente="9999999-9", n_pedido="1-SUP-02", ejecutivo=ajeno_ej,
            promocion=self.promo, fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07", rgu_base=1,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )
        corte_ajeno = Corte.objects.create(
            venta=ajena, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.PAGADO, rgu_kpi=1, es_medible=True,
            meta_pct=Decimal("0"),
        )

        ventas_visibles = _scope_ventas_qs(Venta.objects.all(), self.supervisor)
        self.assertTrue(ventas_visibles.filter(pk=propia.pk).exists())
        self.assertFalse(ventas_visibles.filter(pk=ajena.pk).exists())

        cortes_visibles = _scope_cortes_qs(Corte.objects.all(), self.supervisor)
        self.assertTrue(cortes_visibles.filter(pk=corte.pk).exists())
        self.assertFalse(cortes_visibles.filter(pk=corte_ajeno.pk).exists())


    def test_resumen_equipo_cuenta_dotacion_asignada_aunque_no_tenga_ventas(self):
        from .views import resumen_equipo_view

        # Ejecutivo regular del setUp ya está asignado al Supervisor.
        honorario = Ejecutivo.objects.create_user(
            rut="55555555-5", password="test12345", nombre="Honorario sin ventas",
            supervisor=self.supervisor, tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS,
        )
        sin_ventas = Ejecutivo.objects.create_user(
            rut="66666666-6", password="test12345", nombre="Regular sin ventas",
            supervisor=self.supervisor, tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
        )

        factory = APIRequestFactory()
        request = factory.get('/api/equipo/resumen/')
        force_authenticate(request, user=self.supervisor)
        response = resumen_equipo_view(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["ejecutivos_asignados"], 3)
        self.assertEqual(response.data["ejecutivos_regulares"], 2)
        self.assertEqual(response.data["ejecutivos_honorarios"], 1)
        self.assertEqual(response.data["ejecutivos"], 3)

    def test_kpi_supervisor_coincide_con_portal_ejecutivo(self):
        from .services import resumen_cortes_actuales, resumen_por_ejecutivo_actual

        estados = [
            ("1-CAM-01", 2, Corte.EstadoPago.PAGADO),
            ("1-CAM-02", 3, Corte.EstadoPago.PENDIENTE),
            ("1-CAM-03", 1, Corte.EstadoPago.NO_PAGO),
        ]
        for pedido, rgu, estado in estados:
            v = self._venta(pedido, rgu)
            v.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
            v.save(update_fields=["estado_instalacion"])
            Corte.objects.create(
                venta=v, mes_ano="2026-07", boleta=Corte.Boleta.B1,
                estado_pago=estado, rgu_kpi=rgu, es_medible=True,
                meta_pct=Decimal("0"),
            )

        focos = {"B1": "2026-07", "B2": "", "B3": ""}
        metas = {"B1": Decimal("85"), "B2": None, "B3": None}
        cortes = Corte.objects.filter(venta__ejecutivo=self.ejecutivo)

        individual = resumen_cortes_actuales(cortes, focos=focos, metas=metas)[0]
        supervisor = resumen_por_ejecutivo_actual(cortes, focos=focos, metas=metas)[0]["cortes"][0]

        self.assertEqual(supervisor["pct_cumplimiento"], individual["pct_cumplimiento"])
        self.assertEqual(supervisor["pagadas"], individual["pagadas"])
        self.assertEqual(supervisor["pendientes"], individual["pendientes"])
        self.assertEqual(supervisor["faltan_para_meta"], individual["faltan_para_meta"])


    def test_dashboard_supervisor_consolidado_excluye_honorarios(self):
        from integraciones.models import KPIRegistro
        from .views import dashboard_kpi

        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI_TEST.xlsx",
            fecha_corte=datetime.date(2026, 8, 24),
            dia_reporte=CargaExcel.DiaReporte.LUNES,
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            foco_b1="2026-07", foco_b2="2026-06", foco_b3="2026-05",
            meta_b1=Decimal("85"), meta_b2=Decimal("83"), meta_b3=Decimal("78"),
        )
        regular = self.ejecutivo
        regular.tipo_kpi = Ejecutivo.TipoKPI.REGULAR
        regular.save(update_fields=["tipo_kpi"])
        honorario = Ejecutivo.objects.create_user(
            rut="55555555-5", password="test12345", nombre="Honorario KPI",
            supervisor=self.supervisor, tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS,
        )

        vr = self._venta("1-REG-AGG", 2)
        vr.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        vr.save(update_fields=["estado_instalacion"])
        KPIRegistro.objects.create(
            carga=carga, venta=vr, num_pedido=vr.n_pedido, camada="2026-07", boleta="B1",
            rgu=2, estado_normalizado=Corte.EstadoPago.PAGADO, es_medible=True, cruce_ok=True,
        )

        vh = Venta.objects.create(
            rut_cliente="9999999-8", n_pedido="1-HON-AGG", ejecutivo=honorario,
            promocion=self.promo, fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07", rgu_base=5,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )
        KPIRegistro.objects.create(
            carga=carga, venta=vh, num_pedido=vh.n_pedido, camada="2026-07", boleta="B1",
            rgu=5, estado_normalizado=Corte.EstadoPago.PAGADO, es_medible=True, cruce_ok=True,
        )

        factory = APIRequestFactory()
        request = factory.get('/api/dashboard/kpi/')
        force_authenticate(request, user=self.supervisor)
        response = dashboard_kpi(request)

        self.assertEqual(response.status_code, 200)
        b1 = next(x for x in response.data["cortes"] if x["boleta"] == "B1")
        self.assertEqual(b1["pagadas"], 2)
        self.assertEqual(b1["total"], 2)
        self.assertEqual(b1["pct_cumplimiento"], 100.0)


    def test_dashboard_gerencia_operacion_usa_solo_mes_y_base_vigente(self):
        from django.utils import timezone
        from .views import dashboard_gerencia

        gerencia = Ejecutivo.objects.create_user(
            rut="76767676-7", password="test12345", nombre="Gerencia Actual",
            cargo=Ejecutivo.Cargo.GERENCIA,
        )
        hoy = timezone.localdate()
        mes = hoy.strftime("%Y-%m")
        fecha = hoy.replace(day=1)

        Venta.objects.create(
            rut_cliente="10101010-1", n_pedido="ACTUAL-VIGENTE", ejecutivo=self.ejecutivo,
            promocion=self.promo, fecha_venta=fecha, camada=mes, rgu_base=2,
            origen_venta=Venta.OrigenVenta.BASE_VENTAS, en_base_vigente=True,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )
        # Misma camada pero ya fuera de la matriz ESACOM vigente: no debe
        # volver a inflar las tarjetas actuales de Gerencia.
        Venta.objects.create(
            rut_cliente="20202020-2", n_pedido="ACTUAL-HISTORICA", ejecutivo=self.ejecutivo,
            promocion=self.promo, fecha_venta=fecha, camada=mes, rgu_base=3,
            origen_venta=Venta.OrigenVenta.BASE_VENTAS, en_base_vigente=False,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )

        factory = APIRequestFactory()
        request = factory.get('/api/dashboard/gerencia/')
        force_authenticate(request, user=gerencia)
        response = dashboard_gerencia(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["operacion"]["mes_actual"], mes)
        self.assertEqual(response.data["operacion"]["clientes"], 1)
        self.assertEqual(response.data["operacion"]["instaladas"], 1)
        self.assertEqual(response.data["operacion"]["rgu_fijo_vendidos"], 2)

    def test_dashboard_gerencia_global_excluye_honorarios(self):
        from .views import dashboard_gerencia

        gerencia = Ejecutivo.objects.create_user(
            rut="77777777-7", password="test12345", nombre="Gerencia KPI",
            cargo=Ejecutivo.Cargo.GERENCIA,
        )
        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI_TEST_GERENCIA.xlsx",
            fecha_corte=datetime.date(2026, 8, 24),
            dia_reporte=CargaExcel.DiaReporte.LUNES,
            foco_b1="2026-07", foco_b2="2026-06", foco_b3="2026-05",
            meta_b1=Decimal("85"), meta_b2=Decimal("83"), meta_b3=Decimal("78"),
        )
        regular = self.ejecutivo
        regular.tipo_kpi = Ejecutivo.TipoKPI.REGULAR
        regular.save(update_fields=["tipo_kpi"])
        honorario = Ejecutivo.objects.create_user(
            rut="66666666-6", password="test12345", nombre="Honorario Global",
            supervisor=self.supervisor, tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS,
        )

        vr = self._venta("1-REG-GER", 3)
        vr.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        vr.save(update_fields=["estado_instalacion"])
        Corte.objects.create(
            venta=vr, carga_kpi=carga, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.PAGADO, rgu_kpi=3, es_medible=True,
            meta_pct=Decimal("0"),
        )
        vh = Venta.objects.create(
            rut_cliente="8888888-7", n_pedido="1-HON-GER", ejecutivo=honorario,
            promocion=self.promo, fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07", rgu_base=4,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )
        Corte.objects.create(
            venta=vh, carga_kpi=carga, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.NO_PAGO, rgu_kpi=4, es_medible=True,
            meta_pct=Decimal("0"),
        )

        # Un Ejecutivo REGULAR histórico/inactivo puede conservar ventas y
        # cortes KPI por trazabilidad, pero no pertenece a la dotación vigente
        # y no debe contaminar Gerencia.
        inactivo = Ejecutivo.objects.create_user(
            rut="88888888-8", password="test12345", nombre="Regular Histórico",
            supervisor=self.supervisor, tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
        )
        inactivo.is_active = False
        inactivo.save(update_fields=["is_active"])
        vi = Venta.objects.create(
            rut_cliente="7777777-6", n_pedido="1-INACT-GER", ejecutivo=inactivo,
            promocion=self.promo, fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07", rgu_base=6,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )
        Corte.objects.create(
            venta=vi, carga_kpi=carga, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.NO_PAGO, rgu_kpi=6, es_medible=True,
            meta_pct=Decimal("0"),
        )

        # Un SUPERVISOR puede conservar ventas históricas de cuando fue
        # Ejecutivo; tampoco debe entrar a la población KPI de Ejecutivos
        # Regular activos.
        vs = Venta.objects.create(
            rut_cliente="6666666-5", n_pedido="1-SUP-HIST-GER", ejecutivo=self.supervisor,
            promocion=self.promo, fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07", rgu_base=7,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )
        Corte.objects.create(
            venta=vs, carga_kpi=carga, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.NO_PAGO, rgu_kpi=7, es_medible=True,
            meta_pct=Decimal("0"),
        )

        factory = APIRequestFactory()
        request = factory.get('/api/dashboard/gerencia/')
        force_authenticate(request, user=gerencia)
        response = dashboard_gerencia(request)

        self.assertEqual(response.status_code, 200)
        b1 = next(x for x in response.data["global"] if x["boleta"] == "B1")
        self.assertEqual(b1["pagadas"], 3)
        self.assertEqual(b1["no_pago"], 0)
        self.assertEqual(b1["total"], 3)
        self.assertEqual(b1["pct_cumplimiento"], 100.0)
        nombres = {x["ejecutivo"]["nombre"] for x in response.data["ejecutivos"]}
        self.assertNotIn("Regular Histórico", nombres)
        self.assertNotIn(self.supervisor.nombre, nombres)


class SeguridadRolesApiTests(KpiPorRguTests):
    def setUp(self):
        super().setUp()
        self.supervisor = Ejecutivo.objects.create_user(
            rut="77777777-7", password="test12345", nombre="Supervisor Seguridad",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.gerencia = Ejecutivo.objects.create_user(
            rut="88888888-8", password="test12345", nombre="Gerencia Seguridad",
            cargo=Ejecutivo.Cargo.GERENCIA,
        )
        self.ejecutivo.supervisor = self.supervisor
        self.ejecutivo.save(update_fields=["supervisor"])

        venta = self._venta("1-SEC-01", 1)
        venta.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        venta.save(update_fields=["estado_instalacion"])
        self.corte = Corte.objects.create(
            venta=venta, mes_ano="2026-07", boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.NO_PAGO, rgu_kpi=1, es_medible=True,
            meta_pct=Decimal("0"),
        )
        from .models import Apelacion
        self.apelacion = Apelacion.objects.create(
            corte=self.corte, motivo=Apelacion.Motivo.ACREDITACION,
            estado=Apelacion.Estado.DETECTADA,
        )

    def test_supervisor_no_puede_enviar_apelacion_externamente(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import ApelacionViewSet

        request = APIRequestFactory().post(f"/api/apelaciones/{self.apelacion.pk}/enviar/")
        force_authenticate(request, user=self.supervisor)
        view = ApelacionViewSet.as_view({"post": "enviar"})
        response = view(request, pk=self.apelacion.pk)
        self.assertEqual(response.status_code, 403)

    def test_supervisor_no_puede_crear_apelacion_manual(self):
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import ApelacionViewSet

        request = APIRequestFactory().post("/api/apelaciones/", {"corte": self.corte.pk})
        force_authenticate(request, user=self.supervisor)
        view = ApelacionViewSet.as_view({"post": "create"})
        response = view(request)
        # Supervisor base no posee permiso de apelaciones: DRF bloquea antes
        # de entrar al create(), por lo que la respuesta correcta es 403.
        self.assertEqual(response.status_code, 403)


class AccionablesUniversoEsacomTests(KpiPorRguTests):
    def test_accionables_excluye_venta_no_instalada(self):
        from django.utils import timezone
        from .services import filtrar_cortes_kpi_operativos, resumen_accionables

        instalada = self._venta("1-ACC-1", 2)
        instalada.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        instalada.save(update_fields=["estado_instalacion"])

        pendiente = self._venta("1-ACC-2", 50)
        pendiente.estado_instalacion = Venta.EstadoInstalacion.PENDIENTE_INSTALACION
        pendiente.save(update_fields=["estado_instalacion"])

        vencimiento = timezone.localdate() - datetime.timedelta(days=1)
        for venta, rgu in ((instalada, 2), (pendiente, 50)):
            Corte.objects.create(
                venta=venta,
                mes_ano="2026-07",
                boleta=Corte.Boleta.B1,
                estado_pago=Corte.EstadoPago.PENDIENTE,
                es_medible=True,
                fecha_vencimiento=vencimiento,
                rgu_kpi=rgu,
                meta_pct=Decimal("0"),
            )

        cortes = filtrar_cortes_kpi_operativos(Corte.objects.filter(venta__ejecutivo=self.ejecutivo))
        data = resumen_accionables(cortes, focos={"B1": "2026-07"})
        self.assertEqual(data["vencidos"]["casos"], 1)
        self.assertEqual(data["vencidos"]["rgu"], 2)

    def test_filtro_operativo_es_el_mismo_universo_del_portal(self):
        from .services import filtrar_cortes_kpi_operativos

        instalada = self._venta("1-ACC-3", 1)
        instalada.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        instalada.save(update_fields=["estado_instalacion"])
        anulada = self._venta("1-ACC-4", 1)
        anulada.estado_instalacion = Venta.EstadoInstalacion.ANULADO
        anulada.save(update_fields=["estado_instalacion"])
        Corte.objects.create(venta=instalada, mes_ano="2026-07", boleta=Corte.Boleta.B1, meta_pct=Decimal("0"))
        Corte.objects.create(venta=anulada, mes_ano="2026-07", boleta=Corte.Boleta.B1, meta_pct=Decimal("0"))

        qs = filtrar_cortes_kpi_operativos(Corte.objects.filter(venta__ejecutivo=self.ejecutivo))
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().venta_id, instalada.id)


    def test_accionables_no_mezcla_snapshot_kpi_anterior(self):
        from django.utils import timezone
        from .services import filtrar_cortes_kpi_operativos, resumen_accionables
        from .views import _cortes_visibles

        carga_anterior = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI_ANTERIOR.xlsx",
        )

        carga_actual = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI_ACTUAL.xlsx",
        )

        venta_anterior = self._venta("1-ACC-HIST", 50)
        venta_anterior.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        venta_anterior.save(update_fields=["estado_instalacion"])

        venta_actual = self._venta("1-ACC-ACT", 2)
        venta_actual.estado_instalacion = Venta.EstadoInstalacion.INSTALADO
        venta_actual.save(update_fields=["estado_instalacion"])

        vencimiento = timezone.localdate() - datetime.timedelta(days=1)

        Corte.objects.create(
            venta=venta_anterior,
            carga_kpi=carga_anterior,
            mes_ano="2026-07",
            boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.PENDIENTE,
            es_medible=True,
            fecha_vencimiento=vencimiento,
            rgu_kpi=50,
            meta_pct=Decimal("85"),
        )

        Corte.objects.create(
            venta=venta_actual,
            carga_kpi=carga_actual,
            mes_ano="2026-07",
            boleta=Corte.Boleta.B1,
            estado_pago=Corte.EstadoPago.PENDIENTE,
            es_medible=True,
            fecha_vencimiento=vencimiento,
            rgu_kpi=2,
            meta_pct=Decimal("85"),
        )

        cortes = _cortes_visibles(
            self.ejecutivo,
            carga_kpi=carga_actual,
        )

        cortes = filtrar_cortes_kpi_operativos(cortes)

        data = resumen_accionables(
            cortes,
            focos={"B1": "2026-07"},
        )

        self.assertEqual(data["vencidos"]["casos"], 1)
        self.assertEqual(data["vencidos"]["rgu"], 2)

class HonorariosCalidadYProduccionTests(TestCase):
    def setUp(self):
        self.supervisor = Ejecutivo.objects.create_user(
            rut="22222222-2", password="test12345", nombre="Supervisor Honorarios",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.honorario = Ejecutivo.objects.create_user(
            rut="33333333-3", password="test12345", nombre="Max Negri Test",
            cargo=Ejecutivo.Cargo.EJECUTIVO, tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS,
            supervisor=self.supervisor,
        )
        self.promo = Promocion.objects.create(
            nombre="Promo Honorarios", rgu=1, empresa=Promocion.Empresa.CLARO
        )

    def _venta(self, pedido, rgu, camada="2026-07", origen=Venta.OrigenVenta.HONORARIOS):
        return Venta.objects.create(
            rut_cliente=f"{pedido[-6:]}-K",
            n_pedido=pedido,
            ejecutivo=self.honorario,
            promocion=self.promo,
            fecha_venta=datetime.date(2026, 7, 1),
            camada=camada,
            rgu_base=rgu,
            origen_venta=origen,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
        )

    def test_kpi_honorarios_informa_pago_sin_meta_regular(self):
        from integraciones.models import KPIRegistro
        from .views import _resumen_par_snapshot_usuario

        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="CIERRE_FIJO_HON.xlsx",
            fecha_corte=datetime.date(2026, 8, 31),
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=CargaExcel.EstadoReporte.CIERRE,
            formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
            foco_b1="2026-07", foco_b2="2026-06", foco_b3="2026-05",
        )
        datos = [
            ("1-HON-PAGO", 111, Corte.EstadoPago.PAGADO, True),
            ("1-HON-NOPAGO", 9, Corte.EstadoPago.NO_PAGO, True),
            ("1-HON-FUERA", 5, Corte.EstadoPago.FUERA_PLAZO, True),
            ("1-HON-SB", 1, Corte.EstadoPago.SIN_BOLETA, True),
        ]
        for pedido, rgu, estado, medible in datos:
            venta = self._venta(pedido, rgu)
            KPIRegistro.objects.create(
                carga=carga, venta=venta, num_pedido=pedido, camada="2026-07", boleta="B1",
                rgu=rgu, estado_normalizado=estado, es_medible=medible, cruce_ok=True,
            )

        r = _resumen_par_snapshot_usuario(self.honorario, "B1", "2026-07", carga=carga)
        self.assertEqual(r["pagadas"], 111)
        self.assertEqual(r["no_pago"], 9)
        self.assertEqual(r["fuera_plazo"], 5)
        self.assertEqual(r["sin_boleta"], 1)
        self.assertEqual(r["total"], 126)
        self.assertEqual(r["pct_cumplimiento"], 88.10)
        self.assertFalse(r["meta_definida"])
        self.assertEqual(r["meta_pct"], 0.0)
        self.assertIsNone(r["faltan_para_meta"])
        self.assertEqual(r["perfil_kpi"], "HONORARIOS")
        self.assertEqual(r["fuente_formato"], "CIERRE_FIJO")

    def test_produccion_mes_incluye_ventas_honorarios_esacom(self):
        from .produccion import resumen_produccion_mes

        self._venta("1-HON-SEP", 2, camada="2026-09")
        r = resumen_produccion_mes(mes="2026-09", ejecutivo=self.honorario)
        self.assertEqual(r["ventas_fijo"], 1)
        self.assertEqual(r["rgu_fijo_vendidos"], 2)
        self.assertEqual(r["rgu_fijo_gestionables"], 2)
        self.assertTrue(r["disponible"])

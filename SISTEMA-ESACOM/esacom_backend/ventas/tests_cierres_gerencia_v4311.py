import datetime

from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.views import (
    _cierres_oficiales_canal,
    dashboard_gerencia_cierre_detalle,
    dashboard_gerencia_cierres,
)


class CierresGerenciaV4311Tests(TestCase):
    def setUp(self):
        self.gerencia = Ejecutivo.objects.create_user(
            rut="11111111-1",
            nombre="Gerencia Cierres",
            password="Clave12345!",
            cargo=Ejecutivo.Cargo.GERENCIA,
        )
        self.factory = APIRequestFactory()

    def _carga(self, *, estado, formato, corte, b1="", b2="", b3=""):
        return CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre=f"{formato}-{corte}.xlsx",
            fecha_corte=corte,
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=estado,
            formato_kpi=formato,
            foco_b1=b1,
            foco_b2=b2,
            foco_b3=b3,
            avance_b1=100,
            avance_b2=95,
            avance_b3=90,
            meta_b1=85,
            meta_b2=83,
            meta_b3=78,
        )

    def test_avance_no_cierra_mes_y_cierre_fijo_si(self):
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            formato=CargaExcel.FormatoKPI.DETALLADO,
            corte=datetime.date(2026, 9, 15),
            b1="2026-08",
        )
        cierre = self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
            corte=datetime.date(2026, 8, 31),
            b1="2026-07",
        )
        mapa = _cierres_oficiales_canal("FIJO")
        self.assertNotIn("2026-08", mapa)
        self.assertEqual(mapa["2026-07"]["carga"].id, cierre.id)

    def test_primer_cierre_del_mes_permanece_congelado(self):
        primero = self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
            corte=datetime.date(2026, 8, 31),
            b1="2026-07",
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
            corte=datetime.date(2026, 9, 20),
            b2="2026-07",
        )
        self.assertEqual(_cierres_oficiales_canal("FIJO")["2026-07"]["carga"].id, primero.id)

    def test_fijo_y_movil_no_se_mezclan(self):
        fijo = self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
            corte=datetime.date(2026, 8, 31),
            b1="2026-07",
        )
        movil = self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            formato=CargaExcel.FormatoKPI.CIERRE_MOVIL,
            corte=datetime.date(2026, 8, 31),
            b1="2026-06",
        )
        self.assertEqual(_cierres_oficiales_canal("FIJO")["2026-07"]["carga"].id, fijo.id)
        self.assertNotIn("2026-06", _cierres_oficiales_canal("FIJO"))
        self.assertEqual(_cierres_oficiales_canal("MOVIL")["2026-06"]["carga"].id, movil.id)

    def test_endpoint_muestra_periodo_abierto_y_cierres(self):
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            formato=CargaExcel.FormatoKPI.DETALLADO,
            corte=datetime.date(2026, 9, 15),
            b1="2026-08", b2="2026-07", b3="2026-06",
        )
        self._carga(
            estado=CargaExcel.EstadoReporte.CIERRE,
            formato=CargaExcel.FormatoKPI.CIERRE_FIJO,
            corte=datetime.date(2026, 8, 31),
            b1="2026-07", b2="2026-06", b3="2026-05",
        )
        request = self.factory.get("/api/dashboard/gerencia/cierres/?canal=FIJO")
        force_authenticate(request, user=self.gerencia)
        response = dashboard_gerencia_cierres(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["actual"]["mes_ano"], "2026-08")
        self.assertEqual([x["mes_ano"] for x in response.data["cierres"]], ["2026-07", "2026-06", "2026-05"])
        self.assertTrue(all(x["estado"] == "CIERRE_OFICIAL" for x in response.data["cierres"]))

    def test_detalle_rechaza_mes_sin_cierre(self):
        self._carga(
            estado=CargaExcel.EstadoReporte.AVANCE,
            formato=CargaExcel.FormatoKPI.DETALLADO,
            corte=datetime.date(2026, 9, 15),
            b1="2026-08",
        )
        request = self.factory.get("/api/dashboard/gerencia/cierres/FIJO/2026-08/")
        force_authenticate(request, user=self.gerencia)
        response = dashboard_gerencia_cierre_detalle(request, "FIJO", "2026-08")
        self.assertEqual(response.status_code, 404)


class CierreFijoPlanillaSnapshotTests(TestCase):
    """La planilla Gerencia usa población ESACOM histórica, no el filtro CRM."""

    def setUp(self):
        from catalogos.models import Promocion
        from integraciones.models import KPIRegistro
        from ventas.models import Venta, VentaFijaFuente

        self.KPIRegistro = KPIRegistro
        self.Venta = Venta
        self.VentaFijaFuente = VentaFijaFuente
        self.promo = Promocion.objects.create(
            nombre="PROMO CIERRE R23", rgu=1, empresa=Promocion.Empresa.CLARO
        )
        self.carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI_CIERRE_R23.xlsx",
            fecha_corte=datetime.date(2026, 8, 31),
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            estado_reporte=CargaExcel.EstadoReporte.CIERRE,
            formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
            foco_b1="2026-07",
            avance_b1=103.40,
            meta_b1=85,
        )

    def _fila(self, *, idx, pedido, rgu, nombre, rut, estado_kpi=None, activo=True, tipo="REGULAR", supervisor="Charly Estay", supervisor_kpi=None, medible=True):
        from ventas.models import Venta, VentaFijaFuente, Corte

        ejecutivo = Ejecutivo.objects.create(
            rut=rut,
            nombre=nombre,
            cargo=Ejecutivo.Cargo.EJECUTIVO,
            tipo_kpi=tipo,
            is_active=activo,
        )
        venta = Venta.objects.create(
            rut_cliente=f"{idx}-9",
            n_pedido=pedido,
            rut_evt=rut,
            nombre_evt=nombre,
            supervisor_fuente=supervisor,
            estado_instalacion_fuente="Completada",
            rgu_base=rgu,
            ejecutivo=ejecutivo,
            promocion=self.promo,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
            fecha_venta=datetime.date(2026, 7, 1),
            fecha_cierre=datetime.date(2026, 7, 20),
            camada="2026-07",
            en_base_vigente=True,
        )
        VentaFijaFuente.objects.create(
            fila_fuente=idx,
            en_base_vigente=True,
            n_pedido=pedido,
            rut_evt=rut,
            nombre_evt=nombre,
            supervisor_fuente=supervisor,
            estado_instalacion_fuente="Completada",
            rgu_base=rgu,
            fecha_venta=datetime.date(2026, 7, 1),
            promocion_fuente=self.promo.nombre,
            ejecutivo=ejecutivo,
            venta=venta,
        )
        if estado_kpi is not None:
            mapa_estado = {
                "Pago": Corte.EstadoPago.PAGADO,
                "No Pago": Corte.EstadoPago.NO_PAGO,
                "Pendiente": Corte.EstadoPago.PENDIENTE,
                "S/B": Corte.EstadoPago.SIN_BOLETA,
                "Pagado Fuera de Plazo": Corte.EstadoPago.FUERA_PLAZO,
            }
            self.KPIRegistro.objects.create(
                carga=self.carga,
                venta=venta,
                num_pedido=pedido,
                camada="2026-07",
                boleta="B1",
                rgu=99,  # Debe ignorarse: planilla usa RGU ESACOM de la fila.
                kpi_texto=estado_kpi,
                estado_normalizado=mapa_estado[estado_kpi],
                supervisor_fuente=(supervisor if supervisor_kpi is None else supervisor_kpi),
                es_medible=medible,
                cruce_ok=True,
            )
        return venta

    def test_planilla_incluye_inactivos_honorarios_no_medibles_y_nd(self):
        from integraciones.cierre_fijo_snapshot import (
            asegurar_snapshot_cierre_fijo,
            desglose_snapshot_cierre_fijo,
        )

        self._fila(idx=10, pedido="P-PAGO", rgu=2, nombre="Activo", rut="10000001-1", estado_kpi="Pago")
        self._fila(idx=11, pedido="P-NP", rgu=3, nombre="Historico", rut="10000002-2", estado_kpi="No Pago", activo=False, medible=False)
        self._fila(idx=12, pedido="P-SB", rgu=4, nombre="Honorario", rut="10000003-3", estado_kpi="S/B", tipo=Ejecutivo.TipoKPI.HONORARIOS)
        self._fila(idx=13, pedido="P-ND", rgu=5, nombre="Sin Claro", rut="10000004-4", estado_kpi=None)
        self._fila(idx=14, pedido="P-PEND", rgu=6, nombre="Pendiente", rut="10000005-5", estado_kpi="Pendiente")
        self._fila(idx=15, pedido="P-FUERA", rgu=7, nombre="Fuera", rut="10000006-6", estado_kpi="Pagado Fuera de Plazo")

        self.assertEqual(asegurar_snapshot_cierre_fijo(self.carga, "B1", "2026-07"), 6)
        supervisores, ejecutivos, global_, filas = desglose_snapshot_cierre_fijo(self.carga, "B1", "2026-07")

        self.assertEqual(len(filas), 6)
        self.assertEqual(len(ejecutivos), 6)
        self.assertEqual(len(supervisores), 1)
        self.assertEqual(global_["pagadas"], 2)
        self.assertEqual(global_["no_pago"], 3)
        self.assertEqual(global_["sin_boleta"], 4)
        self.assertEqual(global_["n_d"], 5)
        self.assertEqual(global_["pendientes"], 6)
        self.assertEqual(global_["fuera_plazo"], 7)
        self.assertEqual(global_["total_general"], 27)
        self.assertEqual(global_["kpi_pct"], 7.41)

    def test_snapshot_no_cambia_si_la_fuente_operacional_cambia(self):
        from integraciones.cierre_fijo_snapshot import (
            asegurar_snapshot_cierre_fijo,
            desglose_snapshot_cierre_fijo,
        )

        self._fila(idx=20, pedido="P-FREEZE", rgu=3, nombre="Congelado", rut="10000007-7", estado_kpi="Pago")
        asegurar_snapshot_cierre_fijo(self.carga, "B1", "2026-07")
        _, _, antes, _ = desglose_snapshot_cierre_fijo(self.carga, "B1", "2026-07")

        self.VentaFijaFuente.objects.all().delete()
        _, _, despues, _ = desglose_snapshot_cierre_fijo(self.carga, "B1", "2026-07")
        self.assertEqual(antes, despues)
        self.assertEqual(despues["pagadas"], 3)
        self.assertEqual(despues["total_general"], 3)
    def test_r26_supervisor_esacom_gana_y_pedido_duplicado_no_duplica(self):
        from integraciones.cierre_fijo_snapshot import desglose_snapshot_cierre_fijo
        from ventas.models import Venta, VentaFijaFuente

        venta = self._fila(
            idx=100, pedido="P-HIST", rgu=2, nombre="Ejecutivo Historico",
            rut="10000008-8", estado_kpi="Pago", supervisor="Claudio Torres",
            supervisor_kpi="Charly Estay",
        )
        # Reingreso operacional del mismo pedido: no puede duplicar el cierre.
        VentaFijaFuente.objects.create(
            fila_fuente=101, en_base_vigente=True, n_pedido="P-HIST",
            rut_evt=venta.rut_evt, nombre_evt=venta.nombre_evt,
            supervisor_fuente="", estado_instalacion_fuente="Completada",
            rgu_base=2, fecha_venta=datetime.date(2026, 7, 2),
            promocion_fuente=self.promo.nombre, ejecutivo=venta.ejecutivo, venta=venta,
        )
        # Una fila sin cruce conserva supervisor operacional, pero debe quedar
        # con el supervisor historico dominante del mismo Ejecutivo.
        venta_nd = Venta.objects.create(
            rut_cliente="102-9", n_pedido="P-HIST-ND", rut_evt=venta.rut_evt,
            nombre_evt=venta.nombre_evt, supervisor_fuente="Claudio Torres",
            estado_instalacion_fuente="Completada", rgu_base=1,
            ejecutivo=venta.ejecutivo, promocion=self.promo,
            estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
            fecha_venta=datetime.date(2026, 7, 3),
            fecha_cierre=datetime.date(2026, 7, 21), camada="2026-07",
            en_base_vigente=True,
        )
        VentaFijaFuente.objects.create(
            fila_fuente=102, en_base_vigente=True, n_pedido="P-HIST-ND",
            rut_evt=venta.rut_evt, nombre_evt=venta.nombre_evt,
            supervisor_fuente="Claudio Torres", estado_instalacion_fuente="Completada",
            rgu_base=1, fecha_venta=datetime.date(2026, 7, 3),
            promocion_fuente=self.promo.nombre, ejecutivo=venta.ejecutivo, venta=venta_nd,
        )

        supervisores, ejecutivos, global_, filas = desglose_snapshot_cierre_fijo(
            self.carga, "B1", "2026-07"
        )
        self.assertEqual(len(filas), 2)
        self.assertEqual(global_["pagadas"], 2)
        self.assertEqual(global_["n_d"], 1)
        self.assertEqual(global_["total_general"], 3)
        self.assertEqual(len(ejecutivos), 1)
        # Claro no define el supervisor de la planilla: manda ESACOM.
        self.assertEqual(ejecutivos[0]["supervisor"], "Claudio Torres")
        self.assertEqual([x["nombre"] for x in supervisores], ["Claudio Torres"])
        self.assertEqual(supervisores[0]["planilla_cierre"]["total_general"], 3)

    def test_r26_estado_fuente_vacio_no_entra_aunque_venta_este_instalada(self):
        from integraciones.cierre_fijo_snapshot import asegurar_snapshot_cierre_fijo
        from integraciones.models import KPICierreFijoFila
        from ventas.models import Venta, VentaFijaFuente

        venta = self._fila(
            idx=200, pedido="P-OK", rgu=2, nombre="Completado",
            rut="10000009-9", estado_kpi="Pago", supervisor="Charly Estay",
        )
        ejecutivo = Ejecutivo.objects.create(
            rut="10000010-0", nombre="Normalizado sin fuente",
            cargo=Ejecutivo.Cargo.EJECUTIVO, tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
        )
        venta_vacia = Venta.objects.create(
            rut_cliente="200-9", n_pedido="P-VACIO", rut_evt=ejecutivo.rut,
            nombre_evt=ejecutivo.nombre, supervisor_fuente="Charly Estay",
            estado_instalacion_fuente="", rgu_base=1, ejecutivo=ejecutivo,
            promocion=self.promo, estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
            fecha_venta=datetime.date(2026, 7, 2),
            fecha_cierre=datetime.date(2026, 7, 22), camada="2026-07",
            en_base_vigente=True,
        )
        VentaFijaFuente.objects.create(
            fila_fuente=201, en_base_vigente=True, n_pedido="P-VACIO",
            rut_evt=ejecutivo.rut, nombre_evt=ejecutivo.nombre,
            supervisor_fuente="Charly Estay", estado_instalacion_fuente="",
            rgu_base=1, fecha_venta=datetime.date(2026, 7, 2),
            promocion_fuente=self.promo.nombre, ejecutivo=ejecutivo, venta=venta_vacia,
        )

        asegurar_snapshot_cierre_fijo(self.carga, "B1", "2026-07")
        filas = KPICierreFijoFila.objects.filter(carga=self.carga, camada="2026-07", boleta="B1")
        self.assertEqual(filas.count(), 1)
        self.assertEqual(filas.first().n_pedido, "P-OK")
        self.assertEqual(filas.first().rgu, 2)


    def test_r28_alias_supervisor_historico_no_usa_supervisor_actual_del_ejecutivo(self):
        from integraciones.cierre_fijo_snapshot import _supervisor_historico_canonico

        charly = Ejecutivo.objects.create(
            rut="17480807-4", nombre="CHARLY FABIAN ESTAY LAZO",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        jorge = Ejecutivo.objects.create(
            rut="99999991-1", nombre="JORGE ANTONIO HERNANDEZ URETA",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        claudia = Ejecutivo.objects.create(
            rut="15559883-2", nombre="CLAUDIA ALEXANDRA VEGA LILLO",
            cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=charly,
        )

        # Aunque hoy Claudia figure bajo Charly, Julio conserva Jorge porque
        # esa es la etiqueta historica grabada en la venta ESACOM.
        self.assertEqual(
            _supervisor_historico_canonico("Jorge Hernandez", ejecutivo=claudia),
            jorge.nombre,
        )

    def test_r28_jefatura_intermedia_historica_se_enrolla_al_supervisor_real(self):
        from integraciones.cierre_fijo_snapshot import _supervisor_historico_canonico

        charly = Ejecutivo.objects.create(
            rut="17480807-4", nombre="CHARLY FABIAN ESTAY LAZO",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        claudio = Ejecutivo.objects.create(
            rut="17806413-4", nombre="CLAUDIO ANTONIO TORRES ASTUDILLO",
            cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=charly,
        )

        # La hoja historica puede decir "Claudio Torres", pero Claudio no es
        # un supervisor CRM: sus ventas se consolidan bajo su supervisor real.
        self.assertEqual(
            _supervisor_historico_canonico("Claudio Torres", ejecutivo=claudio),
            charly.nombre,
        )

    def test_r28_alias_corto_del_supervisor_se_canoniza_sin_partir_equipo(self):
        from integraciones.cierre_fijo_snapshot import _supervisor_historico_canonico

        patricio = Ejecutivo.objects.create(
            rut="17790237-3", nombre="PATRICIO ALEJANDRO GUERRA NUÑEZ",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.assertEqual(
            _supervisor_historico_canonico("Patricio Guerra"),
            patricio.nombre,
        )

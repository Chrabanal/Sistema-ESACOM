import datetime

from django.test import TestCase

from catalogos.models import Promocion
from integraciones.models import CargaExcel, KPIRegistro, KPICierreFijoFila
from usuarios.models import Ejecutivo
from ventas.models import Corte, Venta
from ventas.views import _resumen_mes_kpi_usuario, _resumen_par_snapshot_usuario


class SnapshotEsacomInmutableR217Tests(TestCase):
    def setUp(self):
        self.supervisor = Ejecutivo.objects.create_user(
            rut="22222222-2", password="test12345", nombre="Supervisor Original",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.supervisor_nuevo = Ejecutivo.objects.create_user(
            rut="33333333-3", password="test12345", nombre="Supervisor Nuevo",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="11111111-1", password="test12345", nombre="Ejecutivo Snapshot",
            cargo=Ejecutivo.Cargo.EJECUTIVO, tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
            supervisor=self.supervisor,
        )
        self.promo = Promocion.objects.create(
            nombre="Promo Snapshot", rgu=9, empresa=Promocion.Empresa.CLARO
        )
        self.venta = Venta.objects.create(
            rut_cliente="99999999-9", n_pedido="SNAP-001", rut_evt=self.ejecutivo.rut,
            nombre_evt=self.ejecutivo.nombre, ejecutivo=self.ejecutivo,
            promocion=self.promo, fecha_venta=datetime.date(2026, 9, 1), camada="2026-09",
            rgu_base=2, estado_instalacion=Venta.EstadoInstalacion.INSTALADO,
            supervisor_fuente=self.supervisor.nombre,
        )
        self.carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI28092026 ESACOM.xlsx",
            fecha_corte=datetime.date(2026, 9, 28),
            estado_reporte=CargaExcel.EstadoReporte.AVANCE,
            formato_kpi=CargaExcel.FormatoKPI.DETALLADO,
            foco_b1="2026-08",
        )

    def snapshot(self, *, rgu=2):
        return {
            "venta_id": self.venta.id,
            "estado_instalacion": Venta.EstadoInstalacion.INSTALADO,
            "conflicto_fuente": False,
            "rgu": rgu,
            "rut_evt": self.ejecutivo.rut,
            "nombre_evt": self.ejecutivo.nombre,
            "supervisor_fuente": self.supervisor.nombre,
            "ejecutivo_id": self.ejecutivo.id,
            "ejecutivo_rut": self.ejecutivo.rut,
            "ejecutivo_nombre": self.ejecutivo.nombre,
            "tipo_kpi": Ejecutivo.TipoKPI.REGULAR,
            "cargo": Ejecutivo.Cargo.EJECUTIVO,
            "ejecutivo_activo": True,
            "supervisor_id": self.supervisor.id,
            "supervisor_rut": self.supervisor.rut,
            "supervisor_nombre": self.supervisor.nombre,
        }

    def test_sync_posterior_no_cambia_poblacion_ni_rgu_del_avance(self):
        KPIRegistro.objects.create(
            carga=self.carga, venta=self.venta, num_pedido=self.venta.n_pedido,
            camada="2026-09", boleta="B1", rgu=9,
            estado_normalizado=Corte.EstadoPago.PAGADO, es_medible=True,
            marca_mes_kpi=1, cruce_ok=True, snapshot_esacom=self.snapshot(rgu=2),
        )
        antes = _resumen_par_snapshot_usuario(self.ejecutivo, "B1", "2026-09", carga=self.carga)
        self.assertEqual(antes["pagadas"], 2)
        self.assertEqual(antes["total"], 2)

        # Simula una sincronización ESACOM posterior: cambia estado, RGU,
        # supervisor y actividad actual. El reporte 28/09 no debe moverse.
        self.venta.rgu_base = 7
        self.venta.estado_instalacion = Venta.EstadoInstalacion.ANULADO
        self.venta.save(update_fields=["rgu_base", "estado_instalacion"])
        self.ejecutivo.supervisor = self.supervisor_nuevo
        self.ejecutivo.is_active = False
        self.ejecutivo.save(update_fields=["supervisor", "is_active"])

        despues = _resumen_par_snapshot_usuario(self.ejecutivo, "B1", "2026-09", carga=self.carga)
        self.assertEqual(despues["pagadas"], 2)
        self.assertEqual(despues["total"], 2)
        self.assertEqual(despues["pct_cumplimiento"], 100.0)

    def test_correccion_andes_cambia_estado_sin_cambiar_poblacion(self):
        KPIRegistro.objects.create(
            carga=self.carga, venta=self.venta, num_pedido=self.venta.n_pedido,
            camada="2026-09", boleta="B1", rgu=9,
            estado_normalizado=Corte.EstadoPago.FUERA_PLAZO, es_medible=True,
            marca_mes_kpi=1, cruce_ok=True, snapshot_esacom=self.snapshot(rgu=2),
        )
        Corte.objects.create(
            venta=self.venta, carga_kpi=self.carga, mes_ano="2026-09", boleta="B1",
            estado_pago=Corte.EstadoPago.PAGADO, estado_claro=Corte.EstadoPago.FUERA_PLAZO,
            es_medible=True, rgu_kpi=9, verificado_en_andes=True,
        )
        resumen = _resumen_par_snapshot_usuario(self.ejecutivo, "B1", "2026-09", carga=self.carga)
        self.assertEqual(resumen["pagadas"], 2)
        self.assertEqual(resumen["fuera_plazo"], 0)
        self.assertEqual(resumen["total"], 2)

    def test_cierre_oficial_lee_kpicierrefijofila_y_no_venta_actual(self):
        cierre = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI01092026 ESACOM.xlsx",
            fecha_corte=datetime.date(2026, 8, 31),
            estado_reporte=CargaExcel.EstadoReporte.CIERRE,
            formato_kpi=CargaExcel.FormatoKPI.CIERRE_FIJO,
            foco_b1="2026-07",
        )
        KPICierreFijoFila.objects.create(
            carga=cierre, camada="2026-07", boleta="B1", fila_fuente=1,
            n_pedido="JUL-1", rut_evt=self.ejecutivo.rut, nombre_evt=self.ejecutivo.nombre,
            supervisor_fuente=self.supervisor.nombre, tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
            rgu=3, estado_kpi="Pago", categoria=KPICierreFijoFila.Categoria.PAGO,
        )
        KPICierreFijoFila.objects.create(
            carga=cierre, camada="2026-07", boleta="B1", fila_fuente=2,
            n_pedido="JUL-2", rut_evt=self.ejecutivo.rut, nombre_evt=self.ejecutivo.nombre,
            supervisor_fuente=self.supervisor.nombre, tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
            rgu=1, estado_kpi="No Pago", categoria=KPICierreFijoFila.Categoria.NO_PAGO,
        )
        # La venta viva puede cambiar; el cierre oficial no.
        self.venta.estado_instalacion = Venta.EstadoInstalacion.ANULADO
        self.venta.rgu_base = 99
        self.venta.save(update_fields=["estado_instalacion", "rgu_base"])

        resumen = _resumen_mes_kpi_usuario(self.ejecutivo, "2026-07", en_curso=False)
        self.assertEqual(resumen["pagadas"], 3)
        self.assertEqual(resumen["no_pago"], 1)
        self.assertEqual(resumen["total"], 4)
        self.assertTrue(resumen["cierre_oficial"])

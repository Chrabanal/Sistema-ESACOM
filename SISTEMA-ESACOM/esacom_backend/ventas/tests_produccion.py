from datetime import date

from django.test import TestCase

from catalogos.models import Promocion
from usuarios.models import Ejecutivo
from ventas.models import Venta, VentaMovil
from ventas.produccion import (
    clasificar_movil_produccion,
    detalle_produccion_actual,
    resumen_produccion_actual,
    resumen_produccion_mes,
)


class ProduccionActualTests(TestCase):
    def setUp(self):
        self.supervisor = Ejecutivo.objects.create_user(
            rut="17480807-4", password="test", nombre="Charly Estay", cargo=Ejecutivo.Cargo.SUPERVISOR
        )
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="19665650-2", password="test", nombre="Sergio Agustin Osses Labra",
            cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=self.supervisor,
        )
        self.promo = Promocion.objects.create(nombre="VTR TEST", empresa=Promocion.Empresa.VTR)

    def _fija(self, pedido, estado_fuente, estado, vigente=True, rgu=1):
        return Venta.objects.create(
            rut_cliente="11111111-1", n_pedido=pedido, rut_evt=self.ejecutivo.rut,
            nombre_evt=self.ejecutivo.nombre, supervisor_fuente="Charly Estay",
            estado_instalacion_fuente=estado_fuente, hoja_fuente="Base de Ventas",
            en_base_vigente=vigente, ejecutivo=self.ejecutivo, promocion=self.promo,
            tipo_cliente=Venta.TipoCliente.B2C, estado_instalacion=estado,
            fecha_venta=date(2026, 8, 20), camada="2026-08", rgu_base=rgu,
        )

    def _movil(self, clave, tipo, vigente=True, efectiva=True, estado=None, fecha_activacion=None):
        if efectiva:
            estado = "PORTADO" if estado is None else estado
            fecha_activacion = date(2026, 8, 21) if fecha_activacion is None else fecha_activacion
        else:
            estado = "" if estado is None else estado
        return VentaMovil.objects.create(
            clave_origen=clave, rut_cliente="11111111-1", supervisor_fuente="Charly Estay",
            nombre_evt=self.ejecutivo.nombre, rut_evt=self.ejecutivo.rut, ejecutivo=self.ejecutivo,
            tipo_linea=tipo, pcs=f"569000000{clave[-1]}", fecha_venta=date(2026, 8, 20),
            fecha_activacion=fecha_activacion, estado=estado,
            camada="2026-08", hoja_fuente="Ventas Móvil", en_base_vigente=vigente,
        )

    def test_produccion_actual_usa_rgu_y_separa_vigente_de_historico(self):
        self._fija("1", "Completada", Venta.EstadoInstalacion.INSTALADO, rgu=2)
        self._fija("2", "Completada", Venta.EstadoInstalacion.INSTALADO, rgu=1)
        self._fija("3", "Pendiente Instalación", Venta.EstadoInstalacion.PENDIENTE_INSTALACION, rgu=3)
        self._fija("4", "Anulado", Venta.EstadoInstalacion.ANULADO, rgu=2)
        self._fija("5", "Completada", Venta.EstadoInstalacion.INSTALADO, vigente=False, rgu=9)
        self._movil("a1", VentaMovil.TipoLinea.PRINCIPAL)
        self._movil("a2", VentaMovil.TipoLinea.ADICIONAL)
        self._movil("a3", VentaMovil.TipoLinea.PPM)
        self._movil("a4", VentaMovil.TipoLinea.PRINCIPAL, vigente=False)

        r = resumen_produccion_actual(ejecutivo=self.ejecutivo)
        self.assertEqual(r["fija"]["completadas"], 3)  # RGU, no filas
        self.assertEqual(r["fija"]["pendiente_instalacion"], 3)
        self.assertEqual(r["fija"]["anuladas"], 2)
        self.assertEqual(r["fija"]["total_control"], 6)
        self.assertEqual(r["fija"]["ventas_completadas"], 2)
        self.assertEqual(r["fija"]["ventas_pendiente_instalacion"], 1)
        self.assertEqual(r["fija"]["total_control_ventas"], 3)
        self.assertEqual(r["fija"]["total_base_vigente"], 4)
        self.assertEqual(r["movil"]["principal"], 1)
        self.assertEqual(r["movil"]["adicional"], 1)
        self.assertEqual(r["movil"]["ppm"], 1)
        self.assertEqual(r["movil"]["total"], 3)
        self.assertEqual(r["total_produccion"], 9)


    def test_produccion_mes_separa_fijo_rgu_y_movil_portadas(self):
        self._fija("m1", "Completada", Venta.EstadoInstalacion.INSTALADO, rgu=2)
        self._fija("m2", "Pendiente Instalación", Venta.EstadoInstalacion.PENDIENTE_INSTALACION, rgu=3)
        self._fija("m8", "Anulado", Venta.EstadoInstalacion.ANULADO, rgu=1)
        anterior = self._fija("m3", "Completada", Venta.EstadoInstalacion.INSTALADO, rgu=9)
        anterior.fecha_venta = date(2026, 7, 20)
        anterior.camada = "2026-07"
        anterior.save(update_fields=["fecha_venta", "camada"])

        self._movil("m4", VentaMovil.TipoLinea.PRINCIPAL)
        self._movil("m5", VentaMovil.TipoLinea.ADICIONAL)
        self._movil("m6", VentaMovil.TipoLinea.PPM)
        movil_anterior = self._movil("m7", VentaMovil.TipoLinea.PRINCIPAL)
        movil_anterior.fecha_venta = date(2026, 7, 20)
        movil_anterior.camada = "2026-07"
        movil_anterior.save(update_fields=["fecha_venta", "camada"])

        r = resumen_produccion_mes(mes="2026-08", ejecutivo=self.ejecutivo)
        # El KPI Fijo mensual usa todos los RGU vendidos de ESACOM (6),
        # mientras el control gestionable conserva completados + pendientes (5).
        self.assertEqual(r["kpi_fijo_rgu"], 6)
        self.assertEqual(r["rgu_fijo_vendidos"], 6)
        self.assertEqual(r["rgu_fijo_gestionables"], 5)
        self.assertEqual(r["ventas_fijo"], 3)
        self.assertEqual(r["rgu_fijo_anulados"], 1)
        self.assertEqual(r["movil"]["principal"], 1)
        self.assertEqual(r["movil"]["adicional"], 1)
        self.assertEqual(r["movil"]["ppm"], 1)
        self.assertEqual(r["kpi_movil_portadas"], 2)
        self.assertEqual(r["total_produccion"], 8)

    def test_movil_pendiente_permanece_en_base_pero_no_suma_produccion(self):
        self._movil("p1", VentaMovil.TipoLinea.PRINCIPAL, efectiva=False, estado="", fecha_activacion=None)
        self._movil("p2", VentaMovil.TipoLinea.ADICIONAL, efectiva=False, estado="MANDATO", fecha_activacion=None)
        self._movil("p3", VentaMovil.TipoLinea.PPM, efectiva=True)

        r = resumen_produccion_actual(ejecutivo=self.ejecutivo)
        self.assertEqual(r["movil"]["total_base_vigente"], 3)
        self.assertEqual(r["movil"]["total"], 1)
        self.assertEqual(r["movil"]["ppm"], 1)
        self.assertEqual(r["movil"]["pendiente_activacion"], 2)
        self.assertEqual(r["movil"]["pendiente_principal"], 1)
        self.assertEqual(r["movil"]["pendiente_adicional"], 1)
        self.assertEqual(r["movil"]["pendiente_sin_evidencia"], 1)
        self.assertEqual(r["movil"]["pendiente_estado_bloqueado"], 1)

    def test_estado_portado_sin_fecha_es_evidencia_valida(self):
        venta = self._movil(
            "e1", VentaMovil.TipoLinea.PRINCIPAL, efectiva=False,
            estado="PORTADO", fecha_activacion=None,
        )
        efectiva, motivo = clasificar_movil_produccion(venta)
        self.assertTrue(efectiva)
        self.assertEqual(motivo, "ESTADO_CONFIRMADO")

    def test_estado_bloqueado_tiene_prioridad_sobre_fecha_parcial(self):
        venta = self._movil(
            "e2", VentaMovil.TipoLinea.PRINCIPAL, efectiva=False,
            estado="ANULADO", fecha_activacion=date(2026, 8, 21),
        )
        efectiva, motivo = clasificar_movil_produccion(venta)
        self.assertFalse(efectiva)
        self.assertEqual(motivo, "ESTADO_BLOQUEADO")

    def test_venta_fija_sin_rgu_no_inventa_produccion(self):
        self._fija("sr1", "Completada", Venta.EstadoInstalacion.INSTALADO, rgu=None)
        r = resumen_produccion_actual(ejecutivo=self.ejecutivo)
        self.assertEqual(r["fija"]["completadas"], 0)
        self.assertEqual(r["fija"]["ventas_completadas"], 1)
        self.assertEqual(r["fija"]["ventas_sin_rgu"], 1)

    def test_detalle_por_supervisor_conserva_misma_logica_central(self):
        self._fija("10", "Completada", Venta.EstadoInstalacion.INSTALADO, rgu=2)
        self._movil("b1", VentaMovil.TipoLinea.PRINCIPAL)
        self._movil("b2", VentaMovil.TipoLinea.ADICIONAL, efectiva=False)
        d = detalle_produccion_actual()
        self.assertEqual(d["global"]["total_produccion"], 3)
        self.assertEqual(d["supervisores"]["Charly Estay"]["total_produccion"], 3)
        self.assertEqual(d["ejecutivos"][self.ejecutivo.nombre]["total_produccion"], 3)
        self.assertEqual(d["global"]["movil"]["pendiente_activacion"], 1)
    def test_detalle_conserva_ejecutivo_por_supervisor_fuente(self):
        primera = self._fija("sp1", "Completada", Venta.EstadoInstalacion.INSTALADO, rgu=2)
        segunda = self._fija("sp2", "Pendiente Instalación", Venta.EstadoInstalacion.PENDIENTE_INSTALACION, rgu=3)
        segunda.supervisor_fuente = "Patricio Guerra"
        segunda.save(update_fields=["supervisor_fuente"])

        d = detalle_produccion_actual()
        por_sup = d["ejecutivos_por_supervisor"]
        self.assertEqual(
            por_sup["Charly Estay"][self.ejecutivo.nombre]["fija"]["completadas"], 2
        )
        self.assertEqual(
            por_sup["Patricio Guerra"][self.ejecutivo.nombre]["fija"]["pendiente_instalacion"], 3
        )
        # El consolidado global del Ejecutivo se mantiene disponible.
        self.assertEqual(d["ejecutivos"][self.ejecutivo.nombre]["fija"]["total_control"], 5)


import datetime

from django.db import IntegrityError, transaction
from django.test import TestCase

from catalogos.models import Promocion
from usuarios.models import Ejecutivo
from ventas.models import Venta

from .models import CargaExcel, KPIRegistro


class HistorialKpiTests(TestCase):
    def setUp(self):
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="22222222-2", password="test12345", nombre="Ejecutivo KPI"
        )
        promo = Promocion.objects.create(
            nombre="Promo KPI", rgu=2, empresa=Promocion.Empresa.CLARO
        )
        self.venta = Venta.objects.create(
            rut_cliente="12345678-5",
            n_pedido="1-ABC",
            ejecutivo=self.ejecutivo,
            promocion=promo,
            fecha_venta=datetime.date(2026, 7, 10),
            camada="2026-07",
            rgu_base=2,
        )
        self.carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI.xlsx",
        )

    def test_snapshot_kpi_es_unico_por_carga_pedido_camada_boleta(self):
        KPIRegistro.objects.create(
            carga=self.carga,
            venta=self.venta,
            num_pedido="1-ABC",
            camada="2026-07",
            boleta="B1",
            cruce_ok=True,
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                KPIRegistro.objects.create(
                    carga=self.carga,
                    venta=self.venta,
                    num_pedido="1-ABC",
                    camada="2026-07",
                    boleta="B1",
                    cruce_ok=True,
                )

    def test_mismo_registro_puede_reaparecer_en_nueva_carga(self):
        KPIRegistro.objects.create(
            carga=self.carga,
            venta=self.venta,
            num_pedido="1-ABC",
            camada="2026-07",
            boleta="B1",
            kpi_texto="Pendiente",
            cruce_ok=True,
        )
        carga2 = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="KPI_miercoles.xlsx",
        )
        KPIRegistro.objects.create(
            carga=carga2,
            venta=self.venta,
            num_pedido="1-ABC",
            camada="2026-07",
            boleta="B1",
            kpi_texto="Pago",
            cruce_ok=True,
        )
        self.assertEqual(KPIRegistro.objects.filter(num_pedido="1-ABC").count(), 2)


class NormalizacionRutKpiTests(TestCase):
    def test_rut_claro_con_cero_inicial_equivale_a_esacom(self):
        # Caso observado en el KPI real: Claro rellena el cuerpo con un cero.
        from .management.commands.importar_kpi import normalizar_rut

        self.assertEqual(normalizar_rut("013425831-4"), normalizar_rut("13.425.831-4"))
        self.assertEqual(normalizar_rut("017140093-7"), normalizar_rut("17140093-7"))

    def test_normalizacion_conserva_digito_verificador_k(self):
        from .management.commands.importar_kpi import normalizar_rut

        self.assertEqual(normalizar_rut("00.123.456-K"), "123456K")


class ReglasMedicionClaroTests(TestCase):
    def test_vencimiento_mas_8_despues_del_corte_queda_fuera(self):
        from .management.commands.importar_kpi import calcular_estado_esacom
        from ventas.models import Corte

        estado, limite, medible = calcular_estado_esacom(
            estado_claro=Corte.EstadoPago.PENDIENTE,
            boleta=Corte.Boleta.B1,
            fecha_venc=datetime.date(2026, 7, 25),
            fecha_pago=None,
            fecha_corte=datetime.date(2026, 7, 31),
            estados_fuente={},
            clave_base=("1-X", "2026-07"),
        )
        self.assertEqual(limite, datetime.date(2026, 8, 2))
        self.assertFalse(medible)
        self.assertEqual(estado, Corte.EstadoCalculado.FUERA_MEDICION)


    def test_corte_intermedio_agosto_no_excluye_vencimiento_mas_8_dentro_de_agosto(self):
        from .management.commands.importar_kpi import calcular_estado_esacom
        from ventas.models import Corte

        estado, limite, medible = calcular_estado_esacom(
            estado_claro=Corte.EstadoPago.PENDIENTE,
            boleta=Corte.Boleta.B1,
            fecha_venc=datetime.date(2026, 8, 12),
            fecha_pago=None,
            fecha_corte=datetime.date(2026, 8, 9),
            estados_fuente={},
            clave_base=("1-X", "2026-07"),
        )
        self.assertEqual(limite, datetime.date(2026, 8, 20))
        self.assertTrue(medible)
        self.assertEqual(estado, Corte.EstadoCalculado.PENDIENTE)

    def test_agosto_excluye_si_vencimiento_mas_8_cae_en_septiembre(self):
        from .management.commands.importar_kpi import calcular_estado_esacom
        from ventas.models import Corte

        estado, limite, medible = calcular_estado_esacom(
            estado_claro=Corte.EstadoPago.PENDIENTE,
            boleta=Corte.Boleta.B1,
            fecha_venc=datetime.date(2026, 8, 25),
            fecha_pago=None,
            fecha_corte=datetime.date(2026, 8, 9),
            estados_fuente={},
            clave_base=("1-X", "2026-07"),
        )
        self.assertEqual(limite, datetime.date(2026, 9, 2))
        self.assertFalse(medible)
        self.assertEqual(estado, Corte.EstadoCalculado.FUERA_MEDICION)

    def test_tercera_sin_boleta_con_primeras_pagadas_permanece_sb(self):
        from .management.commands.importar_kpi import calcular_estado_esacom
        from ventas.models import Corte

        estados = {
            ("1-X", "2026-04", Corte.Boleta.B1): Corte.EstadoPago.PAGADO,
            ("1-X", "2026-04", Corte.Boleta.B2): Corte.EstadoPago.PAGADO,
        }
        estado, _, medible = calcular_estado_esacom(
            estado_claro=Corte.EstadoPago.SIN_BOLETA,
            boleta=Corte.Boleta.B3,
            fecha_venc=datetime.date(2026, 7, 20),
            fecha_pago=None,
            fecha_corte=datetime.date(2026, 7, 31),
            estados_fuente=estados,
            clave_base=("1-X", "2026-04"),
        )
        self.assertTrue(medible)
        self.assertEqual(estado, Corte.EstadoCalculado.SIN_BOLETA)

    def test_tercera_sin_boleta_sin_pago_previo_es_no_pago(self):
        from .management.commands.importar_kpi import calcular_estado_esacom
        from ventas.models import Corte

        estados = {
            ("1-X", "2026-04", Corte.Boleta.B1): Corte.EstadoPago.NO_PAGO,
            ("1-X", "2026-04", Corte.Boleta.B2): Corte.EstadoPago.NO_PAGO,
        }
        estado, _, _ = calcular_estado_esacom(
            estado_claro=Corte.EstadoPago.SIN_BOLETA,
            boleta=Corte.Boleta.B3,
            fecha_venc=datetime.date(2026, 7, 20),
            fecha_pago=None,
            fecha_corte=datetime.date(2026, 7, 31),
            estados_fuente=estados,
            clave_base=("1-X", "2026-04"),
        )
        self.assertEqual(estado, Corte.EstadoCalculado.NO_PAGO)


class DotacionAsignacionSeguraTests(TestCase):
    """Regresiones para el bug detectado en reunión gerencial 2026-08-23."""

    def _wb(self, filas):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Dotación"
        ws.append([
            "RUT", "Nombre", "Cargo", "SUPERVISOR", "Equipo", "Estado",
            "Nombre Dirve", "RUT2", "Contar", "Tipo Contrato", "Fecha de Ingreso",
            "CODIGO MOVIL", "CODIGO FIJO", "CODIGO ANDES", "FONO EJECUTIVOS",
            "ESTADO DE CONTRATO",
        ])
        for f in filas:
            ws.append(f)
        return wb

    def test_cargo_fuente_no_sobrescribe_rol_crm_y_asigna_por_alias_exacto(self):
        from integraciones.management.commands.importar_excel import Command
        from usuarios.models import Ejecutivo
        charly = Ejecutivo.objects.create_user(
            rut="17480807-4", nombre="CHARLY FABIAN ESTAY LAZO",
            cargo=Ejecutivo.Cargo.SUPERVISOR, password="PruebaSegura2026!",
        )
        vendedor = Ejecutivo.objects.create_user(
            rut="19776727-8", nombre="CAMILO IGNACIO BASCUÑAN PEÑALOZA",
            cargo=Ejecutivo.Cargo.EJECUTIVO, password="PruebaSegura2026!",
        )
        wb = self._wb([
            ["17480807-4", "CHARLY FABIAN ESTAY LAZO", "Supervisor", "Enzo Morales", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
            # Fuente dice Supervisor a propósito: el rol CRM de Camilo NO debe cambiar.
            ["19776727-8", "CAMILO IGNACIO BASCUÑAN PEÑALOZA", "Supervisor", "Charly Estay", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
        ])
        Command()._importar_dotacion(wb)
        vendedor.refresh_from_db()
        self.assertEqual(vendedor.cargo, Ejecutivo.Cargo.EJECUTIVO)
        self.assertEqual(vendedor.cargo_fuente_esacom, "Supervisor")
        self.assertEqual(vendedor.supervisor_id, charly.id)


    def test_usuario_existente_mal_como_supervisor_se_reconcilia_a_ejecutivo(self):
        from integraciones.management.commands.importar_excel import Command
        from usuarios.models import Ejecutivo
        jorge = Ejecutivo.objects.create_user(
            rut="16440386-6", nombre="JORGE ANTONIO HERNANDEZ URETA",
            cargo=Ejecutivo.Cargo.SUPERVISOR, password="PruebaSegura2026!",
        )
        vendedor = Ejecutivo.objects.create_user(
            rut="15559883-2", nombre="CLAUDIA ALEXANDRA VEGA LILLO",
            cargo=Ejecutivo.Cargo.SUPERVISOR, password="PruebaSegura2026!",
        )
        wb = self._wb([
            ["16440386-6", "JORGE ANTONIO HERNANDEZ URETA", "Supervisor", "Enzo Morales", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
            ["15559883-2", "CLAUDIA ALEXANDRA VEGA LILLO", "Supervisor", "Jorge Hernandez", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
        ])
        Command()._importar_dotacion(wb)
        vendedor.refresh_from_db()
        self.assertEqual(vendedor.cargo, Ejecutivo.Cargo.EJECUTIVO)
        self.assertEqual(vendedor.supervisor_id, jorge.id)
        self.assertEqual(vendedor.cargo_fuente_esacom, "Supervisor")

    def test_antonio_permanece_supervisor_aunque_fuente_lo_traiga_ejecutivo(self):
        from integraciones.management.commands.importar_excel import Command
        from usuarios.models import Ejecutivo

        antonio = Ejecutivo.objects.create_user(
            rut="10837118-8", nombre="LEONEL ANTONIO OCHOA GARAY",
            cargo=Ejecutivo.Cargo.EJECUTIVO, password="PruebaSegura2026!",
        )
        luis = Ejecutivo.objects.create_user(
            rut="12121212-1", nombre="LUIS LARENAS",
            cargo=Ejecutivo.Cargo.EJECUTIVO, password="PruebaSegura2026!",
        )
        dilan = Ejecutivo.objects.create_user(
            rut="13131313-1", nombre="DILAN GONZALEZ",
            cargo=Ejecutivo.Cargo.EJECUTIVO, password="PruebaSegura2026!",
        )
        wb = self._wb([
            ["10837118-8", "LEONEL ANTONIO OCHOA GARAY", "Ejecutivo", "Antonio Ochoa", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
            ["12121212-1", "LUIS LARENAS", "Ejecutivo", "Antonio Ochoa", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
            ["13131313-1", "DILAN GONZALEZ", "Ejecutivo", "Antonio Ochoa", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
        ])
        Command()._importar_dotacion(wb)

        antonio.refresh_from_db()
        luis.refresh_from_db()
        dilan.refresh_from_db()
        self.assertEqual(antonio.cargo, Ejecutivo.Cargo.SUPERVISOR)
        self.assertIsNone(antonio.supervisor_id)
        self.assertEqual(luis.supervisor_id, antonio.id)
        self.assertEqual(dilan.supervisor_id, antonio.id)

    def test_finiquitado_desactiva_y_alias_no_resuelto_limpia_supervisor(self):
        from integraciones.management.commands.importar_excel import Command
        from usuarios.models import Ejecutivo
        charly = Ejecutivo.objects.create_user(rut="17480807-4", nombre="CHARLY FABIAN ESTAY LAZO", cargo=Ejecutivo.Cargo.SUPERVISOR, password="PruebaSegura2026!")
        vendedor = Ejecutivo.objects.create_user(rut="11111111-1", nombre="VENDEDOR PRUEBA", cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=charly, password="PruebaSegura2026!")
        wb = self._wb([
            ["17480807-4", "CHARLY FABIAN ESTAY LAZO", "Supervisor", "Enzo Morales", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "CONTRATADO"],
            ["11111111-1", "VENDEDOR PRUEBA", "Ejecutivo de Ventas", "Alias Inexistente", "Q", "Activo", "", "", "", "Indefinido", None, "", "", "", "", "FINIQUITADO"],
        ])
        r = Command()._importar_dotacion(wb)
        vendedor.refresh_from_db()
        self.assertFalse(vendedor.is_active)
        self.assertEqual(vendedor.estado_contrato, Ejecutivo.EstadoContrato.INACTIVO)
        self.assertIsNone(vendedor.supervisor_id)
        self.assertIn("ALIAS INEXISTENTE", r["alias_supervisor_no_resueltos"])

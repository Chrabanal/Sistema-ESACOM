import datetime
from decimal import Decimal

from django.test import TestCase

from catalogos.models import Promocion
from integraciones.models import CargaExcel, KPIRegistro
from usuarios.models import Ejecutivo

from .models import Corte, Venta
from .services import (
    resumen_accionables,
    resumen_kpi,
    resumen_por_ejecutivo_actual,
    resumen_por_supervisor_actual,
)


class KpiV4Base(TestCase):
    def setUp(self):
        self.supervisor = Ejecutivo.objects.create_user(
            rut="22222222-2",
            password="test12345",
            nombre="Supervisor KPI V4",
            cargo=Ejecutivo.Cargo.SUPERVISOR,
        )
        self.ejecutivo = Ejecutivo.objects.create_user(
            rut="11111111-1",
            password="test12345",
            nombre="Ejecutivo KPI V4",
            supervisor=self.supervisor,
            tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
        )
        self.promo = Promocion.objects.create(
            nombre="Promo KPI V4", rgu=1, empresa=Promocion.Empresa.CLARO
        )
        self.seq = 0

    def venta(self, *, rgu_base=1, conflicto=False, estado=None):
        self.seq += 1
        return Venta.objects.create(
            rut_cliente=f"900000{self.seq}-K",
            n_pedido=f"V4-{self.seq:04d}",
            rut_evt=self.ejecutivo.rut,
            nombre_evt=self.ejecutivo.nombre,
            ejecutivo=self.ejecutivo,
            promocion=self.promo,
            fecha_venta=datetime.date(2026, 7, 1),
            camada="2026-07",
            rgu_base=rgu_base,
            conflicto_fuente=conflicto,
            estado_instalacion=estado or Venta.EstadoInstalacion.INSTALADO,
        )

    def corte(self, *, boleta, mes, estado_pago, rgu_kpi, meta, venta=None, fecha_venc=None):
        venta = venta or self.venta()
        return Corte.objects.create(
            venta=venta,
            mes_ano=mes,
            boleta=boleta,
            meta_pct=Decimal(str(meta)),
            estado_pago=estado_pago,
            estado_claro=estado_pago,
            rgu_kpi=rgu_kpi,
            es_medible=True,
            fecha_vencimiento=fecha_venc,
        )


class KpiFormulaOficial2408Tests(KpiV4Base):
    CONTROL = {
        "B1": {
            "mes": "2026-07", "meta": 85,
            "pago": 682, "no_pago": 51, "fuera": 19, "pendiente": 77, "sb": 0,
            "total": 829, "kpi": 82.27, "proyeccion": 89.91, "q_meta": 23,
        },
        "B2": {
            "mes": "2026-06", "meta": 83,
            "pago": 694, "no_pago": 146, "fuera": 19, "pendiente": 37, "sb": 18,
            "total": 896, "kpi": 77.46, "proyeccion": 80.65, "q_meta": 50,
        },
        "B3": {
            "mes": "2026-05", "meta": 78,
            "pago": 528, "no_pago": 163, "fuera": 9, "pendiente": 38, "sb": 16,
            "total": 738, "kpi": 71.54, "proyeccion": 75.23, "q_meta": 48,
        },
    }

    def _crear_control(self, boleta, datos):
        estados = [
            (Corte.EstadoPago.PAGADO, datos["pago"]),
            (Corte.EstadoPago.NO_PAGO, datos["no_pago"]),
            (Corte.EstadoPago.FUERA_PLAZO, datos["fuera"]),
            (Corte.EstadoPago.PENDIENTE, datos["pendiente"]),
        ]
        if datos["sb"]:
            estados.append((Corte.EstadoPago.SIN_BOLETA, datos["sb"]))
        for estado, rgu in estados:
            # rgu_base deliberadamente distinto: V4 debe ponderar KPI con
            # rgu_kpi de Claro, no con RGU operacional ESACOM.
            self.corte(
                boleta=boleta,
                mes=datos["mes"],
                estado_pago=estado,
                rgu_kpi=rgu,
                meta=datos["meta"],
                venta=self.venta(rgu_base=1),
            )

    def test_control_oficial_2408_b1_b2_b3(self):
        for boleta, datos in self.CONTROL.items():
            self._crear_control(boleta, datos)
            r = resumen_kpi(Corte.objects.filter(boleta=boleta, mes_ano=datos["mes"]))
            self.assertEqual(r["pagadas"], datos["pago"])
            self.assertEqual(r["pendientes"], datos["pendiente"])
            self.assertEqual(r["no_pago"], datos["no_pago"])
            self.assertEqual(r["fuera_plazo"], datos["fuera"])
            self.assertEqual(r["sin_boleta"], datos["sb"])
            self.assertEqual(r["total"], datos["total"])
            self.assertEqual(r["pct_cumplimiento"], datos["kpi"])
            self.assertEqual(r["pct_proyectado"], datos["proyeccion"])
            self.assertEqual(r["meta_pct"], float(datos["meta"]))
            self.assertEqual(r["faltan_para_meta"], datos["q_meta"])

    def test_sin_boleta_no_entra_en_denominador(self):
        v1 = self.venta(rgu_base=99)
        v2 = self.venta(rgu_base=99)
        self.corte(
            boleta=Corte.Boleta.B2, mes="2026-06", estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=10, meta=83, venta=v1,
        )
        self.corte(
            boleta=Corte.Boleta.B2, mes="2026-06", estado_pago=Corte.EstadoPago.SIN_BOLETA,
            rgu_kpi=18, meta=83, venta=v2,
        )
        r = resumen_kpi(Corte.objects.all())
        self.assertEqual(r["total"], 10)
        self.assertEqual(r["total_con_sin_boleta"], 28)
        self.assertEqual(r["pct_cumplimiento"], 100.0)


class AtribucionConflictoKpiV4Tests(KpiV4Base):
    def test_conflicto_fuente_permanece_en_global_pero_no_se_adjudica(self):
        normal = self.venta(rgu_base=50)
        conflicto = self.venta(rgu_base=50, conflicto=True)
        self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07", estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=2, meta=85, venta=normal,
        )
        self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07", estado_pago=Corte.EstadoPago.PAGADO,
            rgu_kpi=10, meta=85, venta=conflicto,
        )

        global_kpi = resumen_kpi(Corte.objects.all())
        self.assertEqual(global_kpi["pagadas"], 12)

        focos = {"B1": "2026-07", "B2": "", "B3": ""}
        metas = {"B1": Decimal("85"), "B2": None, "B3": None}
        por_ejecutivo = resumen_por_ejecutivo_actual(Corte.objects.all(), focos=focos, metas=metas)
        self.assertEqual(len(por_ejecutivo), 1)
        self.assertEqual(por_ejecutivo[0]["cortes"][0]["pagadas"], 2)

        por_supervisor = resumen_por_supervisor_actual(Corte.objects.all(), focos=focos, metas=metas)
        self.assertEqual(len(por_supervisor), 1)
        self.assertEqual(por_supervisor[0]["cortes"][0]["pagadas"], 2)

        from .views import _scope_cortes_qs
        individual = _scope_cortes_qs(Corte.objects.all(), self.ejecutivo)
        self.assertEqual(individual.count(), 1)
        self.assertEqual(individual.first().venta_id, normal.id)

    def test_accionables_excluye_pedido_ambiguo(self):
        venc = datetime.date.today() - datetime.timedelta(days=1)
        normal = self.venta()
        conflicto = self.venta(conflicto=True)
        self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07", estado_pago=Corte.EstadoPago.PENDIENTE,
            rgu_kpi=2, meta=85, venta=normal, fecha_venc=venc,
        )
        self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07", estado_pago=Corte.EstadoPago.PENDIENTE,
            rgu_kpi=10, meta=85, venta=conflicto, fecha_venc=venc,
        )
        data = resumen_accionables(Corte.objects.all(), focos={"B1": "2026-07"})
        self.assertEqual(data["vencidos"]["rgu"], 2)
        self.assertEqual(data["vencidos"]["casos"], 1)


class HistoricoKpiUsaRguClaroTests(KpiV4Base):
    def test_snapshot_historico_pondera_con_rgu_del_reporte(self):
        from .views import _resumen_snapshot_historico

        carga = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="kpi-test.xlsx",
            fecha_corte=datetime.date(2026, 8, 24),
            foco_b1="2026-07",
        )
        venta = self.venta(rgu_base=9)
        KPIRegistro.objects.create(
            carga=carga,
            venta=venta,
            num_pedido=venta.n_pedido,
            camada="2026-07",
            boleta="B1",
            rgu=2,
            kpi_texto="PAGO",
            estado_normalizado=Corte.EstadoPago.PAGADO,
            es_medible=True,
            cruce_ok=True,
        )
        r = _resumen_snapshot_historico(carga, {"B1": "2026-07"})
        self.assertEqual(r["B1"]["pagadas"], 2)
        self.assertEqual(r["B1"]["total"], 2)
        self.assertEqual(r["B1"]["pct_cumplimiento"], 100.0)


class SnapshotVigenteKpiV41Tests(KpiV4Base):
    def test_dashboard_no_mezcla_cortes_de_snapshots_anteriores(self):
        from ventas.views import _cortes_visibles

        carga_anterior = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="kpi-anterior.xlsx",
            fecha_corte=datetime.date(2026, 8, 19),
        )
        carga_actual = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="kpi-actual.xlsx",
            fecha_corte=datetime.date(2026, 8, 24),
        )

        viejo = self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07",
            estado_pago=Corte.EstadoPago.PENDIENTE, rgu_kpi=576, meta=85,
            venta=self.venta(),
        )
        viejo.carga_kpi = carga_anterior
        viejo.save(update_fields=["carga_kpi"])

        actual = self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07",
            estado_pago=Corte.EstadoPago.PAGADO, rgu_kpi=10, meta=85,
            venta=self.venta(),
        )
        actual.carga_kpi = carga_actual
        actual.save(update_fields=["carga_kpi"])

        qs = _cortes_visibles(self.ejecutivo, carga_kpi=carga_actual)
        self.assertEqual(list(qs.values_list("id", flat=True)), [actual.id])
        r = resumen_kpi(qs)
        self.assertEqual(r["pagadas"], 10)
        self.assertEqual(r["pendientes"], 0)
        self.assertEqual(r["total"], 10)

    def test_corte_sin_marca_del_snapshot_actual_no_entra_en_scope(self):
        from ventas.views import _cortes_visibles

        carga_actual = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="kpi-actual.xlsx",
            fecha_corte=datetime.date(2026, 8, 24),
        )
        legado = self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07",
            estado_pago=Corte.EstadoPago.PENDIENTE, rgu_kpi=500, meta=85,
            venta=self.venta(),
        )
        self.assertIsNone(legado.carga_kpi_id)
        self.assertFalse(_cortes_visibles(self.ejecutivo, carga_kpi=carga_actual).exists())


class SnapshotActivoValidadoresV421Tests(KpiV4Base):
    def test_validar_dashboard_ejecutivo_no_mezcla_snapshot_anterior(self):
        from io import StringIO
        from django.core.management import call_command

        carga_anterior = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="kpi-anterior.xlsx",
            fecha_corte=datetime.date(2026, 8, 19),
            dia_reporte=CargaExcel.DiaReporte.MIERCOLES,
            foco_b1="2026-07",
            meta_b1=Decimal("85"),
        )
        carga_actual = CargaExcel.objects.create(
            origen=CargaExcel.Origen.MANUAL,
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            archivo_nombre="kpi-actual.xlsx",
            fecha_corte=datetime.date(2026, 8, 24),
            dia_reporte=CargaExcel.DiaReporte.LUNES,
            foco_b1="2026-07",
            meta_b1=Decimal("85"),
        )

        viejo = self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07",
            estado_pago=Corte.EstadoPago.PENDIENTE, rgu_kpi=2, meta=85,
            venta=self.venta(),
        )
        viejo.carga_kpi = carga_anterior
        viejo.save(update_fields=["carga_kpi"])

        pago = self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07",
            estado_pago=Corte.EstadoPago.PAGADO, rgu_kpi=48, meta=85,
            venta=self.venta(),
        )
        pago.carga_kpi = carga_actual
        pago.save(update_fields=["carga_kpi"])
        no_pago = self.corte(
            boleta=Corte.Boleta.B1, mes="2026-07",
            estado_pago=Corte.EstadoPago.NO_PAGO, rgu_kpi=1, meta=85,
            venta=self.venta(),
        )
        no_pago.carga_kpi = carga_actual
        no_pago.save(update_fields=["carga_kpi"])

        out = StringIO()
        call_command("validar_dashboard_ejecutivo", "--rut", self.ejecutivo.rut, stdout=out)
        texto = out.getvalue()
        self.assertIn(f"Snapshot activo: #{carga_actual.id}", texto)
        self.assertIn("B1 2026-07: KPI 97.96%", texto)
        self.assertIn("Pago 48 · Pendiente 0 · No Pago 1", texto)
        self.assertNotIn("Pendiente 2", texto)

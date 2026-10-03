from django.urls import reverse
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import AuditoriaUsuario, Ejecutivo


class SoporteUsuariosApiTests(APITestCase):
    def setUp(self):
        self.soporte = Ejecutivo.objects.create_user(
            rut="11111111-1", nombre="Soporte", cargo=Ejecutivo.Cargo.SOPORTE, password="Clave123!"
        )
        self.gerencia = Ejecutivo.objects.create_user(
            rut="22222222-2", nombre="Gerencia", cargo=Ejecutivo.Cargo.GERENCIA, password="Clave123!"
        )

    def test_soporte_puede_crear_usuario_y_se_audita(self):
        self.client.force_authenticate(self.soporte)
        response = self.client.post("/api/soporte/usuarios/", {
            "rut": "19.784.357-8",
            "nombre": "Ejecutivo Prueba",
            "cargo": "EJECUTIVO",
            "password": "Temporal123!",
            "is_active": True,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Ejecutivo.objects.filter(rut="19784357-8").exists())
        self.assertTrue(AuditoriaUsuario.objects.filter(accion=AuditoriaUsuario.Accion.CREAR).exists())

    def test_gerencia_no_administra_usuarios_soporte(self):
        self.client.force_authenticate(self.gerencia)
        response = self.client.get("/api/soporte/usuarios/")
        self.assertEqual(response.status_code, 403)

    def test_no_hay_delete_fisico(self):
        self.client.force_authenticate(self.soporte)
        response = self.client.delete(f"/api/soporte/usuarios/{self.gerencia.id}/")
        self.assertEqual(response.status_code, 405)

    def test_soporte_no_puede_desactivarse_a_si_mismo(self):
        self.client.force_authenticate(self.soporte)
        response = self.client.post(f"/api/soporte/usuarios/{self.soporte.id}/desactivar/")
        self.assertEqual(response.status_code, 400)
        self.soporte.refresh_from_db()
        self.assertTrue(self.soporte.is_active)

    def test_reset_password_genera_temporal(self):
        self.client.force_authenticate(self.soporte)
        response = self.client.post(f"/api/soporte/usuarios/{self.gerencia.id}/reset-password/", {}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["password_temporal"])
        self.gerencia.refresh_from_db()
        self.assertTrue(self.gerencia.check_password(response.data["password_temporal"]))

class TipoKpiSoporteTests(APITestCase):
    def setUp(self):
        self.soporte = Ejecutivo.objects.create_user(
            rut="33333333-3", nombre="Soporte KPI", cargo=Ejecutivo.Cargo.SOPORTE, password="Clave123!"
        )

    def test_soporte_puede_marcar_ejecutivo_honorarios(self):
        self.client.force_authenticate(self.soporte)
        response = self.client.post("/api/soporte/usuarios/", {
            "rut": "12.345.678-5",
            "nombre": "Vendedor Honorarios",
            "cargo": "EJECUTIVO",
            "tipo_kpi": "HONORARIOS",
            "password": "Temporal123!",
            "is_active": True,
        }, format="json")
        self.assertEqual(response.status_code, 201)
        u = Ejecutivo.objects.get(rut="12345678-5")
        self.assertEqual(u.tipo_kpi, Ejecutivo.TipoKPI.HONORARIOS)


class BusquedaFlexibleSoporteTests(APITestCase):
    def setUp(self):
        self.soporte = Ejecutivo.objects.create_user(
            rut="44444444-4", nombre="Soporte Búsqueda", cargo=Ejecutivo.Cargo.SOPORTE, password="Clave123!"
        )
        self.supervisor = Ejecutivo.objects.create_user(
            rut="17480807-4", nombre="Charly Fabián Estay Lazo", cargo=Ejecutivo.Cargo.SUPERVISOR,
            equipo="Quilpué", password="Clave123!"
        )
        self.camilo = Ejecutivo.objects.create_user(
            rut="01976727-8", nombre="Camilo Ignacio Bascuñán Peñaloza", cargo=Ejecutivo.Cargo.EJECUTIVO,
            supervisor=self.supervisor, equipo="Quilpué", codigo_fijo="CBASCUNAN", password="Clave123!"
        )
        Ejecutivo.objects.create_user(
            rut="17806413-4", nombre="Claudio Antonio Torres Astudillo", cargo=Ejecutivo.Cargo.EJECUTIVO,
            supervisor=self.supervisor, equipo="Quilpué", password="Clave123!"
        )
        self.client.force_authenticate(self.soporte)

    def nombres(self, q):
        response = self.client.get("/api/soporte/usuarios/", {"q": q})
        self.assertEqual(response.status_code, 200)
        return [u["nombre"] for u in response.data]

    def test_busca_por_fragmento_de_nombre_sin_tilde(self):
        self.assertIn(self.camilo.nombre, self.nombres("bascu"))

    def test_busca_por_rut_parcial_sin_formato(self):
        self.assertIn(self.camilo.nombre, self.nombres("1976"))

    def test_busca_por_supervisor_y_equipo(self):
        self.assertIn(self.camilo.nombre, self.nombres("charly quilpue"))

    def test_busca_por_codigo_parcial(self):
        self.assertIn(self.camilo.nombre, self.nombres("basc"))

    def test_busqueda_torres_devuelve_solo_coincidencias_relevantes(self):
        nombres = self.nombres("torres")
        self.assertIn("Claudio Antonio Torres Astudillo", nombres)
        self.assertNotIn(self.camilo.nombre, nombres)


class PermisosRBACRegressionTests(TestCase):
    def test_supervisor_base_es_minimo_privilegio(self):
        u = Ejecutivo.objects.create_user(rut="11111111-1", password="xTest12345!", nombre="Supervisor Test", cargo=Ejecutivo.Cargo.SUPERVISOR)
        p = u.permisos_efectivos()
        self.assertTrue(p["mi_equipo"])
        self.assertTrue(p["accionables"])
        self.assertFalse(p["cobranza"])
        self.assertFalse(p["apelaciones"])
        self.assertFalse(p["historico"])
        self.assertFalse(p["base_datos"])

    def test_override_permiso(self):
        u = Ejecutivo.objects.create_user(rut="22222222-2", password="xTest12345!", nombre="Supervisor Test 2", cargo=Ejecutivo.Cargo.SUPERVISOR)
        u.permisos_personalizados = {"cobranza": True, "accionables": False}
        u.save()
        p = u.permisos_efectivos()
        self.assertTrue(p["cobranza"])
        self.assertFalse(p["accionables"])

    def test_contabilidad_base(self):
        u = Ejecutivo.objects.create_user(rut="33333333-3", password="xTest12345!", nombre="Contabilidad", cargo=Ejecutivo.Cargo.CONTABILIDAD)
        p = u.permisos_efectivos()
        self.assertTrue(p["cobranza"])
        self.assertTrue(p["historico"])
        self.assertFalse(p["mi_equipo"])

class PermisosAdministrativosNoDelegablesTests(APITestCase):
    def setUp(self):
        self.soporte = Ejecutivo.objects.create_user(
            rut="55555555-5", nombre="Soporte Seguridad", cargo=Ejecutivo.Cargo.SOPORTE, password="Clave123!"
        )
        self.supervisor = Ejecutivo.objects.create_user(
            rut="66666666-6", nombre="Supervisor Seguridad", cargo=Ejecutivo.Cargo.SUPERVISOR, password="Clave123!"
        )
        self.client.force_authenticate(self.soporte)

    def test_override_no_puede_delegar_usuarios_ni_permisos(self):
        self.supervisor.permisos_personalizados = {"usuarios": True, "permisos": True}
        self.supervisor.save()
        efectivos = self.supervisor.permisos_efectivos()
        self.assertFalse(efectivos["usuarios"])
        self.assertFalse(efectivos["permisos"])

    def test_api_requiere_motivo_para_cambiar_permisos(self):
        response = self.client.patch(
            f"/api/permisos/usuarios/{self.supervisor.id}/configurar/",
            {"permisos": {**self.supervisor.permisos_efectivos(), "accionables": False}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("motivo", response.data)

    def test_api_rechaza_escalamiento_administrativo(self):
        response = self.client.patch(
            f"/api/permisos/usuarios/{self.supervisor.id}/configurar/",
            {"permisos": {**self.supervisor.permisos_efectivos(), "usuarios": True}, "motivo": "Prueba de seguridad"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

class PreUatSeguridadTests(APITestCase):
    def setUp(self):
        self.soporte = Ejecutivo.objects.create_user(
            rut="10101010-1", nombre="Soporte UAT", cargo=Ejecutivo.Cargo.SOPORTE, password="ClaveUat123!"
        )
        self.supervisor = Ejecutivo.objects.create_user(
            rut="20202020-2", nombre="Supervisor UAT", cargo=Ejecutivo.Cargo.SUPERVISOR, password="ClaveUat123!"
        )
        self.operaciones = Ejecutivo.objects.create_user(
            rut="30303030-3", nombre="Operaciones UAT", cargo=Ejecutivo.Cargo.OPERACIONES, password="ClaveUat123!"
        )
        self.contabilidad = Ejecutivo.objects.create_user(
            rut="40404040-4", nombre="Contabilidad UAT", cargo=Ejecutivo.Cargo.CONTABILIDAD, password="ClaveUat123!"
        )

    def test_modulos_administrativos_no_son_delegables(self):
        self.client.force_authenticate(self.soporte)
        response = self.client.patch(
            f"/api/permisos/usuarios/{self.supervisor.pk}/configurar/",
            {"motivo": "Prueba de seguridad UAT", "permisos": {"permisos": True, "usuarios": True, "estado_sistema": True}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.supervisor.refresh_from_db()
        self.assertFalse(self.supervisor.tiene_permiso("permisos"))
        self.assertFalse(self.supervisor.tiene_permiso("usuarios"))
        self.assertFalse(self.supervisor.tiene_permiso("estado_sistema"))

    def test_estado_sistema_solo_soporte_o_gerencia(self):
        self.client.force_authenticate(self.supervisor)
        self.assertEqual(self.client.get("/api/estado-sistema/").status_code, 403)
        self.client.force_authenticate(self.soporte)
        self.assertEqual(self.client.get("/api/estado-sistema/").status_code, 200)

    def test_perfiles_base_operaciones_y_contabilidad(self):
        self.assertTrue(self.operaciones.tiene_permiso("accionables"))
        self.assertTrue(self.operaciones.tiene_permiso("apelaciones"))
        self.assertFalse(self.operaciones.tiene_permiso("usuarios"))
        self.assertFalse(self.operaciones.tiene_permiso("permisos"))
        self.assertTrue(self.contabilidad.tiene_permiso("cobranza"))
        self.assertTrue(self.contabilidad.tiene_permiso("historico"))
        self.assertFalse(self.contabilidad.tiene_permiso("base_datos"))
        self.assertFalse(self.contabilidad.tiene_permiso("permisos"))

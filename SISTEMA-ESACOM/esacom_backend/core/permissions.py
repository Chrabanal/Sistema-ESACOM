"""Permisos por rol del CRM ESACOM."""
from rest_framework.permissions import BasePermission, SAFE_METHODS


class EsGerencia(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.es_gerencia or u.is_superuser))


class EsSoporte(BasePermission):
    """Administración de accesos: solo Soporte o superusuario técnico."""

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (getattr(u, "es_soporte", False) or u.is_superuser))


class EsSupervisorOModifica(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        u = request.user
        return bool(u and u.is_authenticated and (u.es_gerencia or u.es_supervisor or u.is_superuser))


class EsSupervisorOGerencia(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.es_gerencia or u.es_supervisor or u.is_superuser))


class EsEjecutivo(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.cargo == u.Cargo.EJECUTIVO)




class EsOperacionesOGerencia(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(
            u and u.is_authenticated and
            (u.is_superuser or u.cargo in (u.Cargo.OPERACIONES, u.Cargo.GERENCIA))
        )

class EsSoporteOGerencia(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.cargo in (u.Cargo.SOPORTE, u.Cargo.GERENCIA)))


class PermisoModulo(BasePermission):
    modulo = None
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and self.modulo and u.tiene_permiso(self.modulo))


class PuedeMiEquipo(PermisoModulo): modulo = "mi_equipo"
class PuedeAccionables(PermisoModulo): modulo = "accionables"
class PuedeCobranza(PermisoModulo): modulo = "cobranza"
class PuedeApelaciones(PermisoModulo): modulo = "apelaciones"
class PuedeHistorico(PermisoModulo): modulo = "historico"
class PuedeDashboardGerencia(PermisoModulo): modulo = "dashboard_gerencia"
class PuedeCargarDatos(PermisoModulo): modulo = "cargar_datos"
class PuedeAuditoriaKPI(PermisoModulo): modulo = "auditoria_kpi"
class PuedeBaseDatos(PermisoModulo): modulo = "base_datos"


class PuedeDashboardOAnalisis(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.tiene_permiso("dashboard_gerencia") or u.tiene_permiso("analisis")))


class PuedeMiEquipoOAnalisis(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.tiene_permiso("mi_equipo") or u.tiene_permiso("analisis")))

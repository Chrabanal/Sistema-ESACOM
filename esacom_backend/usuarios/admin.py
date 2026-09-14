from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditoriaUsuario, Ejecutivo


@admin.register(Ejecutivo)
class EjecutivoAdmin(UserAdmin):
    ordering = ("nombre",)
    list_display = ("rut", "nombre", "correo", "cargo", "equipo", "is_active", "last_login")
    list_filter = ("cargo", "is_active", "estado_contrato")
    search_fields = ("rut", "nombre", "correo", "codigo_fijo", "codigo_andes")
    fieldsets = (
        (None, {"fields": ("rut", "password")}),
        ("Identificación", {"fields": ("nombre", "correo", "telefono")}),
        ("Rol y equipo", {"fields": ("cargo", "supervisor", "equipo")}),
        ("Contrato", {"fields": ("tipo_contrato", "fecha_ingreso", "estado_contrato")}),
        ("Códigos", {"fields": ("codigo_movil", "codigo_fijo", "codigo_andes")}),
        ("Permisos", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Fechas", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("rut", "nombre", "correo", "cargo", "password1", "password2", "is_active"),
        }),
    )


@admin.register(AuditoriaUsuario)
class AuditoriaUsuarioAdmin(admin.ModelAdmin):
    list_display = ("creado_en", "accion", "actor", "usuario_objetivo")
    list_filter = ("accion", "creado_en")
    search_fields = ("actor__nombre", "actor__rut", "usuario_objetivo__nombre", "usuario_objetivo__rut")
    readonly_fields = ("actor", "usuario_objetivo", "accion", "detalle", "creado_en")

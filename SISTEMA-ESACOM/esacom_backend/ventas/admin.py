from django.contrib import admin

from .models import Apelacion, Corte, Gestion, MetaKPI, Venta, VentaFijaFuente, VentaMovil
from .produccion import clasificar_movil_produccion


class CorteInline(admin.TabularInline):
    model = Corte
    extra = 0


@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = (
        "n_pedido", "rut_cliente", "ejecutivo", "ejecutivo_ce", "codigo_ce",
        "rgu_base", "promocion", "estado_instalacion", "fecha_venta", "camada",
    )
    list_filter = ("estado_instalacion", "tipo_cliente", "camada", "en_base_vigente")
    search_fields = ("n_pedido", "rut_cliente", "rut_evt", "rut_ce", "codigo_ce")
    inlines = [CorteInline]




@admin.register(VentaFijaFuente)
class VentaFijaFuenteAdmin(admin.ModelAdmin):
    list_display = (
        "fila_fuente", "n_pedido", "nombre_evt", "rut_evt", "supervisor_fuente",
        "estado_instalacion_fuente", "rgu_base", "venta", "en_base_vigente",
    )
    list_filter = ("en_base_vigente", "estado_instalacion_fuente", "supervisor_fuente")
    search_fields = ("n_pedido", "rut_evt", "nombre_evt", "supervisor_fuente")

@admin.register(VentaMovil)
class VentaMovilAdmin(admin.ModelAdmin):
    list_display = (
        "pcs", "nombre_evt", "rut_evt", "supervisor_fuente", "tipo_linea",
        "estado", "fecha_activacion", "es_produccion_efectiva", "fecha_venta", "en_base_vigente",
    )
    list_filter = ("tipo_linea", "estado", "en_base_vigente", "camada")
    search_fields = ("pcs", "rut_cliente", "rut_evt", "nombre_evt", "supervisor_fuente", "observacion")

    @admin.display(boolean=True, description="Producción efectiva")
    def es_produccion_efectiva(self, obj):
        efectiva, _ = clasificar_movil_produccion(obj)
        return efectiva


@admin.register(Corte)
class CorteAdmin(admin.ModelAdmin):
    list_display = ("venta", "boleta", "mes_ano", "estado_pago", "marca_mes_kpi", "carga_kpi", "rgu_kpi", "propietario_final", "ejecutivo_kpi", "meta_pct", "rango_pago", "fecha_vencimiento", "fecha_pago")
    list_filter = ("boleta", "estado_pago", "mes_ano", "marca_mes_kpi", "carga_kpi", "rango_pago", "ejecutivo_kpi")


@admin.register(MetaKPI)
class MetaKPIAdmin(admin.ModelAdmin):
    list_display = ("mes_ano", "boleta", "canal", "tipo_cliente", "meta_pct")
    list_filter = ("mes_ano", "boleta", "canal", "tipo_cliente")


@admin.register(Apelacion)
class ApelacionAdmin(admin.ModelAdmin):
    list_display = ("corte", "motivo", "estado", "fecha_deteccion", "fecha_envio")
    list_filter = ("motivo", "estado")


@admin.register(Gestion)
class GestionAdmin(admin.ModelAdmin):
    list_display = ("venta", "ejecutivo", "tipo", "creado_en")
    list_filter = ("tipo",)

from django.contrib import admin

from .models import CargaExcel, ClaroImport, KPIRegistro, KPICierreResumen, MetaKPICalidad


@admin.register(CargaExcel)
class CargaExcelAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_base",
        "origen",
        "archivo_nombre",
        "estado_reporte",
        "formato_kpi",
        "filas_totales",
        "filas_sin_cruce",
        "filas_con_error",
        "creado_por",
        "creado_en",
    )
    list_filter = ("origen", "tipo_base", "estado_reporte", "formato_kpi", "dia_reporte")
    search_fields = ("archivo_nombre",)


@admin.register(ClaroImport)
class ClaroImportAdmin(admin.ModelAdmin):
    list_display = ("num_pedido", "codigo_claro", "estado_pedido", "cruce_ok", "importado_en")
    list_filter = ("cruce_ok",)
    search_fields = ("num_pedido",)


@admin.register(KPIRegistro)
class KPIRegistroAdmin(admin.ModelAdmin):
    list_display = (
        "num_pedido",
        "camada",
        "boleta",
        "kpi_texto",
        "rgu",
        "marca_mes_kpi",
        "propietario_final",
        "cruce_ok",
        "diferencia_rut",
        "diferencia_rgu",
        "diferencia_propietario",
        "ejecutivo_kpi_no_resuelto",
        "carga",
    )
    list_filter = (
        "camada",
        "boleta",
        "marca_mes_kpi",
        "cruce_ok",
        "diferencia_rut",
        "diferencia_rgu",
        "diferencia_propietario",
        "ejecutivo_kpi_no_resuelto",
    )
    search_fields = ("num_pedido", "rut_cliente", "propietario_final", "bill_no")
    raw_id_fields = ("carga", "venta")


@admin.register(KPICierreResumen)
class KPICierreResumenAdmin(admin.ModelAdmin):
    list_display = ("camada", "boleta", "rut_vendedor_fuente", "ejecutivo", "pagadas", "total_medible", "kpi_pago_pct", "carga")
    list_filter = ("camada", "boleta")
    search_fields = ("rut_vendedor_fuente", "ejecutivo__rut", "ejecutivo__nombre")
    raw_id_fields = ("carga", "ejecutivo")


@admin.register(MetaKPICalidad)
class MetaKPICalidadAdmin(admin.ModelAdmin):
    list_display = ("vigente_desde", "meta_b1", "meta_b2", "meta_b3", "creado_por", "creado_en")
    search_fields = ("vigente_desde", "motivo")
    readonly_fields = ("creado_por", "creado_en")

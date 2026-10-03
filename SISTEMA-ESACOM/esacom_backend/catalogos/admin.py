from django.contrib import admin

from .models import Comuna, Promocion


@admin.register(Comuna)
class ComunaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "region")
    list_filter = ("region",)
    search_fields = ("nombre",)


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "rgu", "tiene_internet", "tiene_tv", "tiene_fono", "activa")
    list_filter = ("empresa", "activa")
    search_fields = ("nombre",)

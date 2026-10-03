from rest_framework import serializers

from catalogos.serializers import ComunaSerializer, PromocionSerializer
from usuarios.serializers import EjecutivoResumenSerializer

from .models import Apelacion, Corte, Gestion, Venta


class VentaSerializer(serializers.ModelSerializer):
    ejecutivo = EjecutivoResumenSerializer(read_only=True)
    ejecutivo_ce = EjecutivoResumenSerializer(read_only=True)
    ejecutivo_id = serializers.PrimaryKeyRelatedField(
        source="ejecutivo", queryset=Venta._meta.get_field("ejecutivo").related_model.objects.all(),
        write_only=True,
    )
    promocion = PromocionSerializer(read_only=True)
    promocion_id = serializers.PrimaryKeyRelatedField(
        source="promocion", queryset=Venta._meta.get_field("promocion").related_model.objects.all(),
        write_only=True,
    )
    comuna = ComunaSerializer(read_only=True)
    comuna_id = serializers.PrimaryKeyRelatedField(
        source="comuna", queryset=Venta._meta.get_field("comuna").related_model.objects.all(),
        write_only=True, required=False, allow_null=True,
    )

    class Meta:
        model = Venta
        fields = [
            "id", "rut_cliente", "nombre_cliente", "telefono_cliente", "n_pedido", "rut_evt", "nombre_evt",
            "origen_venta", "fecha_pago_honorarios", "rut_ce", "codigo_ce", "rgu_base", "ejecutivo_ce",
            "ejecutivo", "ejecutivo_id", "promocion", "promocion_id", "comuna", "comuna_id",
            "tipo_cliente", "estado_instalacion", "motivo_pendiente",
            "fecha_venta", "primera_agenda", "segunda_agenda", "fecha_cierre",
            "precio_venta", "honorarios", "ingresador", "camada",
        ]
        read_only_fields = ["id"]


class VentaResumenSerializer(serializers.ModelSerializer):
    """Para usar como nested dentro de Corte/Apelacion, sin anidar de nuevo."""

    ejecutivo = EjecutivoResumenSerializer(read_only=True)
    ejecutivo_ce = EjecutivoResumenSerializer(read_only=True)

    class Meta:
        model = Venta
        fields = [
            "id", "n_pedido", "rut_cliente", "ejecutivo", "ejecutivo_ce",
            "rut_evt", "nombre_evt", "origen_venta", "codigo_ce", "rgu_base", "estado_instalacion",
        ]


class CorteSerializer(serializers.ModelSerializer):
    venta = VentaResumenSerializer(read_only=True)
    venta_id = serializers.PrimaryKeyRelatedField(source="venta", queryset=Venta.objects.all(), write_only=True)
    dias_vencido = serializers.ReadOnlyField()
    esta_muerto = serializers.ReadOnlyField()
    verificado_por = EjecutivoResumenSerializer(read_only=True)
    ejecutivo_kpi = EjecutivoResumenSerializer(read_only=True)

    class Meta:
        model = Corte
        fields = [
            "id", "venta", "venta_id", "boleta", "mes_ano", "meta_pct",
            "estado_pago", "estado_claro", "estado_calculado",
            "fecha_vencimiento", "fecha_pago", "fecha_limite_medicion", "es_medible", "marca_mes_kpi", "carga_kpi", "dias_diferencia",
            "dias_vencido", "esta_muerto",
            "verificado_en_andes", "fecha_verificacion_andes", "verificado_por",
            "rgu_kpi", "propietario_final", "rut_propietario_final", "ejecutivo_kpi",
            "bill_no", "monto_boleta", "monto_pago", "rango_pago", "apelacion_claro",
        ]
        read_only_fields = [
            "id", "estado_claro", "estado_calculado", "fecha_limite_medicion", "es_medible", "marca_mes_kpi", "carga_kpi", "verificado_en_andes", "fecha_verificacion_andes", "verificado_por",
            "rgu_kpi", "propietario_final", "rut_propietario_final", "ejecutivo_kpi",
            "bill_no", "monto_boleta", "monto_pago", "rango_pago", "apelacion_claro",
        ]


class ApelacionSerializer(serializers.ModelSerializer):
    corte = CorteSerializer(read_only=True)
    corte_id = serializers.PrimaryKeyRelatedField(source="corte", queryset=Corte.objects.all(), write_only=True)
    excluida_por = EjecutivoResumenSerializer(read_only=True)

    class Meta:
        model = Apelacion
        fields = [
            "id", "corte", "corte_id", "motivo", "estado", "observacion", "bill_no",
            "fecha_deteccion", "fecha_envio", "fecha_respuesta", "excluida_por",
        ]
        read_only_fields = ["id", "fecha_deteccion", "excluida_por"]


class GestionSerializer(serializers.ModelSerializer):
    ejecutivo = EjecutivoResumenSerializer(read_only=True)
    venta_id = serializers.PrimaryKeyRelatedField(source="venta", queryset=Venta.objects.all(), write_only=True)

    class Meta:
        model = Gestion
        fields = ["id", "venta_id", "ejecutivo", "tipo", "resultado", "nota", "proximo_contacto", "creado_en"]
        read_only_fields = ["id", "ejecutivo", "creado_en"]

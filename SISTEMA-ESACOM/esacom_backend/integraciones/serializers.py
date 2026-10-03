from rest_framework import serializers

from usuarios.serializers import EjecutivoResumenSerializer

from .models import CargaExcel, ClaroImport, KPIRegistro, MetaKPICalidad


class ClaroImportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClaroImport
        fields = [
            "id",
            "num_pedido",
            "rgu",
            "codigo_claro",
            "ingresador",
            "estado_pedido",
            "fecha_creacion",
            "cruce_ok",
            "importado_en",
        ]
        # raw_data queda fuera a propósito: es para trazabilidad interna.


class KPIRegistroSerializer(serializers.ModelSerializer):
    tiene_inconsistencias = serializers.ReadOnlyField()
    rut_esacom = serializers.CharField(source="venta.rut_cliente", read_only=True, allow_null=True)
    rgu_esacom = serializers.IntegerField(source="venta.rgu_base", read_only=True, allow_null=True)
    codigo_ce_esacom = serializers.CharField(source="venta.codigo_ce", read_only=True, allow_null=True)
    rut_ce_esacom = serializers.CharField(source="venta.rut_ce", read_only=True, allow_null=True)
    ejecutivo_esacom = EjecutivoResumenSerializer(source="venta.ejecutivo", read_only=True)

    class Meta:
        model = KPIRegistro
        fields = [
            "id",
            "carga",
            "venta",
            "num_pedido",
            "camada",
            "boleta",
            "rut_cliente",
            "rut_esacom",
            "propietario_final",
            "codigo_ce_esacom",
            "rut_propietario_final",
            "rut_ce_esacom",
            "ejecutivo_esacom",
            "rgu",
            "rgu_esacom",
            "kpi_texto",
            "estado_normalizado",
            "bill_no",
            "fecha_pago",
            "fecha_vencimiento",
            "fecha_limite_medicion",
            "es_medible",
            "marca_mes_kpi",
            "estado_calculado",
            "diferencia_estado",
            "monto_boleta",
            "monto_pago",
            "rango_pago",
            "apelacion_claro",
            "cruce_ok",
            "diferencia_rut",
            "diferencia_rgu",
            "diferencia_propietario",
            "ejecutivo_kpi_no_resuelto",
            "tiene_inconsistencias",
            "importado_en",
        ]


class CargaExcelSerializer(serializers.ModelSerializer):
    creado_por = EjecutivoResumenSerializer(read_only=True)

    class Meta:
        model = CargaExcel
        fields = [
            "id",
            "origen",
            "tipo_base",
            "archivo_nombre",
            "fecha_corte",
            "dia_reporte",
            "estado_reporte",
            "formato_kpi",
            "avance_b1",
            "avance_b2",
            "avance_b3",
            "meta_b1",
            "meta_b2",
            "meta_b3",
            "foco_b1",
            "foco_b2",
            "foco_b3",
            "filas_totales",
            "filas_sin_cruce",
            "filas_con_error",
            "creado_por",
            "creado_en",
        ]


class MetaKPICalidadSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.CharField(source="creado_por.nombre", read_only=True, allow_null=True)

    class Meta:
        model = MetaKPICalidad
        fields = ["id", "vigente_desde", "meta_b1", "meta_b2", "meta_b3", "motivo", "creado_por", "creado_por_nombre", "creado_en"]
        read_only_fields = ["id", "creado_por", "creado_por_nombre", "creado_en"]

    def validate_vigente_desde(self, value):
        from integraciones.services.metas_kpi import camada_valida
        if not camada_valida(value):
            raise serializers.ValidationError("Usa formato YYYY-MM.")
        return value

    def validate(self, attrs):
        for campo in ("meta_b1", "meta_b2", "meta_b3"):
            valor = attrs.get(campo)
            if valor is not None and not (0 <= valor <= 100):
                raise serializers.ValidationError({campo: "La meta debe estar entre 0 y 100%."})
        motivo = str(attrs.get("motivo", "")).strip()
        if len(motivo) < 5:
            raise serializers.ValidationError({"motivo": "Indica un motivo de al menos 5 caracteres."})
        attrs["motivo"] = motivo
        return attrs

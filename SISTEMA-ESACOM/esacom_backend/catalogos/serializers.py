from rest_framework import serializers

from .models import Comuna, Promocion


class ComunaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comuna
        fields = ["id", "nombre", "region"]


class PromocionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promocion
        fields = ["id", "nombre", "rgu", "tiene_internet", "tiene_tv", "tiene_fono", "empresa", "canal", "activa"]

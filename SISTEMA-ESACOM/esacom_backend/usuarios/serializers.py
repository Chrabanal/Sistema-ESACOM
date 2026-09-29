from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import AuditoriaUsuario, Ejecutivo


class EjecutivoResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ejecutivo
        fields = ["id", "rut", "nombre", "cargo", "equipo", "tipo_kpi"]


class EjecutivoSerializer(serializers.ModelSerializer):
    supervisor = EjecutivoResumenSerializer(read_only=True)
    supervisor_id = serializers.PrimaryKeyRelatedField(
        source="supervisor", queryset=Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.SUPERVISOR),
        write_only=True, required=False, allow_null=True,
    )

    class Meta:
        model = Ejecutivo
        fields = [
            "id", "rut", "nombre", "correo", "cargo", "supervisor", "supervisor_id", "equipo",
            "telefono", "tipo_contrato", "tipo_kpi", "fecha_ingreso", "estado_contrato",
            "codigo_movil", "codigo_fijo", "codigo_andes", "is_active", "permisos_personalizados",
        ]
        read_only_fields = ["id"]


class UsuarioSoporteSerializer(serializers.ModelSerializer):
    supervisor = EjecutivoResumenSerializer(read_only=True)
    supervisor_id = serializers.PrimaryKeyRelatedField(
        source="supervisor",
        queryset=Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.SUPERVISOR, is_active=True),
        write_only=True,
        required=False,
        allow_null=True,
    )
    password = serializers.CharField(write_only=True, required=False, min_length=8, trim_whitespace=False)
    ultimo_acceso = serializers.DateTimeField(source="last_login", read_only=True)

    class Meta:
        model = Ejecutivo
        fields = [
            "id", "rut", "nombre", "correo", "cargo", "supervisor", "supervisor_id",
            "equipo", "telefono", "tipo_contrato", "tipo_kpi", "fecha_ingreso", "estado_contrato",
            "codigo_movil", "codigo_fijo", "codigo_andes", "is_active", "password",
            "cargo_fuente_esacom", "supervisor_fuente", "estado_contrato_fuente", "ultima_sync_dotacion",
            "creado_en", "actualizado_en", "ultimo_acceso",
        ]
        read_only_fields = [
            "id", "cargo_fuente_esacom", "supervisor_fuente", "estado_contrato_fuente",
            "ultima_sync_dotacion", "creado_en", "actualizado_en", "ultimo_acceso",
        ]

    def validate_password(self, value):
        try:
            usuario = self.instance if self.instance else None
            validate_password(value, user=usuario)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate_rut(self, value):
        normalizado = Ejecutivo.objects.normalize_rut(value)
        qs = Ejecutivo.objects.filter(rut=normalizado)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un usuario con este RUT.")
        return normalizado

    def validate(self, attrs):
        cargo = attrs.get("cargo", getattr(self.instance, "cargo", Ejecutivo.Cargo.EJECUTIVO))
        supervisor = attrs.get("supervisor", getattr(self.instance, "supervisor", None))

        if cargo != Ejecutivo.Cargo.EJECUTIVO:
            attrs["supervisor"] = None
        elif supervisor and supervisor.cargo != Ejecutivo.Cargo.SUPERVISOR:
            raise serializers.ValidationError({
                "supervisor_id": "El supervisor seleccionado no tiene rol SUPERVISOR."
            })

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({
                "password": "La contraseña temporal es obligatoria."
            })
        usuario = Ejecutivo(**validated_data)
        usuario.set_password(password)
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        if "password" in validated_data:
            raise serializers.ValidationError({
                "password": "Usa la acción de restablecimiento para cambiar la contraseña."
            })

        cargo_anterior = instance.cargo
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if "cargo" in validated_data and instance.cargo != cargo_anterior:
            instance.permisos_personalizados = {}
        instance.save()
        return instance


class AuditoriaUsuarioSerializer(serializers.ModelSerializer):
    actor_nombre = serializers.CharField(source="actor.nombre", read_only=True)
    actor_rut = serializers.CharField(source="actor.rut", read_only=True)
    objetivo_nombre = serializers.CharField(source="usuario_objetivo.nombre", read_only=True)
    objetivo_rut = serializers.CharField(source="usuario_objetivo.rut", read_only=True)

    class Meta:
        model = AuditoriaUsuario
        fields = [
            "id", "accion", "actor_nombre", "actor_rut", "objetivo_nombre", "objetivo_rut",
            "detalle", "creado_en",
        ]


class MeSerializer(serializers.ModelSerializer):
    permisos = serializers.SerializerMethodField()

    def get_permisos(self, obj):
        return obj.permisos_efectivos()

    class Meta:
        model = Ejecutivo
        fields = [
            "id", "rut", "nombre", "correo", "cargo", "equipo", "telefono",
            "tipo_contrato", "tipo_kpi", "permisos",
        ]


class PermisosUsuarioSerializer(serializers.ModelSerializer):
    permisos = serializers.SerializerMethodField()
    permisos_base = serializers.SerializerMethodField()

    class Meta:
        model = Ejecutivo
        fields = [
            "id", "rut", "nombre", "cargo", "equipo", "is_active",
            "permisos", "permisos_base", "permisos_personalizados",
        ]

    def get_permisos(self, obj):
        return obj.permisos_efectivos()

    def get_permisos_base(self, obj):
        actuales = obj.permisos_personalizados
        obj.permisos_personalizados = {}
        base = obj.permisos_efectivos()
        obj.permisos_personalizados = actuales
        return base


class RutTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        datos = attrs.copy()
        if datos.get("rut"):
            datos["rut"] = Ejecutivo.objects.normalize_rut(datos["rut"])
        return super().validate(datos)
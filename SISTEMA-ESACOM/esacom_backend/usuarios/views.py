import secrets
import string
import re
import unicodedata

from django.db import transaction
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.mixins import RoleScopedMixin
from core.permissions import EsGerencia, EsSoporte, EsSoporteOGerencia

from .models import AuditoriaUsuario, Ejecutivo
from .serializers import (
    AuditoriaUsuarioSerializer,
    EjecutivoSerializer,
    MeSerializer,
    RutTokenObtainPairSerializer,
    UsuarioSoporteSerializer,
    PermisosUsuarioSerializer,
)


class EjecutivoViewSet(RoleScopedMixin, viewsets.ModelViewSet):
    """Vista comercial de personal, acotada por rol."""

    queryset = Ejecutivo.objects.select_related("supervisor").all()
    serializer_class = EjecutivoSerializer
    ejecutivo_lookup = ""
    supervisor_lookup = "supervisor"

    def get_permissions(self):
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            return [EsGerencia()]
        return [IsAuthenticated()]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        return Response(MeSerializer(request.user).data)


class UsuarioSoporteViewSet(viewsets.ModelViewSet):
    """CRUD de accesos de plataforma, exclusivo para Soporte/superuser.

    No se expone eliminación física. El borrado operativo es desactivar para
    mantener íntegro el histórico comercial asociado al usuario.
    """

    permission_classes = [EsSoporte]
    serializer_class = UsuarioSoporteSerializer
    queryset = Ejecutivo.objects.select_related("supervisor").all().order_by("nombre")
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    pagination_class = None

    @staticmethod
    def _normalizar_busqueda(valor):
        """Texto comparable para búsqueda humana: sin tildes, case-insensitive y espacios normalizados."""
        texto = str(valor or "").strip().lower()
        texto = "".join(
            c for c in unicodedata.normalize("NFKD", texto)
            if not unicodedata.combining(c)
        )
        return re.sub(r"\s+", " ", texto)

    @classmethod
    def _coincide_busqueda(cls, usuario, consulta):
        """Permite fragmentos y múltiples términos sobre todo el perfil del usuario.

        Ejemplos válidos: ``cami``, ``bascu``, ``1976``, ``camilo quilpue`` o
        parte del nombre del supervisor. Todos los términos escritos deben
        aparecer en algún campo, sin importar mayúsculas ni tildes.
        """
        campos = [
            usuario.nombre, usuario.rut, usuario.correo, usuario.codigo_fijo,
            usuario.codigo_andes, usuario.equipo, usuario.cargo, usuario.tipo_kpi,
            usuario.estado_contrato, usuario.telefono, usuario.tipo_contrato,
            getattr(usuario.supervisor, "nombre", ""),
            getattr(usuario.supervisor, "rut", ""),
        ]
        normalizados = [cls._normalizar_busqueda(v) for v in campos if v not in (None, "")]
        texto = " | ".join(normalizados)
        compacto = re.sub(r"[^a-z0-9k]", "", texto)
        terminos = [t for t in cls._normalizar_busqueda(consulta).split(" ") if t]
        for termino in terminos:
            termino_compacto = re.sub(r"[^a-z0-9k]", "", termino)
            if termino not in texto and (not termino_compacto or termino_compacto not in compacto):
                return False
        return True

    def get_queryset(self):
        qs = super().get_queryset()
        q = (self.request.query_params.get("q") or "").strip()
        cargo = (self.request.query_params.get("cargo") or "").strip().upper()
        estado = (self.request.query_params.get("estado") or "").strip().lower()
        tipo_kpi = (self.request.query_params.get("tipo_kpi") or "").strip().upper()

        if cargo in Ejecutivo.Cargo.values:
            qs = qs.filter(cargo=cargo)
        if estado == "activo":
            qs = qs.filter(is_active=True)
        elif estado == "inactivo":
            qs = qs.filter(is_active=False)
        if tipo_kpi in Ejecutivo.TipoKPI.values:
            qs = qs.filter(tipo_kpi=tipo_kpi)

        # La dotación es pequeña y esta búsqueda en Python permite coincidencias
        # realmente amigables incluso con tildes, RUT formateados y supervisor.
        if q:
            ids = [u.pk for u in qs if self._coincide_busqueda(u, q)]
            qs = qs.filter(pk__in=ids)
        return qs

    @staticmethod
    def _snapshot(usuario):
        return {
            "rut": usuario.rut,
            "nombre": usuario.nombre,
            "correo": usuario.correo,
            "cargo": usuario.cargo,
            "supervisor_id": usuario.supervisor_id,
            "equipo": usuario.equipo,
            "estado_contrato": usuario.estado_contrato,
            "tipo_kpi": usuario.tipo_kpi,
            "is_active": usuario.is_active,
            "permisos_personalizados": usuario.permisos_personalizados,
        }

    def _auditar(self, accion, usuario, detalle=None):
        AuditoriaUsuario.objects.create(
            actor=self.request.user,
            usuario_objetivo=usuario,
            accion=accion,
            detalle=detalle or {},
        )

    @transaction.atomic
    def perform_create(self, serializer):
        usuario = serializer.save()
        self._auditar(AuditoriaUsuario.Accion.CREAR, usuario, {"despues": self._snapshot(usuario)})

    @transaction.atomic
    def perform_update(self, serializer):
        from rest_framework.exceptions import ValidationError
        antes = self._snapshot(serializer.instance)
        if serializer.instance.is_superuser and not self.request.user.is_superuser:
            raise ValidationError({"detail": "Un usuario de Soporte no puede modificar un superusuario técnico."})
        # Soporte no puede quitarse su propio acceso ni cambiar su propio rol.
        nuevo_cargo = serializer.validated_data.get("cargo")
        nuevo_activo = serializer.validated_data.get("is_active")
        if serializer.instance.pk == self.request.user.pk and nuevo_cargo and nuevo_cargo != serializer.instance.cargo:
            raise ValidationError({"cargo": "No puedes cambiar tu propio rol."})
        if serializer.instance.pk == self.request.user.pk and nuevo_activo is False:
            raise ValidationError({"is_active": "No puedes desactivar tu propia cuenta."})
        usuario = serializer.save()
        despues = self._snapshot(usuario)
        cambios = {k: {"antes": antes[k], "despues": despues[k]} for k in antes if antes[k] != despues[k]}
        self._auditar(AuditoriaUsuario.Accion.EDITAR, usuario, {"cambios": cambios})

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def activar(self, request, pk=None):
        usuario = self.get_object()
        usuario.is_active = True
        if usuario.estado_contrato == Ejecutivo.EstadoContrato.INACTIVO:
            usuario.estado_contrato = Ejecutivo.EstadoContrato.ACTIVO
        usuario.save(update_fields=["is_active", "estado_contrato", "actualizado_en"])
        self._auditar(AuditoriaUsuario.Accion.ACTIVAR, usuario)
        return Response(self.get_serializer(usuario).data)

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def desactivar(self, request, pk=None):
        usuario = self.get_object()
        if usuario.pk == request.user.pk:
            return Response({"detail": "No puedes desactivar tu propia cuenta."}, status=status.HTTP_400_BAD_REQUEST)
        if usuario.is_superuser:
            return Response({"detail": "No se puede desactivar un superusuario desde Soporte."}, status=status.HTTP_400_BAD_REQUEST)
        usuario.is_active = False
        usuario.estado_contrato = Ejecutivo.EstadoContrato.INACTIVO
        usuario.save(update_fields=["is_active", "estado_contrato", "actualizado_en"])
        self._auditar(AuditoriaUsuario.Accion.DESACTIVAR, usuario)
        return Response(self.get_serializer(usuario).data)

    @action(detail=True, methods=["post"], url_path="reset-password")
    @transaction.atomic
    def reset_password(self, request, pk=None):
        usuario = self.get_object()
        password = (request.data.get("password") or "").strip()
        generada = False
        if not password:
            alfabeto = string.ascii_letters + string.digits + "!@#$%"
            password = "".join(secrets.choice(alfabeto) for _ in range(12))
            generada = True
        try:
            validate_password(password, user=usuario)
        except DjangoValidationError as exc:
            return Response({"password": list(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)
        usuario.set_password(password)
        usuario.save(update_fields=["password", "actualizado_en"])
        self._auditar(AuditoriaUsuario.Accion.RESET_PASSWORD, usuario, {"generada_automaticamente": generada})
        return Response({
            "detail": "Contraseña restablecida correctamente.",
            "password_temporal": password if generada else None,
        })

    @action(detail=False, methods=["get"])
    def dotacion(self, request):
        """Vista auditable Ejecutivo -> Supervisor basada en última Dotación ESACOM."""
        qs = Ejecutivo.objects.select_related("supervisor").exclude(cargo__in=[Ejecutivo.Cargo.SOPORTE, Ejecutivo.Cargo.GERENCIA, Ejecutivo.Cargo.OPERACIONES, Ejecutivo.Cargo.CONTABILIDAD])
        supervisor = (request.query_params.get("supervisor") or "").strip()
        estado = (request.query_params.get("estado") or "").strip().lower()
        tipo = (request.query_params.get("tipo_kpi") or "").strip().upper()
        q = (request.query_params.get("q") or "").strip()
        if supervisor:
            if supervisor == "SIN_SUPERVISOR":
                qs = qs.filter(supervisor__isnull=True)
            else:
                qs = qs.filter(supervisor__rut=Ejecutivo.objects.normalize_rut(supervisor))
        if estado == "activo": qs = qs.filter(is_active=True)
        if estado == "inactivo": qs = qs.filter(is_active=False)
        if tipo in Ejecutivo.TipoKPI.values: qs = qs.filter(tipo_kpi=tipo)
        if q:
            ids = [u.pk for u in qs if self._coincide_busqueda(u, q) or self._normalizar_busqueda(q) in self._normalizar_busqueda(u.supervisor_fuente)]
            qs = qs.filter(pk__in=ids)
        qs = qs.order_by("supervisor__nombre", "nombre")
        filas = [{
            "id": u.id, "rut": u.rut, "nombre": u.nombre, "rol_crm": u.cargo,
            "cargo_fuente": u.cargo_fuente_esacom, "tipo_kpi": u.tipo_kpi,
            "estado": "ACTIVO" if u.is_active else "INACTIVO",
            "estado_fuente": u.estado_contrato_fuente, "equipo": u.equipo,
            "supervisor_fuente": u.supervisor_fuente,
            "supervisor": ({"rut": u.supervisor.rut, "nombre": u.supervisor.nombre} if u.supervisor else None),
            "ultima_sync": u.ultima_sync_dotacion,
        } for u in qs]
        base = Ejecutivo.objects.exclude(cargo__in=[Ejecutivo.Cargo.SOPORTE, Ejecutivo.Cargo.GERENCIA, Ejecutivo.Cargo.OPERACIONES, Ejecutivo.Cargo.CONTABILIDAD])
        return Response({
            "resumen": {
                "personas": base.count(), "activos": base.filter(is_active=True).count(),
                "inactivos": base.filter(is_active=False).count(),
                "honorarios": base.filter(is_active=True, tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS).count(),
                "sin_supervisor": base.filter(is_active=True, cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor__isnull=True).count(),
                "supervisores_crm": base.filter(is_active=True, cargo=Ejecutivo.Cargo.SUPERVISOR).count(),
            },
            "filas": filas,
        })

    @action(detail=False, methods=["get"])
    def resumen(self, request):
        total = Ejecutivo.objects.count()
        return Response({
            "total": total,
            "activos": Ejecutivo.objects.filter(is_active=True).count(),
            "inactivos": Ejecutivo.objects.filter(is_active=False).count(),
            "gerencia": Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.GERENCIA, is_active=True).count(),
            "supervisores": Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.SUPERVISOR, is_active=True).count(),
            "ejecutivos": Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.EJECUTIVO, is_active=True).count(),
            "honorarios": Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.EJECUTIVO, tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS, is_active=True).count(),
            "soporte": Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.SOPORTE, is_active=True).count(),
            "operaciones": Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.OPERACIONES, is_active=True).count(),
            "contabilidad": Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.CONTABILIDAD, is_active=True).count(),
        })


class PermisosUsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    """Centro de permisos administrado únicamente por Soporte o Gerencia."""
    permission_classes = [EsSoporteOGerencia]
    serializer_class = PermisosUsuarioSerializer
    queryset = Ejecutivo.objects.all().order_by("nombre")
    pagination_class = None

    @action(detail=True, methods=["patch"], url_path="configurar")
    @transaction.atomic
    def configurar(self, request, pk=None):
        usuario = self.get_object()
        if usuario.is_superuser and not request.user.is_superuser:
            return Response({"detail": "Los permisos del superusuario técnico no se modifican desde el CRM."}, status=400)
        if usuario.pk == request.user.pk:
            return Response({"detail": "No puedes modificar tus propios permisos desde esta pantalla."}, status=400)
        permitidos = set(usuario.permisos_efectivos().keys())
        payload = request.data.get("permisos", {})
        motivo = str(request.data.get("motivo", "")).strip()
        if not isinstance(payload, dict):
            return Response({"permisos": ["Debe ser un objeto clave/booleano."]}, status=400)
        if len(motivo) < 5:
            return Response({"motivo": ["Indica un motivo de al menos 5 caracteres para dejar trazabilidad."]}, status=400)

        # Estos módulos son administrativos y NO se delegan por checkbox.
        # Su acceso depende exclusivamente del rol para impedir escalamiento.
        no_delegables = {"usuarios", "permisos", "estado_sistema"}
        actuales_efectivos = usuario.permisos_efectivos()
        for clave in no_delegables:
            if clave in payload and bool(payload[clave]) != bool(actuales_efectivos.get(clave)):
                return Response(
                    {"detail": f"El permiso '{clave}' es administrativo y no delegable; cambia el rol si corresponde."},
                    status=400,
                )
        overrides = {}
        # Calcular base del rol sin overrides para guardar solo diferencias.
        actuales = usuario.permisos_personalizados
        usuario.permisos_personalizados = {}
        base = usuario.permisos_efectivos()
        usuario.permisos_personalizados = actuales
        for clave, valor in payload.items():
            if clave not in permitidos or not isinstance(valor, bool):
                continue
            if base.get(clave) != valor:
                overrides[clave] = valor
        antes = dict(usuario.permisos_personalizados or {})
        usuario.permisos_personalizados = overrides
        usuario.save(update_fields=["permisos_personalizados", "actualizado_en"])
        cambios = {}
        claves = sorted(set(antes) | set(overrides))
        for clave in claves:
            if antes.get(clave) != overrides.get(clave):
                cambios[clave] = {"antes": antes.get(clave), "despues": overrides.get(clave)}
        AuditoriaUsuario.objects.create(
            actor=request.user, usuario_objetivo=usuario, accion=AuditoriaUsuario.Accion.PERMISOS,
            detalle={"antes": antes, "despues": overrides, "cambios": cambios, "motivo": motivo},
        )
        return Response(self.get_serializer(usuario).data)

    @action(detail=True, methods=["post"], url_path="restablecer")
    @transaction.atomic
    def restablecer(self, request, pk=None):
        usuario = self.get_object()
        if usuario.pk == request.user.pk:
            return Response({"detail": "No puedes restablecer tus propios permisos."}, status=400)
        antes = dict(usuario.permisos_personalizados or {})
        usuario.permisos_personalizados = {}
        usuario.save(update_fields=["permisos_personalizados", "actualizado_en"])
        AuditoriaUsuario.objects.create(
            actor=request.user, usuario_objetivo=usuario, accion=AuditoriaUsuario.Accion.PERMISOS,
            detalle={"antes": antes, "despues": {}, "restablecido": True},
        )
        return Response(self.get_serializer(usuario).data)


class AuditoriaUsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [EsSoporteOGerencia]
    pagination_class = None
    serializer_class = AuditoriaUsuarioSerializer
    queryset = AuditoriaUsuario.objects.select_related("actor", "usuario_objetivo").all()


class RutTokenObtainPairView(TokenObtainPairView):
    serializer_class = RutTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'


class LogoutView(APIView):
    """Invalida el refresh token para cerrar una sesión de forma real."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = (request.data.get('refresh') or '').strip()
        if not refresh:
            return Response({'refresh': ['Token refresh obligatorio.']}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh).blacklist()
        except TokenError:
            # Idempotente: un token expirado/ya revocado se considera sesión cerrada.
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)

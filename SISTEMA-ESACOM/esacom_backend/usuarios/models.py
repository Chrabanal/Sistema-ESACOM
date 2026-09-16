import re

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class EjecutivoManager(BaseUserManager):
    """Manager custom porque el login es por RUT, no por username/email."""

    def create_user(self, rut, password=None, **extra_fields):
        if not rut:
            raise ValueError("El RUT es obligatorio")
        rut = self.normalize_rut(rut)
        user = self.model(rut=rut, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, rut, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("cargo", Ejecutivo.Cargo.GERENCIA)
        return self.create_user(rut, password, **extra_fields)

    @staticmethod
    def normalize_rut(rut: str) -> str:
        """Normaliza RUT para login/cruces: acepta puntos, espacios y sin guion."""
        if rut is None:
            return ""
        limpio = re.sub(r"[^0-9Kk]", "", str(rut)).upper()
        if len(limpio) < 2:
            return limpio
        cuerpo, dv = limpio[:-1], limpio[-1]
        cuerpo = cuerpo.lstrip("0") or "0"
        return f"{cuerpo}-{dv}"


class Ejecutivo(AbstractBaseUser, PermissionsMixin):
    """Personal ESACOM y usuario de acceso a la plataforma."""

    class Cargo(models.TextChoices):
        GERENCIA = "GERENCIA", "Gerencia"
        OPERACIONES = "OPERACIONES", "Operaciones"
        CONTABILIDAD = "CONTABILIDAD", "Contabilidad"
        SUPERVISOR = "SUPERVISOR", "Supervisor"
        EJECUTIVO = "EJECUTIVO", "Ejecutivo"
        SOPORTE = "SOPORTE", "Soporte"

    class EstadoContrato(models.TextChoices):
        ACTIVO = "ACTIVO", "Activo"
        INACTIVO = "INACTIVO", "Inactivo"
        LICENCIA = "LICENCIA", "Licencia"

    class TipoKPI(models.TextChoices):
        REGULAR = "REGULAR", "KPI regular"
        HONORARIOS = "HONORARIOS", "KPI honorarios"

    rut = models.CharField(max_length=12, unique=True, db_index=True)
    nombre = models.CharField(max_length=150)
    correo = models.EmailField(blank=True)
    cargo = models.CharField(max_length=20, choices=Cargo.choices, default=Cargo.EJECUTIVO)
    supervisor = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="miembros_equipo", limit_choices_to={"cargo": Cargo.SUPERVISOR},
        help_text="Auto-referencia: el supervisor de este ejecutivo.",
    )
    equipo = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)

    # Datos de origen ESACOM. Se conservan separados del rol de acceso CRM.
    cargo_fuente_esacom = models.CharField(max_length=100, blank=True)
    supervisor_fuente = models.CharField(max_length=150, blank=True, db_index=True)
    estado_contrato_fuente = models.CharField(max_length=100, blank=True)
    ultima_sync_dotacion = models.DateTimeField(null=True, blank=True)

    tipo_contrato = models.CharField(max_length=50, blank=True)
    tipo_kpi = models.CharField(
        max_length=20, choices=TipoKPI.choices, default=TipoKPI.REGULAR, db_index=True,
        help_text="Separa el KPI regular del KPI específico de vendedores a honorarios.",
    )
    fecha_ingreso = models.DateField(null=True, blank=True)
    estado_contrato = models.CharField(
        max_length=20, choices=EstadoContrato.choices, default=EstadoContrato.ACTIVO
    )

    codigo_movil = models.CharField(max_length=30, blank=True)
    codigo_fijo = models.CharField(max_length=30, blank=True)
    codigo_andes = models.CharField(max_length=30, blank=True)

    # Overrides de permisos por usuario. Solo se guardan diferencias respecto
    # del perfil base del rol; esto evita duplicar la matriz completa.
    permisos_personalizados = models.JSONField(default=dict, blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = EjecutivoManager()

    USERNAME_FIELD = "rut"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        verbose_name = "Ejecutivo"
        verbose_name_plural = "Ejecutivos"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.rut})"

    def save(self, *args, **kwargs):
        self.rut = EjecutivoManager.normalize_rut(self.rut)
        super().save(*args, **kwargs)

    @property
    def es_gerencia(self):
        return self.cargo == self.Cargo.GERENCIA

    @property
    def es_supervisor(self):
        return self.cargo == self.Cargo.SUPERVISOR

    @property
    def es_soporte(self):
        return self.cargo == self.Cargo.SOPORTE

    @property
    def es_honorarios(self):
        return self.tipo_kpi == self.TipoKPI.HONORARIOS

    @property
    def es_operaciones(self):
        return self.cargo == self.Cargo.OPERACIONES

    @property
    def es_contabilidad(self):
        return self.cargo == self.Cargo.CONTABILIDAD

    @property
    def tiene_alcance_global(self):
        return bool(self.is_superuser or self.es_gerencia or self.es_operaciones or self.es_contabilidad)

    def permisos_efectivos(self):
        """Matriz RBAC + overrides administrables por Soporte/Gerencia.

        El rol define el mínimo esperado y ``permisos_personalizados`` permite
        habilitar/deshabilitar módulos concretos sin alterar la fuente maestra
        de datos ni el alcance comercial del usuario.
        """
        modulos = [
            "dashboard_gerencia", "mi_equipo", "mi_portal", "accionables",
            "cobranza", "apelaciones", "historico", "base_datos",
            "auditoria_kpi", "cargar_datos", "analisis", "usuarios", "permisos", "estado_sistema",
        ]
        base = {k: False for k in modulos}
        por_rol = {
            self.Cargo.GERENCIA: {k: True for k in modulos},
            self.Cargo.OPERACIONES: {
                "accionables": True, "apelaciones": True, "historico": True,
                "base_datos": True, "auditoria_kpi": True, "cargar_datos": True,
                "analisis": True,
            },
            self.Cargo.CONTABILIDAD: {
                "cobranza": True, "historico": True, "auditoria_kpi": True,
            },
            self.Cargo.SUPERVISOR: {"mi_equipo": True, "accionables": True},
            self.Cargo.EJECUTIVO: {"mi_portal": True, "accionables": True},
            self.Cargo.SOPORTE: {"usuarios": True, "permisos": True, "estado_sistema": True, "cargar_datos": True, "historico": True},
        }
        base.update(por_rol.get(self.cargo, {}))
        if self.is_superuser:
            return {k: True for k in modulos}
        for clave, valor in (self.permisos_personalizados or {}).items():
            if clave in base and isinstance(valor, bool):
                base[clave] = valor

        # Seguridad: los módulos administrativos no son delegables mediante
        # overrides. Solo los roles GERENCIA/SOPORTE (o superusuario técnico)
        # pueden administrar usuarios/permisos. Así se evita escalamiento de
        # privilegios aunque alguien manipule el payload de la API.
        base["usuarios"] = bool(self.is_superuser or self.cargo == self.Cargo.SOPORTE)
        base["cargar_datos"] = bool(self.is_superuser or self.cargo == self.Cargo.SOPORTE)
        base["permisos"] = bool(self.is_superuser or self.cargo in (self.Cargo.SOPORTE, self.Cargo.GERENCIA))
        base["estado_sistema"] = bool(self.is_superuser or self.cargo in (self.Cargo.SOPORTE, self.Cargo.GERENCIA))
        return base

    def tiene_permiso(self, modulo):
        return bool(self.permisos_efectivos().get(modulo, False))


class AuditoriaUsuario(models.Model):
    """Trazabilidad de cambios realizados desde el módulo de Soporte."""

    class Accion(models.TextChoices):
        CREAR = "CREAR", "Crear usuario"
        EDITAR = "EDITAR", "Editar usuario"
        ACTIVAR = "ACTIVAR", "Activar usuario"
        DESACTIVAR = "DESACTIVAR", "Desactivar usuario"
        RESET_PASSWORD = "RESET_PASSWORD", "Restablecer contraseña"
        PERMISOS = "PERMISOS", "Modificar permisos"
        ASIGNACION_SUPERVISOR = "ASIGNACION_SUPERVISOR", "Actualizar supervisor desde ESACOM"

    actor = models.ForeignKey(
        Ejecutivo, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="auditorias_realizadas",
    )
    usuario_objetivo = models.ForeignKey(
        Ejecutivo, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="auditorias_recibidas",
    )
    accion = models.CharField(max_length=30, choices=Accion.choices)
    detalle = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "Auditoría de usuario"
        verbose_name_plural = "Auditorías de usuarios"

    def __str__(self):
        objetivo = self.usuario_objetivo.rut if self.usuario_objetivo else "eliminado"
        return f"{self.accion} · {objetivo}"

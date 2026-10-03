from pathlib import Path

from django.conf import settings
from django.db import connection
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.permissions import EsSoporteOGerencia
from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.models import Venta


@api_view(["GET"])
@permission_classes([EsSoporteOGerencia])
def estado_sistema(request):
    """Estado técnico seguro para UAT.

    No expone secretos, contraseñas ni contenido de credenciales. Su objetivo
    es que Soporte/Gerencia puedan confirmar que el ambiente está listo antes
    de comenzar una ronda de pruebas funcionales.
    """
    carga = (
        CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            fecha_corte__isnull=False,
        )
        .order_by("-fecha_corte", "-creado_en")
        .first()
    )

    google_id = str(getattr(settings, "GOOGLE_SHEETS_SPREADSHEET_ID", "") or "").strip()
    google_file = str(getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", "") or "").strip()
    credential_path = None
    credential_exists = False
    if google_file:
        p = Path(google_file)
        if not p.is_absolute():
            p = Path(settings.BASE_DIR) / p
        credential_path = p.name  # solo nombre; nunca ruta sensible completa
        credential_exists = p.exists()

    roles = {}
    for cargo, _ in Ejecutivo.Cargo.choices:
        roles[cargo] = {
            "total": Ejecutivo.objects.filter(cargo=cargo).count(),
            "activos": Ejecutivo.objects.filter(cargo=cargo, is_active=True).count(),
        }

    data = {
        "ambiente": {
            "debug": bool(settings.DEBUG),
            "base_datos": connection.vendor,
            "celery_eager": bool(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False)),
            "https_forzado": bool(getattr(settings, "SECURE_SSL_REDIRECT", False)),
        },
        "integraciones": {
            "google_sheets_id_configurado": bool(google_id),
            "credencial_google_configurada": bool(google_file),
            "credencial_google_existe": credential_exists,
            "credencial_google_archivo": credential_path,
        },
        "datos": {
            "usuarios": Ejecutivo.objects.count(),
            "usuarios_activos": Ejecutivo.objects.filter(is_active=True).count(),
            "ventas": Venta.objects.count(),
            "roles": roles,
        },
        "snapshot": {
            "disponible": bool(carga),
            "archivo": carga.archivo_nombre if carga else None,
            "fecha_corte": carga.fecha_corte if carga else None,
            "dia": carga.dia_reporte if carga else None,
            "focos": {
                "B1": carga.foco_b1 if carga else "",
                "B2": carga.foco_b2 if carga else "",
                "B3": carga.foco_b3 if carga else "",
            },
        },
    }

    checks = {
        "base_datos": connection.vendor in {"sqlite", "postgresql"},
        "google_sheets": bool(google_id and google_file and credential_exists),
        "snapshot_kpi": bool(carga),
        "usuarios": Ejecutivo.objects.filter(is_active=True).exists(),
        "ventas": Venta.objects.exists(),
    }
    data["checks"] = checks
    data["listo_uat"] = all(checks.values())
    data["listo_produccion"] = bool(
        data["listo_uat"]
        and connection.vendor == "postgresql"
        and not settings.DEBUG
        and bool(getattr(settings, "SECURE_SSL_REDIRECT", False))
    )
    return Response(data)

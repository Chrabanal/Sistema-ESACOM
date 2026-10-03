from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.models import Venta


class Command(BaseCommand):
    help = "Valida condiciones mínimas antes de iniciar una UAT general ESACOM."

    def _linea(self, ok, texto):
        estilo = self.style.SUCCESS if ok else self.style.ERROR
        self.stdout.write(estilo(("[OK] " if ok else "[FALTA] ") + texto))
        return ok

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("ESACOM · PRE-UAT GENERAL"))
        resultados = []

        resultados.append(self._linea(connection.vendor in {"sqlite", "postgresql"}, f"Base de datos activa: {connection.vendor}"))

        usuarios_activos = Ejecutivo.objects.filter(is_active=True).count()
        resultados.append(self._linea(usuarios_activos > 0, f"Usuarios activos: {usuarios_activos}"))
        resultados.append(self._linea(Venta.objects.exists(), f"Ventas ESACOM: {Venta.objects.count()}"))

        carga = (
            CargaExcel.objects.filter(tipo_base=CargaExcel.TipoBase.REPORTE_KPI, fecha_corte__isnull=False)
            .order_by("-fecha_corte", "-creado_en")
            .first()
        )
        if carga:
            resultados.append(self._linea(True, f"Snapshot activo: {carga.archivo_nombre} · corte {carga.fecha_corte} · {carga.dia_reporte or 'OTRO'}"))
            self.stdout.write(f"     Focos: B1 {carga.foco_b1 or '—'} · B2 {carga.foco_b2 or '—'} · B3 {carga.foco_b3 or '—'}")
        else:
            resultados.append(self._linea(False, "No hay snapshot KPI con fecha de corte."))

        google_id = str(getattr(settings, "GOOGLE_SHEETS_SPREADSHEET_ID", "") or "").strip()
        google_file = str(getattr(settings, "GOOGLE_SERVICE_ACCOUNT_FILE", "") or "").strip()
        p = Path(google_file) if google_file else None
        if p and not p.is_absolute():
            p = Path(settings.BASE_DIR) / p
        google_ok = bool(google_id and p and p.exists())
        resultados.append(self._linea(google_ok, "Google Sheets configurado y archivo de credenciales disponible." if google_ok else "Revisar GOOGLE_SHEETS_SPREADSHEET_ID / GOOGLE_SERVICE_ACCOUNT_FILE."))

        self.stdout.write("\nRoles activos:")
        for cargo, label in Ejecutivo.Cargo.choices:
            total = Ejecutivo.objects.filter(cargo=cargo, is_active=True).count()
            self.stdout.write(f"  - {label}: {total}")

        # Regresiones reales conocidas: se validan solo si esos usuarios existen.
        camilo = Ejecutivo.objects.filter(rut="19776727-8").first()
        if camilo:
            self.stdout.write(self.style.HTTP_INFO("\nCaso patrón Camilo detectado. Ejecuta:"))
            self.stdout.write("  python manage.py validar_dashboard_ejecutivo --rut 19776727-8")
        charly = Ejecutivo.objects.filter(rut="17480807-4").first()
        if charly:
            self.stdout.write(self.style.HTTP_INFO("Caso patrón Supervisor detectado. Ejecuta:"))
            self.stdout.write("  python manage.py validar_dashboard_supervisor --rut 17480807-4 --ejecutivo-rut 19776727-8")

        self.stdout.write("\nSeguridad del ambiente actual:")
        self.stdout.write(f"  DEBUG={settings.DEBUG}")
        self.stdout.write(f"  SECURE_SSL_REDIRECT={getattr(settings, 'SECURE_SSL_REDIRECT', False)}")
        self.stdout.write(f"  CELERY_TASK_ALWAYS_EAGER={getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False)}")
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING("  Ambiente apto para UAT local; NO corresponde aún a producción."))

        if all(resultados):
            self.stdout.write(self.style.SUCCESS("\nRESULTADO: ambiente listo para comenzar UAT general."))
        else:
            self.stdout.write(self.style.ERROR("\nRESULTADO: hay condiciones pendientes antes de UAT general."))

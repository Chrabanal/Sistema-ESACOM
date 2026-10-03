from django.core.management.base import BaseCommand, CommandError

from integraciones.locks import adquirir_lock_operacion_datos, liberar_lock_operacion_datos
from integraciones.services.google_sheets import sincronizar_base_matriz
from usuarios.models import Ejecutivo, EjecutivoManager


class Command(BaseCommand):
    help = "Sincroniza la base maestra ESACOM desde la Google Sheet configurada en .env."

    def add_arguments(self, parser):
        parser.add_argument("--usuario-rut", default="", help="RUT de quien ejecuta la sincronización.")

    def handle(self, *args, **options):
        usuario = None
        if options.get("usuario_rut"):
            usuario = Ejecutivo.objects.filter(rut=EjecutivoManager.normalize_rut(options["usuario_rut"])).first()

        try:
            lock = adquirir_lock_operacion_datos()
        except Exception as exc:
            raise CommandError(f"No se pudo verificar el lock de operaciones: {exc}") from exc
        if lock is False:
            raise CommandError("Hay una carga KPI o sincronización ESACOM en curso. Espera y vuelve a intentar.")

        try:
            resultado = sincronizar_base_matriz(creado_por=usuario)
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        finally:
            liberar_lock_operacion_datos(lock)

        self.stdout.write(self.style.SUCCESS("Sincronización Google Sheets completada."))
        self.stdout.write(str(resultado))

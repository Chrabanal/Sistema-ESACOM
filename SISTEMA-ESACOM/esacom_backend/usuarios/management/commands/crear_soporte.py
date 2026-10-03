from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Ejecutivo


class Command(BaseCommand):
    help = "Crea o convierte una cuenta en usuario SOPORTE para administrar accesos."

    def add_arguments(self, parser):
        parser.add_argument("--rut", required=True)
        parser.add_argument("--nombre", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--correo", default="")

    def handle(self, *args, **options):
        password = options["password"]
        if len(password) < 8:
            raise CommandError("La contraseña debe tener al menos 8 caracteres.")

        rut = Ejecutivo.objects.normalize_rut(options["rut"])
        usuario, creado = Ejecutivo.objects.get_or_create(
            rut=rut,
            defaults={
                "nombre": options["nombre"],
                "correo": options["correo"],
                "cargo": Ejecutivo.Cargo.SOPORTE,
                "is_active": True,
            },
        )
        usuario.nombre = options["nombre"]
        usuario.correo = options["correo"]
        usuario.cargo = Ejecutivo.Cargo.SOPORTE
        usuario.is_active = True
        usuario.supervisor = None
        usuario.set_password(password)
        usuario.save()

        verbo = "creado" if creado else "actualizado"
        self.stdout.write(self.style.SUCCESS(f"Usuario SOPORTE {verbo}: {usuario.rut} · {usuario.nombre}"))

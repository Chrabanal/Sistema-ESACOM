from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from usuarios.models import Ejecutivo


class Command(BaseCommand):
    help = "Crea o convierte una cuenta en usuario GERENCIA para UAT/operación."

    def add_arguments(self, parser):
        parser.add_argument("--rut", required=True)
        parser.add_argument("--nombre", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument("--correo", default="")

    def handle(self, *args, **options):
        rut = Ejecutivo.objects.normalize_rut(options["rut"])
        usuario, creado = Ejecutivo.objects.get_or_create(
            rut=rut,
            defaults={
                "nombre": options["nombre"],
                "correo": options["correo"],
                "cargo": Ejecutivo.Cargo.GERENCIA,
                "is_active": True,
            },
        )

        try:
            validate_password(options["password"], user=usuario)
        except ValidationError as exc:
            raise CommandError(" ".join(exc.messages))

        usuario.nombre = options["nombre"]
        usuario.correo = options["correo"]
        usuario.cargo = Ejecutivo.Cargo.GERENCIA
        usuario.is_active = True
        usuario.supervisor = None
        usuario.set_password(options["password"])
        usuario.save()

        verbo = "creado" if creado else "actualizado"
        self.stdout.write(self.style.SUCCESS(
            f"Usuario GERENCIA {verbo}: {usuario.rut} · {usuario.nombre}"
        ))

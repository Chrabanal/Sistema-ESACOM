from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from usuarios.models import Ejecutivo

class Command(BaseCommand):
    help = "Crea o actualiza un usuario del área Operaciones para UAT."
    def add_arguments(self, parser):
        parser.add_argument("--rut", required=True)
        parser.add_argument("--nombre", required=True)
        parser.add_argument("--correo", default="")
        parser.add_argument("--password", required=True)
    def handle(self, *args, **opts):
        try:
            validate_password(opts["password"])
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages))
        u, created = Ejecutivo.objects.get_or_create(rut=opts["rut"], defaults={"nombre": opts["nombre"]})
        u.nombre = opts["nombre"]
        u.correo = opts["correo"]
        u.cargo = Ejecutivo.Cargo.OPERACIONES
        u.is_active = True
        u.permisos_personalizados = {}
        u.set_password(opts["password"])
        u.save()
        self.stdout.write(self.style.SUCCESS(f"{'Creado' if created else 'Actualizado'} OPERACIONES: {u.nombre} · {u.rut}"))

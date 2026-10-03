from django.core.management.base import BaseCommand

from ventas.apelaciones import detectar_apelaciones
from ventas.models import Corte


class Command(BaseCommand):
    help = "Corre el motor de detección automática de apelaciones sobre todos los Corte."

    def add_arguments(self, parser):
        parser.add_argument("--mes-ano", type=str, default=None, help="Filtra por camada, ej. 2026-08")

    def handle(self, *args, **options):
        cortes = Corte.objects.all()
        if options["mes_ano"]:
            cortes = cortes.filter(mes_ano=options["mes_ano"])

        resultado = detectar_apelaciones(cortes)
        self.stdout.write(self.style.SUCCESS(
            f"Cortes revisados: {resultado.revisadas} | "
            f"Apelaciones nuevas: {resultado.creadas} | "
            f"Ya tenían apelación: {resultado.ya_existian}"
        ))

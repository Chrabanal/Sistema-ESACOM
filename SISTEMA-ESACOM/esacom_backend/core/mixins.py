"""
RoleScopedMixin: cada ViewSet declara CÓMO llegar desde su modelo hasta
el Ejecutivo dueño del registro (`ejecutivo_lookup`) y hasta su
supervisor (`supervisor_lookup`), y este mixin se encarga del resto:

- Gerencia / superuser -> ve todo.
- Supervisor -> ve lo suyo + lo de su equipo.
- Ejecutivo -> ve solo lo suyo.

Ejemplos de lookup por modelo:
  Ejecutivo:  ejecutivo_lookup=''                  supervisor_lookup='supervisor'
  Venta:      ejecutivo_lookup='ejecutivo'         supervisor_lookup='ejecutivo__supervisor'
  Corte:      ejecutivo_lookup='venta__ejecutivo'  supervisor_lookup='venta__ejecutivo__supervisor'
  Apelacion:  ejecutivo_lookup='corte__venta__ejecutivo'
              supervisor_lookup='corte__venta__ejecutivo__supervisor'
"""
from django.db.models import Q


class RoleScopedMixin:
    ejecutivo_lookup: str = "ejecutivo"
    supervisor_lookup: str = "ejecutivo__supervisor"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_authenticated:
            return qs.none()
        if user.es_gerencia or user.is_superuser:
            return qs

        if user.es_supervisor:
            filtro_propio = {self.ejecutivo_lookup: user} if self.ejecutivo_lookup else {"pk": user.pk}
            filtro_equipo = {self.supervisor_lookup: user}
            return qs.filter(Q(**filtro_propio) | Q(**filtro_equipo)).distinct()

        # Ejecutivo raso: solo lo suyo.
        filtro_propio = {self.ejecutivo_lookup: user} if self.ejecutivo_lookup else {"pk": user.pk}
        return qs.filter(**filtro_propio)

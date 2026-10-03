from django.core.management.base import BaseCommand
from django.db import transaction

from usuarios.dotacion import SUPERVISOR_ALIAS_A_RUT, SUPERVISOR_RUTS_CONFIRMADOS
from usuarios.models import AuditoriaUsuario, Ejecutivo, EjecutivoManager


class Command(BaseCommand):
    help = "Repara roles y asignaciones CRM usando los datos de Dotación ya sincronizados."

    @transaction.atomic
    def handle(self, *args, **options):
        protegidos = {
            Ejecutivo.Cargo.SOPORTE,
            Ejecutivo.Cargo.GERENCIA,
            Ejecutivo.Cargo.OPERACIONES,
            Ejecutivo.Cargo.CONTABILIDAD,
        }
        comerciales = Ejecutivo.objects.exclude(cargo__in=protegidos).filter(is_superuser=False)

        # 1) Reconciliar rol CRM por RUT confirmado, nunca por Cargo fuente.
        cambios_rol = 0
        for u in comerciales:
            esperado = (
                Ejecutivo.Cargo.SUPERVISOR
                if u.rut in SUPERVISOR_RUTS_CONFIRMADOS
                else Ejecutivo.Cargo.EJECUTIVO
            )
            if u.cargo != esperado:
                antes = u.cargo
                u.cargo = esperado
                if esperado == Ejecutivo.Cargo.SUPERVISOR:
                    u.supervisor = None
                    u.save(update_fields=["cargo", "supervisor", "actualizado_en"])
                else:
                    u.save(update_fields=["cargo", "actualizado_en"])
                cambios_rol += 1
                AuditoriaUsuario.objects.create(
                    actor=None,
                    usuario_objetivo=u,
                    accion=AuditoriaUsuario.Accion.EDITAR,
                    detalle={"origen": "reconciliar_dotacion_crm", "cargo_antes": antes, "cargo_despues": esperado},
                )

        # 2) Asegurar que existan los cuatro supervisores confirmados con rol correcto.
        supervisores = {}
        for rut in SUPERVISOR_RUTS_CONFIRMADOS:
            n = EjecutivoManager.normalize_rut(rut)
            sup = Ejecutivo.objects.filter(rut=n).first()
            if sup:
                if sup.cargo != Ejecutivo.Cargo.SUPERVISOR:
                    sup.cargo = Ejecutivo.Cargo.SUPERVISOR
                    sup.supervisor = None
                    sup.save(update_fields=["cargo", "supervisor", "actualizado_en"])
                supervisores[n] = sup

        # 3) Reconciliar asignación desde supervisor_fuente exacto.
        cambios_asignacion = 0
        sin_resolver = 0
        for u in Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.EJECUTIVO, is_active=True):
            alias = " ".join((u.supervisor_fuente or "").strip().upper().split())
            rut_sup = SUPERVISOR_ALIAS_A_RUT.get(alias)
            nuevo = supervisores.get(EjecutivoManager.normalize_rut(rut_sup)) if rut_sup else None
            if not nuevo:
                sin_resolver += 1
            if u.supervisor_id != (nuevo.id if nuevo else None):
                u.supervisor = nuevo
                u.save(update_fields=["supervisor", "actualizado_en"])
                cambios_asignacion += 1

        self.stdout.write(self.style.SUCCESS(
            f"Roles corregidos: {cambios_rol} · Asignaciones corregidas: {cambios_asignacion} · Activos sin alias resuelto: {sin_resolver}"
        ))
        self.stdout.write("Supervisores CRM confirmados: " + ", ".join(sorted(SUPERVISOR_RUTS_CONFIRMADOS)))

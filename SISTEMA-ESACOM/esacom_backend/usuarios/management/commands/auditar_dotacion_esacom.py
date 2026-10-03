from django.core.management.base import BaseCommand
from usuarios.dotacion import SUPERVISOR_ALIAS_A_RUT, SUPERVISOR_RUTS_CONFIRMADOS
from usuarios.models import Ejecutivo


class Command(BaseCommand):
    help = "Audita dotación, vigencia y asignaciones después de sincronizar ESACOM."

    def handle(self, *args, **opts):
        protegidos = [Ejecutivo.Cargo.SOPORTE, Ejecutivo.Cargo.GERENCIA, Ejecutivo.Cargo.OPERACIONES, Ejecutivo.Cargo.CONTABILIDAD]
        base = Ejecutivo.objects.exclude(cargo__in=protegidos).filter(is_superuser=False)
        confirmados = Ejecutivo.objects.filter(rut__in=SUPERVISOR_RUTS_CONFIRMADOS).order_by("nombre")

        self.stdout.write(self.style.MIGRATE_HEADING("ESACOM · AUDITORÍA DOTACIÓN"))
        self.stdout.write(f"Personas CRM comerciales: {base.count()}")
        self.stdout.write(f"Activos: {base.filter(is_active=True).count()} · Inactivos: {base.filter(is_active=False).count()}")
        self.stdout.write(f"Honorarios activos: {base.filter(is_active=True, tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS).count()}")
        self.stdout.write(f"Supervisores CRM confirmados encontrados: {confirmados.count()} / {len(SUPERVISOR_RUTS_CONFIRMADOS)}")
        self.stdout.write("")

        for sup in confirmados:
            eq = Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=sup, is_active=True)
            self.stdout.write(
                f"- {sup.nombre} · {sup.rut}: {eq.count()} vigentes · "
                f"{eq.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR).count()} Regular · "
                f"{eq.filter(tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS).count()} Honorarios"
            )

        sin = Ejecutivo.objects.filter(cargo=Ejecutivo.Cargo.EJECUTIVO, is_active=True, supervisor__isnull=True)
        self.stdout.write("")
        self.stdout.write(f"SIN SUPERVISOR RESUELTO: {sin.count()}")
        alias = sorted(set(x for x in sin.values_list("supervisor_fuente", flat=True) if x))
        for a in alias:
            self.stdout.write(self.style.WARNING(f"  - alias fuente pendiente: {a}"))

        mal_rol = base.filter(cargo=Ejecutivo.Cargo.SUPERVISOR).exclude(rut__in=SUPERVISOR_RUTS_CONFIRMADOS)
        self.stdout.write(f"SUPERVISORES CRM NO CONFIRMADOS: {mal_rol.count()}")
        for u in mal_rol.order_by("nombre"):
            self.stdout.write(self.style.ERROR(f"  - {u.rut} · {u.nombre} · Cargo fuente: {u.cargo_fuente_esacom}"))

        if mal_rol.exists():
            self.stdout.write(self.style.ERROR("[ERROR] Hay usuarios con rol SUPERVISOR que no pertenecen al catálogo confirmado."))
        elif sin.exists():
            self.stdout.write(self.style.WARNING("[ALERTA] Hay ejecutivos vigentes sin supervisor CRM resuelto."))
        else:
            self.stdout.write(self.style.SUCCESS("[OK] Roles confirmados y ejecutivos vigentes con supervisor resuelto."))

from django.core.management.base import BaseCommand, CommandError

from integraciones.models import CargaExcel
from usuarios.models import Ejecutivo
from ventas.models import Corte
from ventas.services import resumen_cortes_actuales, resumen_por_ejecutivo_actual, resumen_por_supervisor_actual


class Command(BaseCommand):
    help = "Valida el Dashboard Gerencia usando ESACOM como fuente maestra y solo KPI REGULAR."

    def handle(self, *args, **options):
        ultima = CargaExcel.objects.filter(
            tipo_base=CargaExcel.TipoBase.REPORTE_KPI,
            fecha_corte__isnull=False,
        ).order_by("-fecha_corte", "-creado_en").first()
        if not ultima:
            raise CommandError("No hay reportes KPI cargados.")

        focos = {"B1": ultima.foco_b1, "B2": ultima.foco_b2, "B3": ultima.foco_b3}
        metas = {
            "B1": float(ultima.meta_b1) if ultima.meta_b1 is not None else None,
            "B2": float(ultima.meta_b2) if ultima.meta_b2 is not None else None,
            "B3": float(ultima.meta_b3) if ultima.meta_b3 is not None else None,
        }

        # Filtro defensivo explícito: Gerencia REGULAR nunca mezcla Honorarios.
        cortes = Corte.objects.filter(
            carga_kpi=ultima,
            venta__estado_instalacion="INSTALADO",
            venta__ejecutivo__tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
            venta__ejecutivo__cargo=Ejecutivo.Cargo.EJECUTIVO,
            venta__ejecutivo__is_active=True,
        )
        globales = resumen_cortes_actuales(cortes, focos=focos, metas=metas)
        supervisores = resumen_por_supervisor_actual(cortes, focos=focos, metas=metas)
        ejecutivos = resumen_por_ejecutivo_actual(cortes, focos=focos, metas=metas)

        regulares_activos = Ejecutivo.objects.filter(
            cargo=Ejecutivo.Cargo.EJECUTIVO,
            tipo_kpi=Ejecutivo.TipoKPI.REGULAR,
            is_active=True,
        )
        honorarios_activos = Ejecutivo.objects.filter(
            cargo=Ejecutivo.Cargo.EJECUTIVO,
            tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS,
            is_active=True,
        )
        activos_ids = set(regulares_activos.values_list("id", flat=True))
        medidos_ids = {e["ejecutivo"]["id"] for e in ejecutivos if e["ejecutivo"]["id"] in activos_ids}

        self.stdout.write(self.style.SUCCESS(
            f"Snapshot activo: #{ultima.id} · {ultima.archivo_nombre} · corte {ultima.fecha_corte} · {ultima.dia_reporte}"
        ))
        self.stdout.write(f"Focos: B1 {focos['B1']} · B2 {focos['B2']} · B3 {focos['B3']}")
        self.stdout.write(
            f"Dotación KPI: {regulares_activos.count()} Regular activos · "
            f"{len(medidos_ids)} Regular medidos · "
            f"{regulares_activos.exclude(id__in=medidos_ids).count()} Regular sin base medible · "
            f"{honorarios_activos.count()} Honorarios separados"
        )

        self.stdout.write("\nKPI GLOBAL REGULAR")
        for c in globales:
            self.stdout.write(
                f"{c['boleta']} {c['mes_ano']} → {c['pct_cumplimiento']:.2f}% "
                f"| Meta {c['meta_pct']:.1f}% | Q meta {c['faltan_para_meta']} RGU "
                f"| Pago {c['pagadas']} / Total {c['total']}"
            )

        self.stdout.write(f"\nSupervisores medidos: {len(supervisores)}")
        for s in supervisores[:10]:
            sid = s['supervisor']['id']
            sup = Ejecutivo.objects.filter(id=sid).first()
            asignados = Ejecutivo.objects.filter(
                cargo=Ejecutivo.Cargo.EJECUTIVO, supervisor=sup, is_active=True
            ) if sup else Ejecutivo.objects.none()
            reg_asig = asignados.filter(tipo_kpi=Ejecutivo.TipoKPI.REGULAR)
            hon_asig = asignados.filter(tipo_kpi=Ejecutivo.TipoKPI.HONORARIOS)
            reg_asig_ids = set(reg_asig.values_list("id", flat=True))
            medidos_sup = set()
            for e in ejecutivos:
                if (
                    e['ejecutivo'].get('supervisor_id') == sid
                    and e['ejecutivo']['id'] in reg_asig_ids
                ):
                    medidos_sup.add(e['ejecutivo']['id'])
            self.stdout.write(
                f"- {s['supervisor']['nombre']} · "
                f"{reg_asig.count()} Regular asignados · {len(medidos_sup)} medidos · "
                f"{reg_asig.exclude(id__in=medidos_sup).count()} sin base · "
                f"{hon_asig.count()} Honorarios · promedio {s['promedio_focos']:.1f}% · "
                f"Q meta {s['q_para_meta_total']}"
            )

        self.stdout.write(f"\nEjecutivos REGULAR medidos: {len(ejecutivos)}")
        for e in ejecutivos[:10]:
            tipo = e['ejecutivo'].get('tipo_kpi', 'REGULAR')
            if tipo != Ejecutivo.TipoKPI.REGULAR:
                raise CommandError(
                    f"ERROR de segregación: {e['ejecutivo']['nombre']} aparece como {tipo} en ranking REGULAR."
                )
            self.stdout.write(f"- {e['ejecutivo']['nombre']} · promedio {e['promedio_focos']:.1f}%")

import django.db.models.deletion
from django.db import migrations, models


def backfill_carga_kpi(apps, schema_editor):
    """Asocia cada Corte legado al último snapshot KPI donde apareció.

    KPIRegistro ya conserva la historia por carga. Esto permite migrar desde
    V4 sin dejar el Portal vacío y, a la vez, evita marcar como vigentes filas
    que desaparecieron del último reporte.
    """
    Corte = apps.get_model("ventas", "Corte")
    KPIRegistro = apps.get_model("integraciones", "KPIRegistro")

    ultimo_por_clave = {}
    registros = (
        KPIRegistro.objects.filter(venta_id__isnull=False)
        .order_by("-carga__fecha_corte", "-carga__creado_en", "-carga_id")
        .values_list("venta_id", "camada", "boleta", "carga_id")
    )
    for venta_id, camada, boleta, carga_id in registros.iterator(chunk_size=2000):
        clave = (venta_id, camada, boleta)
        if clave not in ultimo_por_clave:
            ultimo_por_clave[clave] = carga_id

    buffer = []
    for corte in Corte.objects.all().iterator(chunk_size=2000):
        carga_id = ultimo_por_clave.get((corte.venta_id, corte.mes_ano, corte.boleta))
        if carga_id:
            corte.carga_kpi_id = carga_id
            buffer.append(corte)
            if len(buffer) >= 2000:
                Corte.objects.bulk_update(buffer, ["carga_kpi"], batch_size=2000)
                buffer.clear()
    if buffer:
        Corte.objects.bulk_update(buffer, ["carga_kpi"], batch_size=2000)


class Migration(migrations.Migration):
    dependencies = [
        ("integraciones", "0008_kpiregistro_marca_mes_kpi"),
        ("ventas", "0013_corte_marca_mes_kpi"),
    ]

    operations = [
        migrations.AddField(
            model_name="corte",
            name="carga_kpi",
            field=models.ForeignKey(
                blank=True,
                db_index=True,
                help_text="Último snapshot KPI de Claro en el que esta fila estuvo presente. Evita mezclar filas obsoletas de cargas anteriores.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cortes_vigentes",
                to="integraciones.cargaexcel",
            ),
        ),
        migrations.RunPython(backfill_carga_kpi, migrations.RunPython.noop),
    ]

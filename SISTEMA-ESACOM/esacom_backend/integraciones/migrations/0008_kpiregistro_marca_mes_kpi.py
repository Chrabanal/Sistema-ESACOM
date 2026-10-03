from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integraciones", "0007_carga_snapshot_produccion_esacom"),
    ]

    operations = [
        migrations.AddField(
            model_name="kpiregistro",
            name="marca_mes_kpi",
            field=models.SmallIntegerField(
                blank=True,
                db_index=True,
                help_text="Marca de mes original de Claro: 1 entra al foco KPI; 0 queda fuera de medición.",
                null=True,
            ),
        ),
    ]

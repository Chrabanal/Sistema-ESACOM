from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0012_ventafijafuente_conflicto_fuente"),
    ]

    operations = [
        migrations.AddField(
            model_name="corte",
            name="marca_mes_kpi",
            field=models.SmallIntegerField(
                blank=True,
                db_index=True,
                help_text="Marca de mes oficial del reporte Claro: 1 entra al foco KPI; 0 queda fuera de medición.",
                null=True,
            ),
        ),
    ]

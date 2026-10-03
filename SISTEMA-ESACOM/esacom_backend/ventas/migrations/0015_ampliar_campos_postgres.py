from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0014_corte_carga_kpi"),
    ]

    operations = [
        migrations.AlterField(
            model_name="venta",
            name="rut_cliente",
            field=models.CharField(db_index=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="venta",
            name="motivo_pendiente",
            field=models.CharField(blank=True, max_length=500),
        ),
    ]

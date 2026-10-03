from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ventas", "0008_gestion_resultado_proximo_contacto"),
    ]

    operations = [
        migrations.AlterField(
            model_name="venta",
            name="rut_evt",
            field=models.CharField(blank=True, db_index=True, max_length=12),
        ),
        migrations.AlterField(
            model_name="venta",
            name="nombre_evt",
            field=models.CharField(blank=True, db_index=True, max_length=150),
        ),
        migrations.AddField(
            model_name="venta",
            name="origen_venta",
            field=models.CharField(
                choices=[("BASE_VENTAS", "Base de Ventas ESACOM"), ("HONORARIOS", "Honorarios ESACOM")],
                db_index=True,
                default="BASE_VENTAS",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="venta",
            name="fecha_pago_honorarios",
            field=models.DateField(blank=True, null=True),
        ),
    ]

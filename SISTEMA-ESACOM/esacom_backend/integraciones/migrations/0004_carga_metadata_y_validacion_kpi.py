from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integraciones", "0003_kpiregistro"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaexcel",
            name="avance_b1",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name="cargaexcel",
            name="avance_b2",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name="cargaexcel",
            name="avance_b3",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True),
        ),
        migrations.AddField(
            model_name="cargaexcel",
            name="dia_reporte",
            field=models.CharField(
                blank=True,
                choices=[("LUNES", "Lunes"), ("MIERCOLES", "Miércoles"), ("OTRO", "Otro")],
                max_length=12,
            ),
        ),
        migrations.AddField(
            model_name="cargaexcel",
            name="fecha_corte",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="kpiregistro",
            name="diferencia_estado",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="kpiregistro",
            name="es_medible",
            field=models.BooleanField(db_index=True, default=True),
        ),
        migrations.AddField(
            model_name="kpiregistro",
            name="estado_calculado",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="kpiregistro",
            name="fecha_limite_medicion",
            field=models.DateField(blank=True, null=True),
        ),
    ]

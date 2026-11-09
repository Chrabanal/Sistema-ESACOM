from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integraciones", "0018_kpiregistro_b1_open_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cargaexcel",
            name="dia_reporte",
            field=models.CharField(
                blank=True,
                choices=[
                    ("LUNES", "Lunes"),
                    ("MIERCOLES", "Miércoles"),
                    ("JUEVES", "Jueves"),
                    ("OTRO", "Otro"),
                ],
                max_length=12,
            ),
        ),
    ]

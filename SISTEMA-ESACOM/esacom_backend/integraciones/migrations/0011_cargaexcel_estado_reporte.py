from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integraciones", "0010_meta_kpi_calidad_pre_julio_2026"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaexcel",
            name="estado_reporte",
            field=models.CharField(
                choices=[("AVANCE", "Avance"), ("CIERRE", "Cierre")],
                db_index=True,
                default="AVANCE",
                help_text="AVANCE para reportes semanales; CIERRE congela el resultado de cada camada/boleta incluida.",
                max_length=10,
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integraciones", "0005_carga_metas_kpi")]

    operations = [
        migrations.AddField(model_name="cargaexcel", name="foco_b1", field=models.CharField(blank=True, help_text="Camada oficial B1 del reporte, ej. 2026-07", max_length=7)),
        migrations.AddField(model_name="cargaexcel", name="foco_b2", field=models.CharField(blank=True, help_text="Camada oficial B2 del reporte, ej. 2026-06", max_length=7)),
        migrations.AddField(model_name="cargaexcel", name="foco_b3", field=models.CharField(blank=True, help_text="Camada oficial B3 del reporte, ej. 2026-05", max_length=7)),
    ]

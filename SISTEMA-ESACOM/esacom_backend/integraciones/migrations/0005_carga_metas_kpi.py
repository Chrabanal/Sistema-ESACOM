from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integraciones", "0004_carga_metadata_y_validacion_kpi")]
    operations = [
        migrations.AddField(model_name="cargaexcel", name="meta_b1", field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
        migrations.AddField(model_name="cargaexcel", name="meta_b2", field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
        migrations.AddField(model_name="cargaexcel", name="meta_b3", field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integraciones", "0006_carga_focos_kpi"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaexcel",
            name="fuente_modificada_en",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="cargaexcel",
            name="fuente_sha256",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="cargaexcel",
            name="resumen_produccion",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

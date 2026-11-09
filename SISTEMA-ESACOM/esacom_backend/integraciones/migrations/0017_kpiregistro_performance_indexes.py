from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integraciones", "0016_kpiregistro_snapshot_esacom_json")]

    operations = [
        migrations.AddIndex(
            model_name="kpiregistro",
            index=models.Index(
                fields=["carga", "camada", "boleta", "cruce_ok"],
                name="kpi_carga_camada_bol_ok_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="kpiregistro",
            index=models.Index(
                fields=["camada", "boleta", "carga"],
                name="kpi_camada_bol_carga_idx",
            ),
        ),
    ]

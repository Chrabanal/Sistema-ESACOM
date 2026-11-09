from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("integraciones", "0017_kpiregistro_performance_indexes")]

    operations = [
        migrations.AddIndex(
            model_name="kpiregistro",
            index=models.Index(
                fields=["carga", "boleta", "marca_mes_kpi", "camada"],
                name="kpi_carga_bol_marca_cam_idx",
            ),
        ),
    ]

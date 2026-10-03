from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integraciones", "0012_formato_kpi_cierre_resumen"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cargaexcel",
            name="formato_kpi",
            field=models.CharField(
                choices=[
                    ("DETALLADO", "Avance detallado Claro/VTR"),
                    ("CIERRE_FIJO", "Cierre Claro Fijo"),
                    ("CIERRE_MOVIL", "Cierre Claro Móvil"),
                ],
                db_index=True,
                default="DETALLADO",
                help_text=(
                    "DETALLADO para avances semanales con NUM_PEDIDO; CIERRE_FIJO para cierre oficial Fijo "
                    "con NUM_PEDIDO; CIERRE_MOVIL para cierre oficial Móvil agregado sin NUM_PEDIDO."
                ),
                max_length=20,
            ),
        ),
    ]

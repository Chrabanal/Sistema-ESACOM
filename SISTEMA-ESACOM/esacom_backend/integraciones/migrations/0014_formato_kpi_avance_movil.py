from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integraciones", "0013_formato_kpi_cierre_fijo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cargaexcel",
            name="formato_kpi",
            field=models.CharField(
                choices=[
                    ("DETALLADO", "Avance detallado Claro/VTR"),
                    ("AVANCE_MOVIL", "Avance Claro Móvil"),
                    ("CIERRE_FIJO", "Cierre Claro Fijo"),
                    ("CIERRE_MOVIL", "Cierre Claro Móvil"),
                ],
                db_index=True,
                default="DETALLADO",
                help_text=(
                    "DETALLADO para avances semanales Fijo con NUM_PEDIDO; AVANCE_MOVIL para avance "
                    "Móvil agregado sin NUM_PEDIDO; CIERRE_FIJO para cierre oficial Fijo con NUM_PEDIDO; "
                    "CIERRE_MOVIL para cierre oficial Móvil agregado sin NUM_PEDIDO."
                ),
                max_length=20,
            ),
        ),
    ]

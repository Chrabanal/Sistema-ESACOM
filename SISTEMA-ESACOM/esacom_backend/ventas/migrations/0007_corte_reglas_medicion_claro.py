from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0006_kpi_cruce_modelo"),
    ]

    operations = [
        migrations.AddField(
            model_name="corte",
            name="es_medible",
            field=models.BooleanField(
                db_index=True,
                default=True,
                help_text="False cuando fecha_vencimiento + 8 días queda después de la fecha de corte del reporte.",
            ),
        ),
        migrations.AddField(
            model_name="corte",
            name="estado_calculado",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PAGADO", "Pagado"),
                    ("PENDIENTE", "Pendiente"),
                    ("NO_PAGO", "No Pago"),
                    ("FUERA_PLAZO", "Pagado Fuera de Plazo"),
                    ("SIN_BOLETA", "Sin Boleta (S/B)"),
                    ("FUERA_MEDICION", "Fuera de medición"),
                ],
                help_text="Validación ESACOM calculada sin sobrescribir el estado original informado por Claro.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="corte",
            name="fecha_limite_medicion",
            field=models.DateField(
                blank=True,
                help_text="Fecha de vencimiento + 8 días según regla de medición Claro.",
                null=True,
            ),
        ),
    ]

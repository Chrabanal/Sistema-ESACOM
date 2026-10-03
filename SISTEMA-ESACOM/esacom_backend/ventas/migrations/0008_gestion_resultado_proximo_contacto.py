from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ventas", "0007_corte_reglas_medicion_claro")]

    operations = [
        migrations.AddField(
            model_name="gestion",
            name="resultado",
            field=models.CharField(
                blank=True,
                choices=[
                    ("CONTACTADO", "Contactado"),
                    ("NO_CONTESTA", "No contesta"),
                    ("COMPROMISO_PAGO", "Compromiso de pago"),
                    ("NUMERO_INVALIDO", "Número inválido"),
                    ("REAGENDAR", "Reagendar"),
                    ("OTRO", "Otro"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="gestion",
            name="proximo_contacto",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="gestion",
            name="nota",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name="gestion",
            name="tipo",
            field=models.CharField(
                choices=[("LLAMADA", "Llamada"), ("WHATSAPP", "WhatsApp"), ("OTRO", "Otro")],
                max_length=10,
            ),
        ),
    ]

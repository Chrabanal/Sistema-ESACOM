from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("usuarios", "0002_soporte_auditoria_correo"),
    ]

    operations = [
        migrations.AddField(
            model_name="ejecutivo",
            name="tipo_kpi",
            field=models.CharField(
                choices=[("REGULAR", "KPI regular"), ("HONORARIOS", "KPI honorarios")],
                db_index=True,
                default="REGULAR",
                help_text="Separa el KPI regular del KPI específico de vendedores a honorarios.",
                max_length=20,
            ),
        ),
    ]

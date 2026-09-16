from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0003_ejecutivo_tipo_kpi")]

    operations = [
        migrations.AddField(
            model_name="ejecutivo",
            name="permisos_personalizados",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="ejecutivo",
            name="cargo",
            field=models.CharField(choices=[
                ("GERENCIA", "Gerencia"), ("OPERACIONES", "Operaciones"),
                ("CONTABILIDAD", "Contabilidad"), ("SUPERVISOR", "Supervisor"),
                ("EJECUTIVO", "Ejecutivo"), ("SOPORTE", "Soporte")
            ], default="EJECUTIVO", max_length=20),
        ),
    ]

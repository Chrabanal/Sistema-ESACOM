from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="ejecutivo",
            name="correo",
            field=models.EmailField(blank=True, max_length=254),
        ),
        migrations.AlterField(
            model_name="ejecutivo",
            name="cargo",
            field=models.CharField(
                choices=[
                    ("GERENCIA", "Gerencia"),
                    ("SUPERVISOR", "Supervisor"),
                    ("EJECUTIVO", "Ejecutivo"),
                    ("SOPORTE", "Soporte"),
                ],
                default="EJECUTIVO",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="AuditoriaUsuario",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("accion", models.CharField(choices=[("CREAR", "Crear usuario"), ("EDITAR", "Editar usuario"), ("ACTIVAR", "Activar usuario"), ("DESACTIVAR", "Desactivar usuario"), ("RESET_PASSWORD", "Restablecer contraseña")], max_length=30)),
                ("detalle", models.JSONField(blank=True, default=dict)),
                ("creado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="auditorias_realizadas", to="usuarios.ejecutivo")),
                ("usuario_objetivo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="auditorias_recibidas", to="usuarios.ejecutivo")),
            ],
            options={"verbose_name": "Auditoría de usuario", "verbose_name_plural": "Auditorías de usuarios", "ordering": ["-creado_en"]},
        ),
    ]

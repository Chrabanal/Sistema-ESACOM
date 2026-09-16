from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("usuarios", "0005_alter_auditoriausuario_accion")]
    operations = [
        migrations.AddField(model_name="ejecutivo", name="cargo_fuente_esacom", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="ejecutivo", name="supervisor_fuente", field=models.CharField(blank=True, db_index=True, max_length=150)),
        migrations.AddField(model_name="ejecutivo", name="estado_contrato_fuente", field=models.CharField(blank=True, max_length=100)),
        migrations.AddField(model_name="ejecutivo", name="ultima_sync_dotacion", field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(
            model_name="auditoriausuario", name="accion",
            field=models.CharField(choices=[("CREAR", "Crear usuario"), ("EDITAR", "Editar usuario"), ("ACTIVAR", "Activar usuario"), ("DESACTIVAR", "Desactivar usuario"), ("RESET_PASSWORD", "Restablecer contraseña"), ("PERMISOS", "Modificar permisos"), ("ASIGNACION_SUPERVISOR", "Actualizar supervisor desde ESACOM")], max_length=30),
        ),
    ]

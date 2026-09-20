
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_roles_permisos_usuario'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditoriausuario',
            name='accion',
            field=models.CharField(choices=[('CREAR', 'Crear usuario'), ('EDITAR', 'Editar usuario'), ('ACTIVAR', 'Activar usuario'), ('DESACTIVAR', 'Desactivar usuario'), ('RESET_PASSWORD', 'Restablecer contraseña'), ('PERMISOS', 'Modificar permisos')], max_length=30),
        ),
    ]


import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0003_venta_nombre_cliente_venta_telefono_cliente_gestion'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='corte',
            name='estado_claro',
            field=models.CharField(blank=True, help_text='Estado tal como lo reportó Claro en su último KPI. No se pisa nunca.', max_length=15),
        ),
        migrations.AddField(
            model_name='corte',
            name='fecha_verificacion_andes',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='corte',
            name='verificado_en_andes',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='corte',
            name='verificado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cortes_verificados', to=settings.AUTH_USER_MODEL),
        ),
    ]

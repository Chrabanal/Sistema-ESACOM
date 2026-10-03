
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0009_venta_origen_honorarios'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='corte',
            name='ejecutivo_kpi',
            field=models.ForeignKey(blank=True, help_text='Ejecutivo interpretado desde Claro solo para auditoría; la atribución del dashboard usa Venta.ejecutivo (RUT EVT ESACOM).', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cortes_kpi', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='venta',
            name='ejecutivo_ce',
            field=models.ForeignKey(blank=True, help_text='CE/propietario final informado en la base; no cambia al dueño ESACOM de la venta.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ventas_como_ce', to=settings.AUTH_USER_MODEL),
        ),
    ]

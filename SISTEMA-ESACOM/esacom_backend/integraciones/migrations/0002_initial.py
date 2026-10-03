
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('integraciones', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='cargaexcel',
            name='creado_por',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cargas', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='claroimport',
            name='carga',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='registros_claro', to='integraciones.cargaexcel'),
        ),
        migrations.AddIndex(
            model_name='claroimport',
            index=models.Index(fields=['num_pedido'], name='integracion_num_ped_c86b53_idx'),
        ),
    ]

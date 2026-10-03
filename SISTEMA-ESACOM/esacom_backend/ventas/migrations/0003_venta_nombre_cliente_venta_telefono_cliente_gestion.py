
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0002_corte_apelacion_claro_corte_rango_pago_metakpi'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='venta',
            name='nombre_cliente',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name='venta',
            name='telefono_cliente',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.CreateModel(
            name='Gestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('LLAMADA', 'Llamada'), ('WHATSAPP', 'WhatsApp')], max_length=10)),
                ('nota', models.CharField(blank=True, max_length=300)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('ejecutivo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestiones', to=settings.AUTH_USER_MODEL)),
                ('venta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gestiones', to='ventas.venta')),
            ],
            options={
                'verbose_name': 'Gestión',
                'verbose_name_plural': 'Gestiones',
                'ordering': ['-creado_en'],
            },
        ),
    ]

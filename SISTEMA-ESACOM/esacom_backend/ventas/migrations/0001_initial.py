
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalogos', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Corte',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('boleta', models.CharField(choices=[('B1', '1ª Boleta'), ('B2', '2ª Boleta'), ('B3', '3ª Boleta')], max_length=2)),
                ('mes_ano', models.CharField(help_text="Mes evaluado, ej. '2026-08'", max_length=7)),
                ('meta_pct', models.DecimalField(decimal_places=2, help_text='Meta vigente para este corte, ej. 85.00', max_digits=5)),
                ('estado_pago', models.CharField(choices=[('PAGADO', 'Pagado'), ('PENDIENTE', 'Pendiente'), ('NO_PAGO', 'No Pago'), ('FUERA_PLAZO', 'Pagado Fuera de Plazo'), ('SIN_BOLETA', 'Sin Boleta (S/B)')], default='PENDIENTE', max_length=15)),
                ('fecha_vencimiento', models.DateField(blank=True, null=True)),
                ('fecha_pago', models.DateField(blank=True, null=True)),
                ('dias_diferencia', models.SmallIntegerField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Corte',
                'verbose_name_plural': 'Cortes',
                'ordering': ['venta', 'boleta'],
            },
        ),
        migrations.CreateModel(
            name='Apelacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('motivo', models.CharField(choices=[('ACREDITACION', 'Apelación por acreditación'), ('APROVISIONAMIENTO', 'Aprovisionamiento y facturación'), ('SUSPENSION', 'Cliente suspendido o desconectado')], max_length=20)),
                ('estado', models.CharField(choices=[('DETECTADA', 'Detectada'), ('EXCLUIDA', 'Excluida manualmente'), ('ENVIADA', 'Enviada a Claro'), ('APROBADA_EN_PLAZO', 'Aprobada — Pagado en Plazo'), ('APROBADA_FUERA_PLAZO', 'Aprobada — Pagado Fuera de Plazo'), ('RECHAZADA', 'Rechazada — Pagado Fuera de Plazo')], default='DETECTADA', max_length=25)),
                ('observacion', models.TextField(blank=True)),
                ('bill_no', models.CharField(blank=True, max_length=30)),
                ('fecha_deteccion', models.DateTimeField(auto_now_add=True)),
                ('fecha_envio', models.DateTimeField(blank=True, null=True)),
                ('fecha_respuesta', models.DateTimeField(blank=True, null=True)),
                ('excluida_por', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='apelaciones_excluidas', to=settings.AUTH_USER_MODEL)),
                ('corte', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='apelacion', to='ventas.corte')),
            ],
            options={
                'verbose_name': 'Apelación',
                'verbose_name_plural': 'Apelaciones',
                'ordering': ['-fecha_deteccion'],
            },
        ),
        migrations.CreateModel(
            name='Venta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rut_cliente', models.CharField(db_index=True, max_length=12)),
                ('n_pedido', models.CharField(db_index=True, max_length=30, unique=True)),
                ('rut_evt', models.CharField(blank=True, max_length=12)),
                ('nombre_evt', models.CharField(blank=True, max_length=150)),
                ('tipo_cliente', models.CharField(choices=[('B2C', 'B2C'), ('B2B', 'B2B')], default='B2C', max_length=3)),
                ('estado_instalacion', models.CharField(choices=[('INSTALADO', 'Instalado'), ('PENDIENTE_COMERCIAL', 'Pendiente comercial'), ('PENDIENTE_INSTALACION', 'Pendiente instalación'), ('ANULADO', 'Anulado')], default='PENDIENTE_INSTALACION', max_length=25)),
                ('motivo_pendiente', models.CharField(blank=True, max_length=200)),
                ('fecha_venta', models.DateField()),
                ('primera_agenda', models.DateField(blank=True, null=True)),
                ('segunda_agenda', models.DateField(blank=True, null=True)),
                ('fecha_cierre', models.DateField(blank=True, null=True)),
                ('precio_venta', models.DecimalField(blank=True, decimal_places=0, max_digits=10, null=True)),
                ('honorarios', models.DecimalField(blank=True, decimal_places=0, max_digits=10, null=True)),
                ('ingresador', models.CharField(blank=True, max_length=100)),
                ('camada', models.CharField(db_index=True, help_text="Mes de la venta, ej. '2026-08'", max_length=7)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('comuna', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ventas', to='catalogos.comuna')),
                ('ejecutivo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ventas', to=settings.AUTH_USER_MODEL)),
                ('promocion', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='ventas', to='catalogos.promocion')),
            ],
            options={
                'verbose_name': 'Venta',
                'verbose_name_plural': 'Ventas',
                'ordering': ['-fecha_venta'],
            },
        ),
        migrations.AddField(
            model_name='corte',
            name='venta',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cortes', to='ventas.venta'),
        ),
        migrations.AddIndex(
            model_name='venta',
            index=models.Index(fields=['camada', 'ejecutivo'], name='ventas_vent_camada_f9b2da_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='corte',
            unique_together={('venta', 'boleta')},
        ),
    ]

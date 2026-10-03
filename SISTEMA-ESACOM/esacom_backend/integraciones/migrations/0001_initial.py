
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='CargaExcel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('origen', models.CharField(choices=[('MANUAL', 'Carga manual'), ('AUTOMATICO_SHEETS', 'Automático (Google Sheets)')], max_length=20)),
                ('tipo_base', models.CharField(choices=[('BASE_MATRIZ', 'Base matriz'), ('REPORTE_CLARO', 'Reporte Claro'), ('ANDES', 'Andes')], max_length=20)),
                ('archivo_nombre', models.CharField(blank=True, max_length=255)),
                ('filas_totales', models.PositiveIntegerField(default=0)),
                ('filas_sin_cruce', models.PositiveIntegerField(default=0)),
                ('filas_con_error', models.PositiveIntegerField(default=0)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Carga de Excel',
                'verbose_name_plural': 'Cargas de Excel',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='ClaroImport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('num_pedido', models.CharField(db_index=True, max_length=30)),
                ('rgu', models.PositiveSmallIntegerField(blank=True, null=True)),
                ('codigo_claro', models.CharField(blank=True, max_length=30)),
                ('ingresador', models.CharField(blank=True, max_length=100)),
                ('estado_pedido', models.CharField(blank=True, max_length=50)),
                ('fecha_creacion', models.DateField(blank=True, null=True)),
                ('raw_data', models.JSONField(help_text='Registro completo tal como llegó de Claro.')),
                ('cruce_ok', models.BooleanField(default=False, help_text='True si encontró match en Venta por n_pedido.')),
                ('importado_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Registro Claro',
                'verbose_name_plural': 'Registros Claro',
            },
        ),
    ]

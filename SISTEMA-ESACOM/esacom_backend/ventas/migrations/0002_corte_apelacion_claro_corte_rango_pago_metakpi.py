
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='corte',
            name='apelacion_claro',
            field=models.SmallIntegerField(blank=True, help_text='Código 0/1/2 que trae el reporte de Claro (distinto de nuestra tabla Apelacion).', null=True),
        ),
        migrations.AddField(
            model_name='corte',
            name='rango_pago',
            field=models.CharField(blank=True, help_text='Bucket de urgencia de Claro: Pago / Gestionar vence 0-7 / Vencido 0-8 / etc.', max_length=40),
        ),
        migrations.CreateModel(
            name='MetaKPI',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mes_ano', models.CharField(db_index=True, help_text="Ej. '2026-08'", max_length=7)),
                ('boleta', models.CharField(choices=[('B1', '1ª Boleta'), ('B2', '2ª Boleta'), ('B3', '3ª Boleta')], max_length=2)),
                ('canal', models.CharField(choices=[('FIJO', 'Fijo'), ('MOVIL', 'Móvil')], default='FIJO', max_length=5)),
                ('tipo_cliente', models.CharField(choices=[('B2C', 'B2C'), ('B2B', 'B2B')], default='B2C', max_length=3)),
                ('meta_pct', models.DecimalField(decimal_places=2, max_digits=5)),
            ],
            options={
                'verbose_name': 'Meta KPI',
                'verbose_name_plural': 'Metas KPI',
                'ordering': ['-mes_ano', 'boleta'],
                'unique_together': {('mes_ano', 'boleta', 'canal', 'tipo_cliente')},
            },
        ),
    ]

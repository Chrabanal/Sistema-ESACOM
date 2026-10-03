
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Comuna',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True)),
                ('region', models.CharField(max_length=100)),
            ],
            options={
                'verbose_name': 'Comuna',
                'verbose_name_plural': 'Comunas',
                'ordering': ['region', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='Promocion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=150, unique=True)),
                ('rgu', models.PositiveSmallIntegerField(default=1)),
                ('tiene_internet', models.BooleanField(default=False)),
                ('tiene_tv', models.BooleanField(default=False)),
                ('tiene_fono', models.BooleanField(default=False)),
                ('empresa', models.CharField(choices=[('VTR', 'VTR'), ('CLARO', 'Claro')], max_length=10)),
                ('canal', models.CharField(blank=True, max_length=50)),
                ('activa', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Promoción',
                'verbose_name_plural': 'Promociones',
                'ordering': ['nombre'],
            },
        ),
    ]

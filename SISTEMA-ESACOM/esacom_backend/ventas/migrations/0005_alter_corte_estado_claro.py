
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0004_corte_estado_claro_corte_fecha_verificacion_andes_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='corte',
            name='estado_claro',
            field=models.CharField(blank=True, choices=[('PAGADO', 'Pagado'), ('PENDIENTE', 'Pendiente'), ('NO_PAGO', 'No Pago'), ('FUERA_PLAZO', 'Pagado Fuera de Plazo'), ('SIN_BOLETA', 'Sin Boleta (S/B)')], help_text='Estado tal como lo reportó Claro en su último KPI. No se pisa nunca.', max_length=15),
        ),
    ]

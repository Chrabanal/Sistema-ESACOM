
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ventas", "0005_alter_corte_estado_claro"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="corte",
            name="estado_claro",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PAGADO", "Pagado"),
                    ("PENDIENTE", "Pendiente"),
                    ("NO_PAGO", "No Pago"),
                    ("FUERA_PLAZO", "Pagado Fuera de Plazo"),
                    ("SIN_BOLETA", "Sin Boleta (S/B)"),
                ],
                help_text="Último estado reportado por Claro. El historial por carga queda en KPIRegistro.",
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name="venta",
            name="rut_ce",
            field=models.CharField(blank=True, db_index=True, max_length=12),
        ),
        migrations.AddField(
            model_name="venta",
            name="codigo_ce",
            field=models.CharField(blank=True, db_index=True, max_length=30),
        ),
        migrations.AddField(
            model_name="venta",
            name="rgu_base",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="RGU informado por la Base de Ventas de ESACOM.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="venta",
            name="ejecutivo_ce",
            field=models.ForeignKey(
                blank=True,
                help_text="Ejecutivo/CE propietario final de la venta para efectos de KPI.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ventas_como_ce",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="venta",
            name="ejecutivo",
            field=models.ForeignKey(
                blank=True,
                help_text="EVT original. Puede faltar en respaldos históricos incompletos.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="ventas",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="corte",
            name="rgu_kpi",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="RGU reportado por Claro para esta camada/boleta.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="corte",
            name="propietario_final",
            field=models.CharField(blank=True, db_index=True, max_length=50),
        ),
        migrations.AddField(
            model_name="corte",
            name="rut_propietario_final",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="corte",
            name="ejecutivo_kpi",
            field=models.ForeignKey(
                blank=True,
                help_text="Ejecutivo resuelto desde PROPIETARIO_FINAL/CODIGO CE para atribución del KPI.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="cortes_kpi",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="corte",
            name="bill_no",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="corte",
            name="monto_boleta",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AddField(
            model_name="corte",
            name="monto_pago",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True),
        ),
        migrations.AlterUniqueTogether(
            name="corte",
            unique_together=set(),
        ),
        migrations.AlterModelOptions(
            name="corte",
            options={
                "ordering": ["venta", "mes_ano", "boleta"],
                "verbose_name": "Corte",
                "verbose_name_plural": "Cortes",
            },
        ),
        migrations.AddConstraint(
            model_name="corte",
            constraint=models.UniqueConstraint(
                fields=("venta", "mes_ano", "boleta"),
                name="uniq_corte_venta_camada_boleta",
            ),
        ),
        migrations.AddIndex(
            model_name="corte",
            index=models.Index(
                fields=["mes_ano", "boleta", "estado_pago"],
                name="ventas_cort_mes_ano_97858a_idx",
            ),
        ),
    ]

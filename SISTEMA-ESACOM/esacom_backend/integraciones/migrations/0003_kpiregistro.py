
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integraciones", "0002_initial"),
        ("ventas", "0006_kpi_cruce_modelo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cargaexcel",
            name="tipo_base",
            field=models.CharField(
                choices=[
                    ("BASE_MATRIZ", "Base matriz"),
                    ("REPORTE_CLARO", "Reporte Claro"),
                    ("REPORTE_KPI", "Reporte KPI"),
                    ("ANDES", "Andes"),
                ],
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="KPIRegistro",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("num_pedido", models.CharField(db_index=True, max_length=30)),
                ("camada", models.CharField(db_index=True, help_text="Ej. 2026-07", max_length=7)),
                ("boleta", models.CharField(db_index=True, help_text="B1/B2/B3", max_length=2)),
                ("rut_cliente", models.CharField(blank=True, max_length=20)),
                ("propietario_final", models.CharField(blank=True, db_index=True, max_length=50)),
                ("rut_propietario_final", models.CharField(blank=True, max_length=20)),
                ("supervisor_fuente", models.CharField(blank=True, max_length=100)),
                ("ingresador", models.CharField(blank=True, max_length=100)),
                ("comuna", models.CharField(blank=True, max_length=100)),
                ("rgu", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("kpi_texto", models.CharField(blank=True, max_length=40)),
                ("estado_normalizado", models.CharField(blank=True, max_length=20)),
                ("bill_no", models.CharField(blank=True, max_length=50)),
                ("fecha_pago", models.DateField(blank=True, null=True)),
                ("fecha_vencimiento", models.DateField(blank=True, null=True)),
                ("monto_boleta", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("monto_pago", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("rango_pago", models.CharField(blank=True, max_length=40)),
                ("apelacion_claro", models.SmallIntegerField(blank=True, null=True)),
                ("cruce_ok", models.BooleanField(db_index=True, default=False)),
                ("diferencia_rut", models.BooleanField(default=False)),
                ("diferencia_rgu", models.BooleanField(default=False)),
                ("diferencia_propietario", models.BooleanField(default=False)),
                ("ejecutivo_kpi_no_resuelto", models.BooleanField(default=False)),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("importado_en", models.DateTimeField(auto_now_add=True)),
                (
                    "carga",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="registros_kpi",
                        to="integraciones.cargaexcel",
                    ),
                ),
                (
                    "venta",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="registros_kpi",
                        to="ventas.venta",
                    ),
                ),
            ],
            options={
                "verbose_name": "Registro KPI",
                "verbose_name_plural": "Registros KPI",
                "ordering": ["-importado_en", "num_pedido", "boleta"],
            },
        ),
        migrations.AddConstraint(
            model_name="kpiregistro",
            constraint=models.UniqueConstraint(
                fields=("carga", "num_pedido", "camada", "boleta"),
                name="uniq_kpi_por_carga_pedido_camada_boleta",
            ),
        ),
        migrations.AddIndex(
            model_name="kpiregistro",
            index=models.Index(
                fields=["num_pedido", "camada", "boleta"],
                name="integracion_num_ped_9c50e2_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="kpiregistro",
            index=models.Index(
                fields=["cruce_ok", "camada", "boleta"],
                name="integracion_cruce_o_7a8d20_idx",
            ),
        ),
    ]

# Generated manually for ESACOM CRM V4.3.11 R2.3
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("integraciones", "0014_formato_kpi_avance_movil"),
    ]

    operations = [
        migrations.CreateModel(
            name="KPICierreFijoFila",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("camada", models.CharField(db_index=True, max_length=7)),
                ("boleta", models.CharField(db_index=True, max_length=2)),
                ("fila_fuente", models.PositiveIntegerField()),
                ("n_pedido", models.CharField(blank=True, db_index=True, max_length=30)),
                ("rut_evt", models.CharField(blank=True, db_index=True, max_length=20)),
                ("nombre_evt", models.CharField(blank=True, db_index=True, max_length=150)),
                ("supervisor_fuente", models.CharField(blank=True, db_index=True, max_length=150)),
                ("tipo_kpi", models.CharField(blank=True, max_length=20)),
                ("rgu", models.PositiveSmallIntegerField(default=0)),
                ("estado_kpi", models.CharField(blank=True, max_length=40)),
                ("categoria", models.CharField(choices=[("PAGO", "Pago"), ("NO_PAGO", "No Pago"), ("FUERA_PLAZO", "Pagado Fuera de Plazo"), ("PENDIENTE", "Pendiente"), ("SIN_BOLETA", "S/B"), ("N_D", "#N/D")], db_index=True, max_length=20)),
                ("fuente_poblacion", models.CharField(default="VENTA_FIJA_FUENTE", max_length=30)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("carga", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cierre_fijo_filas", to="integraciones.cargaexcel")),
            ],
            options={
                "verbose_name": "Fila cierre KPI Fijo",
                "verbose_name_plural": "Filas cierre KPI Fijo",
                "ordering": ["supervisor_fuente", "nombre_evt", "fila_fuente"],
            },
        ),
        migrations.AddConstraint(
            model_name="kpicierrefijofila",
            constraint=models.UniqueConstraint(fields=("carga", "camada", "boleta", "fila_fuente"), name="uniq_cierre_fijo_fila_snapshot"),
        ),
        migrations.AddIndex(
            model_name="kpicierrefijofila",
            index=models.Index(fields=["carga", "camada", "boleta"], name="cierre_fijo_carga_cb_idx"),
        ),
        migrations.AddIndex(
            model_name="kpicierrefijofila",
            index=models.Index(fields=["supervisor_fuente", "camada"], name="cierre_fijo_sup_mes_idx"),
        ),
        migrations.AddIndex(
            model_name="kpicierrefijofila",
            index=models.Index(fields=["rut_evt", "camada"], name="cierre_fijo_rut_mes_idx"),
        ),
    ]

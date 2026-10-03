from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def crear_meta_inicial(apps, schema_editor):
    Meta = apps.get_model("integraciones", "MetaKPICalidad")
    Meta.objects.get_or_create(
        vigente_desde="2026-07",
        defaults={
            "meta_b1": Decimal("85.00"),
            "meta_b2": Decimal("83.00"),
            "meta_b3": Decimal("80.00"),
            "motivo": "Meta ESACOM confirmada por Gerencia desde ventas de julio 2026.",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("integraciones", "0008_kpiregistro_marca_mes_kpi"),
        ("usuarios", "0006_dotacion_fuente_y_auditoria"),
    ]

    operations = [
        migrations.CreateModel(
            name="MetaKPICalidad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("vigente_desde", models.CharField(db_index=True, help_text="Camada desde la que aplica, formato YYYY-MM.", max_length=7, unique=True)),
                ("meta_b1", models.DecimalField(decimal_places=2, max_digits=5)),
                ("meta_b2", models.DecimalField(decimal_places=2, max_digits=5)),
                ("meta_b3", models.DecimalField(decimal_places=2, max_digits=5)),
                ("motivo", models.CharField(blank=True, max_length=250)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="metas_kpi_calidad_creadas", to="usuarios.ejecutivo")),
            ],
            options={
                "verbose_name": "Meta KPI Calidad",
                "verbose_name_plural": "Metas KPI Calidad",
                "ordering": ["-vigente_desde", "-creado_en"],
            },
        ),
        migrations.RunPython(crear_meta_inicial, migrations.RunPython.noop),
    ]

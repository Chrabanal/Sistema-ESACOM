from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0001_initial"),
        ("ventas", "0011_produccion_actual_movil_y_trazabilidad"),
    ]

    operations = [
        migrations.AddField(
            model_name="venta",
            name="conflicto_fuente",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text="True cuando Base de Ventas trae más de una fila del mismo pedido con datos operacionales incompatibles.",
            ),
        ),
        migrations.AddField(
            model_name="venta",
            name="detalle_conflicto_fuente",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Trazabilidad del conflicto detectado en la matriz ESACOM; no se usa para reasignar la venta.",
            ),
        ),
        migrations.CreateModel(
            name="VentaFijaFuente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fila_fuente", models.PositiveIntegerField()),
                ("hoja_fuente", models.CharField(default="Base de Ventas", max_length=100)),
                ("en_base_vigente", models.BooleanField(db_index=True, default=True)),
                ("n_pedido", models.CharField(blank=True, db_index=True, max_length=30)),
                ("rut_evt", models.CharField(blank=True, db_index=True, max_length=12)),
                ("nombre_evt", models.CharField(blank=True, db_index=True, max_length=150)),
                ("supervisor_fuente", models.CharField(blank=True, db_index=True, max_length=150)),
                ("estado_instalacion_fuente", models.CharField(blank=True, max_length=100)),
                ("rgu_base", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("fecha_venta", models.DateField(blank=True, null=True)),
                ("promocion_fuente", models.CharField(blank=True, max_length=200)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("ejecutivo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="filas_fijas_fuente", to="usuarios.ejecutivo")),
                ("venta", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="filas_fuente", to="ventas.venta")),
            ],
            options={
                "verbose_name": "Fila fija ESACOM",
                "verbose_name_plural": "Filas fijas ESACOM",
                "ordering": ["fila_fuente"],
            },
        ),
        migrations.AddConstraint(
            model_name="ventafijafuente",
            constraint=models.UniqueConstraint(fields=("hoja_fuente", "fila_fuente", "en_base_vigente"), name="venta_fija_fuente_fila_vig_uniq"),
        ),
        migrations.AddIndex(
            model_name="ventafijafuente",
            index=models.Index(fields=["en_base_vigente", "supervisor_fuente"], name="vf_fuente_vig_sup_idx"),
        ),
        migrations.AddIndex(
            model_name="ventafijafuente",
            index=models.Index(fields=["en_base_vigente", "rut_evt"], name="vf_fuente_vig_rut_idx"),
        ),
    ]

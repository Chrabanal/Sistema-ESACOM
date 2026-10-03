from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("integraciones", "0011_cargaexcel_estado_reporte"),
        ("usuarios", "0006_dotacion_fuente_y_auditoria"),
    ]

    operations = [
        migrations.AddField(
            model_name="cargaexcel",
            name="formato_kpi",
            field=models.CharField(
                choices=[("DETALLADO", "Detalle Claro/VTR"), ("CIERRE_MOVIL", "Cierre Claro Móvil")],
                db_index=True,
                default="DETALLADO",
                help_text="DETALLADO para reportes con NUM_PEDIDO; CIERRE_MOVIL para cierres agregados de Claro Móvil.",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="KPICierreResumen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rut_vendedor_fuente", models.CharField(blank=True, db_index=True, max_length=20)),
                ("camada", models.CharField(db_index=True, max_length=7)),
                ("boleta", models.CharField(db_index=True, max_length=2)),
                ("pagadas", models.PositiveIntegerField(default=0)),
                ("pendientes", models.PositiveIntegerField(default=0)),
                ("no_pago", models.PositiveIntegerField(default=0)),
                ("fuera_plazo", models.PositiveIntegerField(default=0)),
                ("sin_boleta", models.PositiveIntegerField(default=0)),
                ("total_medible", models.PositiveIntegerField(default=0)),
                ("kpi_pago_pct", models.DecimalField(decimal_places=2, default=0, max_digits=7)),
                ("meta_claro_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("cierre_claro_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("carga", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="cierres_resumen", to="integraciones.cargaexcel")),
                ("ejecutivo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cierres_kpi_calidad", to="usuarios.ejecutivo")),
            ],
            options={
                "verbose_name": "Resumen cierre KPI",
                "verbose_name_plural": "Resúmenes cierre KPI",
            },
        ),
        migrations.AddConstraint(
            model_name="kpicierreresumen",
            constraint=models.UniqueConstraint(fields=("carga", "rut_vendedor_fuente", "camada", "boleta"), name="uniq_cierre_carga_rut_cb"),
        ),
        migrations.AddIndex(
            model_name="kpicierreresumen",
            index=models.Index(fields=["camada", "boleta"], name="cierre_camada_bol_idx"),
        ),
        migrations.AddIndex(
            model_name="kpicierreresumen",
            index=models.Index(fields=["ejecutivo", "camada", "boleta"], name="cierre_ejec_cb_idx"),
        ),
    ]

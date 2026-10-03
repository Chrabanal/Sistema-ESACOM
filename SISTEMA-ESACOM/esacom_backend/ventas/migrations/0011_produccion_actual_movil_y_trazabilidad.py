from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0006_dotacion_fuente_y_auditoria"),
        ("ventas", "0010_alter_corte_ejecutivo_kpi_alter_venta_ejecutivo_ce"),
    ]

    operations = [
        migrations.AddField(
            model_name="venta",
            name="en_base_vigente",
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.AddField(
            model_name="venta",
            name="estado_instalacion_fuente",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="venta",
            name="hoja_fuente",
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name="venta",
            name="supervisor_fuente",
            field=models.CharField(blank=True, db_index=True, max_length=150),
        ),
        migrations.CreateModel(
            name="VentaMovil",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("clave_origen", models.CharField(db_index=True, max_length=64, unique=True)),
                ("rut_cliente", models.CharField(blank=True, db_index=True, max_length=12)),
                ("supervisor_fuente", models.CharField(blank=True, db_index=True, max_length=150)),
                ("nombre_evt", models.CharField(blank=True, db_index=True, max_length=150)),
                ("rut_evt_ingreso", models.CharField(blank=True, db_index=True, max_length=12)),
                ("codigo_ingreso", models.CharField(blank=True, max_length=30)),
                ("rut_evt", models.CharField(blank=True, db_index=True, max_length=12)),
                ("migracion", models.CharField(blank=True, max_length=100)),
                ("tipo_linea", models.CharField(choices=[("PRINCIPAL", "Principal"), ("ADICIONAL", "Adicional"), ("PPM", "PPM"), ("OTRO", "Otro")], db_index=True, default="OTRO", max_length=15)),
                ("plan", models.CharField(blank=True, max_length=150)),
                ("pcs", models.CharField(blank=True, db_index=True, max_length=30)),
                ("fecha_venta", models.DateField(blank=True, db_index=True, null=True)),
                ("fecha_activacion", models.DateField(blank=True, null=True)),
                ("donante", models.CharField(blank=True, max_length=100)),
                ("estado", models.CharField(blank=True, db_index=True, max_length=100)),
                ("observacion", models.CharField(blank=True, max_length=250)),
                ("fecha_cc", models.DateField(blank=True, null=True)),
                ("camada", models.CharField(blank=True, db_index=True, max_length=7)),
                ("hoja_fuente", models.CharField(blank=True, max_length=100)),
                ("en_base_vigente", models.BooleanField(db_index=True, default=False)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("ejecutivo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ventas_movil", to="usuarios.ejecutivo")),
            ],
            options={
                "verbose_name": "Venta móvil",
                "verbose_name_plural": "Ventas móviles",
                "ordering": ["-fecha_venta", "nombre_evt"],
            },
        ),
        migrations.AddIndex(
            model_name="ventamovil",
            index=models.Index(fields=["en_base_vigente", "supervisor_fuente"], name="ventas_movil_vig_sup_idx"),
        ),
    ]

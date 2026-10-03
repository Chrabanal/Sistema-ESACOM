from decimal import Decimal

from django.db import migrations


def crear_meta_legacy_2026(apps, schema_editor):
    Meta = apps.get_model("integraciones", "MetaKPICalidad")
    Meta.objects.update_or_create(
        vigente_desde="2026-01",
        defaults={
            "meta_b1": Decimal("85.00"),
            "meta_b2": Decimal("83.00"),
            "meta_b3": Decimal("78.00"),
            "motivo": "Meta ESACOM histórica previa al cambio de B3 vigente desde julio 2026.",
        },
    )


def eliminar_meta_legacy_2026(apps, schema_editor):
    Meta = apps.get_model("integraciones", "MetaKPICalidad")
    Meta.objects.filter(vigente_desde="2026-01").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("integraciones", "0009_metakpicalidad"),
    ]

    operations = [
        migrations.RunPython(crear_meta_legacy_2026, eliminar_meta_legacy_2026),
    ]

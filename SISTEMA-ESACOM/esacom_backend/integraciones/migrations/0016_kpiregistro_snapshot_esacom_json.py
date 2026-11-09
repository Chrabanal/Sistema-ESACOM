from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integraciones", "0015_kpicierrefijofila"),
    ]

    operations = [
        migrations.AddField(
            model_name="kpiregistro",
            name="snapshot_esacom",
            field=models.JSONField(blank=True, null=True),
        ),
    ]

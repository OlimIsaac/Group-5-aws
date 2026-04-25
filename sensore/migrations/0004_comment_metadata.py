from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sensore', '0003_pressuremetrics_advanced_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='comment',
            name='metadata',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]

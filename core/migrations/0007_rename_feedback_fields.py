from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_feedback_admin_notes_feedback_reviewed_at_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='feedback',
            old_name='comment',
            new_name='feedback_text',
        ),
        migrations.RenameField(
            model_name='feedback',
            old_name='created_at',
            new_name='timestamp',
        ),
    ]

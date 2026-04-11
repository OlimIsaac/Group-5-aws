from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='SensorSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_date', models.DateField()),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True)),
                ('flagged_for_review', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sessions', to='auth.user')),
            ],
            options={'ordering': ['-session_date', '-start_time']},
        ),
        migrations.CreateModel(
            name='SensorFrame',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timestamp', models.DateTimeField()),
                ('frame_index', models.PositiveIntegerField()),
                ('data', models.TextField()),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='frames', to='sensore.sensorsession')),
            ],
            options={'ordering': ['timestamp', 'frame_index'], 'unique_together': {('session', 'frame_index')}},
        ),
        migrations.CreateModel(
            name='PressureMetrics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('peak_pressure_index', models.FloatField()),
                ('contact_area_percent', models.FloatField()),
                ('average_pressure', models.FloatField()),
                ('asymmetry_score', models.FloatField(default=0.0)),
                ('risk_level', models.CharField(choices=[('low', 'Low Risk'), ('moderate', 'Moderate Risk'), ('high', 'High Risk'), ('critical', 'Critical Risk')], default='low', max_length=20)),
                ('risk_score', models.FloatField(default=0.0)),
                ('hot_zones', models.TextField(default='[]')),
                ('plain_english', models.TextField(blank=True)),
                ('frame', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='metrics', to='sensore.sensorframe')),
            ],
            options={'ordering': ['frame__timestamp']},
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('author_type', models.CharField(choices=[('patient', 'Patient'), ('clinician', 'Clinician')], default='patient', max_length=20)),
                ('timestamp_reference', models.DateTimeField()),
                ('text', models.TextField()),
                ('is_reply', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pressure_comments', to='auth.user')),
                ('frame', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='comments', to='sensore.sensorframe')),
                ('reply_to', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='replies', to='sensore.comment')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='sensore.sensorsession')),
            ],
            options={'ordering': ['created_at']},
        ),
        migrations.CreateModel(
            name='PressureAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('high_ppi', 'High Peak Pressure'), ('sustained', 'Sustained High Pressure'), ('asymmetry', 'Significant Asymmetry'), ('critical', 'Critical Pressure Level')], max_length=30)),
                ('message', models.TextField()),
                ('risk_score', models.FloatField()),
                ('acknowledged', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('acknowledged_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='acknowledged_alerts', to='auth.user')),
                ('frame', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='alerts', to='sensore.sensorframe')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='sensore.sensorsession')),
            ],
            options={'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='Report',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('date_range_start', models.DateField()),
                ('date_range_end', models.DateField()),
                ('summary', models.TextField(blank=True)),
                ('peak_risk_level', models.CharField(default='low', max_length=20)),
                ('avg_ppi', models.FloatField(default=0.0)),
                ('avg_contact_area', models.FloatField(default=0.0)),
                ('total_high_risk_events', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('generated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='generated_reports', to='auth.user')),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='auth.user')),
                ('sessions_included', models.ManyToManyField(blank=True, to='sensore.sensorsession')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]

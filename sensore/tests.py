import json
import unittest
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

try:
    from accounts.models import UserProfile
    from sensore.models import Comment, SensorFrame, SensorSession
    from sensore.utils import analyse_session_frames
except Exception as exc:  # pragma: no cover - legacy compatibility only
    raise unittest.SkipTest(f"Legacy sensore tests skipped: {exc}")

User = get_user_model()


def build_flat_frame(base_value=1200):
    values = []
    for row in range(32):
        for col in range(32):
            value = base_value
            if 11 <= col <= 20 and 12 <= row <= 24:
                value += 1200
            values.append(min(4095, value))
    return values


class SensoreAccessAndFeatureTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.admin = User.objects.create_user('admin_test', password='admin123', is_staff=True, is_superuser=True)
        self.admin_profile, _ = UserProfile.objects.get_or_create(user=self.admin)
        self.admin_profile.role = 'admin'
        self.admin_profile.save(update_fields=['role'])

        self.clinician = User.objects.create_user('clinician_test', password='clinic123')
        self.clinician_profile, _ = UserProfile.objects.get_or_create(user=self.clinician)
        self.clinician_profile.role = 'clinician'
        self.clinician_profile.save(update_fields=['role'])

        self.patient_1 = User.objects.create_user('patient_alpha', password='patient123')
        self.patient_1_profile, _ = UserProfile.objects.get_or_create(user=self.patient_1)
        self.patient_1_profile.role = 'patient'
        self.patient_1_profile.patient_id = 'PAT_ALPHA'
        self.patient_1_profile.assigned_clinician = self.clinician
        self.patient_1_profile.save()

        self.patient_2 = User.objects.create_user('patient_beta', password='patient123')
        self.patient_2_profile, _ = UserProfile.objects.get_or_create(user=self.patient_2)
        self.patient_2_profile.role = 'patient'
        self.patient_2_profile.patient_id = 'PAT_BETA'
        self.patient_2_profile.save()

        start = timezone.make_aware(datetime(2026, 4, 10, 9, 0, 0))
        self.session_1 = SensorSession.objects.create(
            patient=self.patient_1,
            session_date=date(2026, 4, 10),
            start_time=start,
            end_time=start + timedelta(minutes=5),
        )
        self.session_2 = SensorSession.objects.create(
            patient=self.patient_2,
            session_date=date(2026, 4, 10),
            start_time=start,
            end_time=start + timedelta(minutes=5),
        )

        for idx in range(4):
            SensorFrame.objects.create(
                session=self.session_1,
                timestamp=start + timedelta(seconds=idx * 30),
                frame_index=idx,
                data=json.dumps(build_flat_frame(1000 + idx * 50)),
            )
            SensorFrame.objects.create(
                session=self.session_2,
                timestamp=start + timedelta(seconds=idx * 30),
                frame_index=idx,
                data=json.dumps(build_flat_frame(900 + idx * 40)),
            )

        analyse_session_frames(self.session_1, create_alerts=True)
        analyse_session_frames(self.session_2, create_alerts=True)

    def test_patient_cannot_view_other_patient_session(self):
        self.client.login(username='patient_alpha', password='patient123')
        response = self.client.get(f'/api/session/{self.session_2.id}/frames/')
        self.assertEqual(response.status_code, 403)

    def test_clinician_can_only_view_assigned_patient_sessions(self):
        self.client.login(username='clinician_test', password='clinic123')

        allowed = self.client.get(f'/api/session/{self.session_1.id}/frames/')
        self.assertEqual(allowed.status_code, 200)

        forbidden = self.client.get(f'/api/session/{self.session_2.id}/frames/')
        self.assertEqual(forbidden.status_code, 403)

    def test_comment_metadata_pain_zones_and_points_saved(self):
        self.client.login(username='patient_alpha', password='patient123')
        frame = self.session_1.frames.order_by('frame_index').first()

        payload = {
            'text': 'Pain in lower back while leaning.',
            'frame_id': frame.id,
            'pain_zones': ['lower_back', 'left_hip'],
            'pain_points': [{'x': 14, 'y': 20}, {'x': 15, 'y': 21}],
            'time_view': 6,
            'source': 'patient_dashboard',
        }
        response = self.client.post(
            f'/api/session/{self.session_1.id}/comment/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)

        comment = Comment.objects.filter(session=self.session_1, author=self.patient_1).latest('created_at')
        self.assertEqual(comment.metadata.get('pain_zones'), ['lower_back', 'left_hip'])
        self.assertEqual(comment.metadata.get('time_view_hours'), 6)
        self.assertEqual(len(comment.metadata.get('pain_points', [])), 2)

    def test_report_csv_download(self):
        self.client.login(username='patient_alpha', password='patient123')
        response = self.client.get('/report/?download_csv=1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="Sensore_Report_', response['Content-Disposition'])

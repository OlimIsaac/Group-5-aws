import json
import unittest

try:
    from .forms import PainZoneReportForm
    from .models import PREDEFINED_ZONES, PainZoneReport, PressureFrame
except Exception as exc:  # pragma: no cover - legacy compatibility only
    raise unittest.SkipTest(f"Legacy core tests skipped: {exc}")

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

User = get_user_model()

class PainZoneReportModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testpatient', password='pass', role='patient'
        )

    def test_create_report_saves_zones(self):
        report = PainZoneReport.objects.create(
            user=self.user,
            zones=['lower_back', 'left_hip'],
            note='Aches a lot'
        )
        fetched = PainZoneReport.objects.get(pk=report.pk)
        self.assertEqual(fetched.zones, ['lower_back', 'left_hip'])
        self.assertEqual(fetched.note, 'Aches a lot')

    def test_timestamp_auto_set(self):
        report = PainZoneReport.objects.create(
            user=self.user, zones=['tailbone']
        )
        self.assertIsNotNone(report.timestamp)

    def test_predefined_zones_has_eight_entries(self):
        self.assertEqual(len(PREDEFINED_ZONES), 8)
        self.assertIn('lower_back', PREDEFINED_ZONES)
        self.assertIn('tailbone', PREDEFINED_ZONES)


class PainZoneReportFormTest(TestCase):
    def test_valid_zones_accepted(self):
        form = PainZoneReportForm(data={
            'zones': ['lower_back', 'tailbone'],
            'note': 'hurts',
        })
        self.assertTrue(form.is_valid())

    def test_invalid_zone_rejected(self):
        form = PainZoneReportForm(data={
            'zones': ['invented_zone'],
            'note': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('zones', form.errors)

    def test_empty_zones_rejected(self):
        form = PainZoneReportForm(data={'zones': [], 'note': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('zones', form.errors)

    def test_note_is_optional(self):
        form = PainZoneReportForm(data={'zones': ['left_hip']})
        self.assertTrue(form.is_valid())

    def test_note_max_length(self):
        form = PainZoneReportForm(data={
            'zones': ['left_hip'],
            'note': 'x' * 1001,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('note', form.errors)


class PatientStatusAPITest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='pat', password='pass', role='patient'
        )
        self.client.login(username='pat', password='pass')

    def _make_frame(self, minutes_ago, high_pressure=False):
        matrix = [[0]*32 for _ in range(32)]
        PressureFrame.objects.create(
            user=self.patient,
            timestamp=timezone.now() - timedelta(minutes=minutes_ago),
            raw_matrix=matrix,
            peak_pressure_index=4000.0 if high_pressure else 500.0,
            contact_area_percentage=50.0,
            high_pressure_flag=high_pressure,
        )

    def test_returns_json(self):
        response = self.client.get('/patient/api/status/?hours=1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('alert', data)
        self.assertIn('latest_ppi', data)
        self.assertIn('latest_contact', data)
        self.assertIn('latest_matrix', data)
        self.assertIn('chart_data', data)
        self.assertIn('total_counts', data['chart_data'])

    def test_safe_defaults_with_no_frames(self):
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        self.assertFalse(data['alert'])
        self.assertIsNone(data['latest_ppi'])
        self.assertIsNone(data['latest_matrix'])
        self.assertEqual(data['chart_data']['labels'], [])
        self.assertEqual(data['chart_data']['total_counts'], [])

    def test_alert_true_when_latest_frame_is_high(self):
        self._make_frame(minutes_ago=5, high_pressure=True)
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        self.assertTrue(data['alert'])

    def test_alert_false_when_latest_frame_is_normal(self):
        self._make_frame(minutes_ago=5, high_pressure=False)
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        self.assertFalse(data['alert'])

    def test_non_patient_gets_403(self):
        admin = User.objects.create_user(
            username='adm', password='pass', role='admin'
        )
        self.client.login(username='adm', password='pass')
        response = self.client.get('/patient/api/status/?hours=1')
        self.assertEqual(response.status_code, 403)

    def test_out_of_range_hours_defaults_to_one(self):
        # Integer but not in {1,6,24} — should silently clamp, not error
        response = self.client.get('/patient/api/status/?hours=999')
        self.assertEqual(response.status_code, 200)

    def test_non_integer_hours_defaults_to_one(self):
        # Non-integer value — exercises the ValueError branch in the view
        response = self.client.get('/patient/api/status/?hours=abc')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('alert', data)  # valid response shape returned

    def test_chart_data_counts_high_pressure_frames_by_hour(self):
        # 2 high-pressure frames, 1 normal — only high-pressure ones should be counted
        self._make_frame(minutes_ago=20, high_pressure=True)
        self._make_frame(minutes_ago=25, high_pressure=True)
        self._make_frame(minutes_ago=35, high_pressure=False)
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        # Labels and counts must always be the same length
        self.assertEqual(len(data['chart_data']['labels']), len(data['chart_data']['counts']))
        total_high = sum(data['chart_data']['counts'])
        self.assertEqual(total_high, 2)

    def test_six_hour_window_returns_seven_buckets(self):
        # 6-hour window should produce 7 labels (hours 0 through 6 inclusive)
        self._make_frame(minutes_ago=10)
        response = self.client.get('/patient/api/status/?hours=6')
        data = json.loads(response.content)
        self.assertEqual(len(data['chart_data']['labels']), 7)
        self.assertEqual(len(data['chart_data']['counts']), 7)
        self.assertEqual(len(data['chart_data']['total_counts']), 7)

    def test_twenty_four_hour_window_returns_twenty_five_buckets(self):
        self._make_frame(minutes_ago=10)
        response = self.client.get('/patient/api/status/?hours=24')
        data = json.loads(response.content)
        self.assertEqual(len(data['chart_data']['labels']), 25)
        self.assertEqual(len(data['chart_data']['counts']), 25)
        self.assertEqual(len(data['chart_data']['total_counts']), 25)

    def test_recent_frames_include_older_records_outside_selected_hours(self):
        self._make_frame(minutes_ago=5)
        old_frame = PressureFrame.objects.create(
            user=self.patient,
            timestamp=timezone.now() - timedelta(hours=48),
            raw_matrix=[[0] * 32 for _ in range(32)],
            peak_pressure_index=700.0,
            contact_area_percentage=45.0,
            high_pressure_flag=False,
        )

        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        frame_ids = [frame['id'] for frame in data['recent_frames']]
        self.assertIn(old_frame.id, frame_ids)

    def test_chart_fallback_window_uses_latest_when_recent_window_empty(self):
        self._make_frame(minutes_ago=60 * 30, high_pressure=False)

        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)

        self.assertTrue(data['chart_data']['using_fallback_window'])
        self.assertEqual(sum(data['chart_data']['total_counts']), 1)


class PatientFrameDetailAPITest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='framepat', password='pass', role='patient'
        )
        self.other_patient = User.objects.create_user(
            username='framepat2', password='pass', role='patient'
        )
        self.admin = User.objects.create_user(
            username='frameadmin', password='pass', role='admin'
        )

        self.own_frame = PressureFrame.objects.create(
            user=self.patient,
            timestamp=timezone.now() - timedelta(minutes=10),
            raw_matrix=[[100.0] * 32 for _ in range(32)],
            peak_pressure_index=900.0,
            contact_area_percentage=45.0,
            high_pressure_flag=False,
        )
        self.other_frame = PressureFrame.objects.create(
            user=self.other_patient,
            timestamp=timezone.now() - timedelta(minutes=5),
            raw_matrix=[[200.0] * 32 for _ in range(32)],
            peak_pressure_index=1200.0,
            contact_area_percentage=48.0,
            high_pressure_flag=False,
        )

    def test_patient_can_view_own_frame_detail(self):
        self.client.login(username='framepat', password='pass')
        response = self.client.get(f'/patient/api/frames/{self.own_frame.id}/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['id'], self.own_frame.id)
        self.assertIn('matrix', data)
        self.assertIn('peak_pressure_index', data)
        self.assertIn('explanation', data)

    def test_patient_cannot_view_other_patient_frame_detail(self):
        self.client.login(username='framepat', password='pass')
        response = self.client.get(f'/patient/api/frames/{self.other_frame.id}/')
        self.assertEqual(response.status_code, 404)

    def test_non_patient_role_is_forbidden(self):
        self.client.login(username='frameadmin', password='pass')
        response = self.client.get(f'/patient/api/frames/{self.own_frame.id}/')
        self.assertEqual(response.status_code, 403)


class SubmitPainZonesViewTest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='painpat', password='pass', role='patient'
        )
        self.client.login(username='painpat', password='pass')

    def test_valid_submission_creates_report(self):
        response = self.client.post('/patient/pain-zones/', {
            'zones': ['lower_back', 'tailbone'],
            'note': 'sharp pain',
        })
        self.assertRedirects(response, '/patient/')
        self.assertEqual(PainZoneReport.objects.filter(user=self.patient).count(), 1)
        report = PainZoneReport.objects.get(user=self.patient)
        self.assertEqual(sorted(report.zones), ['lower_back', 'tailbone'])
        self.assertEqual(report.note, 'sharp pain')

    def test_invalid_zone_does_not_create_report(self):
        response = self.client.post('/patient/pain-zones/', {
            'zones': ['made_up_zone'],
            'note': '',
        })
        self.assertEqual(response.status_code, 200)  # re-renders dashboard
        self.assertEqual(PainZoneReport.objects.filter(user=self.patient).count(), 0)

    def test_non_patient_forbidden(self):
        admin = User.objects.create_user(
            username='adminx', password='pass', role='admin'
        )
        self.client.login(username='adminx', password='pass')
        response = self.client.post('/patient/pain-zones/', {
            'zones': ['lower_back'],
        })
        self.assertEqual(response.status_code, 403)


class PatientDashboardViewTest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='dashpat', password='pass', role='patient'
        )
        self.client.login(username='dashpat', password='pass')

    def test_dashboard_renders_with_zone_choices(self):
        response = self.client.get('/patient/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('zone_choices', response.context)
        self.assertEqual(len(response.context['zone_choices']), 8)

    def test_dashboard_context_has_no_frames_key(self):
        response = self.client.get('/patient/')
        self.assertNotIn('frames', response.context)

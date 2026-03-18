from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import PainZoneReport, PREDEFINED_ZONES

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

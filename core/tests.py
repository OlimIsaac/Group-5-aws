from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import PainZoneReport, PREDEFINED_ZONES
from .forms import PainZoneReportForm

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

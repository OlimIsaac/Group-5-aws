from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Feedback, SensorData
from core.forms import FeedbackForm, FeedbackAdminForm

User = get_user_model()


class FeedbackModelTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='password123',
            role=User.ROLE_ADMIN
        )
        self.patient = User.objects.create_user(
            username='patient',
            email='patient@test.com',
            password='password123',
            role=User.ROLE_PATIENT
        )
        self.sensor_data = SensorData.objects.create(
            user=self.patient,
            timestamp=timezone.now(),
            pressure_value=1.5,
            sensor_id='test-sensor',
            location='test-location'
        )

    def test_feedback_creation(self):
        feedback = Feedback.objects.create(
            user=self.patient,
            sensor_data=self.sensor_data,
            comment='Test feedback'
        )
        self.assertEqual(feedback.status, Feedback.STATUS_PENDING)
        self.assertIsNone(feedback.reviewed_by)
        self.assertIsNone(feedback.reviewed_at)

    def test_mark_reviewed(self):
        feedback = Feedback.objects.create(
            user=self.patient,
            sensor_data=self.sensor_data,
            comment='Test feedback'
        )
        feedback.mark_reviewed(self.admin)
        self.assertEqual(feedback.status, Feedback.STATUS_REVIEWED)
        self.assertEqual(feedback.reviewed_by, self.admin)
        self.assertIsNotNone(feedback.reviewed_at)

    def test_resolve_feedback(self):
        feedback = Feedback.objects.create(
            user=self.patient,
            sensor_data=self.sensor_data,
            comment='Test feedback'
        )
        feedback.resolve(self.admin)
        self.assertEqual(feedback.status, Feedback.STATUS_RESOLVED)
        self.assertEqual(feedback.reviewed_by, self.admin)
        self.assertIsNotNone(feedback.reviewed_at)


class FeedbackFormTest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='patient',
            email='patient@test.com',
            password='password123',
            role=User.ROLE_PATIENT
        )
        self.sensor_data = SensorData.objects.create(
            user=self.patient,
            timestamp=timezone.now(),
            pressure_value=1.5,
            sensor_id='test-sensor',
            location='test-location'
        )

    def test_feedback_form_valid(self):
        form_data = {
            'sensor_data': self.sensor_data.id,
            'feedback_text': 'This is a test feedback message.'
        }
        form = FeedbackForm(data=form_data)
        form.fields['sensor_data'].queryset = SensorData.objects.all()
        self.assertTrue(form.is_valid())

    def test_feedback_form_invalid_empty_text(self):
        form_data = {
            'sensor_data': self.sensor_data.id,
            'feedback_text': ''
        }
        form = FeedbackForm(data=form_data)
        form.fields['sensor_data'].queryset = SensorData.objects.all()
        self.assertFalse(form.is_valid())
        self.assertIn('feedback_text', form.errors)


class FeedbackViewTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='password123',
            role=User.ROLE_ADMIN
        )
        self.patient = User.objects.create_user(
            username='patient',
            email='patient@test.com',
            password='password123',
            role=User.ROLE_PATIENT
        )
        self.sensor_data = SensorData.objects.create(
            user=self.patient,
            timestamp=timezone.now(),
            pressure_value=1.5,
            sensor_id='test-sensor',
            location='test-location'
        )

    def test_submit_feedback_view_requires_login(self):
        response = self.client.get(reverse('submit_feedback'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_submit_feedback_view_patient_access(self):
        self.client.login(username='patient', password='password123')
        response = self.client.get(reverse('submit_feedback'))
        self.assertEqual(response.status_code, 200)

    def test_submit_feedback_view_admin_denied(self):
        self.client.login(username='admin', password='password123')
        response = self.client.get(reverse('submit_feedback'))
        self.assertEqual(response.status_code, 302)  # Redirect to home

    def test_feedback_list_view_admin_access(self):
        self.client.login(username='admin', password='password123')
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 200)

    def test_feedback_list_view_patient_denied(self):
        self.client.login(username='patient', password='password123')
        response = self.client.get(reverse('feedback_list'))
        self.assertEqual(response.status_code, 302)  # Redirect to home

    def test_feedback_detail_view_admin_access(self):
        feedback = Feedback.objects.create(
            user=self.patient,
            sensor_data=self.sensor_data,
            comment='Test feedback'
        )
        self.client.login(username='admin', password='password123')
        response = self.client.get(reverse('feedback_detail', args=[feedback.id]))
        self.assertEqual(response.status_code, 200)

    def test_feedback_detail_view_patient_denied(self):
        feedback = Feedback.objects.create(
            user=self.patient,
            sensor_data=self.sensor_data,
            comment='Test feedback'
        )
        self.client.login(username='patient', password='password123')
        response = self.client.get(reverse('feedback_detail', args=[feedback.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to home

    def test_delete_feedback_view_admin_access(self):
        feedback = Feedback.objects.create(
            user=self.patient,
            sensor_data=self.sensor_data,
            comment='Test feedback'
        )
        self.client.login(username='admin', password='password123')
        response = self.client.post(reverse('delete_feedback', args=[feedback.id]))
        self.assertEqual(response.status_code, 302)  # Redirect to feedback_list
        self.assertFalse(Feedback.objects.filter(id=feedback.id).exists())
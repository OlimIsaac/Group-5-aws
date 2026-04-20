from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('patient', 'Patient'),
        ('clinician', 'Clinician'),
        ('admin', 'Administrator'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='patient')
    patient_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    date_of_birth = models.DateField(null=True, blank=True)
    medical_notes = models.TextField(blank=True)
    assigned_clinician = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='patients', limit_choices_to={'profile__role': 'clinician'}
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"

    @property
    def is_patient(self):
        return self.role == 'patient'

    @property
    def is_clinician(self):
        return self.role == 'clinician'

    @property
    def is_admin(self):
        return self.role == 'admin'

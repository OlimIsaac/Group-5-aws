from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


PREDEFINED_ZONES = [
    'lower_back', 'left_hip', 'right_hip',
    'left_thigh', 'right_thigh', 'tailbone',
    'left_shoulder', 'right_shoulder',
]


class User(AbstractUser):
    ROLE_ADMIN = "admin"
    ROLE_CLINICIAN = "clinician"
    ROLE_PATIENT = "patient"

    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_CLINICIAN, "Clinician"),
        (ROLE_PATIENT, "Patient"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class PatientProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="patient_profile")
    # additional patient-specific fields can go here (age, medical history, etc.)

    def __str__(self):
        return f"PatientProfile for {self.user.username}"


class ClinicianProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="clinician_profile")
    # additional clinician-specific fields

    def __str__(self):
        return f"ClinicianProfile for {self.user.username}"


class Assignment(models.Model):
    clinician = models.ForeignKey(ClinicianProfile, on_delete=models.CASCADE, related_name="assignments")
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="assignments")
    assigned_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ("clinician", "patient")

    def __str__(self):
        return f"{self.clinician.user.username} -> {self.patient.user.username}"


class PressureFrame(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pressure_frames")
    timestamp = models.DateTimeField()
    raw_matrix = models.JSONField()
    peak_pressure_index = models.FloatField(null=True, blank=True)
    contact_area_percentage = models.FloatField(null=True, blank=True)
    high_pressure_flag = models.BooleanField(default=False)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"Frame for {self.user.username} at {self.timestamp.isoformat()}"


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    pressure_frame = models.ForeignKey(PressureFrame, on_delete=models.CASCADE, related_name="comments")
    timestamp = models.DateTimeField(default=timezone.now)
    text = models.TextField()
    clinician_reply = models.TextField(blank=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.pressure_frame}"


class PainZoneReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pain_zone_reports')
    timestamp = models.DateTimeField(auto_now_add=True)
    zones = models.JSONField()
    note = models.TextField(blank=True)

    def __str__(self):
        return f"PainZoneReport by {self.user.username} at {self.timestamp}"
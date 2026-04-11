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


class Feedback(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_REVIEWED = 'reviewed'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedbacks')
    pressure_frame = models.ForeignKey(PressureFrame, on_delete=models.CASCADE, related_name='feedbacks')
    timestamp = models.DateTimeField(default=timezone.now)
    feedback_text = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_feedbacks')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Feedback by {self.user.username} on {self.pressure_frame} ({self.get_status_display()})"

    def mark_reviewed(self, admin_user):
        self.status = self.STATUS_REVIEWED
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()

    def resolve(self, admin_user, notes=''):
        self.status = self.STATUS_RESOLVED
        self.admin_notes = notes
        self.reviewed_by = admin_user
        self.reviewed_at = timezone.now()
        self.save()


class PainZoneReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pain_zone_reports')
    timestamp = models.DateTimeField(auto_now_add=True)
    zones = models.JSONField()
    note = models.TextField(blank=True)

    def __str__(self):
        return f"PainZoneReport by {self.user.username} at {self.timestamp}"


class HeatmapAnnotation(models.Model):
    """Stores the cells a patient has marked as painful on the pressure heatmap."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='heatmap_annotations')
    timestamp = models.DateTimeField(auto_now_add=True)
    cells = models.JSONField()  # list of [row, col] pairs, each in range [0, 31]
    note = models.TextField(blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"HeatmapAnnotation by {self.user.username} at {self.timestamp}"
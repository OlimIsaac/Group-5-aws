from django.contrib import admin
from .models import User, PatientProfile, ClinicianProfile, Assignment, PressureFrame, Comment, Feedback


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'role']
    list_filter = ['role']


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ['user']


@admin.register(ClinicianProfile)
class ClinicianProfileAdmin(admin.ModelAdmin):
    list_display = ['user']


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ['clinician', 'patient', 'assigned_at']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'sensor_frame', 'timestamp', 'status']
    search_fields = ['feedback_text']


@admin.register(PressureFrame)
class PressureFrameAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'peak_pressure_index', 'high_pressure_flag']
    list_filter = ['high_pressure_flag', 'timestamp']
    search_fields = ['user__username']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'pressure_frame']
    search_fields = ['text']

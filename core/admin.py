from django.contrib import admin
from .models import User, PatientProfile, ClinicianProfile, ClinicianPatientAssignment, PressureFrame, Comment, SensorData, Feedback


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


@admin.register(ClinicianPatientAssignment)
class ClinicianPatientAssignmentAdmin(admin.ModelAdmin):
    list_display = ['clinician', 'patient', 'assigned_at']


@admin.register(SensorData)
class SensorDataAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'pressure_value', 'sensor_id']
    list_filter = ['timestamp', 'sensor_id']
    search_fields = ['user__username']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'sensor_data', 'created_at']
    search_fields = ['comment']


@admin.register(PressureFrame)
class PressureFrameAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'peak_pressure_index', 'high_pressure_flag']
    list_filter = ['high_pressure_flag', 'timestamp']
    search_fields = ['user__username']


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['user', 'timestamp', 'pressure_frame']
    search_fields = ['text']

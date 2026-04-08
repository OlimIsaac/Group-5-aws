from django.contrib import admin
from .models import SensorSession, SensorFrame, PressureMetrics, Comment, PressureAlert, Report

@admin.register(SensorSession)
class SensorSessionAdmin(admin.ModelAdmin):
    list_display = ['patient', 'session_date', 'start_time', 'flagged_for_review']
    list_filter = ['session_date', 'flagged_for_review']

@admin.register(PressureMetrics)
class PressureMetricsAdmin(admin.ModelAdmin):
    list_display = ['frame', 'peak_pressure_index', 'contact_area_percent', 'risk_level', 'risk_score']
    list_filter = ['risk_level']

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'session', 'author_type', 'created_at']

@admin.register(PressureAlert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['session', 'alert_type', 'risk_score', 'acknowledged', 'created_at']
    list_filter = ['acknowledged']

admin.site.register(Report)

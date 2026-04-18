from django.contrib import admin

from .models import (Comment, PressureAlert, PressureMetrics, Report,
                     SensorFrame, SensorSession)


@admin.register(SensorSession)
class SensorSessionAdmin(admin.ModelAdmin):
    list_display = ['patient', 'session_date', 'start_time', 'flagged_for_review']
    list_filter = ['session_date', 'flagged_for_review']

@admin.register(PressureMetrics)
class PressureMetricsAdmin(admin.ModelAdmin):
    list_display = [
        'frame',
        'peak_pressure_index',
        'contact_area_percent',
        'asymmetry_score',
        'pressure_concentration',
        'movement_index',
        'risk_level',
        'risk_score',
    ]
    list_filter = ['risk_level']

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'session', 'author_type', 'created_at', 'is_reply']
    search_fields = ['text', 'author__username', 'session__patient__username']

@admin.register(PressureAlert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['session', 'alert_type', 'risk_score', 'acknowledged', 'created_at']
    list_filter = ['acknowledged']

admin.site.register(Report)

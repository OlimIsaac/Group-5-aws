from django.urls import path, include
from . import views

urlpatterns = [
    path('patient/dashboard/', views.patient_dashboard, name='sensore_patient_dashboard'),
    path('patient/report/', views.patient_report, name='patient_report'),
    path('patient/report/<int:patient_id>/', views.patient_report, name='patient_report'),
    path('api/session/<int:session_id>/frames/', views.api_session_frames, name='api_session_frames'),
    path('api/session/<int:session_id>/latest/', views.api_latest_frame, name='api_session_latest'),
    path('api/session/<int:session_id>/metrics/', views.api_session_metrics_timeline, name='api_session_metrics'),
    path('api/session/<int:session_id>/comment/', views.api_add_comment, name='api_add_comment'),
    path('api/session/<int:session_id>/comments/', views.api_session_comments, name='api_session_comments'),
    path('api/session/<int:session_id>/flag/', views.api_flag_session, name='api_session_flag'),
    path('api/patient/<int:patient_id>/sessions/', views.api_patient_sessions, name='api_patient_sessions'),
    path('api/comment/<int:comment_id>/reply/', views.api_reply_comment, name='api_reply_comment'),
    path('api/alert/<int:alert_id>/acknowledge/', views.api_acknowledge_alert, name='api_acknowledge_alert'),
    path('', include('core.urls')),
]

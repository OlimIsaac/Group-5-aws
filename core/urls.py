from django.urls import path, include
from .auth import LoginView
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('patient/', views.PatientDashboardView.as_view(), name='patient_dashboard'),
    path('patient/pain-zones/', views.SubmitPainZonesView.as_view(), name='submit_pain_zones'),
    path('patient/api/status/', views.PatientStatusAPIView.as_view(), name='patient_status_api'),
    path('clinician/', views.ClinicianDashboardView.as_view(), name='clinician_dashboard'),
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
    
    # Assignment Management
    path('assignments/', views.AssignmentListView.as_view(), name='assignment_list'),
    path('assignments/create/', views.CreateAssignmentView.as_view(), name='create_assignment'),
    path('assignments/<int:assignment_id>/delete/', views.DeleteAssignmentView.as_view(), name='delete_assignment'),
    
    # User Management
    path('manage/users/', views.UserListView.as_view(), name='user_list'),
    path('manage/users/create/', views.CreateUserView.as_view(), name='create_user'),
    path('manage/users/<int:user_id>/edit/', views.EditUserView.as_view(), name='edit_user'),
    path('manage/users/<int:user_id>/delete/', views.DeleteUserView.as_view(), name='delete_user'),
    
    # Clinician Management
    path('manage/clinicians/', views.ClinicianListView.as_view(), name='clinician_list'),
    
    # Patient Management
    path('manage/patients/', views.PatientListView.as_view(), name='patient_list'),
    
    # Pressure Data Management
    path('manage/pressure-data/', views.PressureDataListView.as_view(), name='pressure_data_list'),
    path('manage/pressure-data/<int:frame_id>/', views.PressureDataDetailView.as_view(), name='pressure_data_detail'),
    path('manage/pressure-data/<int:frame_id>/delete/', views.DeletePressureDataView.as_view(), name='delete_pressure_data'),
    
    # Comment Management
    path('manage/comments/', views.CommentListView.as_view(), name='comment_list'),
    path('manage/comments/<int:comment_id>/delete/', views.DeleteCommentView.as_view(), name='delete_comment'),
]

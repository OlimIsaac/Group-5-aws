from django.urls import path, include
from .auth import LoginView
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(next_page='home'), name='logout'),
    path('patient/', views.PatientDashboardView.as_view(), name='patient_dashboard'),
    path('clinician/', views.ClinicianDashboardView.as_view(), name='clinician_dashboard'),
    path('admin-dashboard/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
]

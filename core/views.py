from django.shortcuts import render, redirect
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, logout, authenticate

from .models import User, PressureFrame, ClinicianProfile, Assignment


class HomeView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Redirect based on role
        if request.user.role == User.ROLE_ADMIN:
            return redirect('admin_dashboard')
        elif request.user.role == User.ROLE_CLINICIAN:
            return redirect('clinician_dashboard')
        elif request.user.role == User.ROLE_PATIENT:
            return redirect('patient_dashboard')
        
        return redirect('login')


class PatientDashboardView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return redirect('home')
        frames = PressureFrame.objects.filter(user=request.user).order_by('-timestamp')[:100]
        comment_form = CommentForm()
        return render(request, 'core/patient_dashboard.html', {'frames': frames, 'comment_form': comment_form})


class ClinicianDashboardView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_CLINICIAN:
            return redirect('home')
        # Get assigned patients
        try:
            profile = ClinicianProfile.objects.get(user=request.user)
            assignments = Assignment.objects.filter(clinician=profile)
        except ClinicianProfile.DoesNotExist:
            assignments = []
        
        return render(request, 'core/clinician_dashboard.html', {'assignments': assignments})


class AdminDashboardView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        return render(request, 'core/admin_dashboard.html')

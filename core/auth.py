from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.forms import AuthenticationForm as DjangoAuthForm
from django.views import View
from django import forms
from django.conf import settings
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.db import transaction


class AuthenticationForm(DjangoAuthForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password'
        })
    )


class LoginView(DjangoLoginView):
    form_class = AuthenticationForm
    template_name = 'core/login.html'
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        ensure_demo_users()
        if request.user.is_authenticated and not request.user.role:
            from .models import User
            if request.user.is_superuser or request.user.is_staff:
                request.user.role = User.ROLE_ADMIN
                request.user.save(update_fields=['role'])
            else:
                logout(request)
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        """Redirect to appropriate dashboard based on user role"""
        from .models import User
        user = self.request.user
        if not user.role:
            if user.is_superuser or user.is_staff:
                user.role = User.ROLE_ADMIN
                user.save(update_fields=['role'])
            else:
                logout(self.request)
                return '/login/'
        if user.role == User.ROLE_ADMIN:
            return '/admin-dashboard/'
        elif user.role == User.ROLE_CLINICIAN:
            return '/clinician/'
        elif user.role == User.ROLE_PATIENT:
            return '/patient/'
        return '/'


class LogoutView(View):
    """Simple logout view that handles both GET and POST requests"""
    
    def get(self, request):
        logout(request)
        return redirect('home')
    
    def post(self, request):
        logout(request)
        return redirect('home')


def ensure_demo_users():
    if not settings.DEBUG:
        return

    from .models import User, ClinicianProfile, PatientProfile, Assignment

    with transaction.atomic():
        admin, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@sensore.local',
                'role': User.ROLE_ADMIN,
                'is_staff': True,
                'is_superuser': True,
            },
        )
        if created:
            admin.set_password('admin123')
            admin.save(update_fields=['password'])

        clinician, created = User.objects.get_or_create(
            username='clinician1',
            defaults={
                'email': 'clinician@sensore.local',
                'role': User.ROLE_CLINICIAN,
            },
        )
        if created:
            clinician.set_password('clinician123')
            clinician.save(update_fields=['password'])

        patient, created = User.objects.get_or_create(
            username='patient1',
            defaults={
                'email': 'patient@sensore.local',
                'role': User.ROLE_PATIENT,
            },
        )
        if created:
            patient.set_password('patient123')
            patient.save(update_fields=['password'])

        clinician_profile, _ = ClinicianProfile.objects.get_or_create(user=clinician)
        patient_profile, _ = PatientProfile.objects.get_or_create(user=patient)

        Assignment.objects.get_or_create(
            clinician=clinician_profile,
            patient=patient_profile,
        )

from datetime import timedelta

from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.forms import AuthenticationForm as DjangoAuthForm
from django.views import View
from django import forms
from django.conf import settings
from django.core.cache import cache
from django.shortcuts import redirect
from django.contrib.auth import logout
from django.db import transaction
from django.utils import timezone


class AuthenticationForm(DjangoAuthForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username',
            'autocomplete': 'username',
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password',
            'autocomplete': 'current-password',
        })
    )


def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _login_attempt_key(username, ip_address):
    return f"login:attempts:{username}:{ip_address}"


def _login_lock_key(username, ip_address):
    return f"login:lock:{username}:{ip_address}"


def _login_limits():
    max_attempts = getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5)
    lockout_minutes = getattr(settings, 'LOGIN_LOCKOUT_MINUTES', 15)
    attempt_window_minutes = getattr(settings, 'LOGIN_ATTEMPT_WINDOW_MINUTES', 10)
    return max_attempts, lockout_minutes, attempt_window_minutes


def _get_lockout_until(username, ip_address):
    lock_key = _login_lock_key(username, ip_address)
    lockout_until = cache.get(lock_key)
    if not lockout_until:
        return None
    if timezone.now() >= lockout_until:
        cache.delete(lock_key)
        return None
    return lockout_until


def _record_login_failure(username, ip_address):
    max_attempts, lockout_minutes, attempt_window_minutes = _login_limits()
    attempt_key = _login_attempt_key(username, ip_address)
    attempts = cache.get(attempt_key, 0) + 1
    cache.set(attempt_key, attempts, timeout=attempt_window_minutes * 60)
    if attempts >= max_attempts:
        lockout_until = timezone.now() + timedelta(minutes=lockout_minutes)
        cache.set(
            _login_lock_key(username, ip_address),
            lockout_until,
            timeout=lockout_minutes * 60,
        )
        cache.delete(attempt_key)
        return lockout_until
    return None


def _clear_login_failures(username, ip_address):
    cache.delete(_login_attempt_key(username, ip_address))
    cache.delete(_login_lock_key(username, ip_address))


class LoginView(DjangoLoginView):
    form_class = AuthenticationForm
    template_name = 'core/login.html'
    redirect_authenticated_user = True
    extra_context = {
        'show_demo_credentials': settings.DEBUG,
    }

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

    def post(self, request, *args, **kwargs):
        self._lockout_blocked = False
        username = request.POST.get('username', '').strip() or 'unknown'
        ip_address = _get_client_ip(request)
        lockout_until = _get_lockout_until(username, ip_address)
        if lockout_until:
            self._lockout_blocked = True
            remaining = int((lockout_until - timezone.now()).total_seconds() / 60) + 1
            form = self.get_form()
            form.add_error(
                None,
                f"Too many failed attempts. Try again in {remaining} minute(s).",
            )
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)

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

    def form_valid(self, form):
        username = form.cleaned_data.get('username') or 'unknown'
        ip_address = _get_client_ip(self.request)
        _clear_login_failures(username, ip_address)
        return super().form_valid(form)

    def form_invalid(self, form):
        if not getattr(self, '_lockout_blocked', False):
            username = form.data.get('username', '').strip() or 'unknown'
            ip_address = _get_client_ip(self.request)
            _record_login_failure(username, ip_address)
        return super().form_invalid(form)


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

from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.forms import AuthenticationForm as DjangoAuthForm
from django import forms


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

    def get_success_url(self):
        """Redirect to appropriate dashboard based on user role"""
        from .models import User
        user = self.request.user
        if user.role == User.ROLE_ADMIN:
            return '/admin-dashboard/'
        elif user.role == User.ROLE_CLINICIAN:
            return '/clinician/'
        elif user.role == User.ROLE_PATIENT:
            return '/patient/'
        return '/'

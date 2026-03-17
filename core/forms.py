from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Comment, Assignment, ClinicianProfile, PatientProfile


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'role')


class UserForm(forms.ModelForm):
    password = forms.CharField(required=False, widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Leave blank to keep current password'}))
    
    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'is_active']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'role': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data['password']:
            user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Enter comment...'}),
        }


class AssignmentForm(forms.ModelForm):
    clinician = forms.ModelChoiceField(
        queryset=ClinicianProfile.objects.select_related('user'),
        label="Select Clinician",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    patient = forms.ModelChoiceField(
        queryset=PatientProfile.objects.select_related('user'),
        label="Select Patient",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Assignment
        fields = ['clinician', 'patient']

    def __str__(self):
        return f"{self.cleaned_data['clinician']} -> {self.cleaned_data['patient']}"


class ClinicianProfileForm(forms.ModelForm):
    class Meta:
        model = ClinicianProfile
        fields = []


class PatientProfileForm(forms.ModelForm):
    class Meta:
        model = PatientProfile
        fields = []

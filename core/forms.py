from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Comment, Assignment, ClinicianProfile, PatientProfile, PREDEFINED_ZONES, Feedback, PressureFrame


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


class PainZoneReportForm(forms.Form):
    zones = forms.MultipleChoiceField(
        choices=[(z, z.replace('_', ' ').title()) for z in PREDEFINED_ZONES],
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    note = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional: describe your discomfort...'}),
    )


class FeedbackForm(forms.ModelForm):
    pressure_frame = forms.ModelChoiceField(
        queryset=PressureFrame.objects.none(),
        empty_label="Select a sensor reading...",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Sensor Reading"
    )
    
    class Meta:
        model = Feedback
        fields = ['pressure_frame', 'feedback_text']
        widgets = {
            'feedback_text': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe your feedback about this sensor reading...',
                'class': 'form-control'
            }),
        }


class FeedbackAdminForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ['status', 'admin_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'admin_notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Admin notes...',
                'class': 'form-control'
            }),
        }

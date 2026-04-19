from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Comment, ClinicianPatientAssignment, ClinicianProfile, PatientProfile, PREDEFINED_ZONES, Feedback, PressureFrame, SensorData


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


class ClinicianPatientAssignmentForm(forms.ModelForm):
    clinician = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.ROLE_CLINICIAN),
        label="Select Clinician",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    patient = forms.ModelChoiceField(
        queryset=User.objects.filter(role=User.ROLE_PATIENT),
        label="Select Patient",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = ClinicianPatientAssignment
        fields = ['clinician', 'patient']

    def clean(self):
        cleaned_data = super().clean()
        clinician = cleaned_data.get('clinician')
        patient = cleaned_data.get('patient')

        if clinician and patient:
            if clinician == patient:
                self.add_error('patient', 'Clinician and patient must be different users.')
            if ClinicianPatientAssignment.objects.filter(clinician=clinician, patient=patient).exists():
                self.add_error(None, 'This assignment already exists.')

        return cleaned_data


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
    sensor_data = forms.ModelChoiceField(
        queryset=SensorData.objects.none(),
        empty_label="Select a sensor reading...",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Sensor Reading",
        required=True
    )
    feedback_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Describe your feedback about this sensor reading...',
            'class': 'form-control'
        }),
        label='Feedback Text',
        required=True,
        min_length=10
    )

    class Meta:
        model = Feedback
        fields = ['sensor_data']

    def clean(self):
        cleaned_data = super().clean()
        feedback_text = cleaned_data.get('feedback_text')
        
        if not feedback_text or not feedback_text.strip():
            self.add_error('feedback_text', 'Feedback text is required.')
        elif len(feedback_text.strip()) < 10:
            self.add_error('feedback_text', 'Feedback must be at least 10 characters.')
        
        return cleaned_data

    def save(self, commit=True):
        feedback = super().save(commit=False)
        feedback.comment = self.cleaned_data.get('feedback_text', '').strip()
        if commit:
            feedback.save()
        return feedback


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

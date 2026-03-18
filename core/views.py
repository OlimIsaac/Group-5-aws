from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, logout, authenticate
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages

from django.utils import timezone
from datetime import timedelta
from collections import defaultdict

from .models import (
    User, PressureFrame, ClinicianProfile, Assignment,
    PatientProfile, Comment, PainZoneReport, PREDEFINED_ZONES,
)
from .forms import (
    CommentForm, AssignmentForm, UserForm,
    ClinicianProfileForm, PatientProfileForm,
    CustomUserCreationForm, PainZoneReportForm,
)


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

    def get(self, request, form=None):
        if request.user.role != User.ROLE_PATIENT:
            return redirect('home')
        if form is None:
            form = PainZoneReportForm()
        latest_pain_report = PainZoneReport.objects.filter(
            user=request.user
        ).order_by('-timestamp').first()
        return render(request, 'core/patient_dashboard.html', {
            'zone_choices': PREDEFINED_ZONES,
            'latest_pain_report': latest_pain_report,
            'form': form,
        })


class SubmitPainZonesView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return HttpResponseForbidden("Patients only")

        form = PainZoneReportForm(request.POST)
        if form.is_valid():
            PainZoneReport.objects.create(
                user=request.user,
                zones=form.cleaned_data['zones'],
                note=form.cleaned_data['note'],
            )
            messages.success(request, "Pain zones submitted successfully")
            return redirect('patient_dashboard')

        # Validation failed — re-render dashboard with bound form
        return PatientDashboardView().get(request, form=form)


class PatientStatusAPIView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return JsonResponse({"error": "forbidden"}, status=403)

        try:
            hours = int(request.GET.get('hours', 1))
        except (ValueError, TypeError):
            hours = 1
        if hours not in (1, 6, 24):
            hours = 1

        now = timezone.now()
        since = now - timedelta(hours=hours)
        frames = PressureFrame.objects.filter(
            user=request.user, timestamp__gte=since
        ).order_by('timestamp')

        if not frames.exists():
            return JsonResponse({
                "alert": False,
                "latest_ppi": None,
                "latest_contact": None,
                "latest_matrix": None,
                "chart_data": {"labels": [], "counts": []},
            })

        latest = frames.last()

        # Build hour buckets for chart_data — sorted chronologically
        # Use datetime objects as keys so cross-midnight windows don't collide on "%H:%M" strings
        ordered_bucket_times = []
        bucket_counts = {}
        for offset in range(hours + 1):  # +1 to include the current hour
            bucket_time = (now - timedelta(hours=hours - offset)).replace(
                minute=0, second=0, microsecond=0
            )
            if bucket_time not in bucket_counts:
                ordered_bucket_times.append(bucket_time)
                bucket_counts[bucket_time] = 0

        for frame in frames:
            if frame.high_pressure_flag:
                bucket_time = frame.timestamp.replace(
                    minute=0, second=0, microsecond=0
                )
                if bucket_time in bucket_counts:
                    bucket_counts[bucket_time] += 1

        labels = [bt.strftime("%H:%M") for bt in ordered_bucket_times]
        counts = [bucket_counts[bt] for bt in ordered_bucket_times]

        return JsonResponse({
            "alert": latest.high_pressure_flag,
            "latest_ppi": latest.peak_pressure_index,
            "latest_contact": latest.contact_area_percentage,
            "latest_matrix": latest.raw_matrix,
            "chart_data": {"labels": labels, "counts": counts},
        })


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


class AssignmentListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can manage assignments")
        
        assignments = Assignment.objects.select_related('clinician__user', 'patient__user').all()
        return render(request, 'core/assignment_list.html', {'assignments': assignments})


class CreateAssignmentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can create assignments")
        
        form = AssignmentForm()
        return render(request, 'core/assignment_form.html', {'form': form, 'action': 'Create'})

    def post(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can create assignments")
        
        form = AssignmentForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                clinician_name = form.cleaned_data['clinician'].user.username
                patient_name = form.cleaned_data['patient'].user.username
                messages.success(request, f"Successfully assigned {patient_name} to {clinician_name}!")
                return redirect('assignment_list')
            except Exception as e:
                messages.error(request, f"Error creating assignment: {str(e)}")
        
        return render(request, 'core/assignment_form.html', {'form': form, 'action': 'Create'})


class DeleteAssignmentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, assignment_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete assignments")
        
        assignment = get_object_or_404(Assignment, id=assignment_id)
        return render(request, 'core/assignment_confirm_delete.html', {'assignment': assignment})

    def post(self, request, assignment_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete assignments")
        
        assignment = get_object_or_404(Assignment, id=assignment_id)
        clinician_name = assignment.clinician.user.username
        patient_name = assignment.patient.user.username
        assignment.delete()
        messages.success(request, f"Assignment removed: {patient_name} from {clinician_name}")
        return redirect('assignment_list')


# ==================== USER MANAGEMENT ====================

class UserListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can manage users")
        
        users = User.objects.all().order_by('username')
        return render(request, 'core/user_list.html', {'users': users})


class CreateUserView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can create users")
        
        form = CustomUserCreationForm()
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Create'})

    def post(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can create users")
        
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                # Create profile based on role
                if user.role == User.ROLE_CLINICIAN:
                    ClinicianProfile.objects.get_or_create(user=user)
                elif user.role == User.ROLE_PATIENT:
                    PatientProfile.objects.get_or_create(user=user)
                
                messages.success(request, f"User '{user.username}' created successfully!")
                return redirect('user_list')
            except Exception as e:
                messages.error(request, f"Error creating user: {str(e)}")
        
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Create'})


class EditUserView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can edit users")
        
        user = get_object_or_404(User, id=user_id)
        form = UserForm(instance=user)
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Edit', 'user': user})

    def post(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can edit users")
        
        user = get_object_or_404(User, id=user_id)
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"User '{user.username}' updated successfully!")
                return redirect('user_list')
            except Exception as e:
                messages.error(request, f"Error updating user: {str(e)}")
        
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Edit', 'user': user})


class DeleteUserView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete users")
        
        user = get_object_or_404(User, id=user_id)
        if user.id == request.user.id:
            messages.error(request, "You cannot delete your own account!")
            return redirect('user_list')
        
        return render(request, 'core/user_confirm_delete.html', {'user': user})

    def post(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete users")
        
        user = get_object_or_404(User, id=user_id)
        if user.id == request.user.id:
            messages.error(request, "You cannot delete your own account!")
            return redirect('user_list')
        
        username = user.username
        user.delete()
        messages.success(request, f"User '{username}' deleted successfully!")
        return redirect('user_list')


# ==================== CLINICIAN MANAGEMENT ====================

class ClinicianListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can manage clinicians")
        
        clinicians = ClinicianProfile.objects.select_related('user').all().order_by('user__username')
        return render(request, 'core/clinician_list.html', {'clinicians': clinicians})


# ==================== PATIENT MANAGEMENT ====================

class PatientListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can manage patients")
        
        patients = PatientProfile.objects.select_related('user').all().order_by('user__username')
        return render(request, 'core/patient_list.html', {'patients': patients})


# ==================== PRESSURE DATA MANAGEMENT ====================

class PressureDataListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can manage pressure data")
        
        # Filter by patient if specified
        patient_id = request.GET.get('patient')
        if patient_id:
            frames = PressureFrame.objects.filter(user__patient_profile__id=patient_id).order_by('-timestamp')
        else:
            frames = PressureFrame.objects.select_related('user').order_by('-timestamp')[:500]
        
        patients = PatientProfile.objects.select_related('user').all().order_by('user__username')
        return render(request, 'core/pressure_data_list.html', {'frames': frames, 'patients': patients, 'selected_patient': patient_id})


class PressureDataDetailView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, frame_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can view pressure data details")
        
        frame = get_object_or_404(PressureFrame, id=frame_id)
        return render(request, 'core/pressure_data_detail.html', {'frame': frame})


class DeletePressureDataView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, frame_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete pressure data")
        
        frame = get_object_or_404(PressureFrame, id=frame_id)
        return render(request, 'core/pressure_data_confirm_delete.html', {'frame': frame})

    def post(self, request, frame_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete pressure data")
        
        frame = get_object_or_404(PressureFrame, id=frame_id)
        user = frame.user
        frame.delete()
        messages.success(request, f"Pressure frame from {user.username} deleted successfully!")
        return redirect('pressure_data_list')


# ==================== COMMENT MANAGEMENT ====================

class CommentListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can manage comments")
        
        comments = Comment.objects.select_related('user', 'pressure_frame').order_by('-timestamp')[:200]
        return render(request, 'core/comment_list.html', {'comments': comments})


class DeleteCommentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, comment_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete comments")
        
        comment = get_object_or_404(Comment, id=comment_id)
        return render(request, 'core/comment_confirm_delete.html', {'comment': comment})

    def post(self, request, comment_id):
        if request.user.role != User.ROLE_ADMIN:
            return HttpResponseForbidden("Only admins can delete comments")
        
        comment = get_object_or_404(Comment, id=comment_id)
        user = comment.user
        comment.delete()
        messages.success(request, f"Comment by {user.username} deleted successfully!")
        return redirect('comment_list')

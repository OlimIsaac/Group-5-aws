from datetime import timedelta, timezone
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, logout, authenticate
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages

from .models import PREDEFINED_ZONES, HeatmapAnnotation, PainZoneReport, User, PressureFrame, ClinicianProfile, Assignment, PatientProfile, Comment, Feedback
from .forms import CommentForm, AssignmentForm, PainZoneReportForm, UserForm, ClinicianProfileForm, PatientProfileForm, CustomUserCreationForm, FeedbackForm, FeedbackAdminForm


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

        latest_annotation = HeatmapAnnotation.objects.filter(user=request.user).first()

        return JsonResponse({
            "alert": latest.high_pressure_flag,
            "latest_ppi": latest.peak_pressure_index,
            "latest_contact": latest.contact_area_percentage,
            "latest_matrix": latest.raw_matrix,
            "chart_data": {"labels": labels, "counts": counts},
            "saved_annotation": latest_annotation.cells if latest_annotation else [],
        })


class SaveHeatmapAnnotationView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return JsonResponse({"error": "forbidden"}, status=403)
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "invalid JSON"}, status=400)

        cells = body.get('cells', [])
        note = body.get('note', '')

        if not isinstance(cells, list):
            return JsonResponse({"error": "cells must be a list"}, status=400)
        for cell in cells:
            if not (isinstance(cell, list) and len(cell) == 2 and
                    isinstance(cell[0], int) and isinstance(cell[1], int) and
                    0 <= cell[0] < 32 and 0 <= cell[1] < 32):
                return JsonResponse({"error": "invalid cell coordinates"}, status=400)

        HeatmapAnnotation.objects.create(user=request.user, cells=cells, note=note)
        return JsonResponse({"status": "saved", "count": len(cells)})


class ClinicianDashboardView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_CLINICIAN:
            return redirect('home')
        try:
            profile = ClinicianProfile.objects.get(user=request.user)
            assignments = Assignment.objects.filter(clinician=profile).select_related('patient__user')
        except ClinicianProfile.DoesNotExist:
            assignments = []

        patients_data = []
        for assignment in assignments:
            patient_user = assignment.patient.user
            latest_frame = PressureFrame.objects.filter(user=patient_user).order_by('-timestamp').first()
            latest_annotation = HeatmapAnnotation.objects.filter(user=patient_user).first()
            patients_data.append({
                'assignment': assignment,
                'latest_frame': latest_frame,
                'latest_annotation': latest_annotation,
                'matrix_json': json.dumps(latest_frame.raw_matrix) if latest_frame else 'null',
                'cells_json': json.dumps(latest_annotation.cells) if latest_annotation else '[]',
            })

        return render(request, 'core/clinician_dashboard.html', {'patients_data': patients_data})


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
            return redirect('home')
        assignments = Assignment.objects.select_related('clinician__user', 'patient__user').all()
        return render(request, 'core/assignment_list.html', {'assignments': assignments})


class CreateAssignmentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = AssignmentForm()
        return render(request, 'core/assignment_form.html', {'form': form, 'action': 'Create'})

    def post(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = AssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assignment_list')
        return render(request, 'core/assignment_form.html', {'form': form, 'action': 'Create'})


class DeleteAssignmentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, assignment_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        assignment = get_object_or_404(Assignment, pk=assignment_id)
        return render(request, 'core/assignment_confirm_delete.html', {'assignment': assignment})

    def post(self, request, assignment_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        assignment = get_object_or_404(Assignment, pk=assignment_id)
        assignment.delete()
        return redirect('assignment_list')


class UserListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        users = User.objects.all()
        return render(request, 'core/user_list.html', {'users': users})


class CreateUserView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = CustomUserCreationForm()
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Create'})

    def post(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Create profile based on role
            if user.role == User.ROLE_CLINICIAN:
                ClinicianProfile.objects.create(user=user)
            elif user.role == User.ROLE_PATIENT:
                PatientProfile.objects.create(user=user)
            return redirect('user_list')
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Create'})


class EditUserView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        user = get_object_or_404(User, pk=user_id)
        form = UserForm(instance=user)
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Edit', 'editing': True})

    def post(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        user = get_object_or_404(User, pk=user_id)
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user_list')
        return render(request, 'core/user_form.html', {'form': form, 'action': 'Edit', 'editing': True})


class DeleteUserView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        user = get_object_or_404(User, pk=user_id)
        return render(request, 'core/user_confirm_delete.html', {'user': user})

    def post(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        user = get_object_or_404(User, pk=user_id)
        user.delete()
        return redirect('user_list')


class ClinicianListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        clinicians = User.objects.filter(role=User.ROLE_CLINICIAN)
        return render(request, 'core/clinician_list.html', {'clinicians': clinicians})


class PatientListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        patients = User.objects.filter(role=User.ROLE_PATIENT)
        return render(request, 'core/patient_list.html', {'patients': patients})


class PressureDataListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        frames = PressureFrame.objects.select_related('user').all().order_by('-timestamp')
        return render(request, 'core/pressure_data_list.html', {'frames': frames})


class PressureDataDetailView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, frame_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        frame = get_object_or_404(PressureFrame, pk=frame_id)
        return render(request, 'core/pressure_data_detail.html', {'frame': frame})


class DeletePressureDataView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, frame_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        frame = get_object_or_404(PressureFrame, pk=frame_id)
        return render(request, 'core/pressure_data_confirm_delete.html', {'frame': frame})

    def post(self, request, frame_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        frame = get_object_or_404(PressureFrame, pk=frame_id)
        frame.delete()
        return redirect('pressure_data_list')


class CommentListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        comments = Comment.objects.select_related('user', 'pressure_frame').all().order_by('-timestamp')
        return render(request, 'core/comment_list.html', {'comments': comments})


class DeleteCommentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, comment_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        comment = get_object_or_404(Comment, pk=comment_id)
        return render(request, 'core/comment_confirm_delete.html', {'comment': comment})

    def post(self, request, comment_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        comment = get_object_or_404(Comment, pk=comment_id)
        comment.delete()
        return redirect('comment_list')


class SubmitFeedbackView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role not in [User.ROLE_PATIENT, User.ROLE_CLINICIAN]:
            return redirect('home')
        
        # Filter available frames based on user role
        if request.user.role == User.ROLE_PATIENT:
            frames = PressureFrame.objects.filter(user=request.user)
        elif request.user.role == User.ROLE_CLINICIAN:
            try:
                profile = ClinicianProfile.objects.get(user=request.user)
                assigned_patients = Assignment.objects.filter(clinician=profile).values_list('patient__user', flat=True)
                frames = PressureFrame.objects.filter(user__in=assigned_patients)
            except ClinicianProfile.DoesNotExist:
                frames = PressureFrame.objects.none()
        else:
            frames = PressureFrame.objects.none()
        
        form = FeedbackForm()
        form.fields['pressure_frame'].queryset = frames
        return render(request, 'core/feedback_submit.html', {'form': form})

    def post(self, request):
        if request.user.role not in [User.ROLE_PATIENT, User.ROLE_CLINICIAN]:
            return redirect('home')
        
        form = FeedbackForm(request.POST)
        if form.is_valid():
            frame = form.cleaned_data['pressure_frame']
            
            # Additional permission check
            if request.user.role == User.ROLE_PATIENT and frame.user != request.user:
                messages.error(request, "You can only submit feedback on your own sensor data")
                return redirect('submit_feedback')
            elif request.user.role == User.ROLE_CLINICIAN:
                try:
                    profile = ClinicianProfile.objects.get(user=request.user)
                    if not Assignment.objects.filter(clinician=profile, patient__user=frame.user).exists():
                        messages.error(request, "You are not assigned to this patient")
                        return redirect('submit_feedback')
                except ClinicianProfile.DoesNotExist:
                    messages.error(request, "Clinician profile not found")
                    return redirect('submit_feedback')
            
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()
            messages.success(request, "Feedback submitted successfully")
            return redirect('patient_dashboard' if request.user.role == User.ROLE_PATIENT else 'clinician_dashboard')
        
        # If form is invalid, re-render with errors
        if request.user.role == User.ROLE_PATIENT:
            frames = PressureFrame.objects.filter(user=request.user)
        elif request.user.role == User.ROLE_CLINICIAN:
            try:
                profile = ClinicianProfile.objects.get(user=request.user)
                assigned_patients = Assignment.objects.filter(clinician=profile).values_list('patient__user', flat=True)
                frames = PressureFrame.objects.filter(user__in=assigned_patients)
            except ClinicianProfile.DoesNotExist:
                frames = PressureFrame.objects.none()
        else:
            frames = PressureFrame.objects.none()
        
        form.fields['pressure_frame'].queryset = frames
        return render(request, 'core/feedback_submit.html', {'form': form})


class FeedbackListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        
        feedbacks = Feedback.objects.select_related('user', 'pressure_frame', 'reviewed_by').all()
        return render(request, 'core/feedback_list.html', {'feedbacks': feedbacks})


class FeedbackDetailView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, feedback_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        
        feedback = get_object_or_404(Feedback, pk=feedback_id)
        form = FeedbackAdminForm(instance=feedback)
        return render(request, 'core/feedback_detail.html', {'feedback': feedback, 'form': form})

    def post(self, request, feedback_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        
        feedback = get_object_or_404(Feedback, pk=feedback_id)
        form = FeedbackAdminForm(request.POST, instance=feedback)
        
        if form.is_valid():
            updated_feedback = form.save(commit=False)
            
            if 'mark_reviewed' in request.POST:
                updated_feedback.mark_reviewed(request.user)
                messages.success(request, "Feedback marked as reviewed")
            elif 'resolve' in request.POST:
                updated_feedback.resolve(request.user, request.POST.get('admin_notes', ''))
                messages.success(request, "Feedback resolved")
            else:
                updated_feedback.save()
                messages.success(request, "Feedback updated")
            
            return redirect('feedback_list')
        
        return render(request, 'core/feedback_detail.html', {'feedback': feedback, 'form': form})


class DeleteFeedbackView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, feedback_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        feedback = get_object_or_404(Feedback, pk=feedback_id)
        return render(request, 'core/feedback_confirm_delete.html', {'feedback': feedback})

    def post(self, request, feedback_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        feedback = get_object_or_404(Feedback, pk=feedback_id)
        feedback.delete()
        return redirect('feedback_list')

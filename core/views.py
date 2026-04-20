from datetime import timedelta, timezone
import json

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, logout, authenticate
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib import messages

from .models import PREDEFINED_ZONES, HeatmapAnnotation, PainZoneReport, User, PressureFrame, SensorData, ClinicianProfile, Assignment, PatientProfile, Comment, Feedback
from sensore.models import SensorFrame
from .utils import LOW_PRESSURE_THRESHOLD, HIGH_PRESSURE_THRESHOLD
from .forms import CommentForm, AssignmentForm, PainZoneReportForm, UserForm, ClinicianProfileForm, PatientProfileForm, CustomUserCreationForm, FeedbackForm, FeedbackAdminForm
from .reports import generate_patient_report


class HomeView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')

        if not request.user.role:
            if request.user.is_superuser or request.user.is_staff:
                request.user.role = User.ROLE_ADMIN
                request.user.save(update_fields=['role'])
            else:
                logout(request)
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
        
        # Get recent pressure frames for commenting
        recent_frames = SensorFrame.objects.filter(
            session__patient=request.user
        ).order_by('-timestamp')[:20]
        
        return render(request, 'core/patient_dashboard.html', {
            'zone_choices': PREDEFINED_ZONES,
            'latest_pain_report': latest_pain_report,
            'form': form,
            'recent_frames': recent_frames,
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
        frames = SensorFrame.objects.filter(
            session__patient=request.user, timestamp__gte=since
        ).select_related('metrics').order_by('timestamp')

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
            metrics = getattr(frame, 'metrics', None)
            if metrics and metrics.risk_level in ('high', 'critical'):
                bucket_time = frame.timestamp.replace(
                    minute=0, second=0, microsecond=0
                )
                if bucket_time in bucket_counts:
                    bucket_counts[bucket_time] += 1

        labels = [bt.strftime("%H:%M") for bt in ordered_bucket_times]
        counts = [bucket_counts[bt] for bt in ordered_bucket_times]

        latest_annotation = HeatmapAnnotation.objects.filter(user=request.user).first()

        # Get metrics from the related metrics object
        metrics = getattr(latest, 'metrics', None)
        
        return JsonResponse({
            "alert": metrics.risk_level in ('high', 'critical') if metrics else False,
            "latest_ppi": metrics.peak_pressure_index if metrics else None,
            "latest_contact": metrics.contact_area_percent if metrics else None,
            "latest_matrix": json.loads(latest.data) if latest else None,
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

        patient_users = [assignment.patient.user for assignment in assignments]
        high_pressure_events = []
        average_pressure_events = []
        low_pressure_events = []
        if patient_users:
            base_qs = PressureFrame.objects.filter(
                user__in=patient_users,
                peak_pressure_index__isnull=False,
            ).select_related('user').order_by('-timestamp')

            high_pressure_events = list(
                base_qs.filter(peak_pressure_index__gte=HIGH_PRESSURE_THRESHOLD)[:20]
            )
            average_pressure_events = list(
                base_qs.filter(
                    peak_pressure_index__gt=LOW_PRESSURE_THRESHOLD,
                    peak_pressure_index__lt=HIGH_PRESSURE_THRESHOLD,
                )[:20]
            )
            low_pressure_events = list(
                base_qs.filter(peak_pressure_index__lte=LOW_PRESSURE_THRESHOLD)[:20]
            )

        patient_comments = []
        if patient_users:
            patient_comments = (
                Comment.objects.filter(user__in=patient_users)
                .select_related('user', 'pressure_frame')
                .order_by('-timestamp')[:20]
            )

        return render(request, 'core/clinician_dashboard.html', {
            'patients_data': patients_data,
            'high_pressure_events': high_pressure_events,
            'average_pressure_events': average_pressure_events,
            'low_pressure_events': low_pressure_events,
            'patient_comments': patient_comments,
        })


class ReplyCommentView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request, comment_id):
        if request.user.role != User.ROLE_CLINICIAN:
            return redirect('home')

        reply_text = request.POST.get('clinician_reply', '').strip()
        if not reply_text:
            messages.error(request, 'Reply cannot be empty.')
            return redirect('clinician_dashboard')

        comment = get_object_or_404(Comment, pk=comment_id)

        try:
            profile = ClinicianProfile.objects.get(user=request.user)
        except ClinicianProfile.DoesNotExist:
            return redirect('home')

        is_assigned = Assignment.objects.filter(
            clinician=profile,
            patient__user=comment.user,
        ).exists()
        if not is_assigned:
            messages.error(request, 'You are not assigned to this patient.')
            return redirect('clinician_dashboard')

        comment.clinician_reply = reply_text
        comment.save(update_fields=['clinician_reply'])
        messages.success(request, 'Reply saved.')
        return redirect('clinician_dashboard')


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
        
        # Filter available sensor readings based on user role
        if request.user.role == User.ROLE_PATIENT:
            readings = SensorFrame.objects.filter(session__patient=request.user)
        elif request.user.role == User.ROLE_CLINICIAN:
            try:
                profile = ClinicianProfile.objects.get(user=request.user)
                assigned_patients = Assignment.objects.filter(clinician=profile).values_list('patient__user', flat=True)
                readings = SensorFrame.objects.filter(session__patient__in=assigned_patients)
            except ClinicianProfile.DoesNotExist:
                readings = SensorFrame.objects.none()
        else:
            readings = SensorFrame.objects.none()
        
        form = FeedbackForm(user=request.user)
        form.fields['sensor_frame'].queryset = readings
        return render(request, 'core/feedback_submit.html', {'form': form})

    def post(self, request):
        if request.user.role not in [User.ROLE_PATIENT, User.ROLE_CLINICIAN]:
            return redirect('home')
        
        form = FeedbackForm(request.POST, user=request.user)
        if form.is_valid():
            reading = form.cleaned_data['sensor_frame']
            
            # Additional permission check
            if request.user.role == User.ROLE_PATIENT and reading.session.patient != request.user:
                messages.error(request, "You can only submit feedback on your own sensor data")
                return redirect('submit_feedback')
            elif request.user.role == User.ROLE_CLINICIAN:
                try:
                    profile = ClinicianProfile.objects.get(user=request.user)
                    if not Assignment.objects.filter(clinician=profile, patient__user=reading.session.patient).exists():
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
            readings = SensorFrame.objects.filter(session__patient=request.user)
        elif request.user.role == User.ROLE_CLINICIAN:
            try:
                profile = ClinicianProfile.objects.get(user=request.user)
                assigned_patients = Assignment.objects.filter(clinician=profile).values_list('patient__user', flat=True)
                readings = SensorFrame.objects.filter(session__patient__in=assigned_patients)
            except ClinicianProfile.DoesNotExist:
                readings = SensorFrame.objects.none()
        else:
            readings = SensorFrame.objects.none()
        
        form.fields['sensor_frame'].queryset = readings
        return render(request, 'core/feedback_submit.html', {'form': form})


class FeedbackListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role == User.ROLE_ADMIN:
            feedbacks = Feedback.objects.select_related('user', 'sensor_data', 'reviewed_by').all().order_by('-timestamp')
        elif request.user.role == User.ROLE_CLINICIAN:
            try:
                profile = ClinicianProfile.objects.get(user=request.user)
                assigned_patients = Assignment.objects.filter(clinician=profile).values_list('patient__user', flat=True)
                feedbacks = Feedback.objects.select_related('user', 'sensor_data', 'reviewed_by').filter(sensor_data__user__in=assigned_patients).order_by('-timestamp')
            except ClinicianProfile.DoesNotExist:
                feedbacks = Feedback.objects.none()
        else:
            return redirect('home')

        return render(request, 'core/feedback_list.html', {
            'feedbacks': feedbacks,
            'is_clinician': request.user.role == User.ROLE_CLINICIAN,
        })


class PainZoneReportListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role == User.ROLE_ADMIN:
            reports = PainZoneReport.objects.select_related('user').order_by('-timestamp')
        elif request.user.role == User.ROLE_CLINICIAN:
            try:
                profile = ClinicianProfile.objects.get(user=request.user)
                assigned_patients = Assignment.objects.filter(clinician=profile).values_list('patient__user', flat=True)
                reports = PainZoneReport.objects.select_related('user').filter(user__in=assigned_patients).order_by('-timestamp')
            except ClinicianProfile.DoesNotExist:
                reports = PainZoneReport.objects.none()
        else:
            return redirect('home')

        return render(request, 'core/pain_zone_report_list.html', {'reports': reports})


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


class PatientAddCommentView(LoginRequiredMixin, View):
    """Allow patients to add comments on specific pressure frames."""
    login_url = 'login'

    def post(self, request, frame_id):
        if request.user.role != User.ROLE_PATIENT:
            return JsonResponse({"error": "forbidden"}, status=403)

        frame = get_object_or_404(PressureFrame, pk=frame_id, user=request.user)
        comment_text = request.POST.get('text', '').strip()

        if not comment_text:
            return JsonResponse({"error": "comment text cannot be empty"}, status=400)

        comment = Comment.objects.create(
            user=request.user,
            pressure_frame=frame,
            text=comment_text
        )

        messages.success(request, "Comment added successfully")
        return redirect('patient_dashboard')


class PatientReportView(LoginRequiredMixin, View):
    """Allow patients to download their medical history report as PDF."""
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return HttpResponseForbidden("Patients only")

        # Get all pressure frames for this patient, ordered by timestamp
        frames = PressureFrame.objects.filter(user=request.user).order_by('-timestamp')

        if not frames.exists():
            messages.warning(request, "No pressure data available to generate report")
            return redirect('patient_dashboard')

        # Generate and return PDF
        return generate_patient_report(request.user, frames)

import csv
import io
import json
from collections import defaultdict
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django_filters.rest_framework import DjangoFilterBackend
# DRF imports
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .forms import (ClinicianPatientAssignmentForm, ClinicianProfileForm,
                    CommentForm, CustomUserCreationForm, FeedbackAdminForm,
                    FeedbackForm, PainZoneReportForm, PatientProfileForm,
                    UserForm)
from .models import (PREDEFINED_ZONES, ClinicianPatientAssignment,
                     ClinicianProfile, Comment, Feedback, HeatmapAnnotation,
                     PainZoneReport, PatientProfile, PressureFrame, SensorData,
                     User)
from .permissions import (IsAdmin, IsClinician, IsOwnerOrAssignedClinician,
                          IsPatient)
from .serializers import (ClinicianPatientAssignmentSerializer,
                          FeedbackSerializer, SensorDataSerializer,
                          UserSerializer)

# Temporary merge branch 2


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

        pain_zones = PainZoneReport.objects.filter(user=request.user).order_by('-timestamp').first()
        annotations = HeatmapAnnotation.objects.filter(user=request.user).order_by('-timestamp')[:5]
        latest_pain_report = PainZoneReport.objects.filter(user=request.user).order_by('-timestamp').first()
        form = PainZoneReportForm()

        context = {
            'form': form,
            'zone_choices': PREDEFINED_ZONES,
            'pain_zones': pain_zones,
            'annotations': annotations,
            'latest_pain_report': latest_pain_report,
        }
        return render(request, 'core/patient_dashboard.html', context)


class SubmitPainZonesView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return HttpResponseForbidden()

        form = PainZoneReportForm()
        return render(request, 'core/submit_pain_zones.html', {'form': form})

    def post(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return HttpResponseForbidden()

        form = PainZoneReportForm(request.POST)
        if form.is_valid():
            PainZoneReport.objects.create(
                user=request.user,
                zones=form.cleaned_data['zones'],
                note=form.cleaned_data['note'],
            )
            messages.success(request, "Pain zones submitted successfully")
            return redirect('patient_dashboard')

        return render(request, 'core/submit_pain_zones.html', {'form': form})


class PatientStatusAPIView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        try:
            hours = int(request.GET.get('hours', 1))
            if hours not in [1, 6, 24]:
                hours = 1
        except ValueError:
            hours = 1

        latest_frame = PressureFrame.objects.filter(user=request.user).order_by('-timestamp').first()
        latest_annotation = HeatmapAnnotation.objects.filter(user=request.user).order_by('-timestamp').first()

        alert = latest_frame.high_pressure_flag if latest_frame else False
        latest_ppi = latest_frame.peak_pressure_index if latest_frame else None
        latest_contact = latest_frame.contact_area_percentage if latest_frame else None
        latest_matrix = latest_frame.raw_matrix if latest_frame else None
        saved_annotation = latest_annotation.cells if latest_annotation else []

        now = timezone.now()
        cutoff = now - timedelta(hours=hours)

        frames = PressureFrame.objects.filter(
            user=request.user,
            timestamp__gte=cutoff,
        ).order_by('timestamp')

        high_pressure_frames = frames.filter(high_pressure_flag=True)

        if frames.exists():
            num_buckets = hours + 1
            labels = [f"Hour {i}" for i in range(num_buckets)]
            counts = [0] * num_buckets

            for frame in high_pressure_frames:
                elapsed = now - frame.timestamp
                bucket_idx = min(int(elapsed.total_seconds() // 3600), num_buckets - 1)
                counts[bucket_idx] += 1
        else:
            labels = []
            counts = []

        data = {
            'alert': alert,
            'latest_ppi': latest_ppi,
            'latest_contact': latest_contact,
            'latest_matrix': latest_matrix,
            'saved_annotation': saved_annotation,
            'chart_data': {
                'labels': labels,
                'counts': counts,
            }
        }

        return JsonResponse(data)


class SaveHeatmapAnnotationView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return JsonResponse({'status': 'error', 'error': 'Unauthorized'}, status=403)

        try:
            data = json.loads(request.body)
            cells = data.get('cells', [])
            note = data.get('note', '')

            annotation = HeatmapAnnotation.objects.create(
                user=request.user,
                cells=cells,
                note=note
            )

            return JsonResponse({'status': 'saved', 'count': len(cells), 'id': annotation.id})
        except Exception as e:
            return JsonResponse({'status': 'error', 'error': str(e)}, status=400)


class ClinicianDashboardView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_CLINICIAN:
            return redirect('home')
        try:
            assigned_patients = ClinicianPatientAssignment.objects.filter(clinician=request.user).values_list('patient', flat=True)
            assignments = ClinicianPatientAssignment.objects.filter(clinician=request.user).select_related('patient')

            patients_data = []
            for assignment in assignments:
                patient_user = assignment.patient
                latest_frame = PressureFrame.objects.filter(user=patient_user).order_by('-timestamp').first()
                latest_annotation = HeatmapAnnotation.objects.filter(user=patient_user).order_by('-timestamp').first()
                matrix_json = 'null'
                if latest_frame:
                    try:
                        matrix_json = json.dumps(latest_frame.raw_matrix)
                    except (TypeError, ValueError):
                        matrix_json = 'null'
                cells_json = '[]'
                if latest_annotation:
                    try:
                        cells_json = json.dumps(latest_annotation.cells)
                    except (TypeError, ValueError):
                        cells_json = '[]'
                patients_data.append({
                    'assignment': assignment,
                    'latest_frame': latest_frame,
                    'latest_annotation': latest_annotation,
                    'matrix_json': matrix_json,
                    'cells_json': cells_json,
                })

            return render(request, 'core/clinician_dashboard.html', {'patients_data': patients_data})
        except Exception as e:
            # Log the error and return a simple error page
            return render(request, 'core/clinician_dashboard.html', {'patients_data': [], 'error': str(e)})


class ClinicianDashboardDataAPIView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_CLINICIAN:
            return JsonResponse({'error': 'Unauthorized'}, status=403)

        assignments = ClinicianPatientAssignment.objects.filter(clinician=request.user).select_related('patient')
        patients = []
        for assignment in assignments:
            patient = assignment.patient
            latest_frame = PressureFrame.objects.filter(user=patient).order_by('-timestamp').first()
            latest_annotation = HeatmapAnnotation.objects.filter(user=patient).order_by('-timestamp').first()
            latest_matrix = None
            if latest_frame:
                try:
                    latest_matrix = latest_frame.raw_matrix
                except:
                    latest_matrix = None
            annotation_cells = []
            if latest_annotation:
                try:
                    annotation_cells = latest_annotation.cells
                except:
                    annotation_cells = []
            patients.append({
                'id': patient.id,
                'name': patient.get_full_name() or patient.username,
                'email': patient.email,
                'latest_matrix': latest_matrix,
                'latest_ppi': latest_frame.peak_pressure_index if latest_frame else None,
                'latest_contact': latest_frame.contact_area_percentage if latest_frame else None,
                'high_pressure': latest_frame.high_pressure_flag if latest_frame else False,
                'pressure_timestamp': latest_frame.timestamp.isoformat() if latest_frame else None,
                'annotation_cells': annotation_cells,
                'annotation_note': latest_annotation.note if latest_annotation else '',
                'annotation_timestamp': latest_annotation.timestamp.isoformat() if latest_annotation else None,
            })

        return JsonResponse({'patients': patients})


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
        assignments = ClinicianPatientAssignment.objects.select_related('clinician', 'patient').all()
        return render(request, 'core/assignment_list.html', {'assignments': assignments})


class CreateAssignmentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = ClinicianPatientAssignmentForm()
        return render(request, 'core/assignment_form.html', {'form': form, 'action': 'Create'})

    def post(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = ClinicianPatientAssignmentForm(request.POST)
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                form.add_error(None, 'This assignment already exists.')
                return render(request, 'core/assignment_form.html', {'form': form, 'action': 'Create'})
            return redirect('assignment_list')
        return render(request, 'core/assignment_form.html', {'form': form, 'action': 'Create'})


class DeleteAssignmentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, assignment_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        assignment = get_object_or_404(ClinicianPatientAssignment, pk=assignment_id)
        return render(request, 'core/assignment_confirm_delete.html', {'assignment': assignment})

    def post(self, request, assignment_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        assignment = get_object_or_404(ClinicianPatientAssignment, pk=assignment_id)
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
            user = form.save()
            # Ensure profile exists based on role
            if user.role == User.ROLE_CLINICIAN and not hasattr(user, 'clinician_profile'):
                ClinicianProfile.objects.create(user=user)
            elif user.role == User.ROLE_PATIENT and not hasattr(user, 'patient_profile'):
                PatientProfile.objects.create(user=user)
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
        
        # Limit to recent sensor data only (last 100 records or last 7 days)
        cutoff_date = timezone.now() - timedelta(days=7)
        
        if request.user.role == User.ROLE_PATIENT:
            sensor_records = SensorData.objects.filter(
                user=request.user
            ).filter(
                timestamp__gte=cutoff_date
            ).order_by('-timestamp')[:100]
        elif request.user.role == User.ROLE_CLINICIAN:
            assigned_patients = ClinicianPatientAssignment.objects.filter(clinician=request.user).values_list('patient', flat=True)
            sensor_records = SensorData.objects.filter(
                user__in=assigned_patients,
                timestamp__gte=cutoff_date
            ).order_by('-timestamp')[:100]
        else:
            sensor_records = SensorData.objects.none()
        
        form = FeedbackForm()
        form.fields['sensor_data'].queryset = sensor_records
        return render(request, 'core/feedback_submit.html', {'form': form})

    def post(self, request):
        if request.user.role not in [User.ROLE_PATIENT, User.ROLE_CLINICIAN]:
            return redirect('home')
        
        form = FeedbackForm(request.POST)
        if form.is_valid():
            sensor_data = form.cleaned_data['sensor_data']
            
            if request.user.role == User.ROLE_PATIENT and sensor_data.user != request.user:
                messages.error(request, "You can only submit feedback on your own sensor data")
                return redirect('submit_feedback')
            elif request.user.role == User.ROLE_CLINICIAN:
                if not ClinicianPatientAssignment.objects.filter(clinician=request.user, patient=sensor_data.user).exists():
                    messages.error(request, "You are not assigned to this patient")
                    return redirect('submit_feedback')
            
            feedback = form.save(commit=False)
            feedback.user = request.user
            feedback.save()
            messages.success(request, "Feedback submitted successfully")
            return redirect('patient_dashboard' if request.user.role == User.ROLE_PATIENT else 'clinician_dashboard')
        
        # Limit to recent sensor data only
        cutoff_date = timezone.now() - timedelta(days=7)
        
        if request.user.role == User.ROLE_PATIENT:
            sensor_records = SensorData.objects.filter(
                user=request.user
            ).filter(
                timestamp__gte=cutoff_date
            ).order_by('-timestamp')[:100]
        elif request.user.role == User.ROLE_CLINICIAN:
            assigned_patients = ClinicianPatientAssignment.objects.filter(clinician=request.user).values_list('patient', flat=True)
            sensor_records = SensorData.objects.filter(
                user__in=assigned_patients,
                timestamp__gte=cutoff_date
            ).order_by('-timestamp')[:100]
        else:
            sensor_records = SensorData.objects.none()
        
        form.fields['sensor_data'].queryset = sensor_records
        return render(request, 'core/feedback_submit.html', {'form': form})


class FeedbackListView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        
        feedbacks = Feedback.objects.select_related('user', 'sensor_data', 'reviewed_by').all()
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


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['role', 'username', 'email']
    ordering_fields = ['username', 'email', 'role']


class ClinicianPatientAssignmentViewSet(viewsets.ModelViewSet):
    queryset = ClinicianPatientAssignment.objects.select_related('clinician', 'patient').all()
    serializer_class = ClinicianPatientAssignmentSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['clinician', 'patient']
    ordering_fields = ['assigned_at']


class SensorDataViewSet(viewsets.ModelViewSet):
    queryset = SensorData.objects.all()
    serializer_class = SensorDataSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'timestamp', 'sensor_id', 'location']
    ordering_fields = ['timestamp', 'user']

    def get_queryset(self):
        user = self.request.user
        if user.role == User.ROLE_ADMIN:
            return SensorData.objects.all()
        if user.role == User.ROLE_PATIENT:
            return SensorData.objects.filter(user=user)
        if user.role == User.ROLE_CLINICIAN:
            assigned_patient_ids = ClinicianPatientAssignment.objects.filter(clinician=user).values_list('patient_id', flat=True)
            return SensorData.objects.filter(user_id__in=assigned_patient_ids)
        return SensorData.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        sensor_data_user = serializer.validated_data.get('user')
        if user.role == User.ROLE_PATIENT and sensor_data_user != user:
            raise PermissionDenied("Patients can only upload their own sensor data.")
        if user.role == User.ROLE_CLINICIAN and not ClinicianPatientAssignment.objects.filter(clinician=user, patient=sensor_data_user).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        serializer.save()


class FeedbackViewSet(viewsets.ModelViewSet):
    queryset = Feedback.objects.all()
    serializer_class = FeedbackSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['user', 'sensor_data', 'status', 'reviewed_by']
    ordering_fields = ['created_at', 'status']

    def get_queryset(self):
        user = self.request.user
        if user.role == User.ROLE_ADMIN:
            return Feedback.objects.all()
        if user.role == User.ROLE_PATIENT:
            return Feedback.objects.filter(user=user)
        if user.role == User.ROLE_CLINICIAN:
            patient_ids = ClinicianPatientAssignment.objects.filter(clinician=user).values_list('patient_id', flat=True)
            return Feedback.objects.filter(sensor_data__user_id__in=patient_ids)
        return Feedback.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        sensor_data = serializer.validated_data['sensor_data']
        if user.role == User.ROLE_PATIENT and sensor_data.user != user:
            raise PermissionDenied("Patients can only submit feedback for their own sensor data.")
        if user.role == User.ROLE_CLINICIAN and not ClinicianPatientAssignment.objects.filter(clinician=user, patient=sensor_data.user).exists():
            raise PermissionDenied("You are not assigned to this patient.")
        serializer.save(user=user)


class CSVUploadViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'detail': 'CSV file is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            text = uploaded_file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(text))
            created = 0
            errors = []
            for i, row in enumerate(reader, start=1):
                try:
                    username = row.get('user') or row.get('username') or row.get('patient')
                    if not username:
                        raise ValueError('Missing user identifier')
                    user = User.objects.get(username=username)
                    if user.role != User.ROLE_PATIENT:
                        raise ValueError('CSV rows must reference patient user accounts')

                    timestamp_str = row.get('timestamp')
                    if not timestamp_str:
                        raise ValueError('Missing timestamp')
                    timestamp = datetime.fromisoformat(timestamp_str)
                    if timezone.is_naive(timestamp):
                        timestamp = timezone.make_aware(timestamp)

                    pressure_value = float(row.get('pressure_value') or row.get('pressure'))
                    sensor_id = row.get('sensor_id', '')
                    location = row.get('location', '')

                    SensorData.objects.create(
                        user=user,
                        timestamp=timestamp,
                        pressure_value=pressure_value,
                        sensor_id=sensor_id,
                        location=location,
                    )
                    created += 1
                except Exception as exc:
                    errors.append({'row': i, 'error': str(exc), 'data': row})

            return Response({'created': created, 'errors': errors})
        except Exception as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class AdminPatientCSVUploadView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        patients = User.objects.filter(role=User.ROLE_PATIENT)
        return render(request, 'core/admin_patient_csv_upload.html', {'patients': patients})

    def post(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        
        patient_id = request.POST.get('patient_id')
        files = request.FILES.getlist('file')
        
        if not patient_id:
            messages.error(request, 'Please select a patient.')
            patients = User.objects.filter(role=User.ROLE_PATIENT)
            return render(request, 'core/admin_patient_csv_upload.html', {'patients': patients})
        
        if len(files) > 5:
            messages.error(request, 'You can upload a maximum of 5 CSV files at once.')
            patients = User.objects.filter(role=User.ROLE_PATIENT)
            return render(request, 'core/admin_patient_csv_upload.html', {'patients': patients})
        
        if not files:
            messages.error(request, 'Please upload at least one CSV file.')
            patients = User.objects.filter(role=User.ROLE_PATIENT)
            return render(request, 'core/admin_patient_csv_upload.html', {'patients': patients})
        
        try:
            patient = get_object_or_404(User, pk=patient_id, role=User.ROLE_PATIENT)
            
            total_created = 0
            total_errors = 0
            
            for uploaded_file in files:
                try:
                    # Read and decode file
                    if uploaded_file.size == 0:
                        messages.warning(request, f'{uploaded_file.name} is empty.')
                        continue
                    
                    text = uploaded_file.read().decode('utf-8', errors='replace')
                    if not text.strip():
                        messages.warning(request, f'{uploaded_file.name} is empty or not readable.')
                        continue
                    
                    reader = csv.DictReader(io.StringIO(text))
                    
                    # Accept any CSV format
                    if not reader.fieldnames:
                        messages.error(request, f'{uploaded_file.name}: CSV appears to be empty or malformed.')
                        total_errors += 1
                        continue
                    
                    created = 0
                    errors = []
                    records_to_create = []
                    
                    for i, row in enumerate(reader, start=2):
                        try:
                            # Skip completely empty rows
                            if not any(row.values()):
                                continue
                            
                            # Parse timestamp if available, otherwise use current time
                            timestamp = None
                            timestamp_str = row.get('timestamp', '').strip()
                            if timestamp_str:
                                try:
                                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                                    if timezone.is_naive(timestamp):
                                        timestamp = timezone.make_aware(timestamp)
                                except (ValueError, TypeError):
                                    timestamp = timezone.now()
                            else:
                                timestamp = timezone.now()
                            
                            # Parse pressure_value if available
                            pressure_value = 0
                            pressure_str = row.get('pressure_value') or row.get('pressure') or ''
                            if pressure_str:
                                try:
                                    pressure_value = float(pressure_str)
                                except (ValueError, TypeError):
                                    pressure_value = 0
                            
                            sensor_id = row.get('sensor_id', '').strip() if row.get('sensor_id') else ''
                            location = row.get('location', '').strip() if row.get('location') else ''
                            
                            records_to_create.append(SensorData(
                                user=patient,
                                timestamp=timestamp,
                                pressure_value=pressure_value,
                                sensor_id=sensor_id,
                                location=location,
                            ))
                        except Exception as exc:
                            errors.append({'row': i, 'error': str(exc)})
                    
                    # Bulk create all records at once
                    if records_to_create:
                        SensorData.objects.bulk_create(records_to_create)
                        created = len(records_to_create)
                    
                    total_created += created
                    total_errors += len(errors)
                    
                    if created > 0:
                        messages.success(request, f'✓ {uploaded_file.name}: Uploaded {created} records.')
                    if errors:
                        error_summary = ', '.join([f"row {e['row']}: {e['error']}" for e in errors[:3]])
                        if len(errors) > 3:
                            error_summary += f", and {len(errors) - 3} more"
                        messages.warning(request, f'{uploaded_file.name}: {len(errors)} errors - {error_summary}')
                
                except Exception as file_exc:
                    messages.error(request, f'Error processing {uploaded_file.name}: {str(file_exc)}')
                    total_errors += 1
            
            if total_created > 0:
                messages.success(request, f'✓ Total: {total_created} sensor data records uploaded for {patient.get_full_name() or patient.username}.')
            if total_errors > 0 and total_created == 0:
                messages.error(request, f'Failed to upload any records. Please check the file and try again.')
            
            patients = User.objects.filter(role=User.ROLE_PATIENT)
            return render(request, 'core/admin_patient_csv_upload.html', {'patients': patients})
        except Exception as exc:
            messages.error(request, f'Error: {str(exc)}')
            patients = User.objects.filter(role=User.ROLE_PATIENT)
            return render(request, 'core/admin_patient_csv_upload.html', {'patients': patients})


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

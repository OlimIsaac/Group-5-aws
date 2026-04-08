from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login, logout, authenticate

from .forms import CommentForm, AssignmentForm, CustomUserCreationForm, UserForm

from .models import User, PressureFrame, ClinicianProfile, Assignment, PatientProfile, Comment


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
        frames = PressureFrame.objects.filter(user=request.user).order_by('-timestamp')[:100]
        comment_form = CommentForm()
        return render(request, 'core/patient_dashboard.html', {'frames': frames, 'comment_form': comment_form})


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
            return redirect('home')
        assignments = Assignment.objects.select_related('clinician__user', 'patient__user').all()
        return render(request, 'core/assignment_list.html', {'assignments': assignments})


class CreateAssignmentView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = AssignmentForm()
        return render(request, 'core/assignment_form.html', {'form': form})

    def post(self, request):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        form = AssignmentForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('assignment_list')
        return render(request, 'core/assignment_form.html', {'form': form})


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
        return render(request, 'core/user_form.html', {'form': form})

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
        return render(request, 'core/user_form.html', {'form': form})


class EditUserView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        user = get_object_or_404(User, pk=user_id)
        form = UserForm(instance=user)
        return render(request, 'core/user_form.html', {'form': form, 'editing': True})

    def post(self, request, user_id):
        if request.user.role != User.ROLE_ADMIN:
            return redirect('home')
        user = get_object_or_404(User, pk=user_id)
        form = UserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('user_list')
        return render(request, 'core/user_form.html', {'form': form, 'editing': True})


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

from rest_framework.permissions import BasePermission
from .models import User, ClinicianPatientAssignment


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.ROLE_ADMIN


class IsClinician(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.ROLE_CLINICIAN


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == User.ROLE_PATIENT


class IsOwnerOrAssignedClinician(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.role == User.ROLE_ADMIN:
            return True
        if request.user.role == User.ROLE_PATIENT and obj.user == request.user:
            return True
        if request.user.role == User.ROLE_CLINICIAN:
            # Check if clinician is assigned to the patient
            return ClinicianPatientAssignment.objects.filter(
                clinician=request.user, patient=obj.user
            ).exists()
        return False

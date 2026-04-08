from rest_framework import serializers
from .models import (
    User,
    PatientProfile,
    ClinicianProfile,
    Assignment,
    PressureFrame,
    Comment,
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']


class PatientProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = PatientProfile
        fields = ['id', 'user']


class ClinicianProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = ClinicianProfile
        fields = ['id', 'user']


class AssignmentSerializer(serializers.ModelSerializer):
    clinician = ClinicianProfileSerializer()
    patient = PatientProfileSerializer()

    class Meta:
        model = Assignment
        fields = ['id', 'clinician', 'patient', 'assigned_at']


class PressureFrameSerializer(serializers.ModelSerializer):
    class Meta:
        model = PressureFrame
        fields = ['id', 'user', 'timestamp', 'raw_matrix', 'peak_pressure_index', 'contact_area_percentage', 'high_pressure_flag']


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ['id', 'user', 'pressure_frame', 'timestamp', 'text', 'clinician_reply']

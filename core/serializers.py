from rest_framework import serializers
from .models import (
    User,
    PatientProfile,
    ClinicianProfile,
    ClinicianPatientAssignment,
    SensorData,
    Feedback,
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


class ClinicianPatientAssignmentSerializer(serializers.ModelSerializer):
    clinician = UserSerializer()
    patient = UserSerializer()

    class Meta:
        model = ClinicianPatientAssignment
        fields = ['id', 'clinician', 'patient', 'assigned_at']


class SensorDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SensorData
        fields = ['id', 'user', 'timestamp', 'pressure_value', 'sensor_id', 'location']


class FeedbackSerializer(serializers.ModelSerializer):
    reviewed_by = UserSerializer(read_only=True)

    class Meta:
        model = Feedback
        fields = [
            'id', 'user', 'sensor_data', 'comment', 'status',
            'admin_notes', 'reviewed_at', 'reviewed_by', 'created_at'
        ]

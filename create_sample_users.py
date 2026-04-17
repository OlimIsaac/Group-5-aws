#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

from core.models import User, PatientProfile, ClinicianProfile, ClinicianPatientAssignment

# Create sample clinician
if not User.objects.filter(username='clinician1').exists():
    clinician_user = User.objects.create_user(
        username='clinician1',
        email='clinician@sensore.local',
        password='clinician123',
        role=User.ROLE_CLINICIAN
    )
    ClinicianProfile.objects.create(user=clinician_user)
    print("✓ Clinician 'clinician1' created")
else:
    print("✓ Clinician 'clinician1' already exists")

# Create sample patient
if not User.objects.filter(username='patient1').exists():
    patient_user = User.objects.create_user(
        username='patient1',
        email='patient@sensore.local',
        password='patient123',
        role=User.ROLE_PATIENT
    )
    PatientProfile.objects.create(user=patient_user)
    print("✓ Patient 'patient1' created")
else:
    print("✓ Patient 'patient1' already exists")

# Create assignment
clinician = User.objects.get(username='clinician1')
patient = User.objects.get(username='patient1')
clinician_profile = ClinicianProfile.objects.get(user=clinician)
patient_profile = PatientProfile.objects.get(user=patient)

if not ClinicianPatientAssignment.objects.filter(clinician=clinician, patient=patient).exists():
    ClinicianPatientAssignment.objects.create(clinician=clinician, patient=patient)
    print("✓ Assignment created: clinician1 → patient1")
else:
    print("✓ Assignment already exists")

print("\nTest Credentials:")
print("  Admin:     username=admin, password=admin123")
print("  Clinician: username=clinician1, password=clinician123")
print("  Patient:   username=patient1, password=patient123")

#!/usr/bin/env python
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

# Minor comment for git verification.

from core.models import User, PatientProfile, ClinicianProfile, Assignment

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

if not Assignment.objects.filter(clinician=clinician_profile, patient=patient_profile).exists():
    Assignment.objects.create(clinician=clinician_profile, patient=patient_profile)
    print("✓ Assignment created: clinician1 → patient1")
else:
    print("✓ Assignment already exists")

print("\nTest Credentials:")
print("  Admin:     username=admin, password=admin123")
print("  Clinician: username=clinician1, password=clinician123")
print("  Patient:   username=patient1, password=patient123")
from django.contrib.auth import get_user_model

from accounts.models import UserProfile

User = get_user_model()


clinician_user, created = User.objects.get_or_create(
    username='dr_smith',
    defaults={
        'email': 'clinician@sensore.local',
        'first_name': 'Dr. Sarah',
        'last_name': 'Smith',
    },
)
if created:
    clinician_user.set_password('clinic123')
    clinician_user.save()
clinician_profile, _ = UserProfile.objects.get_or_create(user=clinician_user)
clinician_profile.role = 'clinician'
clinician_profile.save(update_fields=['role'])

patient_user, created = User.objects.get_or_create(
    username='patient_001',
    defaults={
        'email': 'patient@sensore.local',
        'first_name': 'James',
        'last_name': 'Wilson',
    },
)
if created:
    patient_user.set_password('patient123')
    patient_user.save()
patient_profile, _ = UserProfile.objects.get_or_create(user=patient_user)
patient_profile.role = 'patient'
patient_profile.assigned_clinician = clinician_user
patient_profile.patient_id = 'PATIENT_001'
patient_profile.save()

print('✓ Clinician dr_smith ready')
print('✓ Patient patient_001 ready')
print('✓ Assignment stored on patient profile')
print('\nCredentials:')
print('  Admin:     admin / admin123')
print('  Clinician: dr_smith / clinic123')
print('  Patient:   patient_001 / patient123')

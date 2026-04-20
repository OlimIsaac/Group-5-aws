#!/usr/bin/env python
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

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
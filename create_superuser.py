#!/usr/bin/env python
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

from django.contrib.auth import get_user_model

from accounts.models import UserProfile

User = get_user_model()


user, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@sensore.local',
        'is_staff': True,
        'is_superuser': True,
        'first_name': 'System',
        'last_name': 'Admin',
    },
)
if created:
    user.set_password('admin123')
    user.save()

profile, _ = UserProfile.objects.get_or_create(user=user)
profile.role = 'admin'
profile.save(update_fields=['role'])

print("✓ Superuser 'admin' ready")
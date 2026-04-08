#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

from core.models import User

# Create superuser
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@sensore.local',
        password='admin123',
        role='admin'
    )
    print("✓ Superuser 'admin' created successfully")
else:
    print("✓ Superuser 'admin' already exists")

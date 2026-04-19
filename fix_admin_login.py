#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

from core.models import User
from django.contrib.auth import authenticate

# Get admin user and reset password
admin = User.objects.get(username='admin')
admin.set_password('admin123')
admin.save()
print("✓ Password reset for admin user")

# Test authentication
auth_result = authenticate(username='admin', password='admin123')
if auth_result:
    print("✓ Authentication successful!")
    print(f"  User: {auth_result.username}")
    print(f"  Role: {auth_result.get_role_display()}")
else:
    print("✗ Authentication failed")

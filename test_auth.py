#!/usr/bin/env python
import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

from django.contrib.auth import authenticate

# Test the bundled demo users
users = [('admin', 'admin123'), ('dr_smith', 'clinic123'), ('patient_001', 'patient123')]
for username, password in users:
    auth_result = authenticate(username=username, password=password)
    status = '✓' if auth_result else '✗'
    print(f'{status} {username}: {"OK" if auth_result else "FAILED"}')

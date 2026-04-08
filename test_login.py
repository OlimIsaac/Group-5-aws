#!/usr/bin/env python
import os
import django
from django.test import Client

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
django.setup()

client = Client()

# Test login with admin credentials
print("Testing admin login...")
response = client.post('/login/', {
    'username': 'admin',
    'password': 'admin123'
})

print(f"Status Code: {response.status_code}")
print(f"Redirect URL: {response.url if response.status_code in [301, 302] else 'No redirect'}")

if response.status_code in [301, 302]:
    print("✓ Login successful - redirected to dashboard")
    print(f"  Redirecting to: {response.url}")
else:
    print("✗ Login failed")
    if response.context and 'form' in response.context:
        form = response.context['form']
        print(f"  Form errors: {form.errors}")

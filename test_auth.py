#!/usr/bin/env python
import os

def main():
    import django
    from django.contrib.auth import authenticate

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sensore.settings')
    django.setup()

    # Test the bundled demo users
    users = [('admin', 'admin123'), ('dr_smith', 'clinic123'), ('patient_001', 'patient123')]
    for username, password in users:
        auth_result = authenticate(username=username, password=password)
        status = '✓' if auth_result else '✗'
        print(f'{status} {username}: {"OK" if auth_result else "FAILED"}')


if __name__ == '__main__':
    main()

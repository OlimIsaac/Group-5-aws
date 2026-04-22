"""
seed_pressure_data.py
---------------------
Run this script anytime to seed fresh PressureFrame data for patient_001
so that the 1h / 6h / 24h chart views all show clear, varied data.

Usage:
    python seed_pressure_data.py

No arguments needed. Existing frames in the last 25 hours are replaced
so you can run it repeatedly without duplicating data.
"""

import os
import sys
import django

# ── Bootstrap Django ────────────────────────────────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sensore.settings")
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

# ── Imports (after setup) ───────────────────────────────────────────────────
import random
from datetime import timedelta

import numpy as np
from django.utils import timezone

from core.models import User, PatientProfile, PressureFrame

# ── Config: high-pressure event count per hour (hour 0 = most recent) ──────
#
#  Pattern tells a clear story across all 3 views:
#
#  1h  view  → hours  0–1  :  low (3, 1)
#  6h  view  → hours  0–5  :  low → spike (3,1,5,7,2,4)
#  24h view  → full pattern: morning surge, lunch dip, afternoon build,
#                            dinner break, late-night peak
#
HIGH_COUNTS = [
    # hr  0–5   (last 6 h)
    3, 1, 5, 7, 2, 4,
    # hr  6–11  (morning)
    0, 1, 8, 9, 6, 4,
    # hr 12–17  (afternoon)
    0, 2, 5, 7, 3, 1,
    # hr 18–23  (evening)
    0, 2, 4, 6, 8, 9,
    # hr 24     (yesterday boundary)
    3,
]

NORMAL_PER_HOUR = 4   # background low-pressure frames per hour
PATIENT_USERNAME = "patient_001"
PATIENT_PASSWORD = "patient123"


def make_matrix(peak_ppi: float) -> list:
    """32×32 pressure matrix with a realistic central hotspot."""
    mat = np.random.randint(200, 1200, size=(32, 32)).astype(float)
    for r in range(12, 20):
        for c in range(12, 20):
            mat[r][c] = random.uniform(peak_ppi * 0.7, peak_ppi)
    return np.clip(mat, 0, 4095).astype(int).tolist()


def ensure_patient() -> User:
    user, created = User.objects.get_or_create(
        username=PATIENT_USERNAME,
        defaults={
            "first_name": "Alex",
            "last_name": "Patient",
            "email": "patient001@example.com",
            "role": User.ROLE_PATIENT,
        },
    )
    if created:
        user.set_password(PATIENT_PASSWORD)
        user.save()
        print(f"  Created user: {PATIENT_USERNAME}")
    else:
        print(f"  Found existing user: {PATIENT_USERNAME}")

    PatientProfile.objects.get_or_create(user=user)
    return user


def seed(user: User):
    now = timezone.now()

    # Remove stale frames in the window to avoid duplicates
    window_start = now - timedelta(hours=len(HIGH_COUNTS) + 1)
    deleted, _ = PressureFrame.objects.filter(
        user=user, timestamp__gte=window_start
    ).delete()
    if deleted:
        print(f"  Cleared {deleted} old frames")

    frames_to_create = []
    high_total = 0

    for hour_offset, high_count in enumerate(HIGH_COUNTS):
        hour_start = now - timedelta(hours=hour_offset + 1)

        # High-pressure frames
        for _ in range(high_count):
            t = hour_start + timedelta(
                minutes=random.uniform(0, 59),
                seconds=random.uniform(0, 59),
            )
            ppi = random.uniform(3500, 4095)
            frames_to_create.append(PressureFrame(
                user=user,
                timestamp=t,
                raw_matrix=make_matrix(ppi),
                peak_pressure_index=round(ppi, 1),
                contact_area_percentage=round(random.uniform(30, 60), 1),
                high_pressure_flag=True,
            ))
            high_total += 1

        # Normal (background) frames
        for _ in range(NORMAL_PER_HOUR):
            t = hour_start + timedelta(
                minutes=random.uniform(0, 59),
                seconds=random.uniform(0, 59),
            )
            ppi = random.uniform(800, 3200)
            frames_to_create.append(PressureFrame(
                user=user,
                timestamp=t,
                raw_matrix=make_matrix(ppi),
                peak_pressure_index=round(ppi, 1),
                contact_area_percentage=round(random.uniform(10, 35), 1),
                high_pressure_flag=False,
            ))

    PressureFrame.objects.bulk_create(frames_to_create)
    normal_total = NORMAL_PER_HOUR * len(HIGH_COUNTS)
    print(f"  Seeded {high_total + normal_total} frames  "
          f"({high_total} high-pressure, {normal_total} normal)")


def preview(user: User):
    """Print a quick summary so you can verify before opening the browser."""
    now = timezone.now()
    print()
    print("  Chart preview:")
    print("  ─────────────────────────────────────────")
    print("  View  │ Total frames │ High-pressure events")
    print("  ──────┼──────────────┼─────────────────────")
    for h in [1, 6, 24]:
        cutoff = now - timedelta(hours=h)
        total = PressureFrame.objects.filter(user=user, timestamp__gte=cutoff).count()
        high  = PressureFrame.objects.filter(user=user, timestamp__gte=cutoff,
                                              high_pressure_flag=True).count()
        print(f"  {h:>3}h  │ {total:>12} │ {high}")
    print("  ─────────────────────────────────────────")


if __name__ == "__main__":
    print("\nSeeding pressure data for US5 demo...\n")
    patient = ensure_patient()
    seed(patient)
    preview(patient)
    print(f"\nDone! Log in as  {PATIENT_USERNAME} / {PATIENT_PASSWORD}")
    print("Open http://127.0.0.1:8000/patient/ → switch to Last 24 Hours\n")

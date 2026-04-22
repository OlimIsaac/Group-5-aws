"""
Seed rich 24-hour time-series PressureFrame data for patient_001 so that
the US5 bar chart (1h / 6h / 24h views) shows clear, visually interesting
variation across time.

Pattern (working backwards from now):
  Hour 0  (last hour)    →  3 high-pressure events  (currently resting, some pressure)
  Hour 1                 →  1
  Hour 2                 →  5  (mid-morning activity spike)
  Hour 3                 →  7
  Hour 4                 →  2
  Hour 5                 →  4
  Hour 6  (6 h mark)     →  0  (good repositioning)
  Hour 7                 →  1
  Hour 8                 →  8  (morning – prolonged sitting)
  Hour 9                 →  9
  Hour 10                →  6
  Hour 11                →  4
  Hour 12 (noon)         →  0  (lunch break / movement)
  Hour 13                →  2
  Hour 14                →  5
  Hour 15                →  7
  Hour 16                →  3
  Hour 17                →  1
  Hour 18                →  0  (dinner break)
  Hour 19                →  2
  Hour 20                →  4
  Hour 21                →  6
  Hour 22                →  8  (late-night immobility)
  Hour 23                →  9
  Hour 24                →  3

Each high-pressure frame gets PPI ≥ 3500 and high_pressure_flag=True.
Normal frames are scattered between them (PPI 1000–3000).
"""

import random
from datetime import timedelta

import numpy as np
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import User, PatientProfile, PressureFrame


HIGH_COUNTS_BY_HOUR = [3, 1, 5, 7, 2, 4, 0, 1, 8, 9, 6, 4,
                        0, 2, 5, 7, 3, 1, 0, 2, 4, 6, 8, 9, 3]

NORMAL_PER_HOUR = 4   # low-pressure frames added each hour for realism


def _make_matrix(peak_ppi: float) -> list:
    """Return a 32×32 matrix whose max value matches the requested peak PPI."""
    mat = np.random.randint(200, 1200, size=(32, 32)).astype(float)
    # Place a realistic pressure hotspot in the central seating region
    for r in range(12, 20):
        for c in range(12, 20):
            mat[r][c] = random.uniform(peak_ppi * 0.7, peak_ppi)
    mat = np.clip(mat, 0, 4095)
    return mat.astype(int).tolist()


class Command(BaseCommand):
    help = "Seed 24-hour time-series PressureFrame data for patient_001 (US5 demo)"

    def handle(self, *args, **kwargs):
        # ------------------------------------------------------------------
        # 1. Ensure patient_001 exists
        # ------------------------------------------------------------------
        user, created = User.objects.get_or_create(
            username="patient_001",
            defaults={
                "first_name": "Alex",
                "last_name": "Patient",
                "email": "patient001@example.com",
                "role": User.ROLE_PATIENT,
            },
        )
        if created:
            user.set_password("patient123")
            user.save()
            self.stdout.write(f"  Created user: patient_001")
        else:
            self.stdout.write(f"  Found existing user: patient_001")

        PatientProfile.objects.get_or_create(user=user)

        # ------------------------------------------------------------------
        # 2. Remove old frames from the last 25 hours to avoid duplicates
        # ------------------------------------------------------------------
        cutoff = timezone.now() - timedelta(hours=25)
        deleted, _ = PressureFrame.objects.filter(
            user=user, timestamp__gte=cutoff
        ).delete()
        if deleted:
            self.stdout.write(f"  Removed {deleted} existing frames in the window")

        # ------------------------------------------------------------------
        # 3. Seed frames hour by hour
        # ------------------------------------------------------------------
        now = timezone.now()
        total_frames = 0

        for hour_offset, high_count in enumerate(HIGH_COUNTS_BY_HOUR):
            # Spread frames evenly inside this hour bucket
            hour_start = now - timedelta(hours=hour_offset + 1)

            # High-pressure frames
            for i in range(high_count):
                t = hour_start + timedelta(
                    minutes=random.uniform(0, 59),
                    seconds=random.uniform(0, 59),
                )
                ppi = random.uniform(3500, 4095)
                PressureFrame.objects.create(
                    user=user,
                    timestamp=t,
                    raw_matrix=_make_matrix(ppi),
                    peak_pressure_index=round(ppi, 1),
                    contact_area_percentage=round(random.uniform(30, 60), 1),
                    high_pressure_flag=True,
                )
                total_frames += 1

            # Normal frames (background activity)
            for i in range(NORMAL_PER_HOUR):
                t = hour_start + timedelta(
                    minutes=random.uniform(0, 59),
                    seconds=random.uniform(0, 59),
                )
                ppi = random.uniform(800, 3200)
                PressureFrame.objects.create(
                    user=user,
                    timestamp=t,
                    raw_matrix=_make_matrix(ppi),
                    peak_pressure_index=round(ppi, 1),
                    contact_area_percentage=round(random.uniform(10, 35), 1),
                    high_pressure_flag=False,
                )
                total_frames += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! Seeded {total_frames} frames for patient_001 "
                f"({sum(HIGH_COUNTS_BY_HOUR)} high-pressure, "
                f"{NORMAL_PER_HOUR * len(HIGH_COUNTS_BY_HOUR)} normal).\n"
                f"Log in as patient_001 / patient123 and switch to the 24h view."
            )
        )
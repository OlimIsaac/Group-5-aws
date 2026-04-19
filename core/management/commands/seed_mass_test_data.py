import math
import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (PREDEFINED_ZONES, ClinicianPatientAssignment,
                         ClinicianProfile, Comment, Feedback,
                         HeatmapAnnotation, PainZoneReport, PatientProfile,
                         PressureFrame, SensorData, User)
from core.views import _build_matrix_from_pressure, _calculate_frame_metrics


class Command(BaseCommand):
    help = "Seed many clinicians, patients, assignments, and pressure data for legacy UI testing."

    def add_arguments(self, parser):
        parser.add_argument("--clinicians", type=int, default=18)
        parser.add_argument("--patients", type=int, default=120)
        parser.add_argument("--frames-per-patient", type=int, default=70)
        parser.add_argument("--comments-per-patient", type=int, default=4)
        parser.add_argument("--feedback-per-patient", type=int, default=2)
        parser.add_argument("--days-window", type=int, default=21)
        parser.add_argument("--password", type=str, default="test123")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument(
            "--include-existing-patients",
            action="store_true",
            help="Also generate data for existing patient users outside patient_bulk_ prefix.",
        )

    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        now = timezone.now()

        clinician_count = max(1, int(options["clinicians"]))
        patient_count = max(1, int(options["patients"]))
        frames_per_patient = max(1, int(options["frames_per_patient"]))
        comments_per_patient = max(0, int(options["comments_per_patient"]))
        feedback_per_patient = max(0, int(options["feedback_per_patient"]))
        days_window = max(1, int(options["days_window"]))
        password = options["password"]
        include_existing = bool(options["include_existing_patients"])

        first_names = [
            "Alex", "Jordan", "Taylor", "Sam", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Parker",
            "Quinn", "Skyler", "Hayden", "Rowan", "Drew", "Cameron", "Kai", "Reese", "Logan", "Noel",
        ]
        last_names = [
            "Green", "Patel", "Brown", "Khan", "Silva", "Carter", "Wright", "Clark", "Adams", "Nguyen",
            "Taylor", "Brooks", "Morgan", "Bell", "Diaz", "Ali", "Scott", "Evans", "Hall", "Young",
        ]

        comment_templates = [
            "I shifted left because pressure felt high near the tailbone.",
            "Transferred from wheelchair and saw a short pressure spike.",
            "Adjusted cushion and pressure looked lower afterward.",
            "Sat upright for a while and then leaned forward briefly.",
            "Reported discomfort in lower back during this period.",
            "Posture changed after rest break; pressure pattern improved.",
        ]

        feedback_templates = [
            "Readings look consistent with how I felt during the session.",
            "This spike corresponds with a transfer movement.",
            "Contact area changed after I adjusted my sitting position.",
            "Values seem stable for most of the session.",
            "Pressure warning matched discomfort on the right side.",
        ]

        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={
                "role": User.ROLE_ADMIN,
                "email": "admin@sensore.local",
                "is_staff": True,
                "is_superuser": True,
            },
        )
        admin_user.role = User.ROLE_ADMIN
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.email = admin_user.email or "admin@sensore.local"
        admin_user.set_password(password)
        admin_user.save()

        created_clinicians = self._ensure_clinicians(
            clinician_count=clinician_count,
            password=password,
            first_names=first_names,
            last_names=last_names,
        )
        created_patients = self._ensure_patients(
            patient_count=patient_count,
            password=password,
            first_names=first_names,
            last_names=last_names,
        )

        clinicians = list(User.objects.filter(username__startswith="clinician_bulk_").order_by("username"))
        patients = list(User.objects.filter(username__startswith="patient_bulk_").order_by("username"))

        if include_existing:
            existing_patients = User.objects.filter(role=User.ROLE_PATIENT).exclude(username__startswith="patient_bulk_")
            patients.extend(list(existing_patients))

        created_assignments = self._ensure_assignments(clinicians, patients, rng)

        stats = {
            "sensor_rows": 0,
            "pressure_frames": 0,
            "comments": 0,
            "feedback": 0,
            "pain_reports": 0,
            "annotations": 0,
            "patients_seeded": 0,
            "patients_skipped": 0,
        }

        for index, patient in enumerate(patients, start=1):
            existing_sensor_count = SensorData.objects.filter(user=patient).count()
            if existing_sensor_count >= frames_per_patient:
                stats["patients_skipped"] += 1
                continue

            self._seed_patient_timeseries(
                patient=patient,
                frames_per_patient=frames_per_patient,
                days_window=days_window,
                now=now,
                rng=rng,
                stats=stats,
            )
            self._seed_patient_comments_feedback(
                patient=patient,
                comments_per_patient=comments_per_patient,
                feedback_per_patient=feedback_per_patient,
                comment_templates=comment_templates,
                feedback_templates=feedback_templates,
                reviewer=admin_user,
                rng=rng,
                stats=stats,
            )
            self._seed_patient_reports(
                patient=patient,
                rng=rng,
                stats=stats,
            )

            stats["patients_seeded"] += 1

            if index % 20 == 0:
                self.stdout.write(f"Seeded progress: {index}/{len(patients)} patients")

        self.stdout.write(self.style.SUCCESS("Mass test data seed complete."))
        self.stdout.write(
            " | ".join(
                [
                    f"new clinicians={created_clinicians}",
                    f"new patients={created_patients}",
                    f"new assignments={created_assignments}",
                    f"patients seeded={stats['patients_seeded']}",
                    f"patients skipped={stats['patients_skipped']}",
                    f"sensor rows={stats['sensor_rows']}",
                    f"pressure frames={stats['pressure_frames']}",
                    f"comments={stats['comments']}",
                    f"feedback={stats['feedback']}",
                    f"pain reports={stats['pain_reports']}",
                    f"annotations={stats['annotations']}",
                ]
            )
        )
        self.stdout.write(
            f"Login password for generated users: {password} (usernames start with clinician_bulk_ / patient_bulk_)"
        )

    def _ensure_clinicians(self, clinician_count, password, first_names, last_names):
        usernames = [f"clinician_bulk_{idx:03d}" for idx in range(1, clinician_count + 1)]
        existing = set(User.objects.filter(username__in=usernames).values_list("username", flat=True))

        to_create = []
        for idx, username in enumerate(usernames, start=1):
            if username in existing:
                continue
            first = first_names[(idx - 1) % len(first_names)]
            last = last_names[(idx * 2 - 1) % len(last_names)]
            to_create.append(
                User(
                    username=username,
                    first_name=first,
                    last_name=last,
                    email=f"{username}@sensore.local",
                    role=User.ROLE_CLINICIAN,
                    password=make_password(password),
                )
            )

        if to_create:
            User.objects.bulk_create(to_create, batch_size=200)

        clinicians = list(User.objects.filter(username__in=usernames))
        existing_profile_ids = set(
            ClinicianProfile.objects.filter(user__in=clinicians).values_list("user_id", flat=True)
        )
        profiles = [ClinicianProfile(user=user) for user in clinicians if user.id not in existing_profile_ids]
        if profiles:
            ClinicianProfile.objects.bulk_create(profiles, batch_size=200)

        return len(to_create)

    def _ensure_patients(self, patient_count, password, first_names, last_names):
        usernames = [f"patient_bulk_{idx:04d}" for idx in range(1, patient_count + 1)]
        existing = set(User.objects.filter(username__in=usernames).values_list("username", flat=True))

        to_create = []
        for idx, username in enumerate(usernames, start=1):
            if username in existing:
                continue
            first = first_names[(idx * 3 - 1) % len(first_names)]
            last = last_names[(idx * 5 - 1) % len(last_names)]
            to_create.append(
                User(
                    username=username,
                    first_name=first,
                    last_name=last,
                    email=f"{username}@sensore.local",
                    role=User.ROLE_PATIENT,
                    password=make_password(password),
                )
            )

        if to_create:
            User.objects.bulk_create(to_create, batch_size=300)

        patients = list(User.objects.filter(username__in=usernames))
        existing_profile_ids = set(
            PatientProfile.objects.filter(user__in=patients).values_list("user_id", flat=True)
        )
        profiles = [PatientProfile(user=user) for user in patients if user.id not in existing_profile_ids]
        if profiles:
            PatientProfile.objects.bulk_create(profiles, batch_size=300)

        return len(to_create)

    def _ensure_assignments(self, clinicians, patients, rng):
        if not clinicians or not patients:
            return 0

        existing_patient_ids = set(
            ClinicianPatientAssignment.objects.filter(patient__in=patients).values_list("patient_id", flat=True)
        )
        to_create = []
        for patient in patients:
            if patient.id in existing_patient_ids:
                continue
            clinician = clinicians[rng.randrange(len(clinicians))]
            to_create.append(
                ClinicianPatientAssignment(
                    clinician=clinician,
                    patient=patient,
                    assigned_at=timezone.now() - timedelta(days=rng.randint(1, 120)),
                )
            )

        if to_create:
            ClinicianPatientAssignment.objects.bulk_create(to_create, batch_size=400)

        return len(to_create)

    def _seed_patient_timeseries(self, patient, frames_per_patient, days_window, now, rng, stats):
        base_pressure = rng.randint(1400, 2300)
        start = now - timedelta(days=days_window, minutes=rng.randint(0, 720))
        step_minutes = max(4, int((days_window * 24 * 60) / max(frames_per_patient, 1)))

        sensor_rows = []
        frame_rows = []

        for i in range(frames_per_patient):
            timestamp = start + timedelta(minutes=(i * step_minutes) + rng.randint(0, 3))
            wave = int(420 * (1 + math.sin((i + rng.randint(0, 9)) / 5.0)) / 2)
            spike = rng.randint(450, 1050) if rng.random() < 0.16 else 0
            pressure = max(650, min(4095, base_pressure + wave + spike + rng.randint(-150, 150)))

            matrix = _build_matrix_from_pressure(pressure)
            metrics = _calculate_frame_metrics(matrix)

            sensor_rows.append(
                SensorData(
                    user=patient,
                    timestamp=timestamp,
                    pressure_value=pressure,
                    sensor_id=f"SENSOR_{patient.username}",
                    location="seat-mat",
                )
            )
            frame_rows.append(
                PressureFrame(
                    user=patient,
                    timestamp=timestamp,
                    raw_matrix=matrix,
                    peak_pressure_index=metrics["peak_pressure_index"],
                    contact_area_percentage=metrics["contact_area_percentage"],
                    high_pressure_flag=metrics["high_pressure_flag"],
                )
            )

        SensorData.objects.bulk_create(sensor_rows, batch_size=700)
        PressureFrame.objects.bulk_create(frame_rows, batch_size=300)

        stats["sensor_rows"] += len(sensor_rows)
        stats["pressure_frames"] += len(frame_rows)

    def _seed_patient_comments_feedback(
        self,
        patient,
        comments_per_patient,
        feedback_per_patient,
        comment_templates,
        feedback_templates,
        reviewer,
        rng,
        stats,
    ):
        if comments_per_patient > 0:
            recent_frames = list(
                PressureFrame.objects.filter(user=patient).order_by("-timestamp")[: max(6, comments_per_patient + 2)]
            )
            comments = []
            for i in range(min(comments_per_patient, len(recent_frames))):
                frame = recent_frames[i]
                text = comment_templates[(i + rng.randint(0, len(comment_templates) - 1)) % len(comment_templates)]
                comments.append(
                    Comment(
                        user=patient,
                        pressure_frame=frame,
                        timestamp=frame.timestamp,
                        text=text,
                    )
                )
            if comments:
                Comment.objects.bulk_create(comments, batch_size=400)
                stats["comments"] += len(comments)

        if feedback_per_patient > 0:
            recent_sensor = list(
                SensorData.objects.filter(user=patient).order_by("-timestamp")[: max(6, feedback_per_patient + 2)]
            )
            feedback_rows = []
            for i in range(min(feedback_per_patient, len(recent_sensor))):
                sensor_data = recent_sensor[i]
                status_roll = rng.random()
                if status_roll < 0.6:
                    status = Feedback.STATUS_PENDING
                    reviewed_by = None
                    reviewed_at = None
                    admin_notes = ""
                elif status_roll < 0.85:
                    status = Feedback.STATUS_REVIEWED
                    reviewed_by = reviewer
                    reviewed_at = timezone.now() - timedelta(days=rng.randint(0, 20))
                    admin_notes = "Reviewed by QA clinician."
                else:
                    status = Feedback.STATUS_RESOLVED
                    reviewed_by = reviewer
                    reviewed_at = timezone.now() - timedelta(days=rng.randint(0, 20))
                    admin_notes = "Resolved after posture/cushion guidance."

                comment = feedback_templates[(i + rng.randint(0, len(feedback_templates) - 1)) % len(feedback_templates)]
                feedback_rows.append(
                    Feedback(
                        user=patient,
                        sensor_data=sensor_data,
                        comment=comment,
                        status=status,
                        reviewed_by=reviewed_by,
                        reviewed_at=reviewed_at,
                        admin_notes=admin_notes,
                        created_at=sensor_data.timestamp + timedelta(minutes=5),
                    )
                )

            if feedback_rows:
                Feedback.objects.bulk_create(feedback_rows, batch_size=300)
                stats["feedback"] += len(feedback_rows)

    def _seed_patient_reports(self, patient, rng, stats):
        zones = rng.sample(PREDEFINED_ZONES, rng.randint(1, 3))
        PainZoneReport.objects.create(
            user=patient,
            zones=zones,
            note="Auto-generated for bulk legacy QA testing.",
        )
        stats["pain_reports"] += 1

        cells = []
        seen = set()
        for _ in range(rng.randint(5, 16)):
            cell = (rng.randint(9, 25), rng.randint(8, 24))
            if cell in seen:
                continue
            seen.add(cell)
            cells.append([cell[0], cell[1]])

        HeatmapAnnotation.objects.create(
            user=patient,
            cells=cells,
            note="Bulk annotation for clinician review.",
        )
        stats["annotations"] += 1

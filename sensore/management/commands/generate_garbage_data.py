"""
Generate high-volume synthetic/noisy data for testing and preview.

This intentionally creates a messy mix of sessions, frames, comments, and alerts
so the dashboards can be stress-tested with larger datasets.
"""
import json
import math
import random
import string
from datetime import date, datetime, timedelta

import numpy as np
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserProfile
from sensore.models import Comment, SensorFrame, SensorSession
from sensore.utils import analyse_session_frames

User = get_user_model()

FIRST_NAMES = [
    'Alex', 'Jamie', 'Casey', 'Jordan', 'Morgan', 'Taylor', 'Riley', 'Avery',
    'Chris', 'Robin', 'Skyler', 'Quinn', 'Reese', 'Drew', 'Elliot', 'Kai',
    'Sasha', 'Blake', 'Parker', 'Rowan', 'Noel', 'Sam', 'Charlie', 'Hayden',
]

LAST_NAMES = [
    'Stone', 'Nguyen', 'Patel', 'Kim', 'Silva', 'Lopez', 'Brown', 'Clark',
    'Singh', 'Garcia', 'Walker', 'Wright', 'Khan', 'Baker', 'Torres', 'Young',
    'White', 'Hall', 'Allen', 'King', 'Scott', 'Green', 'Adams', 'Rivera',
]

COMMENT_TEMPLATES = [
    'Shifted weight suddenly around this moment.',
    'Leaning left to reach something.',
    'Tried to reposition but still uncomfortable.',
    'Felt numbness for a short period.',
    'Quick movement caused a weird spike.',
    'Possible sensor artifact; please review.',
    'Posture change after reminder alert.',
]

NOTE_TEMPLATES = [
    'Noisy import for UI stress test.',
    'Sensor drift suspected ???',
    'Preview-only batch: random posture artifacts.',
    'Synthetic replay with random spikes.',
    'Intentional garbage data for chart preview and QA.',
    'Long run data; may include outlier frames and odd transitions.',
]


class Command(BaseCommand):
    help = 'Generate high-volume synthetic/noisy data for testing and preview.'

    def add_arguments(self, parser):
        parser.add_argument('--patients', type=int, default=12)
        parser.add_argument('--sessions', type=int, default=6)
        parser.add_argument('--frames', type=int, default=90)
        parser.add_argument('--comments', type=int, default=4)
        parser.add_argument('--clinicians', type=int, default=3)
        parser.add_argument('--days-back', type=int, default=120)
        parser.add_argument('--seed', type=int, default=None)
        parser.add_argument('--batch-tag', default='')
        parser.add_argument('--patient-prefix', default='junk_patient')
        parser.add_argument('--clinician-prefix', default='junk_clin')
        parser.add_argument('--patient-password', default='patient123')
        parser.add_argument('--clinician-password', default='clinic123')

    def handle(self, *args, **options):
        if options['seed'] is not None:
            random.seed(options['seed'])
            np.random.seed(options['seed'])

        patients = max(1, options['patients'])
        sessions_per_patient = max(1, options['sessions'])
        frames_per_session = max(1, options['frames'])
        comments_per_session = max(0, options['comments'])
        clinicians_count = max(1, options['clinicians'])
        days_back = max(1, options['days_back'])
        batch_tag = options['batch_tag'].strip() or timezone.now().strftime('%Y%m%d%H%M%S')

        self.stdout.write(
            f'Generating batch {batch_tag}: {patients} patients x {sessions_per_patient} sessions x {frames_per_session} frames'
        )

        clinicians = self._ensure_clinicians(clinicians_count, batch_tag, options['clinician_prefix'], options['clinician_password'])

        created_patients = 0
        created_sessions = 0
        created_frames = 0
        created_comments = 0
        created_alerts = 0
        analysed_frames = 0

        for patient_index in range(1, patients + 1):
            patient = self._create_patient(patient_index, batch_tag, options['patient_prefix'], clinicians, options['patient_password'])
            created_patients += 1

            for _ in range(sessions_per_patient):
                session = self._create_session(patient, days_back, frames_per_session)
                created_sessions += 1
                created_frames += self._generate_frames(session, session.start_time, frames_per_session)
                created_comments += self._add_comments(session, comments_per_session)
                analysed, alerts = self._analyse_session(session)
                analysed_frames += analysed
                created_alerts += alerts

            if patient_index % 5 == 0 or patient_index == patients:
                self.stdout.write(f'  ...generated {patient_index}/{patients} patients')

        self.stdout.write(self.style.SUCCESS('\nBulk garbage data generation complete.'))
        self.stdout.write(f'Batch tag:           {batch_tag}')
        self.stdout.write(f'Patients created:    {created_patients}')
        self.stdout.write(f'Sessions created:    {created_sessions}')
        self.stdout.write(f'Frames created:      {created_frames}')
        self.stdout.write(f'Comments created:    {created_comments}')
        self.stdout.write(f'Frames analysed:     {analysed_frames}')
        self.stdout.write(f'Alerts generated:    {created_alerts}')
        self.stdout.write('')
        self.stdout.write('Sample login credentials:')
        self.stdout.write(f"  Patients:   {options['patient_password']}")
        self.stdout.write(f"  Clinicians: {options['clinician_password']}")

    def _ensure_clinicians(self, count, batch_tag, prefix, password):
        clinicians = []
        for idx in range(1, count + 1):
            username = self._unique_username(f'{prefix}_{batch_tag}_{idx:03d}')
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@sensore.test',
                },
            )
            user.set_password(password)
            user.save(update_fields=['password'])

            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.role = 'clinician'
            profile.save(update_fields=['role'])
            clinicians.append(user)

        return clinicians

    def _create_patient(self, index, batch_tag, prefix, clinicians, password):
        username = self._unique_username(f'{prefix}_{batch_tag}_{index:04d}')
        patient = User.objects.create_user(
            username=username,
            first_name=random.choice(FIRST_NAMES),
            last_name=random.choice(LAST_NAMES),
            email=f'{username}@sensore.test',
            password=password,
        )

        profile, _ = UserProfile.objects.get_or_create(user=patient)
        profile.role = 'patient'
        profile.patient_id = self._unique_patient_id(f'JUNK-{batch_tag}-{index:04d}')
        profile.date_of_birth = date(random.randint(1940, 2010), random.randint(1, 12), random.randint(1, 28))
        profile.assigned_clinician = random.choice(clinicians)
        profile.medical_notes = random.choice(NOTE_TEMPLATES)
        profile.save()
        return patient

    def _create_session(self, patient, days_back, frames_per_session):
        session_date = date.today() - timedelta(days=random.randint(0, days_back))
        start_dt = timezone.make_aware(
            datetime(
                session_date.year,
                session_date.month,
                session_date.day,
                random.randint(6, 21),
                random.choice([0, 10, 20, 30, 40, 50]),
                0,
            )
        )
        end_dt = start_dt + timedelta(seconds=frames_per_session * 30)
        return SensorSession.objects.create(
            patient=patient,
            session_date=session_date,
            start_time=start_dt,
            end_time=end_dt,
            notes=f'{random.choice(NOTE_TEMPLATES)} [{self._random_token(6)}]',
        )

    def _generate_frames(self, session, start_time, num_frames):
        pattern_kind = random.choice(['balanced', 'left_lean', 'right_lean', 'forward_lean', 'garbage'])
        base = self._generate_pattern(pattern_kind)
        frames = []

        for frame_index in range(num_frames):
            frame_time = start_time + timedelta(seconds=frame_index * 30)
            frame_data = self._vary_frame(base, pattern_kind)

            if random.random() < 0.03:
                frame_data = np.random.randint(0, 4096, size=(32, 32)).astype(np.float32)

            flat = np.clip(frame_data, 0, 4095).astype(int).flatten().tolist()
            frames.append(
                SensorFrame(
                    session=session,
                    timestamp=frame_time,
                    frame_index=frame_index,
                    data=json.dumps(flat),
                )
            )

        SensorFrame.objects.bulk_create(frames, batch_size=500)
        return len(frames)

    def _analyse_session(self, session):
        return analyse_session_frames(session, create_alerts=True)

    def _add_comments(self, session, comments_per_session):
        if comments_per_session <= 0:
            return 0

        frames = list(session.frames.order_by('frame_index'))
        if not frames:
            return 0

        total_comments = random.randint(max(1, comments_per_session - 1), comments_per_session + 2)
        created = 0
        patient = session.patient
        clinician = getattr(patient.profile, 'assigned_clinician', None)

        for _ in range(total_comments):
            frame = random.choice(frames)
            parent = Comment.objects.create(
                session=session,
                author=patient,
                author_type='patient',
                frame=frame,
                timestamp_reference=frame.timestamp,
                text=random.choice(COMMENT_TEMPLATES),
            )
            created += 1

            if clinician and random.random() < 0.35:
                Comment.objects.create(
                    session=session,
                    author=clinician,
                    author_type='clinician',
                    frame=frame,
                    timestamp_reference=frame.timestamp,
                    text=f'Clinician follow-up: {random.choice(COMMENT_TEMPLATES)}',
                    is_reply=True,
                    reply_to=parent,
                )
                created += 1

        return created

    def _generate_pattern(self, kind):
        if kind == 'garbage':
            grid = np.random.gamma(shape=2.0, scale=400.0, size=(32, 32)).astype(np.float32)
            for _ in range(random.randint(3, 7)):
                cx, cy = random.randint(0, 31), random.randint(0, 31)
                peak = random.uniform(2200, 4095)
                spread = random.uniform(1.2, 5.0)
                for y in range(32):
                    for x in range(32):
                        d2 = (x - cx) ** 2 + (y - cy) ** 2
                        grid[y][x] += peak * math.exp(-d2 / (2 * spread * spread))
            return np.clip(grid, 1, 4095)

        left_weight = 1.0
        right_weight = 1.0
        top_weight = 1.0

        if kind == 'left_lean':
            left_weight = 1.35
            right_weight = 0.75
        elif kind == 'right_lean':
            left_weight = 0.75
            right_weight = 1.35
        elif kind == 'forward_lean':
            top_weight = 1.4

        grid = np.ones((32, 32), dtype=np.float32)
        left_center = (10, 18)
        right_center = (22, 18)

        for y in range(32):
            for x in range(32):
                d_left = math.sqrt((x - left_center[0]) ** 2 + (y - left_center[1]) ** 2)
                d_right = math.sqrt((x - right_center[0]) ** 2 + (y - right_center[1]) ** 2)
                left_val = max(0, (3200 - d_left * 270) * left_weight)
                right_val = max(0, (3000 - d_right * 270) * right_weight)
                thigh = 0
                if y < 15:
                    thigh = max(0, 900 - abs(x - 16) * 90)
                    thigh *= top_weight
                value = max(left_val, right_val, thigh)
                grid[y][x] = max(1, value + random.gauss(0, 60))

        return np.clip(grid, 1, 4095)

    def _vary_frame(self, base, kind):
        if kind == 'garbage':
            variation = random.uniform(0.35, 1.75)
            noise_scale = 180
            shift_x = random.randint(-5, 5)
            shift_y = random.randint(-4, 4)
        else:
            variation = random.uniform(0.65, 1.35)
            noise_scale = 90
            shift_x = random.randint(-2, 2)
            shift_y = random.randint(-1, 1)

        varied = base * variation + np.random.normal(0, noise_scale, base.shape)
        if shift_x or shift_y:
            varied = np.roll(varied, shift_x, axis=1)
            varied = np.roll(varied, shift_y, axis=0)
        return np.clip(varied, 1, 4095)

    def _unique_username(self, base):
        username = base
        while User.objects.filter(username=username).exists():
            username = f'{base}_{self._random_token(4)}'
        return username

    def _unique_patient_id(self, base):
        patient_id = base
        while UserProfile.objects.filter(patient_id=patient_id).exists():
            patient_id = f'{base}-{self._random_token(3).upper()}'
        return patient_id

    def _random_token(self, length):
        alphabet = string.ascii_lowercase + string.digits
        return ''.join(random.choice(alphabet) for _ in range(length))

import csv
import io
import json
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from accounts.models import UserProfile

from .models import (Comment, PressureAlert, PressureMetrics, Report,
                     SensorFrame, SensorSession)
from .utils import (analyse_session_frames, generate_session_report_data,
                    get_risk_level)

User = get_user_model()

PAIN_ZONE_CHOICES = [
    ('lower_back', 'Lower Back'),
    ('left_hip', 'Left Hip'),
    ('right_hip', 'Right Hip'),
    ('left_thigh', 'Left Thigh'),
    ('right_thigh', 'Right Thigh'),
    ('tailbone', 'Tailbone'),
    ('left_shoulder', 'Left Shoulder'),
    ('right_shoulder', 'Right Shoulder'),
]


def ensure_user_profile(user):
    """Ensure every authenticated user has a profile."""
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if not profile.role:
        profile.role = 'admin' if (user.is_staff or user.is_superuser) else 'patient'
        profile.save(update_fields=['role'])
    return profile


def get_user_role(user):
    if not user or not user.is_authenticated:
        return 'patient'
    return ensure_user_profile(user).role


def get_accessible_patients(user):
    """Return patient queryset visible to the current user."""
    role = get_user_role(user)
    if role == 'admin':
        return User.objects.filter(profile__role='patient').select_related('profile')
    if role == 'clinician':
        return User.objects.filter(
            profile__role='patient',
            profile__assigned_clinician=user,
        ).select_related('profile')
    return User.objects.filter(id=user.id)


def user_can_access_patient(user, patient):
    role = get_user_role(user)
    if role == 'admin':
        return True
    if role == 'patient':
        return patient.id == user.id
    if role == 'clinician':
        return UserProfile.objects.filter(
            user=patient,
            role='patient',
            assigned_clinician=user,
        ).exists()
    return False


def user_can_access_session(user, session):
    return user_can_access_patient(user, session.patient)


def serialise_metrics(metrics):
    return {
        'ppi': metrics.peak_pressure_index,
        'contact_area': metrics.contact_area_percent,
        'avg_pressure': metrics.average_pressure,
        'asymmetry': metrics.asymmetry_score,
        'pressure_variability': metrics.pressure_variability,
        'pressure_concentration': metrics.pressure_concentration,
        'movement_index': metrics.movement_index,
        'sustained_load_index': metrics.sustained_load_index,
        'center_of_pressure_x': metrics.center_of_pressure_x,
        'center_of_pressure_y': metrics.center_of_pressure_y,
        'risk_score': metrics.risk_score,
        'risk_level': metrics.risk_level,
        'hot_zones': metrics.get_hot_zones(),
        'plain_english': metrics.plain_english,
    }


def serialise_comment(comment_obj):
    replies = Comment.objects.filter(reply_to=comment_obj).order_by('created_at')
    return {
        'id': comment_obj.id,
        'author': comment_obj.author.get_full_name() or comment_obj.author.username,
        'author_type': comment_obj.author_type,
        'text': comment_obj.text,
        'timestamp': comment_obj.timestamp_reference.isoformat(),
        'created_at': comment_obj.created_at.isoformat(),
        'frame_id': comment_obj.frame_id,
        'metadata': comment_obj.metadata or {},
        'replies': [
            {
                'id': reply.id,
                'author': reply.author.get_full_name() or reply.author.username,
                'author_type': reply.author_type,
                'text': reply.text,
                'created_at': reply.created_at.isoformat(),
                'metadata': reply.metadata or {},
            }
            for reply in replies
        ],
    }


def parse_time_view_hours(raw_value):
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError):
        return 1
    return value if value in (1, 6, 24) else 1


@login_required
def dashboard(request):
    role = get_user_role(request.user)
    if role == 'clinician' or role == 'admin':
        return redirect('clinician_dashboard')
    return redirect('patient_dashboard')


# ─── PATIENT VIEWS ────────────────────────────────────────────────────────────

@login_required
def patient_dashboard(request):
    """Main patient dashboard with heatmap, metrics, and comments."""
    user = request.user
    role = get_user_role(user)
    if role in ('clinician', 'admin'):
        return redirect('clinician_dashboard')

    sessions = SensorSession.objects.filter(patient=user).order_by('-session_date', '-start_time')
    latest_session = sessions.first()

    selected_session_id = request.GET.get('session_id')
    if selected_session_id:
        selected_session = get_object_or_404(SensorSession, id=selected_session_id, patient=user)
    else:
        selected_session = latest_session

    alerts = PressureAlert.objects.filter(session__patient=user, acknowledged=False).order_by('-created_at')[:5]

    selected_time_view = request.GET.get('view', '1')
    if selected_time_view not in {'1', '6', '24'}:
        selected_time_view = '1'

    recent_pain_notes = Comment.objects.filter(
        session__patient=user,
        metadata__pain_zones__isnull=False,
    ).order_by('-created_at')[:8]

    context = {
        'sessions': sessions[:10],
        'selected_session': selected_session,
        'alerts': alerts,
        'role': 'patient',
        'selected_time_view': selected_time_view,
        'pain_zone_choices': PAIN_ZONE_CHOICES,
        'recent_pain_notes': recent_pain_notes,
    }
    return render(request, 'sensore/patient_dashboard.html', context)


@login_required
def clinician_dashboard(request):
    """Clinician dashboard showing all patient data and risk summaries."""
    role = get_user_role(request.user)
    if role not in ('clinician', 'admin'):
        return redirect('patient_dashboard')

    patient_users = get_accessible_patients(request.user)

    patient_summaries = []
    for patient in patient_users:
        latest_session = SensorSession.objects.filter(patient=patient).order_by('-start_time').first()
        unack_alerts = PressureAlert.objects.filter(session__patient=patient, acknowledged=False).count()
        comments_count = Comment.objects.filter(session__patient=patient).count()
        latest_risk = 'unknown'
        avg_risk = 0.0
        risk_trend = 'stable'
        predicted_hotspots = []
        previous_avg_risk = None
        if latest_session:
            report_data = generate_session_report_data(latest_session)
            avg_risk = report_data.get('avg_risk_score', 0.0)
            risk_trend = report_data.get('risk_trend', 'stable')
            predicted_hotspots = report_data.get('predicted_hotspots', [])
            latest_frame = latest_session.frames.order_by('-timestamp').first()
            if latest_frame and hasattr(latest_frame, 'metrics'):
                latest_risk = latest_frame.metrics.risk_level

            previous_session = SensorSession.objects.filter(patient=patient).exclude(
                id=latest_session.id
            ).order_by('-start_time').first()
            if previous_session:
                previous_data = generate_session_report_data(previous_session)
                previous_avg_risk = previous_data.get('avg_risk_score')

        patient_summaries.append({
            'user': patient,
            'latest_session': latest_session,
            'unack_alerts': unack_alerts,
            'latest_risk': latest_risk,
            'avg_risk': avg_risk,
            'risk_trend': risk_trend,
            'predicted_hotspots': predicted_hotspots,
            'comments_count': comments_count,
            'previous_avg_risk': previous_avg_risk,
        })

    all_alerts = PressureAlert.objects.filter(
        session__patient__in=patient_users,
        acknowledged=False,
    ).order_by('-created_at')[:20]

    comment_stream = Comment.objects.filter(
        session__patient__in=patient_users,
        is_reply=False,
    ).select_related('author', 'session__patient').order_by('-created_at')[:25]

    context = {
        'patient_summaries': patient_summaries,
        'all_alerts': all_alerts,
        'comment_stream': comment_stream,
        'role': role,
    }
    return render(request, 'sensore/clinician_dashboard.html', context)


# ─── API ENDPOINTS ─────────────────────────────────────────────────────────────

@login_required
@require_GET
def api_session_frames(request, session_id):
    """Return all frames for a session with metrics."""
    session = get_object_or_404(SensorSession, id=session_id)

    if not user_can_access_session(request.user, session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    has_metrics = PressureMetrics.objects.filter(frame__session=session).exists()
    if not has_metrics:
        analyse_session_frames(session, create_alerts=True)

    hours = parse_time_view_hours(request.GET.get('hours', 1))
    latest_frame = session.frames.order_by('-timestamp').first()
    cutoff = None
    if latest_frame:
        cutoff = latest_frame.timestamp - timedelta(hours=hours)

    frames_qs = session.frames.select_related('metrics').order_by('frame_index')
    if cutoff is not None:
        frames_qs = frames_qs.filter(timestamp__gte=cutoff)

    frames_data = []
    for frame in frames_qs[:1200]:
        frame_dict = {
            'id': frame.id,
            'frame_index': frame.frame_index,
            'timestamp': frame.timestamp.isoformat(),
            'data': json.loads(frame.data),
        }
        if hasattr(frame, 'metrics'):
            frame_dict['metrics'] = serialise_metrics(frame.metrics)
        frames_data.append(frame_dict)

    return JsonResponse({
        'frames': frames_data,
        'session_id': session_id,
        'time_view_hours': hours,
        'total_frames_in_session': session.frame_count,
    })


@login_required
@require_GET
def api_latest_frame(request, session_id):
    """Return the latest frame with full metrics."""
    session = get_object_or_404(SensorSession, id=session_id)
    if not user_can_access_session(request.user, session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    frame = session.frames.order_by('-frame_index').first()
    if not frame:
        return JsonResponse({'error': 'No frames'}, status=404)

    if not hasattr(frame, 'metrics'):
        analyse_session_frames(session, create_alerts=True)
        frame.refresh_from_db()

    data = {
        'id': frame.id,
        'frame_index': frame.frame_index,
        'timestamp': frame.timestamp.isoformat(),
        'data': json.loads(frame.data),
    }
    if hasattr(frame, 'metrics'):
        data['metrics'] = serialise_metrics(frame.metrics)
    return JsonResponse(data)


@login_required
@require_GET
def api_frame_detail(request, frame_id):
    """Return a specific frame with full metrics."""
    frame = get_object_or_404(SensorFrame, id=frame_id)
    session = frame.session

    if not user_can_access_session(request.user, session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    data = {
        'id': frame.id,
        'frame_index': frame.frame_index,
        'timestamp': frame.timestamp.isoformat(),
        'data': json.loads(frame.data),
    }
    if hasattr(frame, 'metrics'):
        data['metrics'] = serialise_metrics(frame.metrics)
    return JsonResponse(data)


@login_required
@require_GET
def api_session_metrics_timeline(request, session_id):
    """Return timeline of metrics for charts."""
    session = get_object_or_404(SensorSession, id=session_id)
    if not user_can_access_session(request.user, session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    has_metrics = PressureMetrics.objects.filter(frame__session=session).exists()
    if not has_metrics:
        analyse_session_frames(session, create_alerts=True)

    report_data = generate_session_report_data(session)

    hours = parse_time_view_hours(request.GET.get('hours', 1))
    timeline = report_data.get('timeline', [])
    if timeline:
        last_time = datetime.fromisoformat(timeline[-1]['timestamp'])
        cutoff = last_time - timedelta(hours=hours)
        timeline = [
            point for point in timeline
            if datetime.fromisoformat(point['timestamp']) >= cutoff
        ]
        report_data['timeline'] = timeline
        report_data['time_view_hours'] = hours

    previous_session = SensorSession.objects.filter(patient=session.patient).exclude(
        id=session.id,
    ).order_by('-start_time').first()
    if previous_session:
        previous_data = generate_session_report_data(previous_session)
        report_data['comparison'] = {
            'previous_session_id': previous_session.id,
            'previous_date': str(previous_session.session_date),
            'previous_avg_risk': previous_data.get('avg_risk_score', 0),
            'risk_change': round(
                report_data.get('avg_risk_score', 0) - previous_data.get('avg_risk_score', 0),
                1,
            ),
            'previous_avg_ppi': previous_data.get('avg_ppi', 0),
        }

    return JsonResponse(report_data)


@login_required
def api_add_comment(request, session_id):
    """Add a comment to a session at a specific timestamp."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    session = get_object_or_404(SensorSession, id=session_id)

    if not user_can_access_session(request.user, session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        body = request.POST

    text = body.get('text', '').strip()
    frame_id = body.get('frame_id')
    timestamp_str = body.get('timestamp')
    pain_zones = body.get('pain_zones') or []
    pain_points = body.get('pain_points') or []
    if isinstance(pain_zones, str):
        pain_zones = [z.strip() for z in pain_zones.split(',') if z.strip()]

    if not isinstance(pain_points, list):
        pain_points = []

    source = (body.get('source') or 'dashboard').strip()[:60]

    if not text:
        return JsonResponse({'error': 'Comment text required'}, status=400)

    frame = None
    if frame_id:
        try:
            frame = SensorFrame.objects.get(id=frame_id, session=session)
        except SensorFrame.DoesNotExist:
            pass

    ref_time = timezone.now()
    if timestamp_str:
        try:
            ref_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if timezone.is_naive(ref_time):
                ref_time = timezone.make_aware(ref_time, timezone.get_current_timezone())
        except Exception:
            pass
    elif frame:
        ref_time = frame.timestamp

    if frame is None:
        frames = list(session.frames.order_by('timestamp')[:2000])
        if frames:
            frame = min(
                frames,
                key=lambda f: abs((f.timestamp - ref_time).total_seconds()),
            )

    allowed_zones = {z for z, _ in PAIN_ZONE_CHOICES}
    clean_zones = [z for z in pain_zones if isinstance(z, str) and z in allowed_zones][:8]

    clean_points = []
    for point in pain_points[:12]:
        if not isinstance(point, dict):
            continue
        try:
            x = int(point.get('x'))
            y = int(point.get('y'))
        except (TypeError, ValueError):
            continue
        if 0 <= x <= 31 and 0 <= y <= 31:
            clean_points.append({'x': x, 'y': y})

    role = get_user_role(request.user)
    comment_metadata = {
        'pain_zones': clean_zones,
        'pain_points': clean_points,
        'source': source,
        'time_view_hours': parse_time_view_hours(body.get('time_view')),
    }

    comment = Comment.objects.create(
        session=session,
        author=request.user,
        author_type=role if role in ('patient', 'clinician') else 'clinician',
        frame=frame,
        timestamp_reference=ref_time,
        text=text,
        metadata=comment_metadata,
    )

    return JsonResponse(serialise_comment(comment))


@login_required
@require_GET
def api_session_comments(request, session_id):
    """Return all comments for a session."""
    session = get_object_or_404(SensorSession, id=session_id)
    if not user_can_access_session(request.user, session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    comments = Comment.objects.filter(session=session, is_reply=False).select_related('author').order_by('created_at')
    data = [serialise_comment(comment) for comment in comments]
    return JsonResponse({'comments': data})


@login_required
def api_acknowledge_alert(request, alert_id):
    """Mark an alert as acknowledged."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    alert = get_object_or_404(PressureAlert, id=alert_id)
    if not user_can_access_session(request.user, alert.session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    if alert.acknowledged:
        return JsonResponse({'status': 'already_acknowledged'})

    alert.acknowledged = True
    alert.acknowledged_by = request.user
    alert.save(update_fields=['acknowledged', 'acknowledged_by'])
    remaining = PressureAlert.objects.filter(
        session__patient=alert.session.patient,
        acknowledged=False,
    ).count()
    return JsonResponse({'status': 'acknowledged', 'remaining_unacknowledged': remaining})


@login_required
def patient_report(request, patient_id=None):
    """View and generate a downloadable medical history report."""
    if patient_id:
        patient = get_object_or_404(User, id=patient_id)
        if not user_can_access_patient(request.user, patient):
            return HttpResponse('Forbidden', status=403)
    else:
        patient = request.user

    if not user_can_access_patient(request.user, patient):
        return HttpResponse('Forbidden', status=403)

    sessions = SensorSession.objects.filter(patient=patient).order_by('-session_date')

    filter_start = request.GET.get('start', '').strip()
    filter_end = request.GET.get('end', '').strip()
    selected_window = request.GET.get('window', 'all').strip().lower()

    def _parse_date(value):
        try:
            return datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    start_date = _parse_date(filter_start)
    end_date = _parse_date(filter_end)

    if selected_window in {'7d', '14d', '30d'}:
        days = int(selected_window.replace('d', ''))
        start_date = date.today() - timedelta(days=days)
        if not end_date:
            end_date = date.today()

    if start_date:
        sessions = sessions.filter(session_date__gte=start_date)
    if end_date:
        sessions = sessions.filter(session_date__lte=end_date)


    # Build per-session summaries
    session_summaries = []
    all_ppis, all_risks, all_areas = [], [], []
    total_high_risk = 0

    for session in sessions:
        report_data = generate_session_report_data(session)
        if report_data:
            session_summaries.append({
                'session': session,
                'data': report_data,
            })
            all_ppis.append(report_data.get('avg_ppi', 0))
            all_risks.append(report_data.get('avg_risk_score', 0))
            all_areas.append(report_data.get('avg_contact_area', 0))
            dist = report_data.get('risk_distribution', {})
            total_high_risk += dist.get('high', 0) + dist.get('critical', 0)

    avg_ppi = round(sum(all_ppis) / len(all_ppis), 1) if all_ppis else 0
    avg_risk = round(sum(all_risks) / len(all_risks), 1) if all_risks else 0
    avg_area = round(sum(all_areas) / len(all_areas), 1) if all_areas else 0

    # Downloadable PDF flag
    download = request.GET.get('download') == '1'

    context = {
        'patient': patient,
        'session_summaries': session_summaries,
        'avg_ppi': avg_ppi,
        'avg_risk': avg_risk,
        'avg_area': avg_area,
        'total_high_risk': total_high_risk,
        'overall_risk_level': get_risk_level(avg_risk),
        'generated_at': timezone.now(),
        'download': download,
        'filter_start': start_date.isoformat() if start_date else '',
        'filter_end': end_date.isoformat() if end_date else '',
        'selected_window': selected_window,
    }

    if request.GET.get('format') == 'csv' or request.GET.get('download_csv') == '1':
        return generate_csv_report(context)

    if download:
        return generate_pdf_report(context)

    return render(request, 'sensore/report.html', context)


def generate_pdf_report(context):
    """Generate a PDF report using reportlab."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm, mm
        from reportlab.platypus import (HRFlowable, Paragraph,
                                        SimpleDocTemplate, Spacer, Table,
                                        TableStyle)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                                leftMargin=2*cm, rightMargin=2*cm)

        patient = context['patient']
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle('Title', fontName='Helvetica-Bold', fontSize=20,
                                     spaceAfter=6, textColor=colors.HexColor('#0a1628'))
        subtitle_style = ParagraphStyle('Subtitle', fontName='Helvetica', fontSize=11,
                                        spaceAfter=3, textColor=colors.HexColor('#5a7a9a'))
        body_style = ParagraphStyle('Body', fontName='Helvetica', fontSize=10, spaceAfter=4)
        heading_style = ParagraphStyle('Heading', fontName='Helvetica-Bold', fontSize=13,
                                       spaceBefore=12, spaceAfter=6, textColor=colors.HexColor('#1a3a5c'))

        story.append(Paragraph("SENSORE — Pressure Mapping Report", title_style))
        story.append(Paragraph(f"Graphene Trace Medical Platform", subtitle_style))
        story.append(Paragraph(f"Generated: {context['generated_at'].strftime('%d %B %Y, %H:%M UTC')}", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#00d4c8')))
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("Patient Information", heading_style))
        patient_data = [
            ['Name:', patient.get_full_name() or patient.username],
            ['Username:', patient.username],
            ['Email:', patient.email or 'N/A'],
        ]
        try:
            profile = patient.profile
            if profile.patient_id:
                patient_data.append(['Patient ID:', profile.patient_id])
            if profile.date_of_birth:
                patient_data.append(['Date of Birth:', str(profile.date_of_birth)])
        except Exception:
            pass
        pt = Table(patient_data, colWidths=[4*cm, 12*cm])
        pt.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1a3a5c')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(pt)
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("Summary Metrics", heading_style))
        risk_color = {'low': '#22c55e', 'moderate': '#f59e0b', 'high': '#ef4444', 'critical': '#7c3aed'}
        rl = context['overall_risk_level']
        summary_data = [
            ['Metric', 'Value'],
            ['Average Peak Pressure Index', f"{context['avg_ppi']} / 4095"],
            ['Average Contact Area', f"{context['avg_area']}%"],
            ['Average Risk Score', f"{context['avg_risk']} / 100"],
            ['Total High/Critical Risk Events', str(context['total_high_risk'])],
            ['Overall Risk Level', rl.upper()],
        ]
        st = Table(summary_data, colWidths=[10*cm, 6*cm])
        st.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a3a5c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f4f8'), colors.white]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0dce8')),
        ]))
        story.append(st)
        story.append(Spacer(1, 0.4*cm))

        story.append(Paragraph("Session History", heading_style))
        if context['session_summaries']:
            session_header = ['Date', 'Frames', 'Avg PPI', 'Contact Area', 'Risk Score', 'Peak Risk']
            session_rows = [session_header]
            for ss in context['session_summaries']:
                s = ss['session']
                d = ss['data']
                session_rows.append([
                    str(s.session_date),
                    str(d.get('frame_count', 0)),
                    str(d.get('avg_ppi', 0)),
                    f"{d.get('avg_contact_area', 0)}%",
                    str(d.get('avg_risk_score', 0)),
                    d.get('peak_risk_level', 'N/A').upper(),
                ])
            sst = Table(session_rows, colWidths=[3*cm, 2.5*cm, 3*cm, 3*cm, 3*cm, 2.5*cm])
            sst.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f2744')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f4f8'), colors.white]),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d0dce8')),
            ]))
            story.append(sst)
        else:
            story.append(Paragraph("No session data available.", body_style))

        story.append(Spacer(1, 0.6*cm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#d0dce8')))
        footer = ParagraphStyle('Footer', fontName='Helvetica', fontSize=8,
                                textColor=colors.HexColor('#8a9ab0'), alignment=TA_CENTER)
        story.append(Paragraph(
            "This report is generated automatically by the Sensore platform (Graphene Trace). "
            "For clinical decisions, consult your assigned clinician.", footer))

        doc.build(story)
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/pdf')
        patient_name = (patient.get_full_name() or patient.username).replace(' ', '_')
        response['Content-Disposition'] = f'attachment; filename="Sensore_Report_{patient_name}.pdf"'
        return response

    except ImportError:
        return HttpResponse("PDF generation requires reportlab. Install it with: pip install reportlab",
                            content_type='text/plain', status=500)


def generate_csv_report(context):
    """Generate CSV report download for patient sessions."""
    response = HttpResponse(content_type='text/csv')
    patient = context['patient']
    patient_name = (patient.get_full_name() or patient.username).replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="Sensore_Report_{patient_name}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Sensore Medical History Report'])
    writer.writerow(['Patient', patient.get_full_name() or patient.username])
    writer.writerow(['Username', patient.username])
    writer.writerow(['Generated at', context['generated_at'].isoformat()])
    writer.writerow([])
    writer.writerow(['Summary'])
    writer.writerow(['Average PPI', context['avg_ppi']])
    writer.writerow(['Average Contact Area', context['avg_area']])
    writer.writerow(['Average Risk Score', context['avg_risk']])
    writer.writerow(['Overall Risk Level', context['overall_risk_level']])
    writer.writerow(['Total High/Critical Events', context['total_high_risk']])
    writer.writerow([])

    writer.writerow([
        'Session Date',
        'Frames',
        'Average PPI',
        'Max PPI',
        'Average Contact Area',
        'Average Risk Score',
        'Peak Risk Level',
        'High Risk Ratio (%)',
        'Risk Trend',
    ])
    for item in context['session_summaries']:
        session = item['session']
        data = item['data']
        writer.writerow([
            session.session_date,
            data.get('frame_count', 0),
            data.get('avg_ppi', 0),
            data.get('max_ppi', 0),
            data.get('avg_contact_area', 0),
            data.get('avg_risk_score', 0),
            data.get('peak_risk_level', ''),
            data.get('high_risk_ratio', 0),
            data.get('risk_trend', ''),
        ])

    return response


@login_required
@require_GET
def api_patient_sessions(request, patient_id):
    """Return sessions for a patient (clinician use)."""
    if get_user_role(request.user) not in ('clinician', 'admin'):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    patient = get_object_or_404(User, id=patient_id)
    if not user_can_access_patient(request.user, patient):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    sessions = SensorSession.objects.filter(patient=patient).order_by('-session_date')[:20]
    data = []
    for session in sessions:
        report_data = generate_session_report_data(session)
        data.append({
            'id': session.id,
            'date': str(session.session_date),
            'start_time': session.start_time.isoformat(),
            'frame_count': session.frame_count,
            'flagged': session.flagged_for_review,
            'avg_risk_score': report_data.get('avg_risk_score', 0),
            'risk_trend': report_data.get('risk_trend', 'stable'),
            'high_risk_ratio': report_data.get('high_risk_ratio', 0),
            'predicted_hotspots': report_data.get('predicted_hotspots', []),
        })
    return JsonResponse({'sessions': data})

@login_required
def api_reply_comment(request, comment_id):
    """Clinician replies to a patient comment."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    role = get_user_role(request.user)
    if role not in ('clinician', 'admin'):
        return JsonResponse({'error': 'Only clinicians can reply'}, status=403)

    parent = get_object_or_404(Comment, id=comment_id)
    if not user_can_access_session(request.user, parent.session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        body = request.POST

    text = body.get('text', '').strip()
    recommendation_level = (body.get('recommendation_level') or '').strip().lower()
    if not text:
        return JsonResponse({'error': 'Reply text required'}, status=400)

    if recommendation_level not in {'', 'info', 'warning', 'urgent'}:
        recommendation_level = ''

    reply = Comment.objects.create(
        session=parent.session,
        author=request.user,
        author_type='clinician',
        frame=parent.frame,
        timestamp_reference=parent.timestamp_reference,
        text=text,
        is_reply=True,
        reply_to=parent,
        metadata={
            'recommendation_level': recommendation_level,
            'source': 'clinician_reply',
        },
    )
    return JsonResponse(serialise_comment(reply))


@login_required
def api_flag_session(request, session_id):
    """Clinician flags a session for review."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    if get_user_role(request.user) not in ('clinician', 'admin'):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    session = get_object_or_404(SensorSession, id=session_id)
    if not user_can_access_session(request.user, session):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    session.flagged_for_review = not session.flagged_for_review
    session.save(update_fields=['flagged_for_review'])
    return JsonResponse({'flagged': session.flagged_for_review})


@login_required
@require_GET
def api_my_recent_sessions(request):
    """Return recent sessions visible to the current user."""
    role = get_user_role(request.user)

    if role == 'patient':
        sessions = SensorSession.objects.filter(patient=request.user).order_by('-start_time')[:12]
    else:
        patients = get_accessible_patients(request.user)
        sessions = SensorSession.objects.filter(patient__in=patients).order_by('-start_time')[:20]

    data = []
    for session in sessions:
        latest_frame = session.frames.order_by('-frame_index').first()
        latest_risk = 'unknown'
        if latest_frame and hasattr(latest_frame, 'metrics'):
            latest_risk = latest_frame.metrics.risk_level
        data.append({
            'id': session.id,
            'patient_id': session.patient.id,
            'patient_name': session.patient.get_full_name() or session.patient.username,
            'date': str(session.session_date),
            'start_time': session.start_time.isoformat(),
            'frame_count': session.frame_count,
            'flagged': session.flagged_for_review,
            'latest_risk': latest_risk,
        })

    return JsonResponse({'sessions': data, 'role': role})

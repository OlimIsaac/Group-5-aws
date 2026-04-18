"""
Sensore pressure analysis utilities.
Calculates PPI, Contact Area, risk scores, and generates plain-English explanations.

Internal scale: all stored frame data uses 0-4095 where:
    0    = no contact (pixel below sensor threshold)
    4095 = maximum recorded pressure (saturation)

Real hardware data arriving in compressed ranges (e.g. 0-705) is normalised
during import using the file's global maximum so relative pressures are preserved.
"""
import json

import numpy as np

# ── THRESHOLDS (calibrated for 0-4095 scale) ────────────────────────────────
LOWER_THRESHOLD    =  100   # Below this = no meaningful contact
UPPER_THRESHOLD    = 2800   # Above this = high pressure zone
CRITICAL_THRESHOLD = 3500   # Above this = critical pressure
MIN_ZONE_PIXELS    =   10   # Min connected pixels for PPI (Graphene Trace spec)
ALERT_SUSTAINED_STREAK = 4
ALERT_ASYMMETRY_THRESHOLD = 45.0


def normalise_frame(flat_values, global_max=None):
    """
    Normalise one frame of raw sensor values to the 0-4095 internal scale.

    Parameters
    ----------
    flat_values : list of int/float  (1024 values, 32×32 flattened)
    global_max  : int | None
        The maximum value observed across the *entire session/file*.
        When provided, all frames are scaled consistently so relative
        pressures between frames are preserved.
        When None, the frame's own max is used (less accurate).

    Returns
    -------
    list of int  –  1024 values in 0-4095 range.
        0         = no contact
        1-4095    = scaled pressure
    """
    arr = [max(0, int(v)) for v in flat_values]
    ref_max = global_max if global_max and global_max > 0 else max(arr)

    if ref_max == 0:
        return [0] * 1024   # blank frame

    if ref_max <= 4095:
        # Scale so that ref_max maps to 4095, preserving relative pressures
        scale = 4095.0 / ref_max
        return [min(4095, int(v * scale)) for v in arr]
    else:
        # Already in a wide range — just clamp
        return [min(4095, max(0, v)) for v in arr]


def parse_frame_data(data_json):
    """Parse stored JSON frame data into a 32×32 numpy array."""
    flat = json.loads(data_json)
    return np.array(flat, dtype=np.float32).reshape(32, 32)


def calculate_peak_pressure_index(matrix):
    """
    Peak Pressure Index: highest recorded pressure in the frame,
    excluding contact zones smaller than MIN_ZONE_PIXELS (per spec).
    """
    above = (matrix > LOWER_THRESHOLD).astype(np.uint8)

    try:
        from scipy import ndimage
        labeled, num_features = ndimage.label(above)
        max_pressure = 0.0
        for label_id in range(1, num_features + 1):
            component = labeled == label_id
            if np.sum(component) >= MIN_ZONE_PIXELS:
                region_max = float(np.max(matrix[component]))
                if region_max > max_pressure:
                    max_pressure = region_max
        if max_pressure > 0:
            return max_pressure
    except ImportError:
        pass

    # Fallback: simple max of pixels above threshold
    in_contact = matrix[matrix > LOWER_THRESHOLD]
    return float(np.max(in_contact)) if len(in_contact) >= MIN_ZONE_PIXELS else 0.0


def calculate_contact_area(matrix):
    """Contact Area %: percentage of 32×32 pixels above LOWER_THRESHOLD."""
    contact_pixels = int(np.sum(matrix > LOWER_THRESHOLD))
    return round((contact_pixels / 1024) * 100, 1)


def calculate_asymmetry_score(matrix):
    """
    Left/right asymmetry score (0-100).
    0 = perfectly balanced; 100 = all pressure on one side.
    """
    left  = matrix[:, :16]
    right = matrix[:, 16:]
    l_sum = float(np.sum(left [left  > LOWER_THRESHOLD]))
    r_sum = float(np.sum(right[right > LOWER_THRESHOLD]))
    total = l_sum + r_sum
    if total == 0:
        return 0.0
    return round(abs(l_sum - r_sum) / total * 100, 1)


def calculate_pressure_variability(matrix):
    """Return coefficient-of-variation (%) for in-contact pixels."""
    in_contact = matrix[matrix > LOWER_THRESHOLD]
    if len(in_contact) < 2:
        return 0.0

    mean_value = float(np.mean(in_contact))
    if mean_value <= 0:
        return 0.0

    std_value = float(np.std(in_contact))
    return round(min(100.0, (std_value / mean_value) * 100.0), 1)


def calculate_pressure_concentration(matrix):
    """Return a 0-100 index for how localized the highest load is."""
    in_contact = matrix[matrix > LOWER_THRESHOLD]
    if len(in_contact) == 0:
        return 0.0

    mean_value = float(np.mean(in_contact))
    if mean_value <= 0:
        return 0.0

    sorted_values = np.sort(in_contact)
    top_count = max(1, int(len(sorted_values) * 0.05))
    top_mean = float(np.mean(sorted_values[-top_count:]))
    ratio = top_mean / mean_value
    concentration = (ratio - 1.0) * 40.0
    return round(min(100.0, max(0.0, concentration)), 1)


def calculate_center_of_pressure(matrix):
    """Return the centre of pressure as (x, y) in grid coordinates."""
    weights = np.clip(matrix - LOWER_THRESHOLD, 0, None)
    total_weight = float(np.sum(weights))
    if total_weight <= 0:
        return None, None

    ys, xs = np.indices(matrix.shape)
    cop_x = float(np.sum(xs * weights) / total_weight)
    cop_y = float(np.sum(ys * weights) / total_weight)
    return round(cop_x, 2), round(cop_y, 2)


def calculate_movement_index(current_matrix, previous_matrix=None):
    """Return frame-to-frame movement intensity on a 0-100 scale."""
    if previous_matrix is None:
        return 0.0

    current = np.asarray(current_matrix, dtype=np.float32)
    previous = np.asarray(previous_matrix, dtype=np.float32)
    if current.shape != previous.shape:
        return 0.0

    union_mask = (current > LOWER_THRESHOLD) | (previous > LOWER_THRESHOLD)
    if not np.any(union_mask):
        return 0.0

    mean_delta = float(np.mean(np.abs(current[union_mask] - previous[union_mask])))
    return round(min(100.0, (mean_delta / 4095.0) * 100.0), 1)


def calculate_sustained_load_index(streak_frames):
    """Convert a high-load streak length into a 0-100 persistence index."""
    streak = max(0, int(streak_frames))
    return round(min(100.0, streak * 12.5), 1)


def ensure_alerts_for_frame(frame_obj, metrics_obj, sustained_streak=0):
    """Create system alerts for a frame when risk conditions are met.

    Returns
    -------
    int
        Number of newly created alerts.
    """
    from .models import PressureAlert

    candidates = []

    if metrics_obj.risk_level in ('high', 'critical'):
        candidates.append({
            'alert_type': 'critical' if metrics_obj.risk_level == 'critical' else 'high_ppi',
            'message': (
                f"{metrics_obj.risk_level.capitalize()} pressure detected — "
                f"PPI: {metrics_obj.peak_pressure_index:.0f}, "
                f"Risk: {metrics_obj.risk_score:.0f}/100. "
                "Please reposition soon."
            ),
        })

    if sustained_streak >= ALERT_SUSTAINED_STREAK and metrics_obj.peak_pressure_index >= UPPER_THRESHOLD:
        candidates.append({
            'alert_type': 'sustained',
            'message': (
                f"Sustained high pressure for ~{sustained_streak * 30 // 60} min "
                f"({sustained_streak} frames). Persistent load may increase injury risk."
            ),
        })

    if metrics_obj.asymmetry_score >= ALERT_ASYMMETRY_THRESHOLD and metrics_obj.risk_score >= 45:
        candidates.append({
            'alert_type': 'asymmetry',
            'message': (
                f"Significant left/right imbalance detected "
                f"({metrics_obj.asymmetry_score:.1f}% asymmetry). "
                "Encourage a more central sitting position."
            ),
        })

    created_count = 0
    for candidate in candidates:
        _, created = PressureAlert.objects.get_or_create(
            session=frame_obj.session,
            frame=frame_obj,
            alert_type=candidate['alert_type'],
            defaults={
                'message': candidate['message'],
                'risk_score': metrics_obj.risk_score,
            },
        )
        if created:
            created_count += 1

    return created_count


def analyse_session_frames(session_obj, create_alerts=True):
    """Analyse all frames in a session with temporal context.

    Adds movement and sustained-load context by feeding previous frame matrix
    and high-load streak values into frame analysis.
    """
    previous_matrix = None
    sustained_streak = 0
    analysed_frames = 0
    alerts_created = 0

    frames = session_obj.frames.order_by('frame_index', 'timestamp').all()
    for frame in frames.iterator():
        matrix = parse_frame_data(frame.data)
        current_ppi = calculate_peak_pressure_index(matrix)

        if current_ppi >= UPPER_THRESHOLD:
            sustained_streak += 1
        else:
            sustained_streak = 0

        metrics = analyse_frame(
            frame,
            previous_matrix=previous_matrix,
            sustained_streak=sustained_streak,
        )

        if create_alerts:
            alerts_created += ensure_alerts_for_frame(
                frame,
                metrics,
                sustained_streak=sustained_streak,
            )

        previous_matrix = matrix
        analysed_frames += 1

    return analysed_frames, alerts_created


def find_hot_zones(matrix, top_n=5):
    """Return the top-N highest-pressure pixel positions as {x, y, value}."""
    flat_indices = np.argsort(matrix.flatten())[-top_n:][::-1]
    hot_zones = []
    for idx in flat_indices:
        row = int(idx // 32)
        col = int(idx % 32)
        val = float(matrix[row, col])
        if val > LOWER_THRESHOLD:
            hot_zones.append({'x': col, 'y': row, 'value': val})
    return hot_zones


def calculate_risk_score(ppi, contact_area, asymmetry, concentration=0.0, sustained_load=0.0, movement_index=0.0):
    """
    Composite risk score 0-100.

    PPI component        (0-50 pts): nearness to critical threshold
    Asymmetry            (0-30 pts): left/right imbalance
    Contact area         (0-20 pts): concentrated or abnormally high coverage
    Concentration bonus  (0-10 pts): localized high-pressure load
    Sustained load bonus (0-15 pts): persistent pressure over time
    Movement relief      (-2 pts): movement can briefly reduce risk
    """
    ppi_score  = min(50, (ppi / CRITICAL_THRESHOLD) * 50)
    asym_score = min(30, (asymmetry / 100) * 30)
    concentration_score = min(10, (concentration / 100) * 10)
    sustained_score = min(15, (sustained_load / 100) * 15)
    movement_relief = -2.0 if movement_index >= 12.0 and ppi < UPPER_THRESHOLD else 0.0

    if contact_area < 10:
        area_score = 15      # concentrated pressure — higher risk
    elif contact_area > 70:
        area_score = 5
    else:
        area_score = max(0, 20 - contact_area * 0.2)

    return round(ppi_score + asym_score + area_score + concentration_score + sustained_score + movement_relief, 1)


def get_risk_level(risk_score):
    if risk_score < 25:
        return 'low'
    elif risk_score < 50:
        return 'moderate'
    elif risk_score < 75:
        return 'high'
    else:
        return 'critical'


def generate_plain_english(ppi, contact_area, asymmetry, risk_level, risk_score):
    """Patient-friendly explanation of a single pressure frame."""
    ppi_pct = round((ppi / 4095) * 100, 0)

    if ppi_pct < 30:
        pressure_msg = "Your peak pressure is low — the mat is detecting gentle, even contact."
    elif ppi_pct < 60:
        pressure_msg = (f"Your peak pressure is moderate ({ppi_pct:.0f}% of maximum). "
                        "Some areas are under more load than others.")
    elif ppi_pct < 80:
        pressure_msg = (f"Your peak pressure is quite high ({ppi_pct:.0f}% of maximum). "
                        "This level of pressure over time can be uncomfortable and may affect circulation.")
    else:
        pressure_msg = (f"⚠️ Your peak pressure is very high ({ppi_pct:.0f}% of maximum). "
                        "Please consider repositioning to reduce pressure on these areas.")

    if contact_area < 15:
        area_msg = "Only a small part of the mat is in contact — pressure is concentrated."
    elif contact_area < 40:
        area_msg = f"{contact_area}% of the mat is in contact, which is a moderate contact area."
    else:
        area_msg = (f"{contact_area}% of the mat is in contact — your weight is "
                    "distributed across a good portion of the surface.")

    if asymmetry < 20:
        asym_msg = "Your weight is fairly evenly distributed left-to-right. This is ideal."
    elif asymmetry < 40:
        asym_msg = f"There is a slight lean to one side ({asymmetry}% imbalance). Try to sit more centrally."
    else:
        asym_msg = (f"There is a noticeable imbalance ({asymmetry}% difference between sides). "
                    "Sitting asymmetrically can increase risk of pressure injuries.")

    recs = {
        'low':      "✅ Overall: Your sitting position looks good right now. Keep it up!",
        'moderate': "🔶 Overall: Your position is acceptable but has room for improvement. Consider shifting slightly.",
        'high':     "🔴 Overall: Your sitting position poses a risk. Please reposition soon and let your clinician know.",
        'critical': "🚨 Overall: Critical pressure detected! Please reposition immediately and contact your clinician.",
    }
    rec = recs.get(risk_level, '')

    return f"{pressure_msg}\n\n{area_msg}\n\n{asym_msg}\n\n{rec}"


def analyse_frame(frame_obj, previous_matrix=None, sustained_streak=0):
    """Full analysis of a SensorFrame. Returns and saves PressureMetrics."""
    from .models import PressureMetrics

    matrix = parse_frame_data(frame_obj.data)
    ppi = calculate_peak_pressure_index(matrix)
    contact_area = calculate_contact_area(matrix)
    in_contact = matrix[matrix > LOWER_THRESHOLD]
    avg_pressure = float(np.mean(in_contact)) if len(in_contact) > 0 else 0.0
    asymmetry = calculate_asymmetry_score(matrix)
    pressure_variability = calculate_pressure_variability(matrix)
    pressure_concentration = calculate_pressure_concentration(matrix)
    center_of_pressure_x, center_of_pressure_y = calculate_center_of_pressure(matrix)
    movement_index = calculate_movement_index(matrix, previous_matrix=previous_matrix)
    sustained_load_index = calculate_sustained_load_index(sustained_streak)
    hot_zones = find_hot_zones(matrix)
    risk_score = calculate_risk_score(
        ppi,
        contact_area,
        asymmetry,
        pressure_concentration,
        sustained_load_index,
        movement_index,
    )
    risk_level = get_risk_level(risk_score)
    explanation = generate_plain_english(ppi, contact_area, asymmetry, risk_level, risk_score)

    metrics, _ = PressureMetrics.objects.update_or_create(
        frame=frame_obj,
        defaults={
            'peak_pressure_index': round(ppi, 1),
            'contact_area_percent': contact_area,
            'average_pressure': round(avg_pressure, 1),
            'asymmetry_score': asymmetry,
            'pressure_variability': pressure_variability,
            'pressure_concentration': pressure_concentration,
            'movement_index': movement_index,
            'sustained_load_index': sustained_load_index,
            'center_of_pressure_x': center_of_pressure_x,
            'center_of_pressure_y': center_of_pressure_y,
            'risk_level': risk_level,
            'risk_score': risk_score,
            'hot_zones': json.dumps(hot_zones),
            'plain_english': explanation,
        }
    )
    return metrics


def generate_session_report_data(session):
    """Aggregate metrics across all frames in a session."""
    frames       = session.frames.prefetch_related('metrics').all()
    metrics_list = []

    for frame in frames:
        if hasattr(frame, 'metrics'):
            m = frame.metrics
            metrics_list.append({
                'timestamp':    frame.timestamp.isoformat(),
                'frame_index':  frame.frame_index,
                'ppi':          m.peak_pressure_index,
                'contact_area': m.contact_area_percent,
                'avg_pressure': m.average_pressure,
                'asymmetry':    m.asymmetry_score,
                'pressure_variability': m.pressure_variability,
                'pressure_concentration': m.pressure_concentration,
                'movement_index': m.movement_index,
                'sustained_load_index': m.sustained_load_index,
                'center_of_pressure_x': m.center_of_pressure_x,
                'center_of_pressure_y': m.center_of_pressure_y,
                'hot_zones': m.get_hot_zones(),
                'risk_score':   m.risk_score,
                'risk_level':   m.risk_level,
            })

    if not metrics_list:
        return {}

    ppis  = [m['ppi']          for m in metrics_list]
    risks = [m['risk_score']   for m in metrics_list]
    areas = [m['contact_area'] for m in metrics_list]

    risk_counts = {'low': 0, 'moderate': 0, 'high': 0, 'critical': 0}
    for m in metrics_list:
        risk_counts[m['risk_level']] += 1

    peak_risk = max(metrics_list, key=lambda x: x['risk_score'])['risk_level']
    high_risk_count = risk_counts['high'] + risk_counts['critical']
    high_risk_ratio = round((high_risk_count / len(metrics_list)) * 100.0, 1)

    first_half = metrics_list[: max(1, len(metrics_list) // 2)]
    second_half = metrics_list[max(1, len(metrics_list) // 2):]
    first_avg = float(np.mean([m['risk_score'] for m in first_half]))
    second_avg = float(np.mean([m['risk_score'] for m in second_half])) if second_half else first_avg

    if abs(second_avg - first_avg) < 3:
        risk_trend = 'stable'
    elif second_avg > first_avg:
        risk_trend = 'increasing'
    else:
        risk_trend = 'decreasing'

    hotspot_map = {}
    for point in metrics_list[-12:]:
        for zone in point.get('hot_zones', [])[:3]:
            x = int(zone.get('x', 0))
            y = int(zone.get('y', 0))
            key = (x, y)
            if key not in hotspot_map:
                hotspot_map[key] = {
                    'x': x,
                    'y': y,
                    'samples': 0,
                    'value_sum': 0.0,
                }
            hotspot_map[key]['samples'] += 1
            hotspot_map[key]['value_sum'] += float(zone.get('value', 0.0))

    predicted_hotspots = sorted(
        [
            {
                'x': v['x'],
                'y': v['y'],
                'confidence': round(min(100.0, v['samples'] * 18.0), 1),
                'avg_value': round(v['value_sum'] / max(1, v['samples']), 1),
            }
            for v in hotspot_map.values()
        ],
        key=lambda p: (p['confidence'], p['avg_value']),
        reverse=True,
    )[:3]

    return {
        'frame_count':       len(metrics_list),
        'avg_ppi':           round(float(np.mean(ppis)), 1),
        'max_ppi':           round(float(max(ppis)), 1),
        'avg_contact_area':  round(float(np.mean(areas)), 1),
        'avg_risk_score':    round(float(np.mean(risks)), 1),
        'peak_risk_level':   peak_risk,
        'risk_distribution': risk_counts,
        'high_risk_ratio':   high_risk_ratio,
        'risk_trend':        risk_trend,
        'predicted_hotspots': predicted_hotspots,
        'timeline':          metrics_list,
    }

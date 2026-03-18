# Patient Dashboard — Design Spec

**Date:** 2026-03-18
**Branch:** nihar
**Approach:** Server-rendered Django templates with JS polling (Approach A)

---

## User Stories Covered

1. Alert when pressure is too high so the patient knows when to move
2. Simple and easy to use dashboard
3. Mark painful areas — implemented as a body-zone checklist below the dashboard (not canvas annotation); a deliberate scope decision agreed with the user
4. Switch between time views (1h, 6h, 24h) to track pressure patterns — affects chart only
5. See changes in pressure over time
6. Private login so data stays secure

---

## Data Model

### New model: `PainZoneReport` (`core/models.py`)

| Field | Type | Notes |
|-------|------|-------|
| `user` | `ForeignKey(User, on_delete=CASCADE)` | The patient who submitted |
| `timestamp` | `DateTimeField(auto_now_add=True)` | Auto-set on creation; not editable |
| `zones` | `JSONField` | List of zone strings; must be subset of predefined set |
| `note` | `TextField(blank=True)` | Optional free-text note |

**Predefined zones (authoritative list):**
`lower_back`, `left_hip`, `right_hip`, `left_thigh`, `right_thigh`, `tailbone`, `left_shoulder`, `right_shoulder`

Each submission always creates a new `PainZoneReport` record (history preserved). No uniqueness constraint per day. No rate limiting in this version.

No changes to `PressureFrame`.

---

## Backend

### Updated: `PatientDashboardView` (`GET /patient/`)

- Removes `frames` and `comment_form` from context (no longer used in the new template)
- Adds to context: `zone_choices` (the 8 predefined zone strings), `latest_pain_report` (most recent `PainZoneReport` for the user, or `None`)

### New endpoint: `GET /patient/api/status/?hours=1|6|24`

**Auth & role:**
- Requires login (`LoginRequiredMixin`)
- If `request.user.role != 'patient'`: return `JsonResponse({"error": "forbidden"}, status=403)` — **not** a redirect (redirect would break the JS fetch)

**Parameter validation:**
- `hours` must be in `{1, 6, 24}`; if not, default to `1` (do not return an error — silently clamp)

**Query:**
- Use `django.utils.timezone.now()` (not `datetime.datetime.now()`) for the `now` variable, so the filter works correctly under `USE_TZ = True`
- Filters `PressureFrame.objects.filter(user=request.user, timestamp__gte=now - timedelta(hours=hours))`
- Most recent frame = last by timestamp

**Response shape (always return all keys):**

```json
{
  "alert": false,
  "latest_ppi": 3812.0,
  "latest_contact": 42.3,
  "latest_matrix": [[...32x32 array...]],
  "chart_data": {
    "labels": ["14:00", "15:00", "16:00"],
    "counts": [2, 0, 5]
  }
}
```

**Safe defaults when no frames exist:**
```json
{
  "alert": false,
  "latest_ppi": null,
  "latest_contact": null,
  "latest_matrix": null,
  "chart_data": { "labels": [], "counts": [] }
}
```

**`chart_data` computation:**
- Group frames with `high_pressure_flag=True` by hour bucket
- Labels are formatted in UTC (`datetime.strftime("%H:%M")` on UTC-aware timestamps)
- One label per hour in the requested window (include hours with 0 count)

### New endpoint: `POST /patient/pain-zones/`

**Auth & role:**
- Requires login; if `request.user.role != 'patient'`: return `HttpResponseForbidden`

**Form class:** Create `PainZoneReportForm` in `core/forms.py` (consistent with the project's existing pattern of one form class per model). The form validates:
- `zones`: `MultipleChoiceField` with choices from the predefined set of 8 strings; required (non-empty)
- `note`: `CharField(max_length=1000, required=False)`

**On validation failure:** Re-render `patient_dashboard.html` with context `{"zone_choices": PREDEFINED_ZONES, "latest_pain_report": ..., "form": bound_form}` so checkboxes and error messages render correctly.

**On success:**
- Creates a `PainZoneReport`
- `messages.success(request, "Pain zones submitted successfully")`
- Redirects to `/patient/`

---

## Frontend

### Template: `patient_dashboard.html`

Replaces the existing stub entirely.

**Structure:**
```
<div class="patient-layout">  ← two-column flex/grid wrapper
  <div class="col-left">
    <canvas id="heatmapCanvas" width="320" height="320">
    <p>PPI: <span id="ppiValue">--</span></p>
    <p>Contact Area: <span id="contactValue">--</span></p>
  </div>
  <div class="col-right">
    <div id="alertBanner" class="alert">...</div>   ← replaces old id="alerts"
    <div class="time-filters">
      <button data-hours="1">Last Hour</button>
      <button data-hours="6">Last 6 Hours</button>
      <button data-hours="24">Last 24 Hours</button>
    </div>
    <canvas id="pressureChart"></canvas>
  </div>
</div>

<div class="card pain-zone-card">
  <form method="post" action="{% url 'submit_pain_zones' %}">
    {% csrf_token %}
    <!-- 8 checkboxes, one per zone -->
    <textarea name="note" ...></textarea>
    <button type="submit">Submit</button>
  </form>
</div>
```

**Script tags** — placed inside `{% block scripts %}` (already present in `base.html`). The template must also declare `{% load static %}` at the top (Django does not inherit tag libraries from base templates):
```html
{% load static %}
...
{% block scripts %}
<script src="{% static 'js/patient_dashboard.js' %}"></script>
{% endblock %}
```
Chart.js CDN is already loaded in `base.html` unconditionally; no change needed there. Note: `heatmap.js` is also loaded unconditionally in `base.html` on all pages — this is an accepted pre-existing trade-off; do not move it.

**Login page:** Add one sentence below the submit button:
> "Your data is private and only visible to you and your assigned clinician."

### JavaScript: `core/static/js/patient_dashboard.js`

```
currentHours = 1

loadData(hours):
  currentHours = hours
  fetch `/patient/api/status/?hours=${hours}`
  → on success:
      if data.latest_matrix !== null && Array.isArray(data.latest_matrix):
          drawHeatmap('heatmapCanvas', data.latest_matrix)
      ppiValue.textContent = data.latest_ppi !== null ? data.latest_ppi.toFixed(1) : '--'
      contactValue.textContent = data.latest_contact !== null ? data.latest_contact.toFixed(1) + '%' : '--'
      alertBanner.className = data.alert ? 'alert alert-danger' : 'alert alert-success'
      alertBanner.textContent = data.alert
          ? '⚠ High pressure detected — please shift position'
          : 'Pressure looks normal'
      // Replace arrays fully (not in-place mutation) so Chart.js handles length changes correctly:
      pressureChart.data.labels = data.chart_data.labels
      pressureChart.data.datasets[0].data = data.chart_data.counts
      pressureChart.update()
      highlight active time filter button (remove .active from siblings, add to clicked)
  → on fetch error: leave existing UI unchanged (silent fail — do not crash polling loop)

// Initialization order inside DOMContentLoaded:
//   1. Construct the Chart.js instance first (assigned to pressureChart)
//   2. Then call loadData(1)
//   3. Then start setInterval
on DOMContentLoaded:
  pressureChart = new Chart(...)   ← must come BEFORE loadData(1)
  loadData(1)
  setInterval(() => loadData(currentHours), 8000)

Chart.js instance:
  type: 'bar'
  label: 'High-pressure frames'
  x-axis: chart_data.labels
  y-axis: chart_data.counts (integers ≥ 0)
  kept in a module-level variable so it can be `.update()`d each poll cycle
```

---

## Migration

One new migration for `PainZoneReport`.

---

## URLs added to `core/urls.py`

```python
path('patient/api/status/', views.PatientStatusAPIView.as_view(), name='patient_status_api'),
path('patient/pain-zones/', views.SubmitPainZonesView.as_view(), name='submit_pain_zones'),
```

---

## What is NOT changing

- Login/auth flow (functional already)
- `PressureFrame` model and ingestion pipeline
- Admin and clinician dashboards
- `drawHeatmap()` in `heatmap.js`
- `base.html` (Chart.js CDN already present; `{% block scripts %}` already present)
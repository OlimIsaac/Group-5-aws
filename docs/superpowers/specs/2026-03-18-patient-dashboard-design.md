# Patient Dashboard — Design Spec

**Date:** 2026-03-18
**Branch:** nihar
**Approach:** Server-rendered Django templates with JS polling (Approach A)

---

## User Stories Covered

1. Alert when pressure is too high so the patient knows when to move
2. Simple and easy to use dashboard
3. Mark painful areas on the heatmap so the clinician knows where there is discomfort
4. Switch between time views (1h, 6h, 24h) to track pressure patterns
5. See changes in pressure over time
6. Private login so data stays secure

---

## Data Model

### New model: `PainZoneReport` (`core/models.py`)

| Field | Type | Notes |
|-------|------|-------|
| `user` | ForeignKey(User) | The patient who submitted |
| `timestamp` | DateTimeField | Auto-set on creation |
| `zones` | JSONField | List of zone strings from predefined set |
| `note` | TextField | Optional free-text note |

**Predefined zones:** `lower_back`, `left_hip`, `right_hip`, `left_thigh`, `right_thigh`, `tailbone`, `left_shoulder`, `right_shoulder`

No changes to `PressureFrame` — `high_pressure_flag` and `peak_pressure_index` already exist.

---

## Backend

### New endpoint: `GET /patient/api/status/?hours=1|6|24`

- Auth: `LoginRequiredMixin`, patient role only
- Filters `PressureFrame` objects for `request.user` within the last N hours
- Returns JSON:

```json
{
  "alert": true,
  "latest_ppi": 3812.0,
  "latest_contact": 42.3,
  "latest_matrix": [[...32x32 array...]],
  "chart_data": {
    "labels": ["14:00", "15:00", "16:00"],
    "counts": [2, 0, 5]
  }
}
```

- `alert`: `true` if the most recent frame has `high_pressure_flag=True`
- `chart_data.counts`: number of frames with `high_pressure_flag=True` grouped by hour within the window
- Returns empty/safe defaults if no frames exist

### New endpoint: `POST /patient/pain-zones/`

- Auth: `LoginRequiredMixin`, patient role only
- Accepts: `zones` (list of strings), `note` (optional string)
- Creates a `PainZoneReport` for `request.user`
- Redirects to `/patient/` with a Django success message

### Updated: `PatientDashboardView` (`GET /patient/`)

- Passes to template: `zone_choices` (list of 8 predefined zone labels), `latest_pain_report` (most recent `PainZoneReport` for the user, or `None`)

---

## Frontend

### Layout (`patient_dashboard.html`)

Two-column layout:

**Left column:**
- Heatmap canvas (320×320, existing `drawHeatmap()`)
- PPI value (`#ppiValue`) and Contact Area (`#contactValue`) displayed below

**Right column:**
- Alert banner (`#alertBanner`) — red background + "⚠ High pressure detected — please shift position" when `alert=true`; green + "Pressure looks normal" when `false`
- Time filter buttons: `1h`, `6h`, `24h` — active button highlighted; clicking calls `loadData(N)` and updates `currentHours`
- Bar chart (`Chart.js`) showing high-pressure frame count per hour within selected window

**Below both columns:**
- Pain zone card — 8 checkbox buttons (one per predefined zone) + optional text note input + "Submit" button
- Submits via standard HTML form POST to `/patient/pain-zones/`

**Login page:**
- No functional changes
- Add a one-line note below the form: "Your data is private and only visible to you and your assigned clinician."

### JavaScript (`core/static/js/patient_dashboard.js`)

- `currentHours = 1` (default)
- `loadData(hours)`:
  1. Sets `currentHours = hours`
  2. Fetches `/patient/api/status/?hours=hours`
  3. Calls `drawHeatmap('heatmapCanvas', data.latest_matrix)` if matrix present
  4. Updates `#ppiValue` and `#contactValue`
  5. Shows/hides `#alertBanner` based on `data.alert`
  6. Updates Chart.js instance with `data.chart_data`
  7. Updates active state on time filter buttons
- On page load: `loadData(1)`
- Polling: `setInterval(() => loadData(currentHours), 8000)`

---

## Migration

One new migration for `PainZoneReport`.

---

## URLs added to `core/urls.py`

```
GET  /patient/api/status/    → PatientStatusAPIView
POST /patient/pain-zones/    → SubmitPainZonesView
```

---

## What is NOT changing

- Login/auth flow — already functional
- `PressureFrame` model and ingestion pipeline
- Admin, clinician dashboards
- Existing `drawHeatmap()` function in `heatmap.js`
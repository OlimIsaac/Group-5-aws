# Patient Dashboard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 6 patient user stories — high-pressure alerts, two-column dashboard layout, body-zone pain reporting, time-filtered pressure chart, and a login privacy note.

**Architecture:** Server-rendered Django templates with an 8-second JS polling loop hitting a new JSON endpoint. A new `PainZoneReport` model stores patient-submitted discomfort zones. The patient dashboard JS file manages the heatmap refresh, alert banner, chart updates, and time filter state.

**Tech Stack:** Django 4.2, Django TestCase (built-in, no extra install), Chart.js (CDN already in base.html), vanilla JS fetch API.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `core/models.py` | Add `PainZoneReport` model + `PREDEFINED_ZONES` constant |
| Auto-generate | `core/migrations/` | Migration for `PainZoneReport` |
| Modify | `core/forms.py` | Add `PainZoneReportForm` |
| Modify | `core/views.py` | Add `PatientStatusAPIView`, `SubmitPainZonesView`; update `PatientDashboardView` |
| Modify | `core/urls.py` | Wire 2 new paths |
| Modify | `core/templates/core/patient_dashboard.html` | Rewrite to two-column layout |
| Modify | `core/templates/core/login.html` | Add privacy sentence |
| Create | `core/static/js/patient_dashboard.js` | Polling loop, heatmap refresh, chart, alert banner |
| Modify | `core/static/css/dashboard.css` | Add `.patient-layout` two-column styles |

---

## Task 1: PainZoneReport Model

**Files:**
- Modify: `core/models.py`

- [ ] **Step 1: Write the test**

Create `core/tests.py` (or append if it exists) with:

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import PainZoneReport, PREDEFINED_ZONES

User = get_user_model()

class PainZoneReportModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testpatient', password='pass', role='patient'
        )

    def test_create_report_saves_zones(self):
        report = PainZoneReport.objects.create(
            user=self.user,
            zones=['lower_back', 'left_hip'],
            note='Aches a lot'
        )
        fetched = PainZoneReport.objects.get(pk=report.pk)
        self.assertEqual(fetched.zones, ['lower_back', 'left_hip'])
        self.assertEqual(fetched.note, 'Aches a lot')

    def test_timestamp_auto_set(self):
        report = PainZoneReport.objects.create(
            user=self.user, zones=['tailbone']
        )
        self.assertIsNotNone(report.timestamp)

    def test_predefined_zones_has_eight_entries(self):
        self.assertEqual(len(PREDEFINED_ZONES), 8)
        self.assertIn('lower_back', PREDEFINED_ZONES)
        self.assertIn('tailbone', PREDEFINED_ZONES)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python manage.py test core.tests.PainZoneReportModelTest
```
Expected: `ImportError` — `PainZoneReport` and `PREDEFINED_ZONES` not yet defined.

- [ ] **Step 3: Add `PREDEFINED_ZONES` constant and `PainZoneReport` model to `core/models.py`**

Add after the existing imports at the top of the models file, before the class definitions:

```python
PREDEFINED_ZONES = [
    'lower_back', 'left_hip', 'right_hip',
    'left_thigh', 'right_thigh', 'tailbone',
    'left_shoulder', 'right_shoulder',
]
```

Add the model at the bottom of `core/models.py`:

```python
class PainZoneReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pain_zone_reports')
    timestamp = models.DateTimeField(auto_now_add=True)
    zones = models.JSONField()
    note = models.TextField(blank=True)

    def __str__(self):
        return f"PainZoneReport by {self.user.username} at {self.timestamp}"
```

- [ ] **Step 4: Create and apply the migration**

```bash
python manage.py makemigrations core
python manage.py migrate
```
Expected: migration file created, applied cleanly with no errors.

- [ ] **Step 5: Run the tests**

```bash
python manage.py test core.tests.PainZoneReportModelTest
```
Expected: `Ran 3 tests ... OK`

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ core/tests.py
git commit -m "feat: add PainZoneReport model"
```

---

## Task 2: PainZoneReportForm

**Files:**
- Modify: `core/forms.py`

- [ ] **Step 1: Write the test**

Append to `core/tests.py`:

```python
from .forms import PainZoneReportForm

class PainZoneReportFormTest(TestCase):
    def test_valid_zones_accepted(self):
        form = PainZoneReportForm(data={
            'zones': ['lower_back', 'tailbone'],
            'note': 'hurts',
        })
        self.assertTrue(form.is_valid())

    def test_invalid_zone_rejected(self):
        form = PainZoneReportForm(data={
            'zones': ['invented_zone'],
            'note': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('zones', form.errors)

    def test_empty_zones_rejected(self):
        form = PainZoneReportForm(data={'zones': [], 'note': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('zones', form.errors)

    def test_note_is_optional(self):
        form = PainZoneReportForm(data={'zones': ['left_hip']})
        self.assertTrue(form.is_valid())

    def test_note_max_length(self):
        form = PainZoneReportForm(data={
            'zones': ['left_hip'],
            'note': 'x' * 1001,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('note', form.errors)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python manage.py test core.tests.PainZoneReportFormTest
```
Expected: `ImportError` — `PainZoneReportForm` not yet defined.

- [ ] **Step 3: Add `PainZoneReportForm` to `core/forms.py`**

Add this import at the top of `core/forms.py`:

```python
from .models import User, Comment, Assignment, ClinicianProfile, PatientProfile, PREDEFINED_ZONES
```

Add the form class at the bottom of `core/forms.py`:

```python
class PainZoneReportForm(forms.Form):
    zones = forms.MultipleChoiceField(
        choices=[(z, z.replace('_', ' ').title()) for z in PREDEFINED_ZONES],
        widget=forms.CheckboxSelectMultiple,
        required=True,
    )
    note = forms.CharField(
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional: describe your discomfort...'}),
    )
```

- [ ] **Step 4: Run the tests**

```bash
python manage.py test core.tests.PainZoneReportFormTest
```
Expected: `Ran 5 tests ... OK`

- [ ] **Step 5: Commit**

```bash
git add core/forms.py core/tests.py
git commit -m "feat: add PainZoneReportForm"
```

---

## Task 3: PatientStatusAPIView

**Files:**
- Modify: `core/views.py`

- [ ] **Step 1: Write the test**

Append to `core/tests.py`:

```python
import json
from django.utils import timezone
from datetime import timedelta
from .models import PressureFrame

class PatientStatusAPITest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='pat', password='pass', role='patient'
        )
        self.client.login(username='pat', password='pass')

    def _make_frame(self, minutes_ago, high_pressure=False):
        matrix = [[0]*32 for _ in range(32)]
        PressureFrame.objects.create(
            user=self.patient,
            timestamp=timezone.now() - timedelta(minutes=minutes_ago),
            raw_matrix=matrix,
            peak_pressure_index=4000.0 if high_pressure else 500.0,
            contact_area_percentage=50.0,
            high_pressure_flag=high_pressure,
        )

    def test_returns_json(self):
        response = self.client.get('/patient/api/status/?hours=1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('alert', data)
        self.assertIn('latest_ppi', data)
        self.assertIn('latest_contact', data)
        self.assertIn('latest_matrix', data)
        self.assertIn('chart_data', data)

    def test_safe_defaults_with_no_frames(self):
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        self.assertFalse(data['alert'])
        self.assertIsNone(data['latest_ppi'])
        self.assertIsNone(data['latest_matrix'])
        self.assertEqual(data['chart_data']['labels'], [])

    def test_alert_true_when_latest_frame_is_high(self):
        self._make_frame(minutes_ago=5, high_pressure=True)
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        self.assertTrue(data['alert'])

    def test_alert_false_when_latest_frame_is_normal(self):
        self._make_frame(minutes_ago=5, high_pressure=False)
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        self.assertFalse(data['alert'])

    def test_non_patient_gets_403(self):
        admin = User.objects.create_user(
            username='adm', password='pass', role='admin'
        )
        self.client.login(username='adm', password='pass')
        response = self.client.get('/patient/api/status/?hours=1')
        self.assertEqual(response.status_code, 403)

    def test_out_of_range_hours_defaults_to_one(self):
        # Integer but not in {1,6,24} — should silently clamp, not error
        response = self.client.get('/patient/api/status/?hours=999')
        self.assertEqual(response.status_code, 200)

    def test_non_integer_hours_defaults_to_one(self):
        # Non-integer value — exercises the ValueError branch in the view
        response = self.client.get('/patient/api/status/?hours=abc')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('alert', data)  # valid response shape returned

    def test_chart_data_counts_high_pressure_frames_by_hour(self):
        # 2 high-pressure frames, 1 normal — only high-pressure ones should be counted
        self._make_frame(minutes_ago=20, high_pressure=True)
        self._make_frame(minutes_ago=25, high_pressure=True)
        self._make_frame(minutes_ago=35, high_pressure=False)
        response = self.client.get('/patient/api/status/?hours=1')
        data = json.loads(response.content)
        # Labels and counts must always be the same length
        self.assertEqual(len(data['chart_data']['labels']), len(data['chart_data']['counts']))
        total_high = sum(data['chart_data']['counts'])
        self.assertEqual(total_high, 2)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python manage.py test core.tests.PatientStatusAPITest
```
Expected: `404` errors — URL not yet registered.

- [ ] **Step 3: Add `PatientStatusAPIView` to `core/views.py`**

**Replace** the existing `from django.http import ...` line (currently `from django.http import HttpResponseForbidden`) with:

```python
from django.http import HttpResponseForbidden, JsonResponse
```

Add these additional imports after the existing import block (do not duplicate lines already present):

```python
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
```

**Replace** the existing `from .models import ...` line with the expanded version that includes `PainZoneReport`:

```python
from .models import User, PressureFrame, ClinicianProfile, Assignment, PatientProfile, Comment, PainZoneReport
```

Add the view class (before the `ClinicianDashboardView` or after `PatientDashboardView`):

```python
class PatientStatusAPIView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return JsonResponse({"error": "forbidden"}, status=403)

        try:
            hours = int(request.GET.get('hours', 1))
        except (ValueError, TypeError):
            hours = 1
        if hours not in (1, 6, 24):
            hours = 1

        now = timezone.now()
        since = now - timedelta(hours=hours)
        frames = PressureFrame.objects.filter(
            user=request.user, timestamp__gte=since
        ).order_by('timestamp')

        if not frames.exists():
            return JsonResponse({
                "alert": False,
                "latest_ppi": None,
                "latest_contact": None,
                "latest_matrix": None,
                "chart_data": {"labels": [], "counts": []},
            })

        latest = frames.last()

        # Build hour buckets for chart_data
        hour_counts = defaultdict(int)
        # Pre-fill every hour bucket in the window with 0
        for offset in range(hours):
            bucket_time = (now - timedelta(hours=hours - offset)).replace(
                minute=0, second=0, microsecond=0
            )
            label = bucket_time.strftime("%H:%M")
            hour_counts[label]  # ensures key exists with default 0

        for frame in frames:
            if frame.high_pressure_flag:
                bucket = frame.timestamp.replace(
                    minute=0, second=0, microsecond=0
                ).strftime("%H:%M")
                hour_counts[bucket] += 1

        labels = sorted(hour_counts.keys())
        counts = [hour_counts[l] for l in labels]

        return JsonResponse({
            "alert": latest.high_pressure_flag,
            "latest_ppi": latest.peak_pressure_index,
            "latest_contact": latest.contact_area_percentage,
            "latest_matrix": latest.raw_matrix,
            "chart_data": {"labels": labels, "counts": counts},
        })
```

- [ ] **Step 4: Register the URL temporarily so tests can find it**

Add to `core/urls.py`:

```python
path('patient/api/status/', views.PatientStatusAPIView.as_view(), name='patient_status_api'),
```

- [ ] **Step 5: Run the tests**

```bash
python manage.py test core.tests.PatientStatusAPITest
```
Expected: `Ran 8 tests ... OK`

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/urls.py core/tests.py
git commit -m "feat: add PatientStatusAPIView with polling endpoint"
```

---

## Task 4: SubmitPainZonesView + Update PatientDashboardView

**Files:**
- Modify: `core/views.py`

- [ ] **Step 1: Write the test**

Append to `core/tests.py`:

```python
from .models import PainZoneReport

class SubmitPainZonesViewTest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='painpat', password='pass', role='patient'
        )
        self.client.login(username='painpat', password='pass')

    def test_valid_submission_creates_report(self):
        response = self.client.post('/patient/pain-zones/', {
            'zones': ['lower_back', 'tailbone'],
            'note': 'sharp pain',
        })
        self.assertRedirects(response, '/patient/')
        self.assertEqual(PainZoneReport.objects.filter(user=self.patient).count(), 1)
        report = PainZoneReport.objects.get(user=self.patient)
        self.assertEqual(sorted(report.zones), ['lower_back', 'tailbone'])
        self.assertEqual(report.note, 'sharp pain')

    def test_invalid_zone_does_not_create_report(self):
        response = self.client.post('/patient/pain-zones/', {
            'zones': ['made_up_zone'],
            'note': '',
        })
        self.assertEqual(response.status_code, 200)  # re-renders dashboard
        self.assertEqual(PainZoneReport.objects.filter(user=self.patient).count(), 0)

    def test_non_patient_forbidden(self):
        admin = User.objects.create_user(
            username='adminx', password='pass', role='admin'
        )
        self.client.login(username='adminx', password='pass')
        response = self.client.post('/patient/pain-zones/', {
            'zones': ['lower_back'],
        })
        self.assertEqual(response.status_code, 403)


class PatientDashboardViewTest(TestCase):
    def setUp(self):
        self.patient = User.objects.create_user(
            username='dashpat', password='pass', role='patient'
        )
        self.client.login(username='dashpat', password='pass')

    def test_dashboard_renders_with_zone_choices(self):
        response = self.client.get('/patient/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('zone_choices', response.context)
        self.assertEqual(len(response.context['zone_choices']), 8)

    def test_dashboard_context_has_no_frames_key(self):
        response = self.client.get('/patient/')
        self.assertNotIn('frames', response.context)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python manage.py test core.tests.SubmitPainZonesViewTest core.tests.PatientDashboardViewTest
```
Expected: mix of `404` and assertion failures.

- [ ] **Step 3: Update `PatientDashboardView` in `core/views.py`**

Replace the existing `PatientDashboardView.get` method:

```python
class PatientDashboardView(LoginRequiredMixin, View):
    login_url = 'login'

    def get(self, request, form=None):
        if request.user.role != User.ROLE_PATIENT:
            return redirect('home')
        if form is None:
            form = PainZoneReportForm()
        latest_pain_report = PainZoneReport.objects.filter(
            user=request.user
        ).order_by('-timestamp').first()
        return render(request, 'core/patient_dashboard.html', {
            'zone_choices': PREDEFINED_ZONES,
            'latest_pain_report': latest_pain_report,
            'form': form,
        })
```

- [ ] **Step 4: Add `SubmitPainZonesView` to `core/views.py`**

Add after `PatientDashboardView`:

```python
class SubmitPainZonesView(LoginRequiredMixin, View):
    login_url = 'login'

    def post(self, request):
        if request.user.role != User.ROLE_PATIENT:
            return HttpResponseForbidden("Patients only")

        form = PainZoneReportForm(request.POST)
        if form.is_valid():
            PainZoneReport.objects.create(
                user=request.user,
                zones=form.cleaned_data['zones'],
                note=form.cleaned_data['note'],
            )
            messages.success(request, "Pain zones submitted successfully")
            return redirect('patient_dashboard')

        # Validation failed — re-render dashboard with bound form
        return PatientDashboardView().get(request, form=form)
```

- [ ] **Step 5: Add the import for `PainZoneReportForm` and `PREDEFINED_ZONES` at the top of `core/views.py`**

Update the existing forms import line:

```python
from .forms import (
    CommentForm, AssignmentForm, UserForm,
    ClinicianProfileForm, PatientProfileForm,
    CustomUserCreationForm, PainZoneReportForm,
)
from .models import (
    User, PressureFrame, ClinicianProfile, Assignment,
    PatientProfile, Comment, PainZoneReport, PREDEFINED_ZONES,
)
```

- [ ] **Step 6: Register the URL**

Add to `core/urls.py`:

```python
path('patient/pain-zones/', views.SubmitPainZonesView.as_view(), name='submit_pain_zones'),
```

- [ ] **Step 7: Run the tests**

```bash
python manage.py test core.tests.SubmitPainZonesViewTest core.tests.PatientDashboardViewTest
```
Expected: `Ran 5 tests ... OK`

- [ ] **Step 8: Commit**

```bash
git add core/views.py core/urls.py core/tests.py
git commit -m "feat: add SubmitPainZonesView and update PatientDashboardView"
```

> **Note:** Do NOT manually verify the rendered page at this point. `PatientDashboardView` now passes different context (`zone_choices`, `form`) but the old template still references the removed `frames` variable. Django will silently render it empty — the page won't 500, but it will look broken. The template rewrite in Task 5 fixes this.

---

## Task 5: patient_dashboard.html Template

**Files:**
- Modify: `core/templates/core/patient_dashboard.html`

- [ ] **Step 1: Rewrite `core/templates/core/patient_dashboard.html` entirely**

```html
{% load static %}
{% extends 'core/base.html' %}
{% block title %}My Dashboard - Sensore{% endblock %}

{% block content %}
<div class="dashboard-header">
    <h2>My Pressure Dashboard</h2>
    <p>Your live pressure monitoring data</p>
</div>

{% if messages %}
  {% for message in messages %}
    <div class="alert alert-success">{{ message }}</div>
  {% endfor %}
{% endif %}

<div class="patient-layout">
    <!-- Left column: heatmap + metrics -->
    <div class="col-left card">
        <h3>Live Heatmap</h3>
        <canvas id="heatmapCanvas" width="320" height="320"></canvas>
        <div class="metrics-grid">
            <div class="metric-card">
                <h4>Peak Pressure Index</h4>
                <p class="metric-value" id="ppiValue">--</p>
            </div>
            <div class="metric-card">
                <h4>Contact Area</h4>
                <p class="metric-value" id="contactValue">--</p>
            </div>
        </div>
    </div>

    <!-- Right column: alert + time filters + chart -->
    <div class="col-right">
        <div id="alertBanner" class="alert">Connecting...</div>

        <div class="card">
            <h3>Pressure Over Time</h3>
            <div class="time-filters">
                <button class="btn btn-outline time-btn active" data-hours="1">Last Hour</button>
                <button class="btn btn-outline time-btn" data-hours="6">Last 6 Hours</button>
                <button class="btn btn-outline time-btn" data-hours="24">Last 24 Hours</button>
            </div>
            <canvas id="pressureChart" height="200"></canvas>
        </div>
    </div>
</div>

<!-- Pain zone reporting card -->
<div class="card pain-zone-card">
    <h3>Report Painful Areas</h3>
    <p>Select the areas where you feel discomfort so your clinician can see them.</p>

    {% if form.errors %}
        <div class="alert alert-danger">Please correct the errors below.</div>
    {% endif %}

    <form method="post" action="{% url 'submit_pain_zones' %}">
        {% csrf_token %}
        <div class="zone-checkboxes">
            {% for value, label in form.zones.field.choices %}
                <label class="zone-label">
                    <input type="checkbox" name="zones" value="{{ value }}"
                        {% if value in form.zones.value %}checked{% endif %}>
                    {{ label }}
                </label>
            {% endfor %}
        </div>
        {% if form.zones.errors %}
            <p class="error-text">{{ form.zones.errors.0 }}</p>
        {% endif %}

        <div class="form-group mt-3">
            <label for="id_note">Additional notes (optional)</label>
            {{ form.note }}
        </div>

        <button type="submit" class="btn btn-primary mt-3">Submit Report</button>
    </form>

    {% if latest_pain_report %}
        <div class="mt-3">
            <p><strong>Last submitted:</strong> {{ latest_pain_report.timestamp|date:"N j, Y H:i" }} UTC</p>
            <p><strong>Zones:</strong> {{ latest_pain_report.zones|join:", " }}</p>
        </div>
    {% endif %}
</div>
{% endblock %}

{% block scripts %}
<script src="{% static 'js/patient_dashboard.js' %}"></script>
{% endblock %}
```

- [ ] **Step 2: Verify the page renders without errors**

```bash
python manage.py runserver
```
Navigate to `http://localhost:8000/patient/` (logged in as patient1).
Expected: page loads, two-column layout visible, pain zone checkboxes shown, no 500 error.

- [ ] **Step 3: Commit**

```bash
git add core/templates/core/patient_dashboard.html
git commit -m "feat: rewrite patient dashboard template to two-column layout"
```

---

## Task 6: patient_dashboard.js

**Files:**
- Create: `core/static/js/patient_dashboard.js`

- [ ] **Step 1: Create `core/static/js/patient_dashboard.js`**

```javascript
(function () {
    'use strict';

    let currentHours = 1;
    let pressureChart = null;

    function initChart() {
        const ctx = document.getElementById('pressureChart').getContext('2d');
        pressureChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [{
                    label: 'High-pressure frames',
                    data: [],
                    backgroundColor: 'rgba(220, 53, 69, 0.6)',
                    borderColor: 'rgba(220, 53, 69, 1)',
                    borderWidth: 1,
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    }
                }
            }
        });
    }

    function setActiveButton(hours) {
        document.querySelectorAll('.time-btn').forEach(function (btn) {
            btn.classList.toggle('active', parseInt(btn.dataset.hours) === hours);
        });
    }

    function loadData(hours) {
        currentHours = hours;
        setActiveButton(hours);

        fetch('/patient/api/status/?hours=' + hours)
            .then(function (response) { return response.json(); })
            .then(function (data) {
                // Heatmap
                if (data.latest_matrix !== null && Array.isArray(data.latest_matrix)) {
                    drawHeatmap('heatmapCanvas', data.latest_matrix);
                }

                // Metrics
                var ppiEl = document.getElementById('ppiValue');
                var contactEl = document.getElementById('contactValue');
                ppiEl.textContent = data.latest_ppi !== null
                    ? parseFloat(data.latest_ppi).toFixed(1)
                    : '--';
                contactEl.textContent = data.latest_contact !== null
                    ? parseFloat(data.latest_contact).toFixed(1) + '%'
                    : '--';

                // Alert banner
                var banner = document.getElementById('alertBanner');
                if (data.alert) {
                    banner.className = 'alert alert-danger';
                    banner.textContent = '⚠ High pressure detected — please shift position';
                } else {
                    banner.className = 'alert alert-success';
                    banner.textContent = '✓ Pressure looks normal';
                }

                // Chart — replace arrays fully, do not mutate in place
                pressureChart.data.labels = data.chart_data.labels;
                pressureChart.data.datasets[0].data = data.chart_data.counts;
                pressureChart.update();
            })
            .catch(function () {
                // Silent fail — leave existing UI unchanged, keep polling
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        // 1. Build chart first
        initChart();
        // 2. Load initial data
        loadData(1);
        // 3. Start polling
        setInterval(function () { loadData(currentHours); }, 8000);

        // Wire time filter buttons
        document.querySelectorAll('.time-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                loadData(parseInt(btn.dataset.hours));
            });
        });
    });
}());
```

- [ ] **Step 2: Verify JS loads and polls**

```bash
python manage.py runserver
```
Open `http://localhost:8000/patient/` in browser. Open DevTools → Network tab.
Expected: a request to `/patient/api/status/?hours=1` appears on load and every ~8 seconds. No console errors.

- [ ] **Step 3: Verify heatmap renders if data exists**

If the DB has `PressureFrame` records for patient1, the heatmap canvas should show a coloured grid.
If not, create one quickly via the Django shell:
```bash
python manage.py shell
```
```python
from core.models import PressureFrame, User
import random
u = User.objects.get(username='patient1')
from django.utils import timezone
PressureFrame.objects.create(
    user=u,
    timestamp=timezone.now(),
    raw_matrix=[[random.randint(0, 4095) for _ in range(32)] for _ in range(32)],
    peak_pressure_index=4100.0,
    contact_area_percentage=55.0,
    high_pressure_flag=True,
)
exit()
```
Reload the patient dashboard. Expected: heatmap renders, alert banner shows red "⚠ High pressure detected".

- [ ] **Step 4: Commit**

```bash
git add core/static/js/patient_dashboard.js
git commit -m "feat: add patient_dashboard.js with polling, heatmap refresh, and chart"
```

---

## Task 7: Two-Column CSS

**Files:**
- Modify: `core/static/css/dashboard.css`

- [ ] **Step 1: Add styles to `core/static/css/dashboard.css`**

Append at the bottom of the file:

```css
/* Patient Dashboard Two-Column Layout */
.patient-layout {
    display: grid;
    grid-template-columns: 340px 1fr;
    gap: 1.5rem;
    align-items: start;
    margin-bottom: 1.5rem;
}

@media (max-width: 768px) {
    .patient-layout {
        grid-template-columns: 1fr;
    }
}

.col-left canvas#heatmapCanvas {
    display: block;
    max-width: 100%;
}

.metrics-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    margin-top: 1rem;
}

.metric-card {
    background: var(--light-color);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 0.75rem;
    text-align: center;
}

.metric-card h4 {
    font-size: 0.875rem;
    color: var(--text-secondary);
    margin-bottom: 0.25rem;
}

.metric-value {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--text-primary);
    margin: 0;
}

.time-filters {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.time-btn.active {
    background-color: var(--primary-color);
    color: white;
    border-color: var(--primary-color);
}

/* Pain Zone Card */
.pain-zone-card {
    margin-top: 1.5rem;
}

.zone-checkboxes {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 1rem 0;
}

.zone-label {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    background: var(--light-color);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 0.4rem 0.75rem;
    cursor: pointer;
    font-size: 0.9rem;
    user-select: none;
}

.zone-label:hover {
    border-color: var(--primary-color);
    background: #e8f0fe;
}

.zone-label input[type="checkbox"] {
    margin: 0;
}

.error-text {
    color: var(--danger-color);
    font-size: 0.875rem;
    margin-top: 0.25rem;
}
```

- [ ] **Step 2: Verify layout looks correct**

Reload `http://localhost:8000/patient/`.
Expected: heatmap and metrics on the left, alert + chart on the right. On mobile width (<768px) they stack vertically. Zone checkboxes appear as pill-style labels.

- [ ] **Step 3: Commit**

```bash
git add core/static/css/dashboard.css
git commit -m "feat: add two-column patient dashboard CSS and pain zone styles"
```

---

## Task 8: Login Page Privacy Note

**Files:**
- Modify: `core/templates/core/login.html`

- [ ] **Step 1: Add privacy sentence after the sign-in button**

In `core/templates/core/login.html`, find the closing `</button>` tag for the sign-in button (line 58) and add immediately after it:

```html
            <p class="privacy-note">Your data is private and only visible to you and your assigned clinician.</p>
```

- [ ] **Step 2: Add the style to `dashboard.css`**

Append to `core/static/css/dashboard.css`:

```css
.privacy-note {
    font-size: 0.8rem;
    color: var(--text-secondary);
    text-align: center;
    margin-top: 0.75rem;
}
```

- [ ] **Step 3: Verify**

Navigate to `http://localhost:8000/login/`.
Expected: small grey text "Your data is private..." appears below the Sign In button.

- [ ] **Step 4: Commit**

```bash
git add core/templates/core/login.html core/static/css/dashboard.css
git commit -m "feat: add privacy note to login page"
```

---

## Task 9: Full Regression Check

- [ ] **Step 1: Run all tests**

```bash
python manage.py test core
```
Expected: All tests pass with no errors.

- [ ] **Step 2: Manual smoke test**

Start the server: `python manage.py runserver`

Check the following:
1. Log in as `patient1` → redirects to `/patient/`
2. Dashboard shows two-column layout (heatmap left, chart right)
3. Alert banner shows correct state
4. Clicking "Last 6 Hours" updates the chart, button highlights
5. After 8 seconds, data refreshes (watch Network tab)
6. Submit pain zone form with valid zones → success message, redirects back
7. Submit pain zone form with no zones selected → stays on dashboard, shows error
8. Log in as `clinician1` → cannot access `/patient/api/status/` (403)
9. Login page shows privacy note

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
git add -p
git commit -m "fix: address issues found in regression smoke test"
```
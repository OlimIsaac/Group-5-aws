# Sensore — Graphene Trace Pressure Mapping Platform

Full-stack Django web application for continuous pressure ulcer prevention,
built around the **Sensore** e-textile mat system by Graphene Trace Ltd, Chelmsford.

---

## User Stories

| # | Role | Story | Delivered by |
|---|------|-------|-------------|
| US1 | Patient | Live heatmap of sitting position | 32×32 Canvas heatmap, frame scrubber, animated hot-zone rings, 30 s auto-poll |
| US2 | Patient | Simple explanations of data | Per-frame plain-English panel: pressure level, contact coverage, L/R balance, recommendation |
| US3 | Patient | Add comments to specific times | Notes panel linked to the exact frame; clinician replies appear threaded |
| US4 | Patient | View & download medical history report | Full report page + PDF download via ReportLab |
| US5 | Clinician | Automatic pressure risk calculation | PPI, Contact Area %, Asymmetry Score, composite Risk Score 0–100 → low/moderate/high/critical |

---

## Quick Start

### Linux / macOS

```bash
# 1. Place de0e9b2c_20251013.csv into sample_data/ (optional but recommended)
mkdir -p sample_data
cp /path/to/de0e9b2c_20251013.csv sample_data/

# 2. Run setup (creates venv, installs deps, migrates, seeds data)
chmod +x setup.sh && ./setup.sh

# 3. Start the server
source venv/bin/activate
python manage.py runserver
```

### Windows

```bat
mkdir sample_data
copy de0e9b2c_20251013.csv sample_data\
setup.bat
venv\Scripts\activate
python manage.py runserver
```

Open **http://127.0.0.1:8000**

---

## Login Credentials

| Role | Username | Password | Data |
|------|----------|----------|------|
| Patient (real CSV) | `de0e9b2c` | `patient123` | 4,190 real hardware frames |
| Patient (demo) | `patient_001` … `patient_005` | `patient123` | Synthetic sitting patterns |
| Clinician | `dr_smith` | `clinic123` | Sees all patients |
| Admin | `admin` | `admin123` | Full access |

---

## Real CSV File — de0e9b2c_20251013.csv

This is actual Sensore mat hardware output. Key characteristics:

| Property | Value |
|----------|-------|
| Format | Format A — 32 columns × 32 rows per frame |
| Total frames | 4,190 |
| Session date (from filename) | 2025-10-13 |
| Sensor / patient ID | de0e9b2c |
| Estimated duration | ~34.9 hours at 30 s/frame |
| Raw value scale | 0 – 705 (not 1–4095 as in the case study spec) |
| Zero = no contact | ✓ (0 means no reading, values jump to ~20 at lightest contact) |

### Scale normalisation

The application automatically normalises any CSV file on upload:

1. **Detect scale** — read all raw values, find the global maximum (705)
2. **Two-pass normalisation** — scale every frame by `4095 / global_max`
   so that relative pressures *between frames* are preserved
3. **Store** — SensorFrame.data holds 1024 integers in 0–4095 range

A per-frame normalisation would force every frame to 4095, destroying
time-variation. The global-max approach correctly reflects that Frame 100
(raw max 598) has lower peak pressure than Frame 1000 (raw max 614).

### Import command

```bash
# Import de0e9b2c_20251013.csv from sample_data/ (default path)
python manage.py import_real_csv

# Or specify a path explicitly
python manage.py import_real_csv --path /some/other/path/de0e9b2c_20251013.csv

# Limit frames for quick testing
python manage.py import_real_csv --max-frames 200
```

---

## Project Structure

```
sensore_project/
├── manage.py
├── requirements.txt
├── setup.sh / setup.bat
├── generate_sample_csvs.py     # Synthetic test CSVs in real 0-705 scale
├── docs/
│   └── design_documentation.html  # Wireframes + DB schema (open in browser)
├── sample_data/                # Place de0e9b2c_20251013.csv here
│
├── sensore_project/            # Django config (settings, urls, wsgi)
│
├── accounts/                   # Auth + UserProfile (patient/clinician/admin)
│   └── migrations/
│
├── sensore/                    # Core application
│   ├── models.py               # SensorSession, SensorFrame, PressureMetrics,
│   │                           #   Comment, PressureAlert, Report
│   ├── views.py                # Page views + 10 REST API endpoints
│   ├── utils.py                # Analysis: PPI, Contact Area, Asymmetry,
│   │                           #   Risk Score, plain-English, normalise_frame()
│   ├── csv_upload.py           # CSV parser: Format A/B, two-pass normalisation,
│   │                           #   filename date detection
│   ├── urls.py
│   ├── admin.py
│   ├── migrations/
│   └── management/commands/
│       ├── load_sample_data.py     # Seeds 5 synthetic patients
│       └── import_real_csv.py      # Imports de0e9b2c_20251013.csv
│
└── templates/
    ├── base.html                        # Design system (navy/teal theme)
    ├── accounts/login.html
    └── sensore/
        ├── patient_dashboard.html       # Heatmap · Metrics · Plain-English · Notes
        ├── clinician_dashboard.html     # Patient list · Alerts · Replies · Flag
        ├── report.html                  # Medical history + PDF download
        └── upload_csv.html              # Drag-and-drop CSV import + live preview
```

---

## REST API Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET  | `/api/session/<id>/frames/`     | All frames with metrics |
| GET  | `/api/session/<id>/latest/`     | Latest frame |
| GET  | `/api/session/<id>/metrics/`    | Timeline for Chart.js |
| GET  | `/api/session/<id>/comments/`   | Patient notes + clinician replies |
| POST | `/api/session/<id>/comment/`    | Add timestamped note |
| POST | `/api/session/<id>/flag/`       | Toggle clinician review flag |
| GET  | `/api/frame/<id>/`              | Single frame + metrics |
| POST | `/api/alert/<id>/acknowledge/`  | Dismiss an alert |
| GET  | `/api/patient/<id>/sessions/`   | Patient session list (clinician) |
| POST | `/api/comment/<id>/reply/`      | Clinician reply to patient note |

---

## Pressure Analysis Algorithms

### Peak Pressure Index (PPI)
Highest recorded pressure in a frame, **excluding contact zones smaller
than 10 pixels** (per Graphene Trace spec). Uses SciPy connected-component
labelling when available; falls back to threshold-based max.

### Contact Area %
`pixels_above_threshold / 1024 × 100`

### Asymmetry Score (0–100)
`|left_pressure_sum – right_pressure_sum| / total_pressure × 100`

### Risk Score (0–100)
```
Risk = PPI component (0–50)
     + Asymmetry component (0–30)
     + Contact area component (0–20)

Low < 25  ·  Moderate 25–50  ·  High 50–75  ·  Critical ≥ 75
```

---

## Pages

| URL | Role | Description |
|-----|------|-------------|
| `/` | All | Redirects to role-appropriate dashboard |
| `/accounts/login/` | All | Login page |
| `/patient/` | Patient | Live heatmap, metrics, notes |
| `/clinician/` | Clinician | Patient overview, alerts, replies |
| `/report/` | Patient | Own medical history + PDF |
| `/report/<id>/` | Clinician | Patient report + PDF |
| `/upload/` | All | CSV import with live preview |
| `/admin/` | Admin | Django admin panel |

---

## Production Deployment

```bash
# Switch to PostgreSQL in settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'sensore_db', 'USER': 'sensore', 'PASSWORD': '...', 'HOST': 'localhost'
    }
}

# Install and run Gunicorn
pip install gunicorn whitenoise
gunicorn sensore_project.wsgi:application --bind 0.0.0.0:8000

# Security settings
DEBUG = False
SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
ALLOWED_HOSTS = ['yourdomain.com']
SECURE_SSL_REDIRECT = True
```

---

## Design Documentation

Open `docs/design_documentation.html` in any browser for:
- Interactive wireframes for all 5 screens (tabbed)
- Full database schema (8 tables with field types)
- Relationship table with annotations
- Component-level descriptions of every page

---

© Graphene Trace Ltd · Sensore Platform · Chelmsford

# Sensore

Sensore is a Django pressure-monitoring web app for patients and clinicians. It visualises 32x32 pressure frames, calculates pressure risk, stores timestamped notes, and generates downloadable medical history reports.

## What It Does

- Live heatmap playback for patient sitting pressure
- Time-view switching (1h / 6h / 24h) for trend tracking
- Plain-English pressure explanations for patients
- Timestamp-linked patient comments and clinician replies
- Pain-area marking (body zones + precise heatmap points)
- PDF medical history reports for patients and clinicians
- CSV medical history export for records and audits
- Automatic risk scoring and alert generation for clinicians
- CSV upload/import tools for session data

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Run migrations.
4. Load sample data.
5. Start the development server.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py load_sample_data
python manage.py runserver
```

## Environment Variables

- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG` (`True` or `False`)
- `DJANGO_ALLOWED_HOSTS` (comma-separated host list)
- `DJANGO_CSRF_TRUSTED_ORIGINS` (comma-separated https origins)
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_SECURE_HSTS_SECONDS`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `DJANGO_SECURE_HSTS_PRELOAD`
- `DJANGO_SESSION_COOKIE_SECURE`
- `DJANGO_CSRF_COOKIE_SECURE`
- `DJANGO_SESSION_COOKIE_SAMESITE`
- `DJANGO_CSRF_COOKIE_SAMESITE`
- `DJANGO_SECURE_REFERRER_POLICY`
- `DJANGO_SECURE_PROXY_SSL_HEADER`
- `DJANGO_DB_CONN_MAX_AGE`

## Demo Accounts

- Admin: `admin` / `admin123`
- Clinician: `dr_smith` / `clinic123`
- Patient: `patient_001` / `patient123`

## Main Routes

- Login: `/accounts/login/`
- Patient dashboard: `/patient/`
- Clinician dashboard: `/clinician/`
- Upload CSV: `/upload/`
- Report: `/report/`
- Report CSV export: `/report/?download_csv=1`

## Data Commands

- Load sample users and sessions:
  - `python manage.py load_sample_data`
- Import the bundled real CSV session:
  - `python manage.py import_real_csv --path sample_data/de0e9b2c_20251013.csv`
- Generate large noisy preview datasets:
  - `python manage.py generate_garbage_data --patients 12 --sessions 6 --frames 90 --comments 4`

## Validation

```bash
python manage.py check
python manage.py check --deploy
python manage.py migrate --noinput
python manage.py test
python test_auth.py
python test_login.py
```

## Notes

- The active settings module is `sensore_project.settings`.
- The legacy `sensore.settings` module re-exports the same production settings for compatibility.
- The app uses SQLite locally by default.

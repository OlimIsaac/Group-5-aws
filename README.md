# Sensore

Medical dashboard application for pressure ulcer prevention built with Django and PostgreSQL.

## Features
- Role-based accounts: admin, clinician, patient
- Processing of 32x32 pressure map CSV data
- Heatmap visualization and metrics (PPI, contact area)
- Commenting system linked to frames
- PDF report generation
- REST API endpoints for live updates

## Setup
1. Create virtual environment and activate:
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1  # or venv\Scripts\activate on Windows
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ``` the upload and anlyze ffinnished
3. Configure environment variables (see `sensore/settings.py`):
   - `DJANGO_SECRET_KEY`
   - `DJANGO_DEBUG`
   - Postgres connection vars: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
4. Initialize database:
   ```bash
   python manage.py migrate
   ```
5. Create superuser:
   ```bash
   python manage.py createsuperuser
   ```
6. Load initial data or ingest CSVs using utility functions or the web upload page.
7. Run development server:
   ```bash
   python manage.py runserver
   ```

## What was fixed

## Uploading CSV data for live heatmap
- Admins can upload patient CSVs from the admin dashboard via:
  - `http://127.0.0.1:8000/manage/patient-csv-upload/`
- The app also supports a generic upload page at:
  - `http://127.0.0.1:8000/upload/csv/`
- After uploading CSV data, the system can generate pressure frames and heatmap analysis.
- If you do not have sensor/pressure data loaded, the live heatmap and reports will not display because there is no data to analyze.

## Notes
```
sensore/
├─ manage.py
├─ sensore/          # project config
│  ├─ settings.py
│  ├─ urls.py
│  └─ wsgi.py
└─ core/             # main application
   ├─ migrations/
   ├─ models.py
   ├─ views.py
   ├─ serializers.py
   ├─ urls.py
   ├─ forms.py
   ├─ utils.py       # CSV ingestion and metric calculation
   ├─ templates/
   └─ static/
```

## Notes
- Use Django REST Framework for API endpoints (to be added).
- Chart.js is referenced in frontend templates (to be created).
- PDF reports implemented using ReportLab (not yet coded).
- Role-based permission decorators available in `core/permissions.py` (to be added).

## Migration Strategy
1. After modeling changes, run `python manage.py makemigrations`.
2. Inspect generated migration files, then apply with `python manage.py migrate`.
3. Use `runscript` or custom management commands for bulk ingestion of CSV datasets.

## Future Work
- Complete views, serializers, and templates for dashboards
- Implement heatmap JS and Chart.js graphs
- Add REST endpoints and authentication tokens
- Build reporting and prediction logic
- Styling and responsive layout

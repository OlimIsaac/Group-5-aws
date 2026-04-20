# User Stories Implementation Status

## Summary
Code review of patient dashboard and related features shows **2 out of 5 user stories fully implemented**, with 2 partially implemented and 1 missing entirely.

---

## Detailed Status

### ✅ User Story #1: Live Heatmap (COMPLETE)
**Status:** FULLY IMPLEMENTED

**Patient-facing features:**
- Live pressure heatmap with 320x320 canvas visualization
- Real-time peak pressure index (PPI) metric display
- Contact area percentage metric display
- Pressure over time chart with configurable time filters (1, 6, 24 hours)
- Interactive annotation tool to mark painful areas on heatmap
- Pain marks visualization overlay

**Files:**
- [core/templates/core/patient_dashboard.html](core/templates/core/patient_dashboard.html) - UI rendering
- [core/static/js/patient_dashboard.js](core/static/js/patient_dashboard.js) - Heatmap rendering logic
- [core/views.py](core/views.py) - `PatientStatusAPIView` provides live data via `/patient/api/status/` endpoint

**Location on dashboard:** Left column titled "Live Heatmap"

---

### ⚠️ User Story #2: Simple Explanations of Data (MISSING)
**Status:** NOT IMPLEMENTED

**What's missing:**
- No explanatory text explaining what metrics mean (PPI, contact area, pressure readings)
- No tooltips or hover help for data visualization
- No educational content about normal vs concerning pressure values
- No guidance on how to interpret patterns in the pressure chart

**Required additions:**
1. Add tooltip descriptions to metric cards
2. Add legend/key for pressure chart interpretation
3. Add info boxes explaining what values are healthy/concerning
4. Add context-specific guidance in each section

**Suggested implementation:**
- Add info icons (ℹ️) with Bootstrap tooltips on metrics
- Create a "Help" or "Understanding Your Data" section
- Add color coding for pressure levels with explanations

---

### ⚠️ User Story #3: Add Comments to Specific Times (PARTIALLY IMPLEMENTED)
**Status:** INFRASTRUCTURE EXISTS BUT PATIENT UI MISSING

**What exists:**
- `Comment` model in database stores comments linked to specific `PressureFrame`
- `ReplyCommentView` allows clinicians to reply to patient comments
- Clinician dashboard displays patient comments (`patient_comments` list)
- Comments shown on [clinician_dashboard.html](core/templates/core/clinician_dashboard.html)

**What's missing:**
- **NO patient-facing UI to create comments on specific pressure frames/times**
- Patient can only submit generic "Feedback" (not timestamped comments on specific data points)
- No URL endpoint for patients to add comments
- Patient dashboard doesn't show a way to comment on specific time periods in the pressure chart

**Current feedback mechanism (insufficient):**
- Patient can submit feedback via [core/templates/core/feedback_submit.html](core/templates/core/feedback_submit.html)
- But this is generic feedback, not tied to specific pressure timestamps
- Feedback is linked to `SensorData`, not to `PressureFrame` timestamps

**Required implementation:**
1. Create `PatientAddCommentView` (POST endpoint)
2. Add UI in patient dashboard to add comments on:
   - Specific pressure chart time points
   - Or specific heatmap annotations
3. Link comments to actual `PressureFrame` timestamps
4. Display patient comments alongside pressure data

---

### ❌ User Story #4: View and Download Medical History Report (PARTIALLY IMPLEMENTED)
**Status:** FUNCTION EXISTS BUT NOT EXPOSED IN UI

**What exists:**
- Report generation function: `generate_patient_report()` in [core/reports.py](core/reports.py)
- Function creates PDF with:
  - Patient name
  - Pressure data summary (timestamp, PPI, contact area for up to 50 frames)
  - Proper PDF formatting using ReportLab

**What's missing:**
- **NO URL route for patients to access their report**
- **NO button/link in patient dashboard to download report**
- No UI to select date range or formatting options
- Function exists but is never called anywhere

**Current code:**
```python
def generate_patient_report(user, frames):
    """Return an HttpResponse with PDF containing summary for given frames."""
    # Creates PDF but never called from any view
```

**Required implementation:**
1. Create `PatientReportView` that:
   - Retrieves patient's pressure frames
   - Calls `generate_patient_report()`
   - Returns PDF download response
2. Add URL route: `path('patient/report/', views.PatientReportView.as_view(), name='patient_report')`
3. Add download button to patient dashboard template
4. Consider adding date range filters for report generation

---

### ✅ User Story #5: Calculate Pressure Risk Automatically (COMPLETE)
**Status:** FULLY IMPLEMENTED (Clinician side)

**Features:**
- System automatically categorizes pressure frames as HIGH, AVERAGE, or LOW pressure
- Based on thresholds defined in [core/utils.py](core/utils.py):
  - `HIGH_PRESSURE_THRESHOLD`
  - `LOW_PRESSURE_THRESHOLD`
- Clinician dashboard displays:
  - High-pressure events table with peak pressure values
  - Average-pressure events table
  - Low-pressure events table
  - Filterable alert view

**Implementation:**
- [core/views.py](core/views.py) - `ClinicianDashboardView`:
  ```python
  high_pressure_events = list(
      base_qs.filter(peak_pressure_index__gte=HIGH_PRESSURE_THRESHOLD)[:20]
  )
  ```
- Uses pressure frame `high_pressure_flag` and `peak_pressure_index` fields

**Location on clinician dashboard:** "Pressure Alerts" section with HIGH/AVERAGE/LOW filters

---

## Implementation Priority

### High Priority (Missing Core Features)
1. **Implement User Story #2** (Simple Explanations) - Add 1-2 hours
   - Add tooltips and info sections to explain metrics
   
2. **Implement User Story #4** (Report Download) - Add 2-3 hours
   - Create view, URL route, and dashboard button
   - Most work is already done (report function exists)

3. **Implement User Story #3 Comments UI** (Patient comment creation) - Add 3-4 hours
   - Create backend endpoint
   - Add frontend UI for comment creation
   - Link to pressure frame timestamps

---

## Files to Modify

For **User Story #2 (Explanations):**
- [core/templates/core/patient_dashboard.html](core/templates/core/patient_dashboard.html)

For **User Story #3 (Comments):**
- [core/views.py](core/views.py) - Add `PatientAddCommentView`
- [core/urls.py](core/urls.py) - Add comment creation route
- [core/templates/core/patient_dashboard.html](core/templates/core/patient_dashboard.html)
- [core/static/js/patient_dashboard.js](core/static/js/patient_dashboard.js)

For **User Story #4 (Report Download):**
- [core/views.py](core/views.py) - Add `PatientReportView`
- [core/urls.py](core/urls.py) - Add report route
- [core/templates/core/patient_dashboard.html](core/templates/core/patient_dashboard.html)

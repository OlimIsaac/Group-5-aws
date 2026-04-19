(function() {
    'use strict';

    function formatDateTime(iso) {
        if (!iso) return 'n/a';
        try {
            var d = new Date(iso);
            return d.toLocaleString();
        } catch (e) {
            return iso;
        }
    }

    function renderPatientSummary(data) {
        var flaggedEl = document.getElementById('flaggedEvents');
        if (!flaggedEl) return;

        if (!data.patients || data.patients.length === 0) {
            flaggedEl.textContent = 'No patients assigned yet.';
            return;
        }

        var highPressureCount = data.patients.filter(function(patient) {
            return patient.high_pressure;
        }).length;
        var summary = [
            'Assigned patients: ' + data.patients.length,
            'High pressure alerts: ' + highPressureCount,
        ];

        var lines = summary.map(function(line) {
            var div = document.createElement('div');
            div.textContent = line;
            return div;
        });
        flaggedEl.innerHTML = '';
        lines.forEach(function(line) { flaggedEl.appendChild(line); });
    }

    function updatePatientHeatmaps(data) {
        if (!data.patients) return;

        data.patients.forEach(function(patient) {
            if (!patient.id) return;
            var wrapper = document.querySelector('[data-patient-id="' + patient.id + '"]');
            if (!wrapper) return;

            var heatmapCanvas = wrapper.querySelector('.patient-heatmap');
            var annotCanvas = wrapper.querySelector('.patient-annotation');
            if (heatmapCanvas && patient.latest_matrix) {
                try {
                    drawHeatmapOnCanvas(heatmapCanvas, patient.latest_matrix);
                } catch (e) {
                    console.error('Error drawing heatmap for patient', patient.id, e);
                }
            }
            if (annotCanvas && Array.isArray(patient.annotation_cells)) {
                try {
                    drawAnnotationOnCanvas(annotCanvas, patient.annotation_cells);
                } catch (e) {
                    console.error('Error drawing annotation for patient', patient.id, e);
                }
            }

            var card = wrapper.closest('.clinician-patient-card');
            if (card) {
                var noteEl = card.querySelector('.annotation-note');
                if (noteEl && patient.annotation_note) {
                    noteEl.textContent = 'Pain marks — reported ' + formatDateTime(patient.annotation_timestamp);
                }
            }
        });
    }

    function fetchClinicianDashboardData() {
        fetch('/clinician/api/dashboard/')
            .then(function(response) { return response.json(); })
            .then(function(data) {
                renderPatientSummary(data);
                updatePatientHeatmaps(data);
            })
            .catch(function() {
                var flaggedEl = document.getElementById('flaggedEvents');
                if (flaggedEl) {
                    flaggedEl.textContent = 'Unable to refresh clinician dashboard data.';
                }
            });
    }

    document.addEventListener('DOMContentLoaded', function() {
        fetchClinicianDashboardData();
        setInterval(fetchClinicianDashboardData, 10000);
    });
})();

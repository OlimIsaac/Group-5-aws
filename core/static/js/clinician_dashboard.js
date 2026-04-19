(function () {
    'use strict';

    var currentPatientId = null;
    var trendChart = null;

    function formatDateTime(iso) {
        if (!iso) {
            return 'n/a';
        }
        try {
            return new Date(iso).toLocaleString();
        } catch (e) {
            return iso;
        }
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function clearCanvas(canvas) {
        if (!canvas) {
            return;
        }
        var ctx = canvas.getContext('2d');
        if (!ctx) {
            return;
        }
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    function setStatus(message, cssClass) {
        var el = document.getElementById('clinicianDetailStatus');
        if (!el) {
            return;
        }
        el.textContent = message || '';
        el.className = 'annotation-status' + (cssClass ? ' ' + cssClass : '');
    }

    function updateHeader(patient, reportUrl) {
        var nameEl = document.getElementById('clinicianDetailName');
        var emailEl = document.getElementById('clinicianDetailEmail');
        var reportEl = document.getElementById('clinicianReportLink');
        var csvEl = document.getElementById('clinicianReportCsvLink');

        if (nameEl) {
            nameEl.textContent = patient && patient.name ? patient.name : 'Patient Details';
        }
        if (emailEl) {
            emailEl.textContent = patient && patient.email ? patient.email : '';
        }
        if (reportEl && reportUrl) {
            reportEl.href = reportUrl;
        }
        if (csvEl && reportUrl) {
            csvEl.href = reportUrl + '?download=1';
        }
    }

    function renderHeatmap(latest, annotation) {
        var heatmapCanvas = document.getElementById('clinicianHeatmapCanvas');
        var annotationCanvas = document.getElementById('clinicianAnnotationCanvas');
        var annotationInfo = document.getElementById('clinicianAnnotationInfo');

        if (heatmapCanvas && latest && Array.isArray(latest.matrix)) {
            drawHeatmapOnCanvas(heatmapCanvas, latest.matrix);
        } else {
            clearCanvas(heatmapCanvas);
        }

        if (annotationCanvas) {
            drawAnnotationOnCanvas(annotationCanvas, (annotation && Array.isArray(annotation.cells)) ? annotation.cells : []);
        }

        if (annotationInfo) {
            if (annotation && annotation.cells && annotation.cells.length > 0) {
                annotationInfo.textContent = 'Pain marks: ' + annotation.cells.length + ' cells. Last update: ' + formatDateTime(annotation.timestamp);
            } else {
                annotationInfo.textContent = 'No pain marks submitted.';
            }
        }
    }

    function renderMetrics(latest) {
        var ppiEl = document.getElementById('clinicianPpi');
        var contactEl = document.getElementById('clinicianContact');
        var scoreEl = document.getElementById('clinicianRiskScore');
        var levelEl = document.getElementById('clinicianRiskLevel');
        var tsEl = document.getElementById('clinicianLatestTimestamp');

        if (!latest) {
            if (ppiEl) ppiEl.textContent = '--';
            if (contactEl) contactEl.textContent = '--';
            if (scoreEl) scoreEl.textContent = '--';
            if (levelEl) levelEl.textContent = '--';
            if (tsEl) tsEl.textContent = 'Latest frame: n/a';
            return;
        }

        if (ppiEl) ppiEl.textContent = latest.peak_pressure_index != null ? Number(latest.peak_pressure_index).toFixed(1) : '--';
        if (contactEl) contactEl.textContent = latest.contact_area_percentage != null ? Number(latest.contact_area_percentage).toFixed(1) + '%' : '--';
        if (scoreEl) scoreEl.textContent = latest.risk_score != null ? Number(latest.risk_score).toFixed(1) : '--';
        if (levelEl) levelEl.textContent = latest.risk_level ? String(latest.risk_level).toUpperCase() : '--';
        if (tsEl) tsEl.textContent = 'Latest frame: ' + formatDateTime(latest.timestamp);
    }

    function renderFrames(rows) {
        var body = document.getElementById('clinicianFrameRows');
        if (!body) {
            return;
        }

        if (!rows || rows.length === 0) {
            body.innerHTML = '<tr><td colspan="6" class="text-secondary">No pressure frames available.</td></tr>';
            return;
        }

        var html = rows.slice(0, 30).map(function (row) {
            return '<tr>' +
                '<td>' + formatDateTime(row.timestamp) + '</td>' +
                '<td>' + Number(row.peak_pressure_index).toFixed(1) + '</td>' +
                '<td>' + Number(row.contact_area_percentage).toFixed(1) + '%</td>' +
                '<td>' + Number(row.risk_score).toFixed(1) + '</td>' +
                '<td>' + String(row.risk_level || '').toUpperCase() + '</td>' +
                '<td>' + (row.comment_count || 0) + '</td>' +
            '</tr>';
        }).join('');

        body.innerHTML = html;
    }

    function renderComments(comments) {
        var list = document.getElementById('clinicianCommentList');
        if (!list) {
            return;
        }

        if (!comments || comments.length === 0) {
            list.textContent = 'No comments from this patient yet.';
            return;
        }

        list.innerHTML = '';
        comments.slice(0, 20).forEach(function (comment) {
            var item = document.createElement('div');
            item.className = 'comment-item';
            item.innerHTML =
                '<div class="comment-meta">Patient note at ' + formatDateTime(comment.frame_timestamp) + '</div>' +
                '<div class="comment-text">' + escapeHtml(comment.text) + '</div>' +
                (comment.clinician_reply ? '<div class="comment-reply"><strong>Clinician reply:</strong> ' + escapeHtml(comment.clinician_reply) + '</div>' : '');
            list.appendChild(item);
        });
    }

    function renderTrendChart(trend) {
        var canvas = document.getElementById('clinicianTrendChart');
        if (!canvas || typeof Chart === 'undefined') {
            return;
        }

        if (trendChart) {
            trendChart.destroy();
            trendChart = null;
        }

        var labels = (trend && Array.isArray(trend.labels)) ? trend.labels : [];
        var ppi = (trend && Array.isArray(trend.ppi)) ? trend.ppi : [];
        var risk = (trend && Array.isArray(trend.risk)) ? trend.risk : [];

        trendChart = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'PPI',
                        data: ppi,
                        borderColor: 'rgba(37, 99, 235, 1)',
                        backgroundColor: 'rgba(37, 99, 235, 0.2)',
                        pointRadius: 1,
                        tension: 0.25,
                        yAxisID: 'y',
                    },
                    {
                        label: 'Risk',
                        data: risk,
                        borderColor: 'rgba(220, 53, 69, 1)',
                        backgroundColor: 'rgba(220, 53, 69, 0.2)',
                        pointRadius: 1,
                        tension: 0.25,
                        yAxisID: 'y1',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        suggestedMax: 4095,
                        title: { display: true, text: 'PPI' },
                    },
                    y1: {
                        beginAtZero: true,
                        suggestedMax: 100,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        title: { display: true, text: 'Risk' },
                    }
                }
            }
        });
    }

    function setActivePatient(patientId) {
        document.querySelectorAll('.clinician-patient-item').forEach(function (item) {
            item.classList.toggle('active', Number(item.dataset.patientId) === Number(patientId));
        });
    }

    function updateSidebarSummary(data) {
        if (!data || !Array.isArray(data.patients)) {
            return;
        }

        var byId = {};
        data.patients.forEach(function (patient) {
            byId[String(patient.id)] = patient;
        });

        document.querySelectorAll('.clinician-patient-item').forEach(function (item) {
            var patient = byId[item.dataset.patientId];
            if (!patient) {
                return;
            }

            var metaEl = item.querySelector('.clinician-patient-item-meta');
            if (!metaEl) {
                return;
            }

            var riskLevel = (patient.latest_risk_level || 'none').toLowerCase();
            var ppiText = patient.latest_ppi != null ? Number(patient.latest_ppi).toFixed(1) : '--';
            var riskText = (patient.latest_risk_level || 'no-data').toUpperCase();

            metaEl.innerHTML =
                '<span class="risk-pill risk-' + riskLevel + '">' + riskText + '</span>' +
                '<span>PPI ' + ppiText + '</span>';
        });
    }

    function loadPatientDetail(patientId, silent) {
        if (!silent) {
            setStatus('Loading patient details...', '');
        }

        fetch('/clinician/api/patient/' + patientId + '/')
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to load patient data');
                }
                return response.json();
            })
            .then(function (data) {
                updateHeader(data.patient, data.report_url);
                renderHeatmap(data.latest, data.annotation);
                renderMetrics(data.latest);
                renderFrames(data.recent_frames || []);
                renderComments(data.recent_comments || []);
                renderTrendChart(data.trend || {});
                setStatus('Updated ' + new Date().toLocaleTimeString(), 'saved');
            })
            .catch(function () {
                setStatus('Unable to load patient details.', 'error');
            });
    }

    function refreshSidebar() {
        fetch('/clinician/api/dashboard/')
            .then(function (response) { return response.json(); })
            .then(function (data) {
                updateSidebarSummary(data);
            })
            .catch(function () {
                // keep existing sidebar state
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        var patientItems = Array.prototype.slice.call(document.querySelectorAll('.clinician-patient-item'));
        if (patientItems.length === 0) {
            return;
        }

        patientItems.forEach(function (item) {
            item.addEventListener('click', function () {
                var patientId = Number(item.dataset.patientId || 0);
                if (!patientId) {
                    return;
                }
                currentPatientId = patientId;
                setActivePatient(currentPatientId);
                loadPatientDetail(currentPatientId, false);
            });
        });

        var firstPatient = Number(patientItems[0].dataset.patientId || 0);
        if (firstPatient) {
            currentPatientId = firstPatient;
            setActivePatient(currentPatientId);
            loadPatientDetail(currentPatientId, false);
        }

        setInterval(function () {
            if (currentPatientId) {
                loadPatientDetail(currentPatientId, true);
            }
        }, 12000);

        setInterval(refreshSidebar, 15000);
    });
}());

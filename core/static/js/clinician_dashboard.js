(function () {
    'use strict';

    var currentPatientId = null;
    var trendChart = null;

    function getCsrfToken() {
        var csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
        return csrfMatch ? csrfMatch[1] : '';
    }

    function getDetailApiUrl(patientId) {
        var workspace = document.querySelector('.clinician-workspace');
        var template = workspace && workspace.dataset.detailApiTemplate
            ? workspace.dataset.detailApiTemplate
            : '/clinician/api/patient/0/';

        return template.replace('/0/', '/' + patientId + '/');
    }

    function getReplyApiUrl(commentId) {
        return '/clinician/api/comments/' + commentId + '/reply/';
    }

    function readInitialDetailData() {
        var script = document.getElementById('clinicianInitialDetailData');
        if (!script) {
            return null;
        }

        try {
            return JSON.parse(script.textContent || 'null');
        } catch (e) {
            return null;
        }
    }

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
            item.setAttribute('data-comment-id', comment.id);
            var existingReply = comment.clinician_reply
                ? '<div class="comment-reply"><strong>Clinician reply:</strong> ' + escapeHtml(comment.clinician_reply) + '</div>'
                : '';
            item.innerHTML =
                '<div class="comment-meta">Patient note at ' + formatDateTime(comment.frame_timestamp) + '</div>' +
                '<div class="comment-text">' + escapeHtml(comment.text) + '</div>' +
                existingReply +
                '<div class="clinician-reply-form">' +
                    '<textarea class="form-input clinician-reply-input" rows="2" placeholder="Write advice or follow-up"></textarea>' +
                    '<button type="button" class="btn btn-outline btn-sm clinician-reply-btn" data-comment-id="' + comment.id + '">Save Reply</button>' +
                '</div>';
            list.appendChild(item);
        });
    }

    function riskRank(level) {
        var value = String(level || 'none').toLowerCase();
        if (value === 'critical') return 4;
        if (value === 'high') return 3;
        if (value === 'moderate') return 2;
        if (value === 'low') return 1;
        return 0;
    }

    function parseIsoDate(isoText) {
        if (!isoText) {
            return 0;
        }
        var ms = Date.parse(isoText);
        return isFinite(ms) ? ms : 0;
    }

    function sortPatientItems(items, mode) {
        var sorted = items.slice();

        sorted.sort(function (a, b) {
            var riskA = riskRank(a.dataset.riskLevel);
            var riskB = riskRank(b.dataset.riskLevel);
            var tsA = parseIsoDate(a.dataset.latestTs);
            var tsB = parseIsoDate(b.dataset.latestTs);
            var nameA = String(a.dataset.patientName || '').toLowerCase();
            var nameB = String(b.dataset.patientName || '').toLowerCase();

            if (mode === 'name') {
                return nameA.localeCompare(nameB);
            }

            if (mode === 'recent') {
                if (tsA !== tsB) {
                    return tsB - tsA;
                }
                if (riskA !== riskB) {
                    return riskB - riskA;
                }
                return nameA.localeCompare(nameB);
            }

            if (riskA !== riskB) {
                return riskB - riskA;
            }
            if (tsA !== tsB) {
                return tsB - tsA;
            }
            return nameA.localeCompare(nameB);
        });

        return sorted;
    }

    function applySidebarControls() {
        var list = document.getElementById('clinicianPatientList');
        if (!list) {
            return;
        }

        var searchEl = document.getElementById('clinicianPatientSearch');
        var filterEl = document.getElementById('clinicianRiskFilter');
        var sortEl = document.getElementById('clinicianSortOrder');
        var countEl = document.getElementById('clinicianListCount');

        var searchText = (searchEl && searchEl.value ? searchEl.value : '').trim().toLowerCase();
        var riskFilter = filterEl ? filterEl.value : 'all';
        var sortMode = sortEl ? sortEl.value : 'risk';

        var items = Array.prototype.slice.call(list.querySelectorAll('.clinician-patient-item'));
        var sorted = sortPatientItems(items, sortMode);

        sorted.forEach(function (item) {
            list.appendChild(item);
        });

        var shownCount = 0;
        sorted.forEach(function (item) {
            var name = String(item.dataset.patientName || '').toLowerCase();
            var username = String(item.dataset.patientUsername || '').toLowerCase();
            var email = String(item.dataset.patientEmail || '').toLowerCase();
            var risk = String(item.dataset.riskLevel || 'none').toLowerCase();

            var matchesSearch = !searchText
                || name.indexOf(searchText) >= 0
                || username.indexOf(searchText) >= 0
                || email.indexOf(searchText) >= 0;

            var matchesRisk = false;
            if (riskFilter === 'all') {
                matchesRisk = true;
            } else if (riskFilter === 'high') {
                matchesRisk = (risk === 'high' || risk === 'critical');
            } else if (riskFilter === 'moderate') {
                matchesRisk = (risk === 'moderate' || risk === 'high' || risk === 'critical');
            } else {
                matchesRisk = risk === riskFilter;
            }

            var visible = matchesSearch && matchesRisk;
            item.style.display = visible ? '' : 'none';
            if (visible) {
                shownCount += 1;
            }
        });

        if (countEl) {
            countEl.textContent = 'Showing ' + shownCount + ' of ' + items.length + ' patients';
        }

        var activeItem = list.querySelector('.clinician-patient-item.active');
        if (activeItem && activeItem.style.display === 'none') {
            var firstVisible = sorted.find(function (item) { return item.style.display !== 'none'; });
            if (firstVisible) {
                var patientId = Number(firstVisible.dataset.patientId || 0);
                if (patientId) {
                    currentPatientId = patientId;
                    setActivePatient(patientId);
                    loadPatientDetail(patientId, false);
                }
            }
        }
    }

    function bindSidebarControls() {
        var searchEl = document.getElementById('clinicianPatientSearch');
        var filterEl = document.getElementById('clinicianRiskFilter');
        var sortEl = document.getElementById('clinicianSortOrder');

        if (searchEl) {
            searchEl.addEventListener('input', applySidebarControls);
        }
        if (filterEl) {
            filterEl.addEventListener('change', applySidebarControls);
        }
        if (sortEl) {
            sortEl.addEventListener('change', applySidebarControls);
        }

        applySidebarControls();
    }

    function submitCommentReply(commentId, replyText, buttonEl, cardEl) {
        if (!commentId) {
            return;
        }

        buttonEl.disabled = true;
        var originalText = buttonEl.textContent;
        buttonEl.textContent = 'Saving...';

        fetch(getReplyApiUrl(commentId), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({ reply: replyText }),
        })
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (data.error) {
                    setStatus(data.error, 'error');
                    return;
                }

                var replyEl = cardEl.querySelector('.comment-reply');
                if (!replyEl) {
                    replyEl = document.createElement('div');
                    replyEl.className = 'comment-reply';
                    cardEl.insertBefore(replyEl, cardEl.querySelector('.clinician-reply-form'));
                }
                replyEl.innerHTML = '<strong>Clinician reply:</strong> ' + escapeHtml(data.clinician_reply || replyText);
                setStatus('Reply saved.', 'saved');
            })
            .catch(function () {
                setStatus('Failed to save reply.', 'error');
            })
            .finally(function () {
                buttonEl.disabled = false;
                buttonEl.textContent = originalText;
            });
    }

    function bindCommentReplyActions() {
        var list = document.getElementById('clinicianCommentList');
        if (!list) {
            return;
        }

        list.addEventListener('click', function (event) {
            var target = event.target;
            if (!target || !target.classList || !target.classList.contains('clinician-reply-btn')) {
                return;
            }

            var commentId = Number(target.dataset.commentId || 0);
            var card = target.closest('.comment-item');
            if (!card) {
                return;
            }

            var input = card.querySelector('.clinician-reply-input');
            var replyText = input ? String(input.value || '').trim() : '';
            if (!replyText) {
                setStatus('Reply text is required.', 'error');
                return;
            }

            submitCommentReply(commentId, replyText, target, card);
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

        fetch(getDetailApiUrl(patientId))
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

                if (window.history && typeof window.history.replaceState === 'function') {
                    window.history.replaceState({}, '', '?patient=' + patientId);
                }
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
                applySidebarControls();
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

        var initialDetail = readInitialDetailData();
        if (initialDetail && initialDetail.patient) {
            updateHeader(initialDetail.patient, initialDetail.report_url);
            renderHeatmap(initialDetail.latest, initialDetail.annotation);
            renderMetrics(initialDetail.latest);
            renderFrames(initialDetail.recent_frames || []);
            renderComments(initialDetail.recent_comments || []);
            renderTrendChart(initialDetail.trend || {});
        }

        bindSidebarControls();
        bindCommentReplyActions();

        patientItems.forEach(function (item) {
            item.addEventListener('click', function (event) {
                if (!window.fetch) {
                    return;
                }

                event.preventDefault();
                var patientId = Number(item.dataset.patientId || 0);
                if (!patientId) {
                    return;
                }
                currentPatientId = patientId;
                setActivePatient(currentPatientId);
                loadPatientDetail(currentPatientId, false);
            });
        });

        var activeItem = document.querySelector('.clinician-patient-item.active');
        var activePatientId = Number((activeItem && activeItem.dataset.patientId) || patientItems[0].dataset.patientId || 0);
        if (activePatientId) {
            currentPatientId = activePatientId;
            setActivePatient(currentPatientId);

            if (!initialDetail) {
                loadPatientDetail(currentPatientId, true);
            }
        }

        setInterval(function () {
            if (currentPatientId) {
                loadPatientDetail(currentPatientId, true);
            }
        }, 12000);

        setInterval(refreshSidebar, 15000);
    });
}());

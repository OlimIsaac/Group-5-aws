(function () {
    'use strict';

    var currentPatientId = null;
    var trendChart = null;

    function getCsrfToken() {
        var csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
        return csrfMatch ? csrfMatch[1] : '';
    }

    function getDetailApiUrl(patientId) {
        var workspace = document.querySelector('.clin-workspace');
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

    function normaliseLocalMatrix(matrix) {
        if (!Array.isArray(matrix)) {
            return null;
        }

        if (matrix.length === 32) {
            var rows = [];
            for (var r = 0; r < 32; r++) {
                if (!Array.isArray(matrix[r]) || matrix[r].length < 32) {
                    return null;
                }
                var row = [];
                for (var c = 0; c < 32; c++) {
                    var v = Number(matrix[r][c]);
                    if (!isFinite(v)) {
                        v = 0;
                    }
                    if (v < 0) v = 0;
                    if (v > 4095) v = 4095;
                    row.push(v);
                }
                rows.push(row);
            }
            return rows;
        }

        if (matrix.length === 1024) {
            var reshaped = [];
            for (var rowIndex = 0; rowIndex < 32; rowIndex++) {
                var rowOut = [];
                for (var colIndex = 0; colIndex < 32; colIndex++) {
                    var val = Number(matrix[(rowIndex * 32) + colIndex]);
                    if (!isFinite(val)) {
                        val = 0;
                    }
                    if (val < 0) val = 0;
                    if (val > 4095) val = 4095;
                    rowOut.push(val);
                }
                reshaped.push(rowOut);
            }
            return reshaped;
        }

        return null;
    }

    function drawHeatmapFallback(canvas, matrix) {
        var normalised = normaliseLocalMatrix(matrix);
        if (!canvas || !normalised) {
            return;
        }

        var ctx = canvas.getContext('2d');
        if (!ctx) {
            return;
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        var cellW = canvas.width / 32;
        var cellH = canvas.height / 32;

        for (var r = 0; r < 32; r++) {
            for (var c = 0; c < 32; c++) {
                var norm = normalised[r][c] / 4095;
                ctx.fillStyle = 'rgba(' + Math.floor(255 * norm) + ',0,' + Math.floor(255 * (1 - norm)) + ',1)';
                ctx.fillRect(Math.floor(c * cellW), Math.floor(r * cellH), Math.ceil(cellW), Math.ceil(cellH));
            }
        }
    }

    function drawAnnotationFallback(canvas, cells) {
        if (!canvas || !Array.isArray(cells)) {
            return;
        }

        var ctx = canvas.getContext('2d');
        if (!ctx) {
            return;
        }

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (!cells.length) {
            return;
        }

        var cellW = canvas.width / 32;
        var cellH = canvas.height / 32;
        ctx.fillStyle = 'rgba(220, 53, 69, 0.5)';

        cells.forEach(function (cell) {
            if (!Array.isArray(cell) || cell.length < 2) {
                return;
            }
            var row = Number(cell[0]);
            var col = Number(cell[1]);
            if (!isFinite(row) || !isFinite(col)) {
                return;
            }
            if (row < 0 || row > 31 || col < 0 || col > 31) {
                return;
            }
            ctx.fillRect(Math.floor(col * cellW), Math.floor(row * cellH), Math.ceil(cellW), Math.ceil(cellH));
        });
    }

    function safeDrawHeatmap(canvas, matrix) {
        if (typeof drawHeatmapOnCanvas === 'function') {
            var ok = drawHeatmapOnCanvas(canvas, matrix);
            if (ok) {
                return true;
            }
        }
        drawHeatmapFallback(canvas, matrix);
        return normaliseLocalMatrix(matrix) !== null;
    }

    function safeDrawAnnotation(canvas, cells) {
        if (typeof drawAnnotationOnCanvas === 'function') {
            drawAnnotationOnCanvas(canvas, cells);
            return;
        }
        drawAnnotationFallback(canvas, cells);
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
        el.className = 'clin-detail-status' + (cssClass ? ' ' + cssClass : '');
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
        var container = document.getElementById('clinicianHeatmapContainer');
        var hasHeatmap = false;

        if (heatmapCanvas && latest && Array.isArray(latest.matrix)) {
            // Show the canvas container, hide any empty state
            if (container) container.style.display = '';
            hasHeatmap = safeDrawHeatmap(heatmapCanvas, latest.matrix);
        } else {
            clearCanvas(heatmapCanvas);
            // Show empty state when no data
            if (container) {
                container.style.display = 'none';
                var emptyEl = container.parentNode.querySelector('.clin-heatmap-empty');
                if (!emptyEl) {
                    emptyEl = document.createElement('div');
                    emptyEl.className = 'clin-heatmap-empty';
                    emptyEl.textContent = 'No pressure data available for this patient.';
                    container.parentNode.insertBefore(emptyEl, container.nextSibling);
                }
                emptyEl.style.display = '';
            }
        }

        // Hide empty state if we have data
        if (hasHeatmap && container) {
            var existingEmpty = container.parentNode.querySelector('.clin-heatmap-empty');
            if (existingEmpty) existingEmpty.style.display = 'none';
        }

        if (annotationCanvas) {
            safeDrawAnnotation(annotationCanvas, (annotation && Array.isArray(annotation.cells)) ? annotation.cells : []);
        }

        if (annotationInfo) {
            if (!hasHeatmap && latest && latest.matrix) {
                annotationInfo.textContent = 'Heatmap could not be rendered. Try another patient or newer frame.';
            } else if (!hasHeatmap) {
                annotationInfo.textContent = 'No pressure data available.';
            } else if (annotation && annotation.cells && annotation.cells.length > 0) {
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

        if (levelEl) {
            var level = latest.risk_level ? String(latest.risk_level).toUpperCase() : '--';
            levelEl.textContent = level;
            // Apply risk-level color class
            levelEl.className = 'clin-metric-value';
            if (latest.risk_level) {
                levelEl.classList.add(latest.risk_level.toLowerCase());
            }
        }

        if (tsEl) tsEl.textContent = 'Latest frame: ' + formatDateTime(latest.timestamp);
    }

    function renderFrames(rows) {
        var body = document.getElementById('clinicianFrameRows');
        if (!body) {
            return;
        }

        if (!rows || rows.length === 0) {
            body.innerHTML = '<tr><td colspan="6" style="color:var(--mist);text-align:center;padding:2rem">No pressure frames available.</td></tr>';
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
            list.innerHTML = '<div style="color:var(--mist);text-align:center;padding:2rem;font-size:0.85rem">No comments from this patient yet.</div>';
            return;
        }

        list.innerHTML = '';
        comments.slice(0, 20).forEach(function (comment) {
            var item = document.createElement('div');
            item.className = 'clin-comment-item';
            item.setAttribute('data-comment-id', comment.id);
            var existingReply = comment.clinician_reply
                ? '<div class="clin-comment-reply-existing"><strong>Clinician reply:</strong> ' + escapeHtml(comment.clinician_reply) + '</div>'
                : '';
            item.innerHTML =
                '<div class="clin-comment-meta">Patient note at ' + formatDateTime(comment.frame_timestamp) + '</div>' +
                '<div class="clin-comment-text">' + escapeHtml(comment.text) + '</div>' +
                existingReply +
                '<div class="clin-reply-form">' +
                    '<input type="text" class="clin-reply-input clinician-reply-input" placeholder="Write advice or follow-up…">' +
                    '<button type="button" class="btn btn-primary btn-sm clinician-reply-btn" data-comment-id="' + comment.id + '">Reply</button>' +
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

        var items = Array.prototype.slice.call(list.querySelectorAll('.clin-patient-item'));
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

        var activeItem = list.querySelector('.clin-patient-item.active');
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

                var replyEl = cardEl.querySelector('.clin-comment-reply-existing');
                if (!replyEl) {
                    replyEl = document.createElement('div');
                    replyEl.className = 'clin-comment-reply-existing';
                    cardEl.insertBefore(replyEl, cardEl.querySelector('.clin-reply-form'));
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
            var card = target.closest('.clin-comment-item');
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

        // Get theme-aware colors
        var isDark = document.documentElement.getAttribute('data-theme') !== 'light';
        var gridColor = isDark ? 'rgba(255,255,255,0.04)' : 'rgba(0,0,0,0.06)';
        var tickColor = isDark ? '#5a7a9a' : '#6b7280';

        trendChart = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'PPI',
                        data: ppi,
                        borderColor: '#00d4c8',
                        backgroundColor: 'rgba(0,212,200,0.1)',
                        pointRadius: 1,
                        tension: 0.3,
                        borderWidth: 2,
                        yAxisID: 'y',
                    },
                    {
                        label: 'Risk',
                        data: risk,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239,68,68,0.1)',
                        pointRadius: 1,
                        tension: 0.3,
                        borderWidth: 2,
                        yAxisID: 'y1',
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: tickColor,
                            font: { size: 11 },
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: tickColor, font: { size: 10 }, maxTicksLimit: 10 },
                        grid: { color: gridColor },
                    },
                    y: {
                        beginAtZero: true,
                        suggestedMax: 4095,
                        title: { display: true, text: 'PPI', color: tickColor, font: { size: 11 } },
                        ticks: { color: tickColor, font: { size: 10 } },
                        grid: { color: gridColor },
                    },
                    y1: {
                        beginAtZero: true,
                        suggestedMax: 100,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        title: { display: true, text: 'Risk', color: tickColor, font: { size: 11 } },
                        ticks: { color: tickColor, font: { size: 10 } },
                    }
                }
            }
        });
    }

    function setActivePatient(patientId) {
        document.querySelectorAll('.clin-patient-item').forEach(function (item) {
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

        document.querySelectorAll('.clin-patient-item').forEach(function (item) {
            var patient = byId[item.dataset.patientId];
            if (!patient) {
                return;
            }

            var metaEl = item.querySelector('.clin-p-meta');
            if (!metaEl) {
                return;
            }

            var riskLevel = (patient.latest_risk_level || 'none').toLowerCase();
            var ppiText = patient.latest_ppi != null ? Number(patient.latest_ppi).toFixed(1) : '--';
            var riskText = (patient.latest_risk_level || 'no-data').toUpperCase();

            metaEl.innerHTML =
                '<span class="risk-pill risk-' + riskLevel + '">' + riskText + '</span>' +
                '<span style="color:var(--fog);font-size:0.7rem">PPI ' + ppiText + '</span>';
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

                // Use requestAnimationFrame to ensure canvas is painted before drawing
                requestAnimationFrame(function () {
                    renderHeatmap(data.latest, data.annotation);
                });

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
        var patientItems = Array.prototype.slice.call(document.querySelectorAll('.clin-patient-item'));
        if (patientItems.length === 0) {
            return;
        }

        var initialDetail = readInitialDetailData();
        if (initialDetail && initialDetail.patient) {
            updateHeader(initialDetail.patient, initialDetail.report_url);

            // Use requestAnimationFrame to ensure the canvas element is in
            // the DOM and has computed dimensions before we paint onto it
            requestAnimationFrame(function () {
                renderHeatmap(initialDetail.latest, initialDetail.annotation);
            });

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

        var activeItem = document.querySelector('.clin-patient-item.active');
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

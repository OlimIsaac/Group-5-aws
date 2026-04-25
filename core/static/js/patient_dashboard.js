(function () {
    'use strict';

    var currentHours = 24;
    var pressureChart = null;
    var latestFrameId = 0;
    var pinHistoricalPreview = false;
    var currentHeatmapMatrix = null;
    var heatmapAnimationId = null;
    var liveRequestInFlight = false;

    var LIVE_POLL_MS = 1500;
    var DASHBOARD_REFRESH_MS = 15000;
    var COMMENTS_REFRESH_MS = 30000;
    var HEATMAP_TRANSITION_MS = 450;

    function getDashboardRoot() {
        return document.getElementById('patientDashboardApp');
    }

    function getApiUrl(datasetKey, fallbackUrl) {
        var root = getDashboardRoot();
        if (root && root.dataset && root.dataset[datasetKey]) {
            return root.dataset[datasetKey];
        }
        return fallbackUrl;
    }

    function appendQuery(url, query) {
        if (!query) {
            return url;
        }
        return url + (url.indexOf('?') === -1 ? '?' : '&') + query;
    }

    function getCsrfToken() {
        var csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
        return csrfMatch ? csrfMatch[1] : '';
    }

    function isNumber(value) {
        return typeof value === 'number' && isFinite(value);
    }

    function isValidMatrix(matrix) {
        if (!Array.isArray(matrix) || matrix.length !== 32) {
            return false;
        }

        for (var r = 0; r < 32; r++) {
            if (!Array.isArray(matrix[r]) || matrix[r].length !== 32) {
                return false;
            }
            for (var c = 0; c < 32; c++) {
                if (!isNumber(matrix[r][c])) {
                    return false;
                }
            }
        }

        return true;
    }

    function cloneMatrix(matrix) {
        return matrix.map(function (row) { return row.slice(); });
    }

    function mixMatrices(startMatrix, endMatrix, progress) {
        var mixed = [];
        for (var r = 0; r < 32; r++) {
            var row = [];
            for (var c = 0; c < 32; c++) {
                var startVal = startMatrix[r][c];
                var endVal = endMatrix[r][c];
                row.push(startVal + (endVal - startVal) * progress);
            }
            mixed.push(row);
        }
        return mixed;
    }

    function animateHeatmapTo(nextMatrix) {
        if (!isValidMatrix(nextMatrix)) {
            return;
        }

        var targetMatrix = cloneMatrix(nextMatrix);

        if (!currentHeatmapMatrix) {
            currentHeatmapMatrix = targetMatrix;
            drawHeatmap('heatmapCanvas', currentHeatmapMatrix);
            return;
        }

        if (heatmapAnimationId !== null && typeof window.cancelAnimationFrame === 'function') {
            window.cancelAnimationFrame(heatmapAnimationId);
            heatmapAnimationId = null;
        }

        if (typeof window.requestAnimationFrame !== 'function') {
            currentHeatmapMatrix = targetMatrix;
            drawHeatmap('heatmapCanvas', currentHeatmapMatrix);
            return;
        }

        var startMatrix = currentHeatmapMatrix;
        var startTime = null;

        function step(timestamp) {
            if (startTime === null) {
                startTime = timestamp;
            }

            var progress = Math.min((timestamp - startTime) / HEATMAP_TRANSITION_MS, 1);
            var blended = mixMatrices(startMatrix, targetMatrix, progress);
            drawHeatmap('heatmapCanvas', blended);

            if (progress < 1) {
                heatmapAnimationId = window.requestAnimationFrame(step);
                return;
            }

            currentHeatmapMatrix = targetMatrix;
            heatmapAnimationId = null;
        }

        heatmapAnimationId = window.requestAnimationFrame(step);
    }

    function setLiveStatus(message, state) {
        var statusEl = document.getElementById('liveStatus');
        if (!statusEl) {
            return;
        }

        statusEl.textContent = message;
        statusEl.className = 'live-status' + (state ? ' ' + state : '');
    }

    function updateLiveStatus(frameTimestamp, serverTimestamp, isNew) {
        if (!frameTimestamp) {
            setLiveStatus('Live stream waiting for new pressure data', 'stale');
            return;
        }

        var frameMs = Date.parse(frameTimestamp);
        var serverMs = Date.parse(serverTimestamp || '');
        var nowMs = isFinite(serverMs) ? serverMs : Date.now();

        if (!isFinite(frameMs)) {
            setLiveStatus('Live stream connected', 'live');
            return;
        }

        var ageSeconds = Math.max(0, Math.round((nowMs - frameMs) / 1000));

        if (ageSeconds <= 4) {
            setLiveStatus(isNew ? 'Live stream updated just now' : 'Live stream active (' + ageSeconds + 's delay)', 'live');
            return;
        }

        if (ageSeconds <= 15) {
            setLiveStatus('Live stream slow (' + ageSeconds + 's old)', 'stale');
            return;
        }

        setLiveStatus('Live stream stale (' + ageSeconds + 's old)', 'error');
    }

    function escapeHtml(value) {
        return String(value || '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function getFrameDetailApiUrl(frameId) {
        var template = getApiUrl('frameDetailApiTemplate', '/patient/api/frames/0/');
        return template.replace(/0\/?$/, String(frameId) + '/');
    }

    function getFrameSelectValue() {
        var select = document.getElementById('commentFrameSelect');
        if (!select) {
            return 0;
        }
        var value = parseInt(select.value, 10);
        return isFinite(value) ? value : 0;
    }

    function setFramePreviewStatus(message, state) {
        var statusEl = document.getElementById('framePreviewStatus');
        if (!statusEl) {
            return;
        }
        statusEl.textContent = message;
        statusEl.className = 'annotation-status' + (state ? ' ' + state : '');
    }

    function applyFramePreviewData(frameData) {
        if (!frameData) {
            return;
        }

        if (isValidMatrix(frameData.matrix)) {
            animateHeatmapTo(frameData.matrix);
        }

        applyLiveMetrics({
            latest_ppi: frameData.peak_pressure_index,
            latest_contact: frameData.contact_area_percentage,
            latest_risk_score: frameData.risk_score,
            latest_risk_level: frameData.risk_level,
            alert: frameData.high_pressure_flag,
            explanation: frameData.explanation,
        });

        setLiveStatus('Viewing selected frame: ' + new Date(frameData.timestamp).toLocaleString(), 'stale');
        setFramePreviewStatus('Previewing selected frame from history.', 'saved');
    }

    function loadSelectedFramePreview(frameId, options) {
        options = options || {};

        if (!frameId) {
            return Promise.resolve();
        }

        return fetch(getFrameDetailApiUrl(frameId))
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Failed to load frame detail');
                }
                return response.json();
            })
            .then(function (data) {
                applyFramePreviewData(data);
            })
            .catch(function () {
                if (!options.silent) {
                    setFramePreviewStatus('Could not load selected frame preview.', 'error');
                }
            });
    }

    // Annotation state
    var markedCells = {};   // key "r,c" -> true
    var isAnnotating = false;
    var isDragging = false;
    var dragAction = null;  // 'add' or 'remove'

    function initChart() {
        var ctx = document.getElementById('pressureChart').getContext('2d');
        pressureChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'All frames',
                        data: [],
                        backgroundColor: 'rgba(13, 110, 253, 0.38)',
                        borderColor: 'rgba(13, 110, 253, 0.95)',
                        borderWidth: 1,
                    },
                    {
                        label: 'High-pressure frames',
                        data: [],
                        backgroundColor: 'rgba(220, 53, 69, 0.6)',
                        borderColor: 'rgba(220, 53, 69, 1)',
                        borderWidth: 1,
                    }
                ]
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

    // ---------- Annotation helpers ----------

    function cellKey(r, c) { return r + ',' + c; }

    function getCellFromEvent(canvas, e) {
        var rect = canvas.getBoundingClientRect();
        var scaleX = canvas.width / rect.width;
        var scaleY = canvas.height / rect.height;
        var clientX = e.touches ? e.touches[0].clientX : e.clientX;
        var clientY = e.touches ? e.touches[0].clientY : e.clientY;
        var col = Math.min(31, Math.max(0, Math.floor((clientX - rect.left) * scaleX / (canvas.width / 32))));
        var row = Math.min(31, Math.max(0, Math.floor((clientY - rect.top) * scaleY / (canvas.height / 32))));
        return [row, col];
    }

    function refreshAnnotationCanvas() {
        var cells = Object.keys(markedCells).map(function (k) {
            var p = k.split(',');
            return [parseInt(p[0]), parseInt(p[1])];
        });
        drawAnnotationOverlay('annotationCanvas', cells);
    }

    function applyCell(r, c) {
        var key = cellKey(r, c);
        if (dragAction === 'add') {
            markedCells[key] = true;
        } else {
            delete markedCells[key];
        }
        refreshAnnotationCanvas();
    }

    function initAnnotation() {
        var overlay = document.getElementById('annotationCanvas');
        if (!overlay) return;

        overlay.addEventListener('mousedown', function (e) {
            if (!isAnnotating) return;
            e.preventDefault();
            isDragging = true;
            var cell = getCellFromEvent(overlay, e);
            var key = cellKey(cell[0], cell[1]);
            dragAction = markedCells[key] ? 'remove' : 'add';
            applyCell(cell[0], cell[1]);
        });

        overlay.addEventListener('mousemove', function (e) {
            if (!isAnnotating || !isDragging) return;
            e.preventDefault();
            var cell = getCellFromEvent(overlay, e);
            applyCell(cell[0], cell[1]);
        });

        document.addEventListener('mouseup', function () {
            isDragging = false;
            dragAction = null;
        });

        // Touch support
        overlay.addEventListener('touchstart', function (e) {
            if (!isAnnotating) return;
            e.preventDefault();
            isDragging = true;
            var cell = getCellFromEvent(overlay, e);
            var key = cellKey(cell[0], cell[1]);
            dragAction = markedCells[key] ? 'remove' : 'add';
            applyCell(cell[0], cell[1]);
        }, { passive: false });

        overlay.addEventListener('touchmove', function (e) {
            if (!isAnnotating || !isDragging) return;
            e.preventDefault();
            var cell = getCellFromEvent(overlay, e);
            applyCell(cell[0], cell[1]);
        }, { passive: false });

        overlay.addEventListener('touchend', function () {
            isDragging = false;
            dragAction = null;
        });

        // Toggle annotation mode
        var toggleBtn = document.getElementById('annotateToggleBtn');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', function () {
                isAnnotating = !isAnnotating;
                overlay.style.pointerEvents = isAnnotating ? 'auto' : 'none';
                overlay.style.cursor = isAnnotating ? 'crosshair' : 'default';
                toggleBtn.classList.toggle('active', isAnnotating);
                toggleBtn.textContent = isAnnotating ? 'Done Marking' : 'Mark Pain on Heatmap';
            });
        }

        // Clear marks
        var clearBtn = document.getElementById('annotateClearBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', function () {
                markedCells = {};
                refreshAnnotationCanvas();
                setAnnotationStatus('');
            });
        }

        // Save marks
        var saveBtn = document.getElementById('annotateSaveBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', saveAnnotation);
        }
    }

    function setAnnotationStatus(msg, isError) {
        var el = document.getElementById('annotationStatus');
        if (!el) return;
        el.textContent = msg;
        el.className = 'annotation-status' + (isError ? ' error' : (msg ? ' saved' : ''));
    }

    function saveAnnotation() {
        var cells = Object.keys(markedCells).map(function (k) {
            var p = k.split(',');
            return [parseInt(p[0]), parseInt(p[1])];
        });

        var csrfToken = getCsrfToken();

        fetch(getApiUrl('annotationApi', '/patient/api/heatmap-annotation/'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ cells: cells }),
        })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.status === 'saved') {
                var count = data.count;
                setAnnotationStatus(count > 0
                    ? 'Pain marks saved (' + count + ' cell' + (count !== 1 ? 's' : '') + ')'
                    : 'Marks cleared');
                setTimeout(function () { setAnnotationStatus(''); }, 4000);
            } else {
                setAnnotationStatus('Save failed: ' + (data.error || 'unknown error'), true);
            }
        })
        .catch(function () {
            setAnnotationStatus('Save failed — check your connection', true);
        });
    }

    function populateFrameSelector(frames) {
        var select = document.getElementById('commentFrameSelect');
        if (!select) return;

        var previousValue = select.value;
        select.innerHTML = '';
        if (!frames || frames.length === 0) {
            var empty = document.createElement('option');
            empty.value = '';
            empty.textContent = 'No frame available';
            select.appendChild(empty);
            setFramePreviewStatus('No frame available for preview.', '');
            return;
        }

        var availableValues = [];
        frames.slice().reverse().forEach(function (frame) {
            var option = document.createElement('option');
            option.value = frame.id;
            option.textContent = frame.label;
            select.appendChild(option);
            availableValues.push(String(frame.id));
        });

        if (pinHistoricalPreview && previousValue && availableValues.indexOf(previousValue) !== -1) {
            select.value = previousValue;
        } else {
            select.selectedIndex = 0;
        }
    }

    function renderComments(comments) {
        var list = document.getElementById('patientCommentList');
        if (!list) return;

        if (!comments || comments.length === 0) {
            list.textContent = 'No comments yet.';
            return;
        }

        list.innerHTML = '';
        comments.forEach(function (comment) {
            var item = document.createElement('div');
            item.className = 'comment-item';
            var replyHtml = comment.clinician_reply
                ? '<div class="comment-reply"><strong>Clinician reply:</strong> ' + escapeHtml(comment.clinician_reply) + '</div>'
                : '';
            item.innerHTML =
                '<div class="comment-meta">Frame time: ' + new Date(comment.frame_timestamp).toLocaleString() + '</div>' +
                '<div class="comment-text">' + escapeHtml(comment.text) + '</div>' +
                replyHtml;
            list.appendChild(item);
        });
    }

    function loadComments() {
        fetch(appendQuery(getApiUrl('commentsApi', '/patient/api/comments/'), 'hours=all'))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                renderComments(data.comments || []);
            })
            .catch(function () {
                var list = document.getElementById('patientCommentList');
                if (list) list.textContent = 'Unable to load comments.';
            });
    }

    function saveTimeLinkedComment() {
        var frameSelect = document.getElementById('commentFrameSelect');
        var commentInput = document.getElementById('commentText');
        var status = document.getElementById('commentStatus');
        if (!frameSelect || !commentInput || !status) return;

        var frameId = frameSelect.value;
        var text = (commentInput.value || '').trim();

        if (!frameId) {
            status.textContent = 'Select a frame time first.';
            status.className = 'annotation-status error';
            return;
        }
        if (!text) {
            status.textContent = 'Enter a comment before saving.';
            status.className = 'annotation-status error';
            return;
        }

        fetch(getApiUrl('commentsApi', '/patient/api/comments/'), {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
                frame_id: parseInt(frameId, 10),
                text: text,
            }),
        })
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.error) {
                status.textContent = data.error;
                status.className = 'annotation-status error';
                return;
            }
            commentInput.value = '';
            status.textContent = 'Comment saved for selected frame time.';
            status.className = 'annotation-status saved';
            loadComments();
        })
        .catch(function () {
            status.textContent = 'Failed to save comment.';
            status.className = 'annotation-status error';
        });
    }

    function applyLiveMetrics(data) {
        var ppiEl = document.getElementById('ppiValue');
        var contactEl = document.getElementById('contactValue');

        if (ppiEl) {
            ppiEl.textContent = data.latest_ppi !== null && data.latest_ppi !== undefined
                ? parseFloat(data.latest_ppi).toFixed(1)
                : '--';
        }

        if (contactEl) {
            contactEl.textContent = data.latest_contact !== null && data.latest_contact !== undefined
                ? parseFloat(data.latest_contact).toFixed(1) + '%'
                : '--';
        }

        var explanationEl = document.getElementById('simpleExplanation');
        if (explanationEl) {
            explanationEl.textContent = data.explanation || 'No pressure frame available yet. Upload data to start analysis.';
        }

        var banner = document.getElementById('alertBanner');
        if (banner) {
            if (data.alert) {
                banner.className = 'alert alert-danger';
                banner.textContent = 'High pressure detected. Please shift position.';
            } else {
                banner.className = 'alert alert-success';
                banner.textContent = 'Pressure looks normal.';
            }
        }
    }

    function pollLiveHeatmap() {
        if (liveRequestInFlight) {
            return;
        }

        liveRequestInFlight = true;

        fetch(appendQuery(getApiUrl('liveApi', '/patient/api/live/'), 'since_frame_id=' + encodeURIComponent(latestFrameId || 0)))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                if (!data || data.error) {
                    setLiveStatus('Live stream reconnecting', 'error');
                    return;
                }

                if (!data.has_data) {
                    setLiveStatus('Live stream waiting for new pressure data', 'stale');
                    return;
                }

                if (data.frame_id) {
                    latestFrameId = data.frame_id;
                }

                var selectedFrameId = getFrameSelectValue();
                if (pinHistoricalPreview && selectedFrameId && latestFrameId && Number(selectedFrameId) !== Number(latestFrameId)) {
                    setLiveStatus('Live stream active. Preview is pinned to selected historical frame.', 'stale');
                    return;
                }

                if (data.latest_matrix && isValidMatrix(data.latest_matrix)) {
                    animateHeatmapTo(data.latest_matrix);
                }

                applyLiveMetrics(data);
                updateLiveStatus(data.frame_timestamp, data.server_time, !!data.is_new);
            })
            .catch(function () {
                setLiveStatus('Live stream reconnecting', 'error');
            })
            .finally(function () {
                liveRequestInFlight = false;
            });
    }

    // ---------- Data loading ----------

    function loadData(hours, options) {
        options = options || {};

        currentHours = hours;
        setActiveButton(hours);

        fetch(appendQuery(getApiUrl('statusApi', '/patient/api/status/'), 'hours=' + hours))
            .then(function (response) { return response.json(); })
            .then(function (data) {
                // Heatmap
                if (isValidMatrix(data.latest_matrix)) {
                    animateHeatmapTo(data.latest_matrix);
                }

                // Redraw annotation overlay on top (preserves unsaved marks)
                refreshAnnotationCanvas();

                // On first load, populate markedCells from saved annotation
                if (data.saved_annotation && Array.isArray(data.saved_annotation)
                        && Object.keys(markedCells).length === 0) {
                    data.saved_annotation.forEach(function (cell) {
                        markedCells[cellKey(cell[0], cell[1])] = true;
                    });
                    refreshAnnotationCanvas();
                }

                if (data.latest_frame_id) {
                    latestFrameId = data.latest_frame_id;
                }

                updateLiveStatus(data.latest_timestamp, data.server_time, true);

                applyLiveMetrics(data);

                populateFrameSelector(data.recent_frames || []);

                var selectedFrameId = getFrameSelectValue();
                if (pinHistoricalPreview && selectedFrameId && data.latest_frame_id && Number(selectedFrameId) !== Number(data.latest_frame_id)) {
                    loadSelectedFramePreview(selectedFrameId, { silent: true });
                } else {
                    pinHistoricalPreview = false;
                    setFramePreviewStatus('Showing latest live frame.', '');
                }

                // Chart
                if (data.chart_data && Array.isArray(data.chart_data.labels)) {
                    pressureChart.data.labels = data.chart_data.labels;
                    pressureChart.data.datasets[0].data = data.chart_data.total_counts || [];
                    pressureChart.data.datasets[1].data = data.chart_data.counts || [];
                    pressureChart.update();
                }

                if (options.includeComments !== false) {
                    loadComments();
                }
            })
            .catch(function () {
                setLiveStatus('Live stream reconnecting', 'error');
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initChart();
        initAnnotation();
        setLiveStatus('Live stream connecting', 'connecting');

        var saveCommentBtn = document.getElementById('saveCommentBtn');
        if (saveCommentBtn) {
            saveCommentBtn.addEventListener('click', saveTimeLinkedComment);
        }

        var frameSelect = document.getElementById('commentFrameSelect');
        if (frameSelect) {
            frameSelect.addEventListener('change', function () {
                var selectedFrameId = getFrameSelectValue();
                if (!selectedFrameId) {
                    pinHistoricalPreview = false;
                    setFramePreviewStatus('No frame selected for preview.', '');
                    return;
                }

                if (latestFrameId && Number(selectedFrameId) === Number(latestFrameId)) {
                    pinHistoricalPreview = false;
                    setFramePreviewStatus('Showing latest live frame.', '');
                    loadData(currentHours, { includeComments: false });
                    return;
                }

                pinHistoricalPreview = true;
                loadSelectedFramePreview(selectedFrameId, { silent: false });
            });
        }

        loadData(24, { includeComments: true });
        pollLiveHeatmap();

        setInterval(function () {
            pollLiveHeatmap();
        }, LIVE_POLL_MS);

        setInterval(function () {
            loadData(currentHours, { includeComments: false });
        }, DASHBOARD_REFRESH_MS);

        setInterval(function () {
            loadComments();
        }, COMMENTS_REFRESH_MS);

        document.querySelectorAll('.time-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                loadData(parseInt(btn.dataset.hours, 10), { includeComments: true });
            });
        });
    });
}());

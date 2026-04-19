(function () {
    'use strict';

    var currentHours = 1;
    var pressureChart = null;
    var latestFrameId = 0;
    var currentHeatmapMatrix = null;
    var heatmapAnimationId = null;
    var liveRequestInFlight = false;

    var LIVE_POLL_MS = 1500;
    var DASHBOARD_REFRESH_MS = 15000;
    var COMMENTS_REFRESH_MS = 30000;
    var HEATMAP_TRANSITION_MS = 450;

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

        fetch('/patient/api/heatmap-annotation/', {
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

        select.innerHTML = '';
        if (!frames || frames.length === 0) {
            var empty = document.createElement('option');
            empty.value = '';
            empty.textContent = 'No frame available';
            select.appendChild(empty);
            return;
        }

        frames.slice().reverse().forEach(function (frame) {
            var option = document.createElement('option');
            option.value = frame.id;
            option.textContent = frame.label;
            select.appendChild(option);
        });
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
        fetch('/patient/api/comments/?hours=' + currentHours)
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

        fetch('/patient/api/comments/', {
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

        fetch('/patient/api/live/?since_frame_id=' + encodeURIComponent(latestFrameId || 0))
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

        fetch('/patient/api/status/?hours=' + hours)
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

                // Chart
                if (data.chart_data && Array.isArray(data.chart_data.labels)) {
                    pressureChart.data.labels = data.chart_data.labels;
                    pressureChart.data.datasets[0].data = data.chart_data.counts;
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

        loadData(1, { includeComments: true });
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

(function () {
    'use strict';

    var currentHours = 1;
    var pressureChart = null;

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

        var csrfMatch = document.cookie.match(/csrftoken=([^;]+)/);
        var csrfToken = csrfMatch ? csrfMatch[1] : '';

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

    // ---------- Data loading ----------

    function loadData(hours) {
        currentHours = hours;
        setActiveButton(hours);

        fetch('/patient/api/status/?hours=' + hours)
            .then(function (response) { return response.json(); })
            .then(function (data) {
                // Heatmap
                if (data.latest_matrix !== null && Array.isArray(data.latest_matrix)) {
                    drawHeatmap('heatmapCanvas', data.latest_matrix);
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

                // Metrics
                var ppiEl = document.getElementById('ppiValue');
                var contactEl = document.getElementById('contactValue');
                ppiEl.textContent = data.latest_ppi !== null
                    ? parseFloat(data.latest_ppi).toFixed(1)
                    : '--';
                contactEl.textContent = data.latest_contact !== null
                    ? parseFloat(data.latest_contact).toFixed(1) + '%'
                    : '--';

                // Alert banner
                var banner = document.getElementById('alertBanner');
                if (data.alert) {
                    banner.className = 'alert alert-danger';
                    banner.textContent = '⚠ High pressure detected — please shift position';
                } else {
                    banner.className = 'alert alert-success';
                    banner.textContent = '✓ Pressure looks normal';
                }

                // Chart
                if (data.chart_data && Array.isArray(data.chart_data.labels)) {
                    pressureChart.data.labels = data.chart_data.labels;
                    pressureChart.data.datasets[0].data = data.chart_data.counts;
                    pressureChart.update();
                }
            })
            .catch(function () {
                // Silent fail — leave existing UI unchanged, keep polling
            });
    }

    document.addEventListener('DOMContentLoaded', function () {
        initChart();
        initAnnotation();
        loadData(24);
        setInterval(function () { loadData(currentHours); }, 8000);

        document.querySelectorAll('.time-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                loadData(parseInt(btn.dataset.hours));
            });
        });
    });
}());

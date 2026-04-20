// Draw a 32x32 pressure matrix onto a canvas element
function drawHeatmapOnCanvas(canvas, matrix) {
    if (!canvas) return;
    if (!Array.isArray(matrix)) return;
    var ctx = canvas.getContext('2d');
    ctx.imageSmoothingEnabled = false;
    var cellW = canvas.width / 32;
    var cellH = canvas.height / 32;
    var isFlat = matrix.length === 1024;
    if (!isFlat && (matrix.length !== 32 || !Array.isArray(matrix[0]))) return;
    for (var r = 0; r < 32; r++) {
        for (var c = 0; c < 32; c++) {
            var value = 0;
            if (isFlat) {
                value = matrix[r * 32 + c] || 0;
            } else if (Array.isArray(matrix[r]) && typeof matrix[r][c] === 'number') {
                value = matrix[r][c];
            }
            var norm = value / 4095;
            ctx.fillStyle = 'rgba(' + Math.floor(255 * norm) + ',0,' + Math.floor(255 * (1 - norm)) + ',1)';
            ctx.fillRect(c * cellW, r * cellH, cellW, cellH);
        }
    }
}

function generateLivePressureMatrix(baseMatrix) {
    var matrix = [];
    for (var r = 0; r < 32; r++) {
        matrix[r] = [];
        for (var c = 0; c < 32; c++) {
            var base = 0;
            if (Array.isArray(baseMatrix) && baseMatrix.length === 32 && Array.isArray(baseMatrix[r]) && typeof baseMatrix[r][c] === 'number') {
                base = baseMatrix[r][c];
            } else if (Array.isArray(baseMatrix) && baseMatrix.length === 1024 && typeof baseMatrix[r * 32 + c] === 'number') {
                base = baseMatrix[r * 32 + c];
            }
            var noise = Math.round((Math.random() - 0.5) * 160);
            var wave = Math.round(Math.sin((r + c + Date.now() / 1200) * 0.82) * 42);
            matrix[r][c] = Math.max(0, Math.min(4095, base + noise + wave));
        }
    }
    return matrix;
}

function pressureMatrixExplanation(matrix) {
    if (!Array.isArray(matrix)) {
        return 'Live heatmap is warming up.';
    }
    var isFlat = matrix.length === 1024;
    if (!isFlat && matrix.length !== 32) {
        return 'Live heatmap is warming up.';
    }
    var total = 0;
    var left = 0;
    var right = 0;
    var top = 0;
    var bottom = 0;
    var center = 0;
    for (var r = 0; r < 32; r++) {
        for (var c = 0; c < 32; c++) {
            var value = 0;
            if (isFlat) {
                value = matrix[r * 32 + c] || 0;
            } else if (Array.isArray(matrix[r]) && typeof matrix[r][c] === 'number') {
                value = matrix[r][c];
            }
            total += value;
            if (c < 11) left += value;
            if (c > 20) right += value;
            if (r < 11) top += value;
            if (r > 20) bottom += value;
            if (c >= 11 && c <= 20 && r >= 11 && r <= 20) center += value;
        }
    }
    if (total < 1024 * 120) {
        return 'Low pressure overall — posture looks relaxed and balanced.';
    }
    if (center > total * 0.26) {
        return 'Too much pressure in the center — try shifting slightly outward.';
    }
    if (left > right * 1.15) {
        return 'High pressure on the left side — shift your weight to the right.';
    }
    if (right > left * 1.15) {
        return 'High pressure on the right side — shift your weight to the left.';
    }
    if (top > bottom * 1.15) {
        return 'Pressure is heavier toward the top edge.';
    }
    if (bottom > top * 1.15) {
        return 'Pressure is heavier toward the bottom edge.';
    }
    return 'Good balanced posture — weight looks evenly distributed.';
}

// Draw pain annotation cells onto a canvas element (semi-transparent red)
function drawAnnotationOnCanvas(canvas, cells) {
    if (!canvas) return;
    if (!Array.isArray(cells)) return;
    var ctx = canvas.getContext('2d');
    var cellW = canvas.width / 32;
    var cellH = canvas.height / 32;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (cells.length === 0) return;
    ctx.fillStyle = 'rgba(220, 53, 69, 0.5)';
    cells.forEach(function (cell) {
        if (Array.isArray(cell) && cell.length >= 2 && typeof cell[0] === 'number' && typeof cell[1] === 'number') {
            ctx.fillRect(cell[1] * cellW, cell[0] * cellH, cellW, cellH);
        }
    });
}

// Convenience wrappers that look up by canvas ID
function getHeatmapCanvasElement(canvasId) {
    var canvas = null;
    if (canvasId) {
        canvas = document.getElementById(canvasId);
    }
    if (!canvas) {
        canvas = document.getElementById('pressureHeatmap');
    }
    if (!canvas) {
        canvas = document.querySelector('canvas.heatmap, canvas.heatmap-canvas');
    }
    return canvas;
}

function drawHeatmap(canvasId, matrix) {
    drawHeatmapOnCanvas(getHeatmapCanvasElement(canvasId), matrix);
}

function drawAnnotationOverlay(canvasId, cells) {
    drawAnnotationOnCanvas(getHeatmapCanvasElement(canvasId), cells);
}

function createPlaceholderPressureMatrix() {
    var matrix = [];
    for (var r = 0; r < 32; r++) {
        matrix[r] = [];
        for (var c = 0; c < 32; c++) {
            var base = 1600 + Math.round(900 * Math.sin((r + c) / 6)) + Math.round(400 * Math.cos((r - c) / 7));
            var jitter = Math.round((Math.random() - 0.5) * 260);
            matrix[r][c] = Math.max(0, Math.min(4095, base + jitter));
        }
    }
    return matrix;
}

function initHeatmapCanvas() {
    var canvas = getHeatmapCanvasElement('heatmapCanvas');
    if (!canvas) return;

    var matrix = createPlaceholderPressureMatrix();
    drawHeatmapOnCanvas(canvas, matrix);

    if (window.__heatmapLiveInterval) {
        return;
    }

    window.__heatmapLiveInterval = setInterval(function () {
        matrix = generateLivePressureMatrix(matrix);
        drawHeatmapOnCanvas(canvas, matrix);
    }, 2500);
}

window.addEventListener('DOMContentLoaded', initHeatmapCanvas);

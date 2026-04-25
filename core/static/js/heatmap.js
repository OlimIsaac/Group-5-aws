function pressureNumber(value) {
    var numeric = Number(value);
    if (!isFinite(numeric)) {
        return 0;
    }
    if (numeric < 0) {
        return 0;
    }
    if (numeric > 4095) {
        return 4095;
    }
    return numeric;
}

function pressureToRgb(value) {
    var v = pressureNumber(value);
    if (v <= 100) {
        return [10, 20, 34];
    }

    var t = (v - 100) / (4095 - 100);
    if (t < 0.25) {
        // navy -> blue
        var a0 = t / 0.25;
        return [
            Math.floor(10 + (0 - 10) * a0),
            Math.floor(20 + (90 - 20) * a0),
            Math.floor(34 + (220 - 34) * a0),
        ];
    }
    if (t < 0.5) {
        // blue -> cyan
        var a1 = (t - 0.25) / 0.25;
        return [
            Math.floor(0 + (0 - 0) * a1),
            Math.floor(90 + (205 - 90) * a1),
            Math.floor(220 + (255 - 220) * a1),
        ];
    }
    if (t < 0.75) {
        // cyan -> yellow
        var a2 = (t - 0.5) / 0.25;
        return [
            Math.floor(0 + (255 - 0) * a2),
            Math.floor(205 + (215 - 205) * a2),
            Math.floor(255 + (0 - 255) * a2),
        ];
    }

    // yellow -> red
    var a3 = (t - 0.75) / 0.25;
    return [
        Math.floor(255 + (255 - 255) * a3),
        Math.floor(215 + (36 - 215) * a3),
        Math.floor(0 + (0 - 0) * a3),
    ];
}

function normaliseHeatmapMatrix(matrix) {
    if (!Array.isArray(matrix)) {
        return null;
    }

    if (matrix.length === 32) {
        var out = [];
        for (var r = 0; r < 32; r++) {
            if (!Array.isArray(matrix[r]) || matrix[r].length < 32) {
                return null;
            }
            var row = [];
            for (var c = 0; c < 32; c++) {
                row.push(pressureNumber(matrix[r][c]));
            }
            out.push(row);
        }
        return out;
    }

    if (matrix.length === 1024) {
        var reshaped = [];
        for (var rowIndex = 0; rowIndex < 32; rowIndex++) {
            var rowOut = [];
            for (var colIndex = 0; colIndex < 32; colIndex++) {
                rowOut.push(pressureNumber(matrix[(rowIndex * 32) + colIndex]));
            }
            reshaped.push(rowOut);
        }
        return reshaped;
    }

    return null;
}

function cellBounds(index, size) {
    var start = Math.floor((index * size) / 32);
    var end = Math.floor(((index + 1) * size) / 32);
    if (end <= start) {
        end = start + 1;
    }
    return [start, end];
}

// Draw a 32x32 pressure matrix onto a canvas element
function drawHeatmapOnCanvas(canvas, matrix) {
    if (!canvas) return false;

    var normalised = normaliseHeatmapMatrix(matrix);
    if (!normalised) return false;

    var ctx = canvas.getContext('2d');
    if (!ctx) return false;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.imageSmoothingEnabled = false;

    for (var r = 0; r < 32; r++) {
        var y = cellBounds(r, canvas.height);
        for (var c = 0; c < 32; c++) {
            var value = matrix[r][c];
            var norm = value / 4095;
            var red = Math.round(10 + 150 * norm);
            var green = Math.round(14 + 80 * norm);
            var blue = Math.round(22 + 55 * norm);
            ctx.fillStyle = 'rgb(' + red + ',' + green + ',' + blue + ')';
            ctx.fillRect(c * cellW, r * cellH, cellW, cellH);

        }
    }

    return true;
}

// Draw pain annotation cells onto a canvas element (semi-transparent red)
function drawAnnotationOnCanvas(canvas, cells) {
    if (!canvas) return;
    if (!Array.isArray(cells)) return;
    var ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.imageSmoothingEnabled = false;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (cells.length === 0) return;
    ctx.fillStyle = 'rgba(220, 53, 69, 0.5)';
    cells.forEach(function (cell) {
        if (Array.isArray(cell) && cell.length >= 2 && typeof cell[0] === 'number' && typeof cell[1] === 'number') {
            if (cell[0] < 0 || cell[0] > 31 || cell[1] < 0 || cell[1] > 31) {
                return;
            }
            var y = cellBounds(cell[0], canvas.height);
            var x = cellBounds(cell[1], canvas.width);
            ctx.fillRect(x[0], y[0], x[1] - x[0], y[1] - y[0]);
        }
    });
}

// Convenience wrappers that look up by canvas ID
function drawHeatmap(canvasId, matrix) {
    drawHeatmapOnCanvas(document.getElementById(canvasId), matrix);
}

function drawAnnotationOverlay(canvasId, cells) {
    drawAnnotationOnCanvas(document.getElementById(canvasId), cells);
}

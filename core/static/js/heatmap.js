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
    if (!canvas) return;

    var normalised = normaliseHeatmapMatrix(matrix);
    if (!normalised) return;

    var ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.imageSmoothingEnabled = false;

    for (var r = 0; r < 32; r++) {
        var y = cellBounds(r, canvas.height);
        for (var c = 0; c < 32; c++) {
            var x = cellBounds(c, canvas.width);
            var norm = normalised[r][c] / 4095;
            ctx.fillStyle = 'rgba(' + Math.floor(255 * norm) + ',0,' + Math.floor(255 * (1 - norm)) + ',1)';
            ctx.fillRect(x[0], y[0], x[1] - x[0], y[1] - y[0]);
        }
    }
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

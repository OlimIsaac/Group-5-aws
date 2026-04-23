// Draw a 32x32 pressure matrix onto a canvas element
function drawHeatmapOnCanvas(canvas, matrix) {
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var cellW = canvas.width / 32;
    var cellH = canvas.height / 32;
    for (var r = 0; r < 32; r++) {
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
}

// Draw pain annotation cells onto a canvas element (semi-transparent red)
function drawAnnotationOnCanvas(canvas, cells) {
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    var cellW = canvas.width / 32;
    var cellH = canvas.height / 32;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!cells || cells.length === 0) return;
    ctx.fillStyle = 'rgba(220, 53, 69, 0.5)';
    cells.forEach(function (cell) {
        ctx.fillRect(cell[1] * cellW, cell[0] * cellH, cellW, cellH);
    });
}

// Convenience wrappers that look up by canvas ID
function drawHeatmap(canvasId, matrix) {
    drawHeatmapOnCanvas(document.getElementById(canvasId), matrix);
}

function drawAnnotationOverlay(canvasId, cells) {
    drawAnnotationOnCanvas(document.getElementById(canvasId), cells);
}

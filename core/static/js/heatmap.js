// Simple heatmap rendering on canvas from 32x32 matrix
function drawHeatmap(canvasId, matrix) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const cellW = width / 32;
    const cellH = height / 32;

    for (let r = 0; r < 32; r++) {
        for (let c = 0; c < 32; c++) {
            const value = matrix[r][c];
            const norm = value / 4095;
            const color = `rgba(${Math.floor(255 * norm)},0,${Math.floor(255*(1-norm))},1)`;
            ctx.fillStyle = color;
            ctx.fillRect(c * cellW, r * cellH, cellW, cellH);
        }
    }
}

// Example usage: drawHeatmap('heatmapCanvas', someMatrix);

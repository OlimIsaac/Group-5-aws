(function () {
    'use strict';

    let currentHours = 1;
    let pressureChart = null;

    function initChart() {
        const ctx = document.getElementById('pressureChart').getContext('2d');
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

                // Chart — replace arrays fully, do not mutate in place
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
        // 1. Build chart first
        initChart();
        // 2. Load initial data
        loadData(1);
        // 3. Start polling
        setInterval(function () { loadData(currentHours); }, 8000);

        // Wire time filter buttons
        document.querySelectorAll('.time-btn').forEach(function (btn) {
            btn.addEventListener('click', function () {
                loadData(parseInt(btn.dataset.hours));
            });
        });
    });
}());

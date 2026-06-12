document.addEventListener('DOMContentLoaded', () => {
    const refreshBtn = document.getElementById('refresh-analytics');
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadAnalytics);
    }
    
    loadAnalytics();
});

function loadAnalytics() {
    // Set loading states
    document.getElementById('total-queries').textContent = '...';
    document.getElementById('query-volume-chart').innerHTML = 'Loading chart data...';
    document.getElementById('latency-chart').innerHTML = 'Loading chart data...';
    
    // Mock API delay (Phase 5 will fetch real metrics)
    setTimeout(() => {
        document.getElementById('total-queries').textContent = '4,821';
        document.getElementById('retrieval-latency').textContent = '120 ms';
        document.getElementById('generation-latency').textContent = '2.4 s';
        document.getElementById('confidence-score').textContent = '88%';
        
        drawBarChart('query-volume-chart', [
            { label: 'Mon', value: 420 },
            { label: 'Tue', value: 550 },
            { label: 'Wed', value: 810 },
            { label: 'Thu', value: 650 },
            { label: 'Fri', value: 920 },
            { label: 'Sat', value: 310 },
            { label: 'Sun', value: 250 }
        ]);

        drawHorizontalBarChart('latency-chart', [
            { label: 'Embedding', value: 45 },
            { label: 'Vector DB', value: 25 },
            { label: 'Re-ranking', value: 50 },
            { label: 'LLM Gen', value: 2400 }
        ]);

    }, 800);
}

/**
 * Pure JavaScript/SVG Vertical Bar Chart Generator
 */
function drawBarChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const maxVal = Math.max(...data.map(d => d.value));
    
    // Use explicit percentages for layout to prevent font-size distortion
    let svgHtml = `<svg width="100%" height="100%" style="overflow: visible;">`;
    
    const barWidth = 100 / (data.length * 2);
    
    data.forEach((d, i) => {
        const height = (d.value / maxVal) * 70; // max 70% height to leave room for labels
        const x = (i * (100 / data.length)) + (100 / data.length / 4);
        const y = 85 - height;
        
        svgHtml += `
            <rect class="chart-bar" x="${x}%" y="${y}%" width="${barWidth}%" height="${height}%" fill="var(--primary)" rx="4">
                <animate attributeName="height" from="0%" to="${height}%" dur="0.5s" fill="freeze" />
                <animate attributeName="y" from="85%" to="${y}%" dur="0.5s" fill="freeze" />
            </rect>
            <text x="${x + barWidth/2}%" y="98%" font-size="12px" fill="var(--text-secondary)" text-anchor="middle" font-family="var(--font-family)">${d.label}</text>
            <text x="${x + barWidth/2}%" y="${y - 3}%" font-size="14px" font-weight="600" fill="var(--text-primary)" text-anchor="middle" font-family="var(--font-family)">${d.value}</text>
        `;
    });
    
    svgHtml += `</svg>`;
    container.innerHTML = svgHtml;
}

/**
 * Pure JavaScript/SVG Horizontal Bar Chart Generator
 */
function drawHorizontalBarChart(containerId, data) {
    const container = document.getElementById(containerId);
    if (!container) return;
    
    const maxVal = Math.max(...data.map(d => d.value));
    let svgHtml = `<svg width="100%" height="100%" style="overflow: visible;">`;
    
    const gap = 100 / data.length;
    
    data.forEach((d, i) => {
        const width = (d.value / maxVal) * 55; // 55% max width
        const y = (i * gap) + (gap / 2) - 5; // center in the gap vertically
        
        svgHtml += `
            <text x="2%" y="${y + 5}%" font-size="12px" fill="var(--text-secondary)" font-family="var(--font-family)" dominant-baseline="middle">${d.label}</text>
            <rect class="chart-bar" x="25%" y="${y}%" width="${width || 1}%" height="10%" fill="var(--accent)" rx="4">
                <animate attributeName="width" from="0%" to="${width || 1}%" dur="0.5s" fill="freeze" />
            </rect>
            <text x="${25 + width + 2}%" y="${y + 5}%" font-size="14px" font-weight="600" fill="var(--text-primary)" font-family="var(--font-family)" dominant-baseline="middle">${d.value} ms</text>
        `;
    });
    
    svgHtml += `</svg>`;
    container.innerHTML = svgHtml;
}

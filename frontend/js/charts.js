/**
 * SmartFlow 3D - Analytics & Comparison Charts
 * Renders lightweight, high-performance SVG sparkline and bar charts for trends and comparisons.
 */

class SmartFlowCharts {
  constructor() {
    this.history = {
      timestamps: [],
      waitingTimes: [],
      queueLengths: [],
      throughputs: [],
      congestions: [],
    };
    this.maxPoints = 40;
  }

  recordSnapshot(metrics, timeS) {
    if (!metrics) return;
    this.history.timestamps.push(timeS || (this.history.timestamps.length * 2));
    this.history.waitingTimes.push(metrics.average_waiting_time_s || 0);
    this.history.queueLengths.push(metrics.average_queue_length || 0);
    this.history.throughputs.push(metrics.throughput_vph || 0);
    this.history.congestions.push((metrics.congestion_index || 0) * 100);

    if (this.history.timestamps.length > this.maxPoints) {
      this.history.timestamps.shift();
      this.history.waitingTimes.shift();
      this.history.queueLengths.shift();
      this.history.throughputs.shift();
      this.history.congestions.shift();
    }
  }

  renderLineChart(containerId, dataKey, colorHex = '#06b6d4', unit = '') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const data = this.history[dataKey] || [];
    if (data.length < 2) {
      container.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-dim);font-size:0.8rem">Recording simulation metrics...</div>`;
      return;
    }

    const w = container.clientWidth || 400;
    const h = container.clientHeight || 180;
    const padding = 28;

    const maxVal = Math.max(...data, 1) * 1.15;
    const minVal = 0;

    const points = data.map((val, idx) => {
      const x = padding + (idx / (data.length - 1)) * (w - padding * 2);
      const y = h - padding - ((val - minVal) / (maxVal - minVal)) * (h - padding * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });

    const pathD = `M ${points.join(' L ')}`;
    const areaD = `M ${padding},${h - padding} L ${points.join(' L ')} L ${w - padding},${h - padding} Z`;

    const latestVal = data[data.length - 1];

    container.innerHTML = `
      <svg viewBox="0 0 ${w} ${h}">
        <defs>
          <linearGradient id="grad_${dataKey}" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="${colorHex}" stop-opacity="0.35"/>
            <stop offset="100%" stop-color="${colorHex}" stop-opacity="0.0"/>
          </linearGradient>
        </defs>

        <!-- Grid Lines -->
        <line x1="${padding}" y1="${padding}" x2="${w - padding}" y2="${padding}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4,4"/>
        <line x1="${padding}" y1="${h / 2}" x2="${w - padding}" y2="${h / 2}" stroke="rgba(255,255,255,0.06)" stroke-dasharray="4,4"/>
        <line x1="${padding}" y1="${h - padding}" x2="${w - padding}" y2="${h - padding}" stroke="rgba(255,255,255,0.1)"/>

        <!-- Area Fill -->
        <path d="${areaD}" fill="url(#grad_${dataKey})" />

        <!-- Line Stroke -->
        <path d="${pathD}" fill="none" stroke="${colorHex}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />

        <!-- Axis Value Badges -->
        <text x="${padding}" y="${padding - 8}" fill="#94a3b8" font-size="10" font-family="'JetBrains Mono', monospace">${maxVal.toFixed(1)}${unit}</text>
        <text x="${w - padding}" y="${h - padding + 16}" text-anchor="end" fill="#38bdf8" font-size="11" font-weight="600" font-family="'JetBrains Mono', monospace">${latestVal.toFixed(1)} ${unit}</text>
      </svg>
    `;
  }

  renderBarComparison(containerId, baselineVal, optVal, label, unit = '') {
    const container = document.getElementById(containerId);
    if (!container) return;

    const max = Math.max(baselineVal, optVal, 1) * 1.15;
    const basePct = (baselineVal / max) * 100;
    const optPct = (optVal / max) * 100;

    container.innerHTML = `
      <div style="display:flex;flex-direction:column;gap:0.4rem;width:100%">
        <div style="display:flex;justify-content:space-between;font-size:0.8rem;color:var(--text-sub)">
          <span>${label}</span>
          <span>Baseline: <strong>${baselineVal}</strong> &rarr; Opt: <strong style="color:#38bdf8">${optVal}</strong> ${unit}</span>
        </div>
        <div style="display:flex;flex-direction:column;gap:0.25rem;">
          <div style="height:8px;background:rgba(255,255,255,0.08);border-radius:999px;overflow:hidden">
            <div style="height:100%;width:${basePct}%;background:#64748b;border-radius:999px"></div>
          </div>
          <div style="height:8px;background:rgba(255,255,255,0.08);border-radius:999px;overflow:hidden">
            <div style="height:100%;width:${optPct}%;background:#06b6d4;border-radius:999px"></div>
          </div>
        </div>
      </div>
    `;
  }
}

window.smartFlowCharts = new SmartFlowCharts();

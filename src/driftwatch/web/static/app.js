/* DriftWatch Dashboard — Vanilla JS */

const API = '/api';

// --- Navigation ---
document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
    });
});

// --- Helpers ---
async function fetchJSON(url) {
    const res = await fetch(url);
    return res.json();
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

function formatTime(iso) {
    const d = new Date(iso);
    return d.toLocaleString();
}

// --- Timeline ---
async function loadTimeline() {
    const data = await fetchJSON(`${API}/snapshots?limit=50`);
    const container = document.getElementById('timeline-list');

    if (!data.snapshots || data.snapshots.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No snapshots yet</h3>
                <p>Run <code>driftwatch scan --demo</code> to generate demo data</p>
            </div>`;
        return;
    }

    container.innerHTML = data.snapshots.map(s => `
        <div class="timeline-item" data-id="${escapeHtml(s.id)}">
            <div>
                <span class="timeline-id">${escapeHtml(s.id)}</span>
                <span class="timeline-time">${formatTime(s.timestamp)}</span>
            </div>
            <div class="timeline-meta">
                <span class="badge badge-count">${s.resource_count} resources</span>
                ${s.providers.map(p => `<span class="badge badge-provider">${escapeHtml(p)}</span>`).join('')}
            </div>
        </div>
    `).join('');
}

// --- Diff View ---
async function loadDiffSelectors() {
    const data = await fetchJSON(`${API}/snapshots?limit=50`);
    const beforeSel = document.getElementById('diff-before');
    const afterSel = document.getElementById('diff-after');
    const graphSel = document.getElementById('graph-snapshot');

    const options = (data.snapshots || []).map(s =>
        `<option value="${escapeHtml(s.id)}">${escapeHtml(s.id)} — ${formatTime(s.timestamp)}</option>`
    ).join('');

    beforeSel.innerHTML = options;
    afterSel.innerHTML = options;
    graphSel.innerHTML = options;

    // Default: compare last two
    if (data.snapshots && data.snapshots.length >= 2) {
        afterSel.selectedIndex = 0;
        beforeSel.selectedIndex = 1;
    }
}

document.getElementById('diff-btn').addEventListener('click', async () => {
    const beforeId = document.getElementById('diff-before').value;
    const afterId = document.getElementById('diff-after').value;
    if (!beforeId || !afterId) return;

    const data = await fetchJSON(`${API}/diff/${beforeId}/${afterId}`);
    renderDiff(data);
});

function renderDiff(data) {
    const summary = document.getElementById('diff-summary');
    const container = document.getElementById('diff-result');

    if (data.error) {
        container.innerHTML = `<div class="empty-state"><h3>${escapeHtml(data.error)}</h3></div>`;
        summary.innerHTML = '';
        return;
    }

    const s = data.summary;
    summary.innerHTML = `
        <div class="diff-stat added">+${s.added} added</div>
        <div class="diff-stat removed">-${s.removed} removed</div>
        <div class="diff-stat modified">~${s.modified} modified</div>
    `;

    if (!data.changes || data.changes.length === 0) {
        container.innerHTML = '<div class="empty-state"><h3>No changes detected</h3></div>';
        return;
    }

    container.innerHTML = data.changes.map(c => {
        const type = c.change_type;
        let detail = '';
        if (c.field_path) {
            detail = `<span>${escapeHtml(c.field_path)}: `;
            if (c.old_value !== null && c.old_value !== undefined) {
                detail += `<span class="old-val">${escapeHtml(JSON.stringify(c.old_value))}</span> → `;
            }
            if (c.new_value !== null && c.new_value !== undefined) {
                detail += `<span class="new-val">${escapeHtml(JSON.stringify(c.new_value))}</span>`;
            }
            detail += '</span>';
        }
        return `
            <div class="change-row ${type}">
                <span class="change-type ${type}">${type}</span>
                <span class="change-resource">${escapeHtml(c.resource_id)}</span>
                <span class="change-detail">${detail || '—'}</span>
            </div>`;
    }).join('');
}

// --- Alerts ---
async function loadAlerts() {
    const data = await fetchJSON(`${API}/anomalies?limit=20`);
    const container = document.getElementById('alerts-list');

    if (!data.anomalies || data.anomalies.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h3>No anomalies detected</h3>
                <p>Run multiple scans to enable drift detection</p>
            </div>`;
        return;
    }

    container.innerHTML = data.anomalies.map(a => `
        <div class="alert-item">
            <span class="severity-badge severity-${a.severity}">${escapeHtml(a.severity)}</span>
            <span class="alert-resource">${escapeHtml(a.resource_id)}</span>
            <span class="alert-desc">${escapeHtml(a.description)}</span>
        </div>
    `).join('');
}

// --- Dependency Graph (Canvas) ---
document.getElementById('graph-btn').addEventListener('click', async () => {
    const snapId = document.getElementById('graph-snapshot').value;
    if (!snapId) return;
    const data = await fetchJSON(`${API}/graph/${snapId}`);
    renderGraph(data);
});

function renderGraph(data) {
    const canvas = document.getElementById('graph-canvas');
    const ctx = canvas.getContext('2d');
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (!data.nodes || data.nodes.length === 0) {
        ctx.fillStyle = '#8b949e';
        ctx.font = '16px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No resources in this snapshot', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Simple force-directed-ish layout
    const providerColors = {
        aws: '#ff9900',
        docker: '#2496ed',
        kubernetes: '#326ce5',
        terraform: '#7b42bc',
        demo: '#58a6ff',
    };

    const padding = 60;
    const nodes = data.nodes.map((n, i) => {
        const angle = (2 * Math.PI * i) / data.nodes.length;
        const rx = (canvas.width - padding * 2) / 2.5;
        const ry = (canvas.height - padding * 2) / 2.5;
        return {
            ...n,
            x: canvas.width / 2 + rx * Math.cos(angle),
            y: canvas.height / 2 + ry * Math.sin(angle),
        };
    });

    const nodeMap = {};
    nodes.forEach(n => { nodeMap[n.id] = n; });

    // Draw edges
    ctx.strokeStyle = 'rgba(48, 54, 61, 0.7)';
    ctx.lineWidth = 1;
    data.edges.forEach(e => {
        const src = nodeMap[e.source];
        const tgt = nodeMap[e.target];
        if (src && tgt) {
            ctx.beginPath();
            ctx.moveTo(src.x, src.y);
            ctx.lineTo(tgt.x, tgt.y);
            ctx.stroke();

            // Arrow
            const angle = Math.atan2(tgt.y - src.y, tgt.x - src.x);
            const arrowLen = 8;
            const ax = tgt.x - 14 * Math.cos(angle);
            const ay = tgt.y - 14 * Math.sin(angle);
            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(ax - arrowLen * Math.cos(angle - 0.4), ay - arrowLen * Math.sin(angle - 0.4));
            ctx.lineTo(ax - arrowLen * Math.cos(angle + 0.4), ay - arrowLen * Math.sin(angle + 0.4));
            ctx.closePath();
            ctx.fillStyle = 'rgba(48, 54, 61, 0.7)';
            ctx.fill();
        }
    });

    // Draw nodes
    nodes.forEach(n => {
        const color = providerColors[n.provider] || '#58a6ff';
        ctx.beginPath();
        ctx.arc(n.x, n.y, 8, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = '#e6edf3';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // Label
        ctx.fillStyle = '#e6edf3';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        const label = n.name.length > 25 ? n.name.slice(0, 22) + '...' : n.name;
        ctx.fillText(label, n.x, n.y + 20);
    });
}

// --- Init ---
async function init() {
    await loadTimeline();
    await loadDiffSelectors();
    await loadAlerts();
}

init();

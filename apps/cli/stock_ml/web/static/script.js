let rawData = [];
let filteredData = [];
let currentSort = { col: 'precision_high_conf', dir: 'desc' };

async function init() {
    try {
        const response = await fetch('/api/data');
        rawData = await response.json();
        filteredData = [...rawData];
        
        renderStats();
        renderTable();
        
        document.getElementById('search').addEventListener('input', e => {
            const term = e.target.value.toUpperCase();
            filteredData = rawData.filter(item => item.ticker.includes(term));
            renderTable();
        });

        document.querySelectorAll('th[data-col]').forEach(th => {
            th.addEventListener('click', () => {
                const col = th.getAttribute('data-col');
                const dir = currentSort.col === col && currentSort.dir === 'desc' ? 'asc' : 'desc';
                currentSort = { col, dir };
                document.querySelectorAll('th').forEach(el => el.classList.remove('sort-asc', 'sort-desc'));
                th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
                sortAndRender();
            });
        });
    } catch (err) {
        console.error("Failed to load data:", err);
    }
}

function sortAndRender() {
    filteredData.sort((a, b) => {
        let valA = a[currentSort.col];
        let valB = b[currentSort.col];
        if (typeof valA === 'string') {
            return currentSort.dir === 'asc' ? valA.localeCompare(valB) : valB.localeCompare(valA);
        }
        return currentSort.dir === 'asc' ? valA - valB : valB - valA;
    });
    renderTable();
}

function renderStats() {
    const globalAvg = (rawData.reduce((acc, cur) => acc + cur.global_acc, 0) / rawData.length) * 100;
    const precisionAvg = (rawData.filter(d => d.precision_high_conf > 0).reduce((acc, cur) => acc + cur.precision_high_conf, 0) / 
                         rawData.filter(d => d.precision_high_conf > 0).length) * 100;
    const liarAvg = (rawData.reduce((acc, cur) => acc + cur.random_acc, 0) / rawData.length) * 100;
    const validated = rawData.filter(d => d.precision_high_conf >= 0.8).length;

    document.getElementById('stat-global').textContent = globalAvg.toFixed(2) + '%';
    document.getElementById('stat-precision').textContent = precisionAvg.toFixed(2) + '%';
    document.getElementById('stat-liar').textContent = liarAvg.toFixed(1) + '%';
    document.getElementById('stat-validated').textContent = validated + ' / ' + rawData.length;
}

function renderTable() {
    const tbody = document.querySelector('tbody');
    tbody.innerHTML = '';

    filteredData.forEach(row => {
        const sig = row.latest_signal;
        const sigType = sig.includes('LONG') ? 'LONG' : sig.includes('SHORT') ? 'SHORT' : 'NEUTRAL';
        const badgeClass = sigType === 'LONG' ? 'badge-long' : sigType === 'SHORT' ? 'badge-short' : 'badge-neutral';
        const probPct = row.latest_prob * 100;
        const precColor = row.precision_high_conf >= 0.8 ? '#000' : 'inherit';

        const tr = document.createElement('tr');
        tr.style.cursor = "pointer";
        tr.onclick = () => showDeepAnalysis(row.ticker);
        tr.innerHTML = `
            <td class="ticker-cell">${row.ticker}</td>
            <td>${(row.global_acc * 100).toFixed(1)}%</td>
            <td style="color: ${precColor}; font-weight: 500">${(row.precision_high_conf * 100).toFixed(1)}%</td>
            <td>${row.n_selective_signals}</td>
            <td><span class="badge ${badgeClass}">${sigType}</span></td>
            <td>
                <div class="conf-wrap">
                    <span style="min-width: 45px">${prob_pct.toFixed(1)}%</span>
                    <div class="bar-bg"><div class="bar-fill" style="width: ${prob_pct}%"></div></div>
                </div>
            </td>
            <td class="timestamp">${row.timestamp}</td>
        `;
        tbody.appendChild(tr);
    });
}

async function showDeepAnalysis(ticker) {
    const modal = document.getElementById('modal');
    const content = document.getElementById('modal-content');
    content.innerHTML = `<div style="padding: 2rem; text-align: center;">Analyzing ${ticker} structural data...</div>`;
    modal.style.display = 'block';

    try {
        const res = await fetch(`/api/analyze/${ticker}`);
        const d = await res.json();
        
        if (d.error) {
            content.innerHTML = `<div style="padding: 2rem; color: red;">Error: ${d.error}</div>`;
            return;
        }

        content.innerHTML = `
            <div style="padding: 2rem;">
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 2rem;">
                    <h2 style="margin: 0; font-size: 1.5rem;">${d.ticker} // DEEP ANALYSIS</h2>
                    <div style="font-family: monospace; font-size: 0.8rem; color: #717171;">Structural Score: ${d.score}/10</div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 3rem;">
                    <div>
                        <div style="font-size: 0.7rem; text-transform: uppercase; color: #717171; margin-bottom: 1rem;">Execution Levels</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">Price</span><span style="font-size: 1.1rem;">$${d.price}</span></div>
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">Signal</span><span style="font-size: 1.1rem; font-weight: 600;">${d.signal}</span></div>
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">Support</span><span style="font-size: 0.9rem;">$${d.support}</span></div>
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">Resistance</span><span style="font-size: 0.9rem;">$${d.resistance}</span></div>
                            <div style="grid-column: span 2; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #eee;">
                                <div style="display: flex; justify-content: space-between; color: #ef4444;"><span>Stop Loss</span><span>$${d.stop_loss}</span></div>
                                <div style="display: flex; justify-content: space-between; color: #22c55e;"><span>Take Profit</span><span>$${d.take_profit}</span></div>
                            </div>
                        </div>
                    </div>
                    
                    <div>
                        <div style="font-size: 0.7rem; text-transform: uppercase; color: #717171; margin-bottom: 1rem;">Risk Dynamics</div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">Win Rate</span><span style="font-size: 0.9rem;">${d.win_rate}</span></div>
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">RR Ratio</span><span style="font-size: 0.9rem;">1:${d.rr_ratio}</span></div>
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">Kelly Crit.</span><span style="font-size: 0.9rem;">${d.kelly}</span></div>
                            <div><span style="display:block; font-size: 0.7rem; color: #717171;">Pos. Size</span><span style="font-size: 0.9rem;">${d.pos_size} units</span></div>
                            <div style="grid-column: span 2; margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #eee;">
                                <div style="display: flex; justify-content: space-between;"><span>Macro (CSS)</span><span>${d.css}</span></div>
                                <div style="display: flex; justify-content: space-between;"><span>Trend (MRZG)</span><span>${d.mrzg}</span></div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 3rem; text-align: right;">
                    <button onclick="document.getElementById('modal').style.display='none'" style="border: 1px solid #000; padding: 0.5rem 2rem;">CLOSE</button>
                </div>
            </div>
        `;
    } catch (err) {
        content.innerHTML = `<div style="padding: 2rem; color: red;">Failed to fetch deep analysis.</div>`;
    }
}

function filterVerified() {
    document.getElementById('btn-all').classList.remove('active');
    document.getElementById('btn-verified').classList.add('active');
    filteredData = rawData.filter(d => d.precision_high_conf >= 0.8);
    renderTable();
}

function filterAll() {
    document.getElementById('btn-all').classList.add('active');
    document.getElementById('btn-verified').classList.remove('active');
    filteredData = [...rawData];
    renderTable();
}

window.addEventListener('DOMContentLoaded', init);
window.onclick = (e) => { if(e.target == document.getElementById('modal')) document.getElementById('modal').style.display='none'; }

let pollInterval = null;
let industryChartInstance = null;

// Heatmap state
const hmState = { metric: "price", period: "1d", view: "stock" };

document.addEventListener("DOMContentLoaded", () => {
    fetchMarketOverview();
    fetchPotentialStocks();
    fetchHeatmap();
    checkSyncStatus();

    document.getElementById("btn-refresh").addEventListener("click", () => {
        fetchMarketOverview();
        fetchPotentialStocks();
        fetchHeatmap();
    });

    document.getElementById("btn-sync").addEventListener("click", () => {
        triggerSync();
    });

    // Heatmap toolbar listeners
    document.getElementById("hm-metric-group").addEventListener("click", e => {
        const btn = e.target.closest(".sw");
        if (!btn) return;
        hmState.metric = btn.dataset.metric;
        setActiveSwitch("hm-metric-group", btn);
        fetchHeatmap();
    });

    document.getElementById("hm-period-group").addEventListener("click", e => {
        const btn = e.target.closest(".sw");
        if (!btn) return;
        hmState.period = btn.dataset.period;
        setActiveSwitch("hm-period-group", btn);
        fetchHeatmap();
    });

    document.getElementById("hm-view-group").addEventListener("click", e => {
        const btn = e.target.closest(".sw");
        if (!btn) return;
        hmState.view = btn.dataset.view;
        setActiveSwitch("hm-view-group", btn);
        fetchHeatmap();
    });
});

function setActiveSwitch(groupId, activeBtn) {
    document.getElementById(groupId).querySelectorAll(".sw").forEach(b => b.classList.remove("active"));
    activeBtn.classList.add("active");
}

// ============================================================
// MARKET OVERVIEW
// ============================================================
async function fetchMarketOverview() {
    try {
        const res = await fetch("/api/market-overview");
        const data = await res.json();

        if (data.error && !data.gainers) {
            console.warn("Market overview lỗi:", data.error);
            return;
        }

        const gainers   = data.gainers   || 0;
        const losers    = data.losers    || 0;
        const unchanged = data.unchanged || 0;
        const total     = data.total_stocks || (gainers + losers + unchanged);

        // KPI Breadth
        document.getElementById("kpi-gainers").innerText  = gainers;
        document.getElementById("kpi-unchanged").innerText = unchanged;
        document.getElementById("kpi-losers").innerText   = losers;

        // Breadth bar proportions
        if (total > 0) {
            document.getElementById("breadth-bar-green").style.width  = ((gainers / total) * 100).toFixed(1) + "%";
            document.getElementById("breadth-bar-yellow").style.width = ((unchanged / total) * 100).toFixed(1) + "%";
            document.getElementById("breadth-bar-red").style.width    = ((losers / total) * 100).toFixed(1) + "%";
        }

        // Header badge
        if (total > 0) {
            document.getElementById("header-total").innerText = `${total} mã HOSE`;
            document.getElementById("total-stocks-badge").classList.remove("hidden");
        }

        // Stats card
        document.getElementById("stat-total").innerText      = total;
        document.getElementById("stat-gain-pct").innerText   = total > 0 ? ((gainers / total) * 100).toFixed(1) + "%" : "—";
        document.getElementById("stat-loss-pct").innerText   = total > 0 ? ((losers / total) * 100).toFixed(1) + "%" : "—";
        document.getElementById("stat-unch-pct").innerText   = total > 0 ? ((unchanged / total) * 100).toFixed(1) + "%" : "—";

        // Top gainers / losers (card 2)
        renderTopMiniList(data.top_gainers || [], "top-gainers-list", true);
        renderTopMiniList(data.top_losers  || [], "top-losers-list",  false);

    } catch (err) {
        console.error("Fetch market overview failed:", err);
    }
}

function renderTopMiniList(items, elementId, isGainer) {
    const ul = document.getElementById(elementId);
    ul.innerHTML = "";
    if (!items.length) {
        ul.innerHTML = `<li style="color:var(--text-secondary);font-size:0.8rem">Chưa có dữ liệu</li>`;
        return;
    }
    items.forEach(item => {
        const sign  = item.percent_change > 0 ? "+" : "";
        const color = isGainer ? "var(--green)" : "var(--red)";
        const li = document.createElement("li");
        li.innerHTML = `
            <span class="stock-sym">${item.symbol}</span>
            <span class="stock-pct" style="color:${color}">${sign}${(item.percent_change || 0).toFixed(2)}%</span>
            <span class="stock-val">${formatNumber(item.total_value)}</span>
        `;
        ul.appendChild(li);
    });
}

// ============================================================
// POTENTIAL STOCKS SCREENER
// ============================================================
async function fetchPotentialStocks() {
    try {
        const res  = await fetch("/api/potential-stocks");
        const json = await res.json();

        if (json.last_updated > 0) {
            const date = new Date(json.last_updated * 1000);
            document.getElementById("last-update").innerText =
                `Sync lúc: ${date.toLocaleTimeString("vi-VN")} ${date.toLocaleDateString("vi-VN")}`;
        }

        const tbody = document.getElementById("potential-tbody");
        tbody.innerHTML = "";

        if (!json.data || json.data.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="11" class="text-center empty-state">
                    <div class="empty-icon">📊</div>
                    Chưa có cổ phiếu nào thỏa tiêu chí hoặc chưa đồng bộ.<br>
                    Vui lòng bấm <strong>Sync Historical Data</strong>.
                </td></tr>`;
            return;
        }

        json.data.forEach(item => {
            const tr = document.createElement("tr");

            // Tín hiệu
            const signals = [];
            if (item.rsi <= 35 && item.stoch_k <= 20)
                signals.push('<span class="signal-badge sig-oversold">⚡ Quá Bán</span>');
            if (item.is_uptrend)
                signals.push('<span class="signal-badge sig-cross">✨ Uptrend</span>');

            const pctChange = item.percent_change || 0;
            const pctColor  = pctChange > 0 ? "var(--green)" : pctChange < 0 ? "var(--red)" : "var(--yellow)";
            const pctSign   = pctChange > 0 ? "+" : "";

            tr.innerHTML = `
                <td><strong>${item.symbol}</strong></td>
                <td style="color:var(--text-secondary);font-size:0.82rem">${item.industry || '—'}</td>
                <td><strong>${(item.close || 0).toLocaleString("vi-VN")}</strong></td>
                <td style="color:${pctColor};font-weight:600">${pctSign}${pctChange.toFixed(2)}%</td>
                <td style="${item.rsi <= 35 ? 'color:var(--yellow);font-weight:700' : ''}">${(item.rsi || 0).toFixed(1)}</td>
                <td>${(item.stoch_k || 0).toFixed(1)}</td>
                <td style="font-size:0.82rem">${(item.ma50 || 0).toFixed(0)} <span style="color:var(--text-secondary)">/</span> ${(item.ma100 || 0).toFixed(0)}</td>
                <td>${signals.join(" ")}</td>
                <td>${item.pe > 0 ? item.pe.toFixed(1) : '—'}</td>
                <td>${item.pb > 0 ? item.pb.toFixed(1) : '—'}</td>
                <td>${formatNumber(item.avg_match_volume_2w || item.volume || 0)}</td>
            `;
            tbody.appendChild(tr);
        });

    } catch (err) {
        console.error("Fetch potential failed:", err);
    }
}

// ============================================================
// SYNC STATUS POLLING
// ============================================================
async function checkSyncStatus() {
    try {
        const res    = await fetch("/api/status");
        const status = await res.json();
        const banner = document.getElementById("sync-progress");
        const msg    = document.getElementById("sync-message");
        const bar    = document.getElementById("progress-fill");
        const pctEl  = document.getElementById("progress-pct");

        if (status.is_syncing) {
            banner.classList.remove("hidden");
            msg.innerText = status.message || "Đang đồng bộ...";

            if (status.total > 0) {
                const pct = Math.round((status.progress / status.total) * 100);
                bar.style.width = pct + "%";
                pctEl.innerText = pct + "%";
            }

            if (!pollInterval) {
                pollInterval = setInterval(checkSyncStatus, 3000);
            }
        } else {
            banner.classList.add("hidden");
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
                // Tải lại dữ liệu sau khi sync xong
                fetchMarketOverview();
                fetchPotentialStocks();
            }
        }
    } catch (err) {
        console.error("Check sync status failed:", err);
    }
}

async function triggerSync() {
    try {
        const res  = await fetch("/api/sync", { method: 'POST' });
        const data = await res.json();
        if (data.status === "started" || data.status === "already_running") {
            document.getElementById("sync-progress").classList.remove("hidden");
            document.getElementById("sync-message").innerText = data.status === "started"
                ? "Đang khởi chạy đồng bộ..."
                : "Đang đồng bộ (đã chạy phiên trước)...";
            checkSyncStatus();
        }
    } catch (err) {
        console.error("Trigger sync failed:", err);
    }
}

// ============================================================
// UTILITY
// ============================================================
function formatNumber(num) {
    if (num === null || num === undefined || num === 0) return "—";
    const n = Math.abs(num);
    if (n >= 1e9)  return (num / 1e9).toFixed(2) + " Tỷ";
    if (n >= 1e6)  return (num / 1e6).toFixed(2) + " Tr";
    if (n >= 1e3)  return (num / 1e3).toFixed(1) + " K";
    return num.toLocaleString("vi-VN");
}

// ============================================================
// HEATMAP — Squarified Treemap on SVG
// ============================================================
async function fetchHeatmap() {
    try {
        const url = `/api/heatmap?metric=${hmState.metric}&period=${hmState.period}&top=200`;
        const res  = await fetch(url);
        const json = await res.json();

        if (!json.data || json.data.length === 0) {
            showHeatmapEmpty(json.error || "Chưa có dữ liệu.");
            return;
        }

        renderHeatmapSVG(json.data, hmState.metric, hmState.period, hmState.view);
    } catch (err) {
        console.error("Fetch heatmap failed:", err);
        showHeatmapEmpty("Lỗi tải dữ liệu heatmap.");
    }
}

function showHeatmapEmpty(msg) {
    document.getElementById("heatmap-empty").querySelector("span").innerHTML =
        msg + ' Vui lòng bấm <strong>Sync Historical Data</strong>.';
    document.getElementById("heatmap-empty").style.display = "flex";
    document.getElementById("heatmap-svg").style.display   = "none";
}


// ---- Color scale ----
function pctToColor(val, metric) {
    // For net_volume, normalise differently
    let v = val;
    if (metric === "net_volume") {
        // treat as positive/negative sign
        v = Math.max(-1, Math.min(1, val / 1e7)) * 5;
    }
    const clamped = Math.max(-5, Math.min(5, v)); // ±5%
    const t = (clamped + 5) / 10; // 0→1
    if (t < 0.5) {
        const u = t * 2;
        const r = Math.round(239 + (63 - 239) * u);
        const g = Math.round(68  + (63 - 68)  * u);
        const b = Math.round(68  + (70 - 68)  * u);
        return `rgb(${r},${g},${b})`;
    } else {
        const u = (t - 0.5) * 2;
        const r = Math.round(63 + (16  - 63) * u);
        const g = Math.round(63 + (185 - 63) * u);
        const b = Math.round(70 + (129 - 70) * u);
        return `rgb(${r},${g},${b})`;
    }
}

// ---- Main SVG Render ----
function renderHeatmapSVG(data, metric, period, view = "stock") {
    const svgEl    = d3.select("#heatmap-svg");
    const emptyEl  = document.getElementById("heatmap-empty");
    const container = document.getElementById("heatmap-container");

    svgEl.style("display", "block");
    emptyEl.style.display = "none";

    const W = container.clientWidth || 900;
    const H = 480;
    svgEl.attr("viewBox", `0 0 ${W} ${H}`)
         .attr("width", W)
         .attr("height", H);

    // Group by industry
    const rootData = { name: "root", children: [] };
    const industryMap = {};
    for (const d of data) {
        if (!d.volume || d.volume <= 0) continue;
        const ind = d.industry || "Khác";
        if (!industryMap[ind]) {
            industryMap[ind] = { name: ind, children: [], volume: 0, weightedValueSum: 0, pct_1d_sum: 0, close_sum: 0 };
            rootData.children.push(industryMap[ind]);
        }
        industryMap[ind].children.push({ ...d, name: d.symbol, value: d.value });
        industryMap[ind].volume += d.volume;
        industryMap[ind].weightedValueSum += (d.volume * (d.value || 0));
        industryMap[ind].pct_1d_sum += (d.volume * (d.pct_1d || 0));
        industryMap[ind].close_sum += (d.close || 0);
    }

    if (view === "industry") {
        rootData.children.forEach(ind => {
            ind.value = ind.volume > 0 ? ind.weightedValueSum / ind.volume : 0;
            ind.pct_1d = ind.volume > 0 ? ind.pct_1d_sum / ind.volume : 0;
            ind.close = ind.children.length > 0 ? ind.close_sum / ind.children.length : 0;
            ind.symbol = ind.name;
            ind.industry = "Ngành";
            ind.children = undefined; // Leaf node
        });
    }

    if (rootData.children.length === 0) {
        showHeatmapEmpty("Dữ liệu volume bằng 0.");
        return;
    }

    // Process D3 Hierarchy
    const root = d3.hierarchy(rootData)
        .sum(d => d.children ? 0 : d.volume)
        .sort((a, b) => b.value - a.value);

    // Treemap layout
    d3.treemap()
        .size([W, H])
        .paddingInner(1)
        .paddingOuter(1)
        .paddingTop(view === "stock" ? 20 : 0) // space for industry label only for stocks
        .round(false)
        .tile(d3.treemapSquarify)(root);

    svgEl.selectAll("*").remove();

    // Tooltip elements
    const tooltip  = document.getElementById("hm-tooltip");
    const ttSym    = document.getElementById("hm-tt-sym");
    const ttInd    = document.getElementById("hm-tt-ind");
    const ttPrice  = document.getElementById("hm-tt-price");
    const ttPct1d  = document.getElementById("hm-tt-pct1d");
    const ttVol    = document.getElementById("hm-tt-vol");

    // Draw industry backgrounds (depth 1)
    if (view === "stock") {
        const industries = svgEl.selectAll(".industry-group")
            .data(root.children || [])
            .enter()
            .append("g")
            .attr("class", "industry-group")
            .attr("transform", d => `translate(${d.x0}, ${d.y0})`);

        industries.append("rect")
            .attr("width", d => Math.max(0, d.x1 - d.x0))
            .attr("height", d => Math.max(0, d.y1 - d.y0))
            .attr("fill", "rgba(0,0,0,0.15)")
            .attr("rx", 4);

        industries.append("text")
            .attr("class", "hm-group-label")
            .attr("x", 6)
            .attr("y", 14)
            .text(d => {
                const ind = d.data.name;
                const w = d.x1 - d.x0;
                if (w < 60) return "";
                return ind.length > 20 ? ind.substring(0, 18) + "…" : ind;
            });
    }

    // Draw stock cells (depth 2)
    const leaves = root.leaves();

    const cells = svgEl.selectAll(".stock-cell")
        .data(leaves)
        .enter()
        .append("g")
        .attr("class", "stock-cell")
        .attr("transform", d => `translate(${d.x0}, ${d.y0})`);

    cells.append("rect")
        .attr("width", d => Math.max(0, d.x1 - d.x0))
        .attr("height", d => Math.max(0, d.y1 - d.y0))
        .attr("fill", d => pctToColor(d.data.value || 0, metric))
        .attr("rx", 3)
        .attr("class", "hm-cell")
        .on("mouseenter", (event, d) => {
            const sr = d.data;
            ttSym.textContent   = sr.symbol || "";
            ttInd.textContent   = sr.industry || "";
            ttPrice.textContent = (sr.close || 0).toLocaleString("vi-VN");
            const p1d = sr.pct_1d || 0;
            ttPct1d.textContent = `${p1d >= 0 ? "+" : ""}${p1d.toFixed(2)}%`;
            ttPct1d.style.color = p1d >= 0 ? "var(--green)" : "var(--red)";
            ttVol.textContent   = formatNumber(sr.volume || 0);
            tooltip.style.display = "block";
            positionTooltip(event);
        })
        .on("mousemove", (event) => positionTooltip(event))
        .on("mouseleave", () => { tooltip.style.display = "none"; });

    // Symbol label (only if cell big enough)
    cells.append("text")
        .attr("class", "hm-label-sym")
        .attr("x", d => (d.x1 - d.x0) / 2)
        .attr("y", d => {
             const h = d.y1 - d.y0;
             return h > 36 ? h / 2 - 7 : h / 2;
        })
        .text(d => {
            const w = d.x1 - d.x0;
            const h = d.y1 - d.y0;
            if (w < 34 || h < 18) return "";
            return d.data.symbol || "";
        });

    // Percent label
    cells.append("text")
        .attr("class", "hm-label-pct")
        .attr("x", d => (d.x1 - d.x0) / 2)
        .attr("y", d => (d.y1 - d.y0) / 2 + 8)
        .text(d => {
            const w = d.x1 - d.x0;
            const h = d.y1 - d.y0;
            if (w > 34 && h > 36) {
                const val = d.data.value || 0;
                const sign = val >= 0 ? "+" : "";
                return `${sign}${val.toFixed(2)}%`;
            }
            return "";
        });
}

function positionTooltip(e) {
    const tt = document.getElementById("hm-tooltip");
    const vw = window.innerWidth, vh = window.innerHeight;
    let tx = e.clientX + 16, ty = e.clientY + 16;
    if (tx + 200 > vw) tx = e.clientX - 210;
    if (ty + 160 > vh) ty = e.clientY - 165;
    tt.style.left = tx + "px";
    tt.style.top  = ty + "px";
}

// ─── TrendChart.jsx ──────────────────────────────────────────────────────────
// Reusable pure-SVG line chart with hover tooltip.
// Zero external dependencies — works without recharts/d3/chart.js.
//
// Props:
//   series  : [{ key, label, color, data: [{ label, value }] }]
//   title   : string
//   height  : number (default 140)
//   fmt     : value formatter function (default n => n)

import { useState, useRef, useCallback, useMemo, useEffect, useId } from "react";
import { createPortal } from "react-dom";

const W = 520;
const PAD = { top: 18, bottom: 24, left: 52, right: 12 };

function niceMax(v) {
  const val = Number(v || 0);
  if (val <= 0) return 1;
  const mag = Math.pow(10, Math.floor(Math.log10(val)));
  return Math.ceil(val / mag) * mag;
}

function fmtShort(n) {
  const val = Number(n || 0);
  if (val >= 1_000_000_000) return `${(val / 1_000_000_000).toFixed(1)}M`;
  if (val >= 1_000_000)     return `${(val / 1_000_000).toFixed(1)}jt`;
  if (val >= 1_000)         return `${(val / 1_000).toFixed(0)}K`;
  return String(Math.round(val));
}

export default function TrendChart({ series = [], title, height = 140, fmt = n => n }) {
  const [hover, setHover] = useState(null);       // column index
  const [tipPos, setTipPos] = useState(null);     // { x, y } viewport coords — both mobile & desktop
  const chartTitleId = useId();
  const chartDescId  = useId();

  if (!series.length || !series[0].data?.length) return null;

  const pts    = Math.max(series[0].data.length, 1);
  const H      = height;
  const chartW = W - PAD.left - PAD.right;
  const chartH = H - PAD.top  - PAD.bottom;

  const { allVals, maxVal, allPaths, yTicks, xLabels } = useMemo(() => {
    const allVals = series.flatMap(s => s.data.map(d => Number(d.value || 0)));
    const maxVal  = niceMax(Math.max(...allVals, 1));
    const xPos = i => PAD.left + (i / (pts - 1)) * chartW;
    const yPos = v => PAD.top  + chartH - Math.max(0, Math.min(1, Number(v || 0) / maxVal)) * chartH;

    const toPath = data =>
      data.map((d, i) => `${i === 0 ? "M" : "L"}${xPos(i).toFixed(1)},${yPos(Number(d.value || 0)).toFixed(1)}`).join(" ");

    const toArea = data => {
      const line = toPath(data);
      return `${line} L${xPos(pts - 1).toFixed(1)},${(PAD.top + chartH).toFixed(1)} L${PAD.left},${(PAD.top + chartH).toFixed(1)} Z`;
    };

    const allPaths = series.map(s => ({
      key: s.key,
      line: toPath(s.data),
      area: toArea(s.data)
    }));

    const yTicks = [0, 0.25, 0.5, 0.75, 1].map(f => ({
      v: maxVal * f,
      y: yPos(maxVal * f),
    }));

    const fmtXLabel = (raw) => {
      const str = String(raw || "");
      if (!str) return "";
      const m = str.match(/^(\d{4})-(\d{2})-(\d{2})$/);
      if (m) {
        const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        return `${parseInt(m[3])} ${months[parseInt(m[2])-1]}`;
      }
      const m2 = str.match(/^(\d{4})-(\d{2})$/);
      if (m2) {
        const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
        return `${months[parseInt(m2[2])-1]} '${m2[1].slice(2)}`;
      }
      return str.slice(0, 6);
    };

    const xLabels = series[0].data.map((d, i) => {
      const show = pts <= 6 || i % Math.ceil(pts / 6) === 0 || i === pts - 1;
      return show ? { i, label: fmtXLabel(d.label) } : null;
    }).filter(Boolean);

    return { allVals, maxVal, allPaths, yTicks, xLabels };
  }, [series, pts, chartW, chartH]);

  const xPos = useCallback(i => PAD.left + (i / (pts - 1)) * chartW, [pts, chartW]);
  const yPos = useCallback(v => PAD.top  + chartH - Math.max(0, Math.min(1, Number(v || 0) / maxVal)) * chartH, [chartH, maxVal]);

  // Calculate column index from touch/mouse X coordinate within SVG element
  const idxFromSvg = useCallback((svgEl, clientX) => {
    const rect = svgEl.getBoundingClientRect();
    const relX  = clientX - rect.left;
    const svgW  = rect.width;
    const cw    = svgW - (PAD.left / W * svgW) - (PAD.right / W * svgW);
    const startX = (PAD.left / W) * svgW;
    return Math.max(0, Math.min(pts - 1, Math.round(((relX - startX) / cw) * (pts - 1))));
  }, [pts]);

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      {/* Header */}
      <div className="card-h">
        <span className="card-t">{title}</span>
        <div style={{ display: "flex", gap: 14, fontSize: 11, color: "var(--tx3)", alignItems: "center", flexWrap: "wrap" }}>
          {series.map(s => (
            <span key={s.key} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span style={{ width: 12, height: 3, background: s.color, display: "inline-block", borderRadius: 2 }} />
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="trend-chart-wrap" style={{ padding: "2px 14px 10px", position: "relative" }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-labelledby={`${chartTitleId} ${chartDescId}`}
          style={{ width: "100%", height: "auto", minHeight: Math.max(H, 100), display: "block", overflow: "visible" }}
          onMouseLeave={() => { setHover(null); setTipPos(null); }}
          onMouseMove={e => {
            setHover(idxFromSvg(e.currentTarget, e.clientX));
            const TW = 150;
            const tx = Math.max(8, Math.min(window.innerWidth - TW - 8, e.clientX + 14));
            const ty = Math.max(8, e.clientY - 60);
            setTipPos({ x: tx, y: ty });
          }}
          onTouchStart={e => {
            // Prevent page scroll while interacting with chart
            e.stopPropagation();
          }}
          onTouchMove={e => {
            e.preventDefault();
            const touch = e.touches[0];
            const idx = idxFromSvg(e.currentTarget, touch.clientX);
            setHover(idx);
            // Position tooltip above finger, clamped to screen
            const TW = 170;
            const tx = Math.max(8, Math.min(window.innerWidth - TW - 8, touch.clientX - TW / 2));
            const ty = Math.max(8, touch.clientY - 130);
            setTipPos({ x: tx, y: ty });
          }}
          onTouchEnd={() => {
            setTimeout(() => { setHover(null); setTipPos(null); }, 1200);
          }}
        >
          {/* SVG accessibility: title + description for screen readers */}
          <title id={chartTitleId}>{title || "Trend Chart"}</title>
          <desc id={chartDescId}>
            {series.map(s =>
              `${s.label}: ${s.data.map(d => `${d.label} ${fmt(d.value)}`).join(', ')}`
            ).join('; ')}
          </desc>

          {/* Premium Gradient and Shadow Definitions */}
          <defs>
            {series.map(s => (
              <linearGradient key={s.key + "-grad"} id={`grad-${s.key}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity={0.25} />
                <stop offset="100%" stopColor={s.color} stopOpacity={0.0} />
              </linearGradient>
            ))}
          </defs>

          {/* Grid lines + Y labels */}
          {yTicks.map(({ v, y }) => (
            <g key={v}>
              <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
                stroke={v === 0 ? "var(--bdr2)" : "var(--bdr)"} strokeWidth={v === 0 ? 1.5 : 0.75} strokeDasharray={v === 0 ? "" : "3 3"} />
              <text x={PAD.left - 5} y={y + 4} textAnchor="end"
                style={{ fontSize: 9, fill: "var(--tx3)", fontFamily: "var(--mono)" }}>
                {v > 0 ? fmtShort(v) : "0"}
              </text>
            </g>
          ))}

          {/* Area fills with gradient fade */}
          {allPaths.map(s => (
            <path key={s.key + "-area"} d={s.area}
              fill={`url(#grad-${s.key})`} />
          ))}

          {/* Glow Lines (Neon Glow Layer) */}
          {allPaths.map(s => (
            <path key={s.key + "-glow"} d={s.line}
              fill="none" stroke={series.find(item => item.key === s.key).color} strokeWidth={4}
              strokeOpacity={0.2} strokeLinejoin="round" strokeLinecap="round" style={{ pointerEvents: "none" }} />
          ))}

          {/* Lines */}
          {allPaths.map(s => (
            <path key={s.key + "-line"} d={s.line}
              fill="none" stroke={series.find(item => item.key === s.key).color} strokeWidth={2}
              strokeLinejoin="round" strokeLinecap="round" />
          ))}

          {/* Hover vertical line */}
          {hover !== null && (
            <line
              x1={xPos(hover)} y1={PAD.top} x2={xPos(hover)} y2={PAD.top + chartH}
              stroke="var(--tx3)" strokeWidth={1} strokeDasharray="4 3" />
          )}

          {/* Dots */}
          {series.map(s =>
            s.data.map((d, i) => {
              const isHover = hover === i;
              const isEndpt = i === 0 || i === pts - 1;
              if (!isHover && !isEndpt) return null;
              return (
                <circle key={s.key + i} cx={xPos(i)} cy={yPos(d.value)} r={isHover ? 4.5 : 3}
                  fill={s.color} stroke="var(--bg1)" strokeWidth={1.5} />
              );
            })
          )}

          {/* Invisible wide hover targets */}
          {series[0].data.map((_, i) => (
            <rect key={i}
              x={xPos(i) - (chartW / (pts - 1)) / 2}
              y={PAD.top} width={chartW / (pts - 1)} height={chartH}
              fill="transparent"
            />
          ))}

          {/* X-axis labels */}
          {xLabels.map(({ i, label }) => (
            <text key={i} x={xPos(i)} y={H - 4} textAnchor="middle"
              style={{ fontSize: 9, fill: hover === i ? "var(--tx1)" : "var(--tx3)", fontFamily: "var(--mono)", fontWeight: hover === i ? 700 : 400 }}>
              {label}
            </text>
          ))}
        </svg>

        {/* Unified tooltip — rendered via portal, position:fixed, works on desktop & mobile */}
        {hover !== null && tipPos !== null && createPortal(
          <div style={{
            position: "fixed",
            top: tipPos.y,
            left: tipPos.x,
            zIndex: 9999,
            width: 150,
            background: "var(--bg2)",
            border: "1px solid var(--bdr2)",
            borderRadius: 10,
            padding: "10px 13px",
            boxShadow: "0 8px 28px rgba(0,0,0,.55)",
            pointerEvents: "none",
          }}>
            <div style={{ fontWeight: 700, color: "var(--tx1)", marginBottom: 5, fontSize: 11, fontFamily: "var(--mono)" }}>
              {series[0].data[hover]?.label}
            </div>
            {series.map(s => (
              <div key={s.key} style={{ display: "flex", justifyContent: "space-between", gap: 8, marginTop: 3 }}>
                <span style={{ color: "var(--tx2)", fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.label}</span>
                <span style={{ fontFamily: "var(--mono)", fontWeight: 700, color: s.color, fontSize: 11, flexShrink: 0 }}>
                  {fmt(s.data[hover]?.value ?? null)}
                </span>
              </div>
            ))}
          </div>,
          document.body
        )}
      </div>

      {/* WCAG 1.1.1: keyboard-accessible data table — visually hidden, available to
          screen readers and keyboard users who tab into it */}
      <details className="sr-only" style={{ position: "static", width: "auto", height: "auto", clip: "auto", overflow: "visible", whiteSpace: "normal", margin: 0 }}>
        <summary style={{ cursor: "pointer", fontSize: 11, color: "var(--tx2)", padding: "4px 14px" }}>
          View {title || "chart"} data as table
        </summary>
        <div style={{ overflowX: "auto", padding: "0 14px 10px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }} aria-label={`${title || "Trend"} data table`}>
            <thead>
              <tr>
                <th scope="col" style={{ textAlign: "left", padding: "4px 8px", borderBottom: "1px solid var(--bdr)" }}>Period</th>
                {series.map(s => (
                  <th key={s.key} scope="col" style={{ textAlign: "right", padding: "4px 8px", borderBottom: "1px solid var(--bdr)", color: s.color }}>{s.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {series[0].data.map((d, i) => (
                <tr key={i}>
                  <td style={{ padding: "3px 8px", borderBottom: "1px solid var(--bdr)", color: "var(--tx2)" }}>{d.label}</td>
                  {series.map(s => (
                    <td key={s.key} style={{ textAlign: "right", padding: "3px 8px", borderBottom: "1px solid var(--bdr)", fontFamily: "var(--mono)", color: s.color }}>
                      {fmt(s.data[i]?.value ?? null)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

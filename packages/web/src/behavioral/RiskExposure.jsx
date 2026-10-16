// ─── RiskExposure.jsx ─────────────────────────────────────────────────────────
// Feature 2: Risk Exposure Dashboard
//   • Asset Allocation Breakdown — SVG donut + ranked rows
//   • Income Dependency Ratio — bar + per-source breakdown
//   • Financial Fragility Score (0–100, higher = more stable)
//
// Design: precision instrument aesthetic — gauges, clean bars, clinical data.
//
// Responsibility : rendering only.
// Design Pattern : Presentational Component.
// ─────────────────────────────────────────────────────────────────────────────

import { fragilityGrade } from "./behavioralEngine.js";
import { IconShield } from "../icons.jsx";
import { fmtRp, fmt } from "../finance/constants.js";

const fmtPct = (v, d = 1) => (v !== null && v !== undefined) ? `${Number(v).toFixed(d)}%` : "—";

// ── SVG Donut ─────────────────────────────────────────────────────────────────
function Donut({ slices, size = 124, stroke = 20 }) {
  const r     = (size - stroke) / 2;
  const circ  = 2 * Math.PI * r;
  const total = slices.reduce((s, sl) => s + (sl.value || 0), 0) || 1;
  let offset  = 0;
  return (
    <svg width={size} height={size} style={{ display: "block", flexShrink: 0 }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,.05)" strokeWidth={stroke} />
      {slices.map((sl, i) => {
        const val  = sl.value || 0;
        const dash = (val / total) * circ;
        const el   = (
          <circle key={i}
            cx={size/2} cy={size/2} r={r}
            fill="none" stroke={val > 0 ? sl.color : "transparent"} strokeWidth={stroke}
            strokeDasharray={`${Math.max(0, dash - 1.5)} ${circ}`}
            strokeLinecap="butt"
            transform={`rotate(${-90 + (offset / total) * 360} ${size/2} ${size/2})`}
            style={{ transition: "stroke-dasharray .7s cubic-bezier(.4,0,.2,1)" }}
            opacity={0.88}
          />
        );
        offset += val;
        return el;
      })}
    </svg>
  );
}

// ── Asset Allocation Panel ────────────────────────────────────────────────────
const ALLOC_META = {
  cash:   { label: "Cash",   color: "#34d399", icon: null, risk: "Low"  },
  stock:  { label: "Stocks", color: "#6b85ff", icon: null, risk: "Med"  },
  crypto: { label: "Crypto", color: "#a78bfa", icon: null, risk: "High" },
  gold:   { label: "Gold",   color: "#fbbf24", icon: null, risk: "Low"  },
};

const RISK_STYLE = {
  High: { bg: "rgba(248,113,113,.15)", color: "#f87171" },
  Med:  { bg: "rgba(251,191,36,.12)",  color: "#fbbf24" },
  Low:  { bg: "rgba(52,211,153,.12)",  color: "#34d399" },
};

function AllocationPanel({ allocation }) {
  const slices = Object.entries(ALLOC_META).map(([k, { color }]) => ({ value: allocation[k] ?? 0, color }));
  const rows   = Object.entries(ALLOC_META)
    .map(([k, meta]) => ({ ...meta, pct: allocation[k] ?? null }))
    .sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1));

  return (
    <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: "var(--rl)", overflow: "hidden" }}>
      <div style={{ height: 2, background: "linear-gradient(90deg, #6b85ff, transparent)" }} />
      <div style={{ padding: "14px 18px 12px", borderBottom: "1px solid var(--bdr)" }}>
        <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".8px", color: "var(--tx2)" }}>
          Asset Allocation
        </span>
      </div>
      <div style={{ padding: 18, display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flexShrink: 0 }}>
          <Donut slices={slices} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          {rows.map(({ label, color, icon, risk, pct }) => {
            const rs = RISK_STYLE[risk];
            const isValid = pct !== null && pct !== undefined;
            return (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                <div style={{ width: 7, height: 7, borderRadius: 2, background: color, flexShrink: 0 }} />
                <span style={{ fontSize: 12, color: "var(--tx2)", flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{icon} {label}</span>
                <span style={{ fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 4, background: rs.bg, color: rs.color, flexShrink: 0 }}>{risk}</span>
                <div style={{ width: 36, height: 3, background: "rgba(255,255,255,.06)", borderRadius: 99, overflow: "hidden", flexShrink: 0 }}>
                  <div style={{ width: `${isValid ? pct : 0}%`, height: "100%", background: color, borderRadius: 99, transition: "width .6s" }} />
                </div>
                <span style={{ width: 36, textAlign: "right", fontSize: 11, fontFamily: "'Space Mono', monospace", color: isValid ? color : "var(--tx3)", fontWeight: 700, flexShrink: 0 }}>
                  {fmtPct(pct)}
                </span>
              </div>
            );
          })}
          {allocation.highRisk > 0 && (
            <div style={{ marginTop: 8, fontSize: 10, color: "var(--rd)", fontFamily: "'Space Mono', monospace", padding: "6px 8px", background: "rgba(248,113,113,.08)", borderRadius: 6, border: "1px solid rgba(248,113,113,.15)" }}>
              High-risk exposure: {fmtPct(allocation.highRisk)} of total assets
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Income Dependency Panel ───────────────────────────────────────────────────
const INCOME_ICONS = {};

function IncomeDependencyPanel({ depResult, incomeBySource }) {
  const { ratio, primarySource } = depResult;
  const isValid = ratio !== null && ratio !== undefined;
  const color  = !isValid ? "var(--tx3)" : (ratio > 0.9 ? "var(--rd)" : ratio > 0.7 ? "var(--yl)" : "var(--gr)");
  const total  = Object.values(incomeBySource).reduce((s, v) => s + (v || 0), 0);

  return (
    <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: "var(--rl)", overflow: "hidden" }}>
      <div style={{ height: 2, background: "linear-gradient(90deg, #34d399, transparent)" }} />
      <div style={{ padding: "14px 18px 12px", borderBottom: "1px solid var(--bdr)" }}>
        <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".8px", color: "var(--tx2)" }}>
          Income Dependency
        </span>
      </div>

      <div style={{ padding: 18 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16 }}>
          <div style={{ flexShrink: 0 }}>
            <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 4 }}>Dependency</div>
            <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 26, fontWeight: 900, color, lineHeight: 1 }}>
              {isValid ? fmtPct(ratio * 100) : "—"}
            </div>
            <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 4, textTransform: "capitalize" }}>
              Primary: {primarySource ?? "—"}
            </div>
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ height: 8, background: "rgba(255,255,255,.06)", borderRadius: 99, overflow: "hidden" }}>
              <div style={{
                width: `${isValid ? ratio * 100 : 0}%`, height: "100%", borderRadius: 99,
                background: `linear-gradient(90deg, ${color}, ${color}99)`,
                transition: "width .7s cubic-bezier(.4,0,.2,1)",
              }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 9, color: "var(--tx3)", fontFamily: "'Space Mono', monospace" }}>
              <span>Diversified</span><span>Single Source</span>
            </div>
          </div>
        </div>

        {total > 0 && Object.keys(incomeBySource).length > 0 ? (
          Object.entries(incomeBySource).sort(([, a], [, b]) => b - a).map(([src, val]) => {
            const share = (val / total) * 100;
            const c     = share > 70 ? "var(--rd)" : share > 40 ? "var(--yl)" : "var(--gr)";
            return (
              <div key={src} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <span style={{ fontSize: 14, flexShrink: 0 }}></span>
                <span style={{ fontSize: 11, color: "var(--tx2)", flex: 1, textTransform: "capitalize" }}>{src}</span>
                <div style={{ width: 60, height: 4, background: "rgba(255,255,255,.06)", borderRadius: 99, overflow: "hidden", flexShrink: 0 }}>
                  <div style={{ width: `${share}%`, height: "100%", background: c, borderRadius: 99 }} />
                </div>
                <span style={{ width: 40, textAlign: "right", fontSize: 11, fontFamily: "'Space Mono', monospace", color: c, flexShrink: 0 }}>
                  {fmtPct(share, 0)}
                </span>
              </div>
            );
          })
        ) : (
          <div style={{ fontSize: 11, color: "var(--tx3)", textAlign: "center", padding: "12px 0" }}>No income data this month</div>
        )}
      </div>
    </div>
  );
}

// ── Fragility Score Panel ─────────────────────────────────────────────────────
function FragilityScorePanel({ score, allocation, depResult, debtRatio, emergencyFund, netWorth }) {
  const grade = fragilityGrade(score ?? 0);
  const isValid = score !== null && score !== undefined;

  // Emergency fund score: months of expenses covered. Use ef / (netWorth * 0.05) as proxy,
  // capped at 1. If ef = 0, score = 0.
  const efScore = (netWorth > 0 && emergencyFund != null) ? Math.min(emergencyFund / (netWorth * 0.05), 1) : 0;
  const efHint  = emergencyFund != null ? `Rp${Math.abs(emergencyFund).toLocaleString("id-ID")}` : "—";

  const FACTORS = [
    { label: "Emergency Fund",   w: "30%", v: efScore,                                                      hint: efHint },
    { label: "Income Diversif.", w: "20%", v: depResult.ratio != null ? 1 - depResult.ratio : null,         hint: depResult.ratio != null ? `Dep. ${Number(depResult.ratio * 100).toFixed(1)}%` : "—" },
    { label: "High-Risk Asset",  w: "20%", v: allocation.highRisk != null ? 1 - Math.min(allocation.highRisk / 100, 1) : null, hint: allocation.highRisk != null ? `${Number(allocation.highRisk).toFixed(1)}% high-risk` : "—" },
    { label: "Debt Ratio",       w: "20%", v: debtRatio != null ? 1 - debtRatio : null,                      hint: debtRatio != null ? `${Number(debtRatio * 100).toFixed(1)}% credit` : "—" },
    { label: "Save Stability",   w: "10%", v: 0.70,                                                         hint: "Estimated" },
  ];

  return (
    <div style={{
      background: "var(--bg2)", border: `1px solid ${isValid ? grade.color : "var(--bdr)"}28`, borderRadius: "var(--rl)", overflow: "hidden",
      gridColumn: "1 / -1", boxShadow: isValid ? `0 0 40px ${grade.color}08` : "none",
    }}>
      <div style={{ height: 2, background: isValid ? `linear-gradient(90deg, ${grade.color}, transparent)` : "var(--bdr)" }} />

      {/* Score header */}
      <div style={{
        padding: "18px 22px 16px", borderBottom: "1px solid var(--bdr)",
        background: isValid ? `linear-gradient(90deg, ${grade.color}06, transparent)` : "transparent",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap" }}>
          <div style={{ flexShrink: 0 }}>
            <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "1.2px", marginBottom: 5 }}>
              Financial Fragility Score
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
              <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 40, fontWeight: 900, color: isValid ? grade.color : "var(--tx3)", lineHeight: 1 }}>
                {isValid ? Math.round(score) : "—"}
              </span>
              <span style={{ fontSize: 14, color: "var(--tx3)", fontFamily: "'Space Mono', monospace" }}>/100</span>
              {isValid && (
                <span style={{
                  fontSize: 11, fontWeight: 700, padding: "3px 12px", borderRadius: 99,
                  background: `${grade.color}18`, color: grade.color, border: `1px solid ${grade.color}30`,
                  display: "flex", alignItems: "center", gap: 5,
                }}>
                  <IconShield size={11} /> {grade.label}
                </span>
              )}
            </div>
          </div>

          {/* Gradient progress track */}
          <div className="risk-flex-row" style={{ flex: 1, minWidth: 0 }}>
            <div style={{ height: 10, background: "rgba(255,255,255,.05)", borderRadius: 99, overflow: "hidden", position: "relative" }}>
              <div style={{
                position: "absolute", inset: 0,
                background: "linear-gradient(90deg, #f87171, #fbbf24 50%, #34d399)",
              }} />
              <div style={{
                position: "absolute", inset: 0, borderRadius: 99,
                background: "var(--bg2)",
                transform: `translateX(${isValid ? score : 0}%)`,
                transition: "transform .9s cubic-bezier(.4,0,.2,1)",
              }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 5, fontSize: 9, color: "var(--tx3)", fontFamily: "'Space Mono', monospace", overflowX: "hidden" }}>
              {["Critical", "Fragile", "Moderate", "Stable", "Stable+"].map(l => <span key={l} style={{ flexShrink: 1, overflow: "hidden", textOverflow: "ellipsis" }}>{l}</span>)}
            </div>
          </div>
        </div>
      </div>

      {/* Factor grid */}
      <div style={{ padding: 18 }}>
        <div className="beh-grid-5" style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
          {FACTORS.map(({ label, w, v, hint }) => {
            const isValidFactor = v !== null && v !== undefined;
            const c = !isValidFactor ? "var(--tx3)" : (v > 0.7 ? "var(--gr)" : v > 0.4 ? "var(--yl)" : "var(--rd)");
            return (
              <div key={label} style={{ background: "var(--bg3)", borderRadius: 8, padding: "11px 12px", border: "1px solid var(--bdr)" }}>
                <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 7 }}>{label}</div>
                <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 18, fontWeight: 800, color: c, marginBottom: 4 }}>
                  {isValidFactor ? (v * 100).toFixed(0) : "—"}
                </div>
                <div style={{ fontSize: 8, color: "var(--tx3)", marginBottom: 6 }}>{w} weight</div>
                <div style={{ height: 3, background: "rgba(255,255,255,.06)", borderRadius: 99 }}>
                  <div style={{ width: `${isValidFactor ? v * 100 : 0}%`, height: "100%", background: c, borderRadius: 99, transition: "width .6s" }} />
                </div>
                <div style={{ fontSize: 8, color: "var(--tx3)", marginTop: 5, fontFamily: "'Space Mono', monospace" }}>{hint}</div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function RiskExposure({ data }) {
  if (!data) return null;

  const fragility = data.fragility || {};
  const summary   = data.summary || {};
  
  // 1. Asset Allocation (using IDR values from fragility.asset_values)
  const av = fragility.asset_values || {};
  const totalAssets = Object.values(av).length > 0 ? Object.values(av).reduce((s, v) => s + v, 0) : null;
  const cashSavings = summary.cash_savings ?? null;

  const allocation = {
    cash:   (cashSavings != null && totalAssets > 0) ? (cashSavings / totalAssets) * 100 : null,
    stock:  (av.stock != null && totalAssets > 0) ? (av.stock / totalAssets) * 100 : null,
    crypto: (av.crypto != null && totalAssets > 0) ? (av.crypto / totalAssets) * 100 : null,
    gold:   (av.gold != null && totalAssets > 0) ? (av.gold / totalAssets) * 100 : null,
    highRisk: (av.crypto != null && totalAssets > 0) ? (av.crypto / totalAssets) * 100 : null,
  };

  // 2. Income Dependency (fallback if not in API)
  const depResult = { 
    ratio: fragility.asset_concentration ?? null, 
    primarySource: fragility.income_sources != null ? (fragility.income_sources > 1 ? "Diversified" : "Single Source") : null
  };

  return (
    <div className="risk-grid" style={{ 
      display: "grid", 
      gridTemplateColumns: "1fr 1fr", 
      gap: 16 
    }}>
      <AllocationPanel allocation={allocation} />
      <IncomeDependencyPanel depResult={depResult} incomeBySource={{}} />
      <FragilityScorePanel
        score={fragility.score ?? null}
        allocation={allocation}
        depResult={depResult}
        debtRatio={null}
        emergencyFund={summary.emergency_fund ?? null}
        netWorth={summary.net_worth ?? null}
      />
    </div>
  );
}

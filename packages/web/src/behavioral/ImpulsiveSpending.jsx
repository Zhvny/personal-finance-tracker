// ─── ImpulsiveSpending.jsx ────────────────────────────────────────────────────
// Feature 1: Behavioral Finance Tracker
//   • Financial Behaviour Score (FBS) with ring + weight breakdown
//   • Monthly Impulsivity Index (IS per tx + category heatmap)
//   • Lifestyle Inflation detector
//
// Design: dark trading-terminal aesthetic — monospace numbers, glowing rings,
//         status pills, and tension between red/green semantic colour.
//
// Responsibility : rendering only — all maths live in behavioralEngine.js.
// Design Pattern : Presentational Component (dumb UI, smart parent).
// ─────────────────────────────────────────────────────────────────────────────

import { fbsGrade } from "./behavioralEngine.js";
import { useState, useEffect } from "react";
import { CatIcon } from "../finance/icon-maps.jsx";
import { IconTarget, IconWarning, IconSuccess, IconInfo } from "../icons.jsx";
import { fmtRp, API_BASE } from "../finance/constants.js";
import { _getToken } from "../finance/useApi.js";
import { useI18n } from "../i18n/context.js";

// ── Formatters (local, DRY) ───────────────────────────────────────────────────
const fmtPct  = (v, d = 1) => v != null ? `${(v * 100).toFixed(d)}%` : "—";
const sign    = v => v >= 0 ? "+" : "";

// ── Shared atoms ──────────────────────────────────────────────────────────────

/** Circular SVG progress ring */
function Ring({ score, size = 92, strokeW = 8, color, bg = "rgba(255,255,255,.05)" }) {
  const r    = (size - strokeW) / 2;
  const circ = 2 * Math.PI * r;
  const isValid = score !== null && score !== undefined;
  const dash = isValid ? clamp01(score / 100) * circ : 0;
  return (
    <svg width={size} height={size} style={{ display: "block", flexShrink: 0 }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={bg} strokeWidth={strokeW} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={isValid ? color : "transparent"} strokeWidth={strokeW}
        strokeDasharray={`${dash} ${circ - dash}`} strokeLinecap="round"
        transform={`rotate(-90 ${size/2} ${size/2})`}
        style={{ transition: "stroke-dasharray .9s cubic-bezier(.4,0,.2,1)" }}
      />
      <text x="50%" y="50%" textAnchor="middle" dy=".35em"
        fill={isValid ? color : "var(--tx3)"} fontSize={size * 0.235} fontWeight="800"
        fontFamily="'Space Mono', monospace">
        {isValid ? Math.round(score) : "—"}
      </text>
    </svg>
  );
}
const clamp01 = v => Math.min(1, Math.max(0, v));

/** Thin horizontal bar */
function Bar({ value, color, h = 5 }) {
  const isValid = value !== null && value !== undefined;
  return (
    <div style={{ flex: 1, height: h, background: "rgba(255,255,255,.06)", borderRadius: 99, overflow: "hidden" }}>
      <div style={{ width: `${isValid ? clamp01(value) * 100 : 0}%`, height: "100%", background: color, borderRadius: 99, transition: "width .6s cubic-bezier(.4,0,.2,1)" }} />
    </div>
  );
}

/** Score chip — coloured pill */
function Chip({ label, color, small }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center",
      padding: small ? "1px 7px" : "3px 11px",
      borderRadius: 99, fontSize: small ? 9 : 11, fontWeight: 700,
      background: `${color}18`, color, border: `1px solid ${color}30`,
      letterSpacing: ".3px",
    }}>{label}</span>
  );
}

// ── FBS Panel ──────────────────────────────────────────────────────────────────
function FBSPanel({ fbs, savingRate, impulsivityIndex, emotionalRatio, liScore, budgetAdherence }) {
  const { t } = useI18n();
  const grade = fbsGrade(fbs ?? 0);
  const isValid = fbs !== null && fbs !== undefined;

  const ROWS = [
    { label: t("behavioral.row_saving_rate"),       v: savingRate,        fmt: v => v != null ? fmtPct(v) : "—",               w: "30%", inv: false },
    { label: t("behavioral.row_impulsivity"),       v: impulsivityIndex,  fmt: v => v != null ? (v * 100).toFixed(1) + "%" : "—", w: "25%", inv: true  },
    { label: t("behavioral.row_emotional"),         v: emotionalRatio,    fmt: v => v != null ? fmtPct(v) : "—",               w: "15%", inv: true  },
    { label: t("behavioral.row_lifestyle"),         v: liScore,           fmt: v => v != null ? `${sign(v)}${(v*100).toFixed(1)}pp` : "—", w: "15%", inv: true  },
    { label: t("behavioral.row_budget_adherence"),  v: budgetAdherence,   fmt: v => v != null ? fmtPct(v) : "—",               w: "15%", inv: false },
  ];

  const rowColor = (v, inv) => {
    if (v == null) return "var(--tx3)";
    return inv ? (v < 0.2 ? "var(--gr)" : v < 0.5 ? "var(--yl)" : "var(--rd)")
               : (v > 0.5 ? "var(--gr)" : v > 0.25 ? "var(--yl)" : "var(--rd)");
  };

  return (
    <div style={{
      background: "var(--bg2)", borderRadius: "var(--rl)", overflow: "hidden",
      border: `1px solid ${isValid ? grade.color : "var(--bdr)"}28`, marginBottom: 16,
      boxShadow: isValid ? `0 0 40px ${grade.color}0a` : "none",
    }}>
      {/* Accent bar */}
      <div style={{ height: 2, background: isValid ? `linear-gradient(90deg, ${grade.color}, transparent)` : "var(--bdr)" }} />

      <div style={{ padding: "20px 22px" }}>
        {/* Header row */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 16, marginBottom: 20, flexWrap: "wrap" }}>
          <Ring score={fbs} color={grade.color} />

          <div className="fbs-header-row" style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "1.2px", marginBottom: 6 }}>
              {t("behavioral.fbs_title")}
            </div>
            <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 8, flexWrap: "wrap" }}>
              <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 32, fontWeight: 900, color: isValid ? grade.color : "var(--tx3)", lineHeight: 1 }}>
                {isValid ? Math.round(fbs) : "—"}
              </span>
              <span style={{ fontSize: 13, color: "var(--tx3)", fontFamily: "'Space Mono', monospace" }}>/100</span>
              {isValid && <Chip label={`${grade.tier} · ${grade.label}`} color={grade.color} />}
            </div>
            <div style={{ fontSize: 11, color: "var(--tx3)", fontStyle: "italic", lineHeight: 1.6 }}>
              {t("behavioral.fbs_desc")}
            </div>
          </div>

          <div className="fbs-theory" style={{ textAlign: "right", flexShrink: 0 }}>
            <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "1px", marginBottom: 6 }}>{t("behavioral.theory")}</div>
            {[t("behavioral.loss_aversion"), t("behavioral.present_bias"), t("behavioral.mental_accounting")].map(theory => (
              <div key={theory} style={{ fontSize: 9, color: "var(--ind-b)", fontFamily: "'Space Mono', monospace", marginBottom: 3 }}>{theory}</div>
            ))}
          </div>
        </div>

        {/* Component breakdown */}
        <div style={{ display: "grid", gap: 8, overflowX: "hidden" }}>
          {ROWS.map(({ label, v, fmt, w, inv }) => {
            const col  = rowColor(v, inv);
            const fill = v != null ? (inv ? 1 - clamp01(v) : clamp01(v)) : 0;
            return (
              <div key={label} style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <div style={{ minWidth: "clamp(72px, 24vw, 100px)", maxWidth: "clamp(90px, 32vw, 140px)", fontSize: 11, color: "var(--tx2)", flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{label}</div>
                <div style={{ width: 28, fontSize: 9, color: "var(--tx3)", fontFamily: "'Space Mono', monospace", flexShrink: 0 }}>{w}</div>
                <Bar value={fill} color={col} />
                <div style={{ width: "clamp(42px, 14vw, 58px)", textAlign: "right", fontSize: 11, fontFamily: "'Space Mono', monospace", color: col, fontWeight: 700, flexShrink: 0 }}>
                  {fmt(v)}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Impulsivity Panel ─────────────────────────────────────────────────────────
function ImpulsivityPanel({ impulsivityIndex, breakdown, perTx }) {
  const { t } = useI18n();
  const isValid = impulsivityIndex !== null && impulsivityIndex !== undefined;
  const pctVal = isValid ? (impulsivityIndex * 100).toFixed(1) : "—";
  const color  = !isValid ? "var(--tx3)" : (impulsivityIndex < 0.2 ? "var(--gr)" : impulsivityIndex < 0.5 ? "var(--yl)" : "var(--rd)");
  const topTx  = [...(perTx ?? [])].sort((a, b) => b.is - a.is).slice(0, 5);

  return (
    <div style={{
      background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: "var(--rl)", overflow: "hidden",
    }}>
      <div style={{ padding: "14px 18px 12px", borderBottom: "1px solid var(--bdr)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".8px", color: "var(--tx2)", display: "flex", alignItems: "center", gap: 6 }}>
          <IconTarget size={14} /> {t("behavioral.row_impulsivity")}
        </span>
        <span style={{ fontFamily: "'Space Mono', monospace", fontSize: 22, fontWeight: 800, color }}>{isValid ? `${pctVal}%` : "—"}</span>
      </div>

      <div style={{ padding: 16 }}>

        {/* Category breakdown bars */}
        {Object.keys(breakdown ?? {}).length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--tx3)", marginBottom: 10 }}>{t("behavioral.by_category")}</div>
            {Object.entries(breakdown).sort(([, a], [, b]) => b - a).map(([cat, val]) => {
              const c = val > 0.5 ? "var(--rd)" : val > 0.3 ? "var(--yl)" : "var(--gr)";
              return (
                <div key={cat} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  <span style={{ width: 20, textAlign: "center", fontSize: 13, flexShrink: 0, display:"flex", alignItems:"center" }}>{CatIcon({ cat, size: 13 })}</span>
                  <span style={{ width: "clamp(62px, 22vw, 86px)", fontSize: 11, color: "var(--tx2)", textTransform: "capitalize", flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cat}</span>
                  <Bar value={val} color={c} />
                  <span style={{ width: 36, textAlign: "right", fontSize: 11, fontFamily: "'Space Mono', monospace", color: c, fontWeight: 600, flexShrink: 0 }}>
                    {(val * 100).toFixed(0)}%
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Top impulsive transactions */}
        {topTx.length > 0 && (
          <div>
            <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--tx3)", marginBottom: 10 }}>
              {t("behavioral.top_impulsive")}
            </div>
            {topTx.map(({ tx, is }, i) => {
              const col = is > 0.6 ? "var(--rd)" : is > 0.4 ? "var(--yl)" : "var(--tx2)";
              const bdr = is > 0.6 ? "rgba(248,113,113,.22)" : "var(--bdr)";
              return (
                <div key={i} style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "9px 11px",
                  background: "var(--bg3)", borderRadius: 8, marginBottom: 6,
                  border: `1px solid ${bdr}`,
                  boxShadow: is > 0.6 ? "0 0 10px rgba(248,113,113,.06)" : "none",
                }}>
                  <span style={{ fontSize: 14, flexShrink: 0, display:"flex", alignItems:"center" }}>{CatIcon({ cat: tx.category, size: 13 })}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, color: "var(--tx)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {tx.description || tx.category}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 1 }}>
                      {tx.date?.slice(0, 10)} · {tx.payment_method ?? "—"}
                    </div>
                  </div>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <div style={{ fontSize: 12, fontFamily: "'Space Mono', monospace", color: col, fontWeight: 700 }}>
                      IS {(is * 100).toFixed(0)}%
                    </div>
                    <div style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "'Space Mono', monospace" }}>{fmtRp(tx.amount)}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {!topTx.length && (
          <div style={{ textAlign: "center", color: "var(--tx3)", fontSize: 12, padding: "20px 0" }}>{t("behavioral.no_tx_month")}</div>
        )}
      </div>
    </div>
  );
}

// ── Lifestyle Inflation Panel ─────────────────────────────────────────────────
function LifestylePanel({ liScore, expGrowth, incGrowth, expTotalThis, expTotalPrev, incTotalThis, incTotalPrev }) {
  const { t } = useI18n();
  const isValid = liScore !== null && liScore !== undefined;
  const isInflating = isValid && liScore > 0.05;
  const isHealthy   = isValid && liScore < -0.05;
  const color       = !isValid ? "var(--tx3)" : (isInflating ? "var(--rd)" : isHealthy ? "var(--gr)" : "var(--yl)");
  const label       = !isValid ? t("behavioral.data_pending") : (isInflating ? t("behavioral.li_inflation") : isHealthy ? t("behavioral.income_leading") : t("behavioral.stable"));

  const StatBox = ({ l, v, v2, bad }) => {
    const isValidVal = v !== null && v !== undefined;
    const isValidPrev = v2 !== null && v2 !== undefined && v2 > 0;
    const delta = (isValidVal && isValidPrev) ? (v - v2) / v2 : null;
    const c     = delta == null ? "var(--tx3)" : (bad ? (delta > 0.1 ? "var(--rd)" : "var(--gr)") : (delta > 0 ? "var(--gr)" : "var(--rd)"));
    return (
      <div style={{ background: "var(--bg3)", borderRadius: 8, padding: "10px 12px", border: "1px solid var(--bdr)" }}>
        <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 5 }}>{l}</div>
        <div style={{ fontFamily: "'Space Mono', monospace", fontSize: 13, fontWeight: 700 }}>{fmtRp(v)}</div>
        <div style={{ fontSize: 10, color: c, fontFamily: "'Space Mono', monospace", marginTop: 2 }}>
          {delta != null ? `${sign(delta)}${(delta * 100).toFixed(1)}% vs prev` : "—"}
        </div>
      </div>
    );
  };

  return (
    <div style={{
      background: "var(--bg2)", borderRadius: "var(--rl)", overflow: "hidden",
      border: isInflating ? "1px solid rgba(248,113,113,.2)" : "1px solid var(--bdr)",
    }}>
      <div style={{ padding: "14px 18px 12px", borderBottom: "1px solid var(--bdr)", display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ display: "flex", alignItems: "center", flexShrink: 0 }}>
          {!isValid ? <IconInfo size={15} color="var(--tx3)" /> : (isInflating ? <IconWarning size={15} color="var(--rd)" /> : isHealthy ? <IconSuccess size={15} color="var(--gr)" /> : <IconInfo size={15} color="var(--yl)" />)}
        </span>
        <span style={{ fontSize: 12, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".8px", color: "var(--tx2)" }}>
          {t("behavioral.row_lifestyle")}
        </span>
        <div style={{ marginLeft: "auto" }}>
          <Chip label={label} color={color} small />
        </div>
      </div>

      <div style={{ padding: 16 }}>

        <div className="beh-grid-3" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
          {[
            { l: t("behavioral.exp_growth"), v: expGrowth, inv: true },
            { l: t("behavioral.inc_growth"), v: incGrowth, inv: false },
            { l: t("behavioral.li_score"),   v: liScore,   inv: true, bold: true },
          ].map(({ l, v, inv, bold }) => {
            const isValidRow = v !== null && v !== undefined;
            const c = !isValidRow ? "var(--tx3)" : (inv
              ? (v > 0.1 ? "var(--rd)" : v < -0.05 ? "var(--gr)" : "var(--tx)")
              : (v > 0.1 ? "var(--gr)" : v < -0.05 ? "var(--rd)" : "var(--tx)"));
            return (
              <div key={l} style={{ background: "var(--bg3)", borderRadius: 8, padding: "10px 12px", border: "1px solid var(--bdr)" }}>
                <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 5 }}>{l}</div>
                <div style={{ fontFamily: "'Space Mono', monospace", fontSize: bold ? 18 : 14, fontWeight: 800, color: bold ? color : c }}>
                  {isValidRow ? `${sign(v)}${(v * 100).toFixed(1)}pp` : "—"}
                </div>
              </div>
            );
          })}
        </div>

        <div className="sg" style={{ gap: 10 }}>
          <StatBox l={t("behavioral.exp_this_month")} v={expTotalThis} v2={expTotalPrev} bad={true}  />
          <StatBox l={t("behavioral.inc_this_month")} v={incTotalThis} v2={incTotalPrev} bad={false} />
        </div>

        {/* 6-month rolling LI sparkline */}
        <_LISparkline />
      </div>
    </div>
  );
}

function _LISparkline() {
  const { t } = useI18n();
  const [trend, setTrend] = useState(null);
  const [loadError, setLoadError] = useState("");
  useEffect(() => {
    const base = (typeof window !== "undefined" && window.__API_BASE__) || API_BASE || "http://127.0.0.1:8444/api";
    const token = _getToken();
    fetch(`${String(base).replace(/\/$/, "")}/behavioral/lifestyle-trend?months=6`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.trend?.length >= 2) setTrend(d.trend); })
      .catch((e) => { setLoadError(e?.message || t("behavioral.lifestyle_load_failed")); });
  }, []);
  if (loadError) {
    return (
      <div role="alert" style={{ marginTop: 14, fontSize: 11, color: "var(--rd)" }}>
        {loadError}
      </div>
    );
  }
  if (!trend) return null;
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--tx3)", marginBottom: 8 }}>
        {t("behavioral.li_trend_6m")}
      </div>
      <div style={{ display: "flex", gap: 4, alignItems: "flex-end", height: 50 }}>
        {trend.map((m, i) => {
          const li = m.li_score;
          const barH = Math.min(38, Math.abs(li) * 200 + 4);
          const c = li > 0.1 ? "var(--rd)" : li > 0.05 ? "#f97316" : li < -0.05 ? "var(--gr)" : "var(--yl)";
          return (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ fontSize: 7, fontFamily: "'Space Mono', monospace", color: c, marginBottom: 1, fontWeight: 700 }}>
                {li >= 0 ? "+" : ""}{(li * 100).toFixed(0)}
              </div>
              <div style={{ width: "100%", minWidth: 10, height: barH, background: c, borderRadius: "2px 2px 0 0", opacity: 0.8 }} />
              <div style={{ width: "100%", height: 1, background: "var(--bdr2)" }} />
              <div style={{ fontSize: 7, color: "var(--tx3)", marginTop: 2, fontFamily: "'Space Mono', monospace" }}>
                {(m.label || "").slice(0, 3)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function ImpulsiveSpending({ data }) {
  if (!data) return null;

  // Map API payload to component props
  const fbs = data.fbs || {};
  const fragility = data.fragility || {};
  const impulse = data.impulse || {};
  const summary = data.summary || {};

  const expThis   = summary.exp_total_this ?? null;
  const expPrev   = summary.exp_total_prev ?? null;
  const incThis   = summary.inc_total_this ?? null;
  const incPrev   = summary.inc_total_prev ?? null;
  const expGrowth = (expPrev != null && expThis != null && expPrev > 0) ? (expThis - expPrev) / expPrev : null;
  const incGrowth = (incPrev != null && incThis != null && incPrev > 0) ? (incThis - incPrev) / incPrev : null;
  const liScore   = (expGrowth != null && incGrowth != null) ? expGrowth - incGrowth : null;
  const impIdx    = fbs.impulse_index ?? impulse.index ?? null;
  const emotRatio = impIdx != null ? Math.min(1, (impIdx / 100) * 0.6) : null;
  const budgetAdh = (fbs.component_scores?.budget_adherence ?? null) != null ? fbs.component_scores.budget_adherence / 100 : null;

  return (
    <div>
      <FBSPanel
        fbs={fbs.score ?? null}
        savingRate={fbs.saving_rate != null ? fbs.saving_rate / 100 : null}
        impulsivityIndex={impIdx != null ? impIdx / 100 : null}
        emotionalRatio={emotRatio}
        liScore={liScore}
        budgetAdherence={budgetAdh}
      />
      <div className="g2" style={{ gap: 16 }}>
        <ImpulsivityPanel 
          impulsivityIndex={impIdx != null ? impIdx / 100 : null} 
          breakdown={impulse.by_category ?? {}} 
          perTx={impulse.per_tx ?? []} 
        />
        <LifestylePanel
          liScore={liScore} 
          expGrowth={expGrowth} 
          incGrowth={incGrowth}
          expTotalThis={expThis} 
          expTotalPrev={expPrev}
          incTotalThis={incThis} 
          incTotalPrev={incPrev}
        />
      </div>
    </div>
  );
}

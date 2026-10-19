// Icon-based tab rendering — no emoji
// ─── BehavioralDashboard.jsx ──────────────────────────────────────────────────
// Entry-point for the Behavioral Finance module.
//
// Responsibility : tab routing + data lifecycle. Zero business logic.
// High Cohesion  : only orchestration here.
// Low Coupling   : sub-components receive typed data objects, never raw API.
// Design Pattern : Composite — assembles 3 independent feature panels.
// Clean Architecture: "application" ring — connects data adapter to UI.
// ─────────────────────────────────────────────────────────────────────────────

import { useState } from "react";
import { useBehavioralData } from "../behavioral/useBehavioralData.js";
import { useBalances, apiSetBalance, usePersistedTab } from "../finance/useApi.js";
import { IconBehavioral, IconRisk, IconHeatmap, IconRefresh, IconInfo } from "../icons.jsx";
import ImpulsiveSpending  from "../behavioral/ImpulsiveSpending.jsx";
import RiskExposure       from "../behavioral/RiskExposure.jsx";
import NetWorthHeatmap    from "../behavioral/NetWorthHeatmap.jsx";
import AIInsightPanel     from "../behavioral/AIInsightPanel.jsx";
import AIPassiveStatus     from "../behavioral/AIPassiveStatus.jsx";
import { useAIStatus }    from "../finance/useApi.js";
import { useI18n }        from "../i18n/context.js";

// ── Loading skeleton ──────────────────────────────────────────────────────────
function Skeleton({ h = 120, mb = 12 }) {
  return (
    <div style={{
      height: h, borderRadius: "var(--rl)", marginBottom: mb,
      background: "linear-gradient(90deg, var(--bg3) 25%, var(--bg4) 50%, var(--bg3) 75%)",
      backgroundSize: "200% 100%",
      animation: "beh-shimmer 1.6s infinite linear",
    }} />
  );
}

function LoadingState() {
  return (
    <div>
      <Skeleton h={210} mb={14} />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <Skeleton h={300} mb={0} />
        <Skeleton h={300} mb={0} />
      </div>
      <style>{`@keyframes beh-shimmer{from{background-position:200% 0}to{background-position:-200% 0}}`}</style>
    </div>
  );
}

// ── Error state ───────────────────────────────────────────────────────────────
function ErrorState({ error, onRetry }) {
  const { t } = useI18n();
  // Normalize to string — error may be an Error object, string, or null
  const errStr = typeof error === "string"
    ? error
    : (error?.message ? String(error.message) : String(error || ""));

  const is404    = errStr.includes("404") || (typeof error === "object" && error !== null && error.status === 404);
  const is500    = errStr.includes("500") || (typeof error === "object" && error !== null && error.status === 500);
  const isOffline = errStr.includes("Failed to fetch") || errStr.includes("API Offline") || (typeof error === "object" && error !== null && error.type === "OFFLINE");

  let title = t("behavioral.load_failed_title");
  let suggestion = t("behavioral.load_failed_sub");

  if (is404) {
    title = t("behavioral.err_404_title");
    suggestion = t("behavioral.err_404_sub");
  } else if (is500) {
    title = t("behavioral.err_500_title");
    suggestion = t("behavioral.err_500_sub");
  } else if (isOffline) {
    title = t("behavioral.err_offline_title");
    suggestion = t("behavioral.err_offline_sub");
  }

  return (
    <div style={{
      padding: 28, background: "rgba(248,113,113,.07)", border: "1px solid rgba(248,113,113,.18)",
      borderRadius: "var(--rl)", textAlign: "center",
    }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--rd)", marginBottom: 6 }}>{title}</div>
      <div style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "'Space Mono', monospace", marginBottom: 14, wordBreak: "break-all" }}>
        {errStr || t("behavioral.unknown_error")}
      </div>
      <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 16 }}>
        {suggestion}
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "center" }}>
        <button className="btn btn-g btn-s" onClick={onRetry}>{t("common.retry")}</button>
        <button className="btn btn-s" style={{ background: "var(--bg3)" }} onClick={() => window.location.reload()}>{t("behavioral.reload_app")}</button>
      </div>
    </div>
  );
}

// ── Tab definitions ───────────────────────────────────────────────────────────
const TABS = [
  { id: "behavior", Icon: IconBehavioral, labelKey: "behavioral.tab_behavior", subKey: "behavioral.tab_behavior_sub" },
  { id: "risk",     Icon: IconRisk,       labelKey: "behavioral.tab_risk",     subKey: "behavioral.tab_risk_sub"     },
  { id: "heatmap",  Icon: IconHeatmap,    labelKey: "behavioral.tab_heatmap",  subKey: "behavioral.tab_heatmap_sub"  },
  { id: "ai",       Icon: IconInfo,       labelKey: "behavioral.tab_ai",       subKey: "behavioral.tab_ai_sub"       },
];

// ── Tab bar ───────────────────────────────────────────────────────────────────
function TabBar({ active, onChange }) {
  const { t } = useI18n();
  return (
    <div className="tabs" style={{ marginBottom: 20, display: "flex", gap: 6, overflowX: "auto", scrollbarWidth: "none", WebkitOverflowScrolling: "touch" }}>
      {TABS.map(tab => {
        const on = active === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            className={`tab${on ? " act" : ""}`}
            style={{
              flex: "0 0 auto", minWidth: 0, padding: "10px 14px",
              borderRadius: "var(--r)", outline: "none", cursor: "pointer",
              background: on ? "var(--sb-act)" : "var(--bg2)", textAlign: "left",
              border: on ? "1px solid rgba(79,110,247,.3)" : "1px solid var(--bdr)",
              transition: "all .15s",
              boxShadow: on ? "0 0 18px rgba(79,110,247,.08)" : "none",
              display: "flex", flexDirection: "column", alignItems: "flex-start",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 7, marginBottom: 2 }}>
              <span style={{ display:"flex",alignItems:"center" }}><tab.Icon size={15} /></span>
              <span className="beh-tab-label" style={{ fontSize: 12, fontWeight: 700, color: on ? "var(--ind-b)" : "var(--tx2)", whiteSpace: "nowrap" }}>
                {t(tab.labelKey)}
              </span>
            </div>
            <div className="beh-tab-sub" style={{ fontSize: 9, color: "var(--tx3)", fontFamily: "'Space Mono', monospace", paddingLeft: 22, whiteSpace: "nowrap" }}>
              {t(tab.subKey)}
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function BehavioralDashboard() {
  const { t } = useI18n();
  const [tab, setTab] = usePersistedTab("behavioral", "behavior");
  const { loading, error, report, reload } = useBehavioralData();
  const { data: balances } = useBalances();
  const { status: aiStatus, loading: aiStatusLoading } = useAIStatus();

  // Map flat CLI report to the shape each sub-component expects.
  // API: report.fbs = { score, grade, label, color, saving_rate, impulse_index, component_scores }
  // component_scores keys: saving_rate, budget_adherence, impulse_control, consistency, emergency_buffer
  const behavioral = report ? (() => {
    const fbsScore  = report.fbs?.score ?? null;
    const impIdx    = report.fbs?.impulse_index ?? report.impulse?.index ?? null;
    const savRate   = report.fbs?.saving_rate != null ? report.fbs.saving_rate / 100 : null;
    const expThis   = report.summary?.exp_total_this ?? null;
    const expPrev   = report.summary?.exp_total_prev ?? null;
    const incThis   = report.summary?.inc_total_this ?? null;
    const incPrev   = report.summary?.inc_total_prev ?? null;
    const expGrowth = (expPrev != null && expThis != null && expPrev > 0) ? (expThis - expPrev) / expPrev : null;
    const incGrowth = (incPrev != null && incThis != null && incPrev > 0) ? (incThis - incPrev) / incPrev : null;
    const liScore   = (expGrowth != null && incGrowth != null) ? expGrowth - incGrowth : null;
    const emotRatio = impIdx != null ? Math.min(1, (impIdx / 100) * 0.6) : null;
    const budgetAdh = (report.fbs?.component_scores?.budget_adherence ?? null) != null ? report.fbs.component_scores.budget_adherence / 100 : null;
    // API returns by_category as 0-100 percent; ImpulsivityPanel expects 0-1
    const rawBreakdown = report.impulse?.by_category ?? {};
    const breakdown    = Object.fromEntries(
      Object.entries(rawBreakdown).map(([k, v]) => [k, v / 100])
    );
    return {
      fbs:             fbsScore,
      impulsivityIndex: impIdx != null ? impIdx / 100 : null,
      breakdown,
      perTx:           report.impulse?.per_tx ?? [],
      savingRate:      savRate,
      emotionalRatio:  emotRatio,
      liScore,
      expGrowth,
      incGrowth,
      expTotalThis:    expThis,
      expTotalPrev:    expPrev,
      incTotalThis:    incThis,
      incTotalPrev:    incPrev,
      monthLabel:      report.month_label ?? "",
      budgetAdherence: budgetAdh,
    };
  })() : null;

  const fragility = (() => {
    if (!report) return null;
    const av       = report.fragility?.asset_values ?? {};
    const cash     = av.cash ?? report.summary?.cash_savings ?? null;
    const totalInv = Object.entries(av).filter(([k]) => k !== "cash").reduce((s, [, v]) => s + (v || 0), 0);
    const netWorth = (cash != null || totalInv > 0) ? (cash ?? 0) + totalInv : null;
    const total    = netWorth || 1;  // avoid /0

    // Build allocation as percentages (0-100) for AllocationPanel
    const allocation = {
      cash:   cash != null ? (cash / total) * 100 : null,
      stock:  av.stock != null ? (av.stock / total) * 100 : null,
      crypto: av.crypto != null ? (av.crypto / total) * 100 : null,
      gold:   av.gold != null ? (av.gold / total) * 100 : null,
      highRisk: av.crypto != null ? (av.crypto / total) * 100 : null,
    };

    // Income dependency
    const incThis  = report.summary?.inc_total_this ?? null;
    const nSources = report.fragility?.income_sources ?? null;
    const depRatio = nSources != null ? (nSources > 1 ? Math.max(0.2, 1 - (nSources - 1) * 0.25) : 1.0) : null;

    return {
      score:      report.fragility?.score ?? null,
      grade:      report.fragility?.grade ?? "",
      label:      report.fragility?.label ?? "",
      color:      report.fragility?.color ?? "#fff",
      allocation,
      depResult:  { ratio: depRatio, primarySource: nSources != null ? (nSources > 1 ? "Diversified" : "Single Source") : null },
      debtRatio:  null,
      cashSavings: cash,
      netWorth,
      emergencyFund: report.summary?.emergency_fund ?? null,
      totalInvestment: totalInv,
      assetValues: av,
      incomeBySource: incThis != null ? { "Other": incThis } : {},
    };
  })();

  // Build a HeatCell-compatible object from raw values
  const makeCell = (label, current, previous) => {
    if (current === null || current === undefined) {
      return { label, current: null, previous: null, pct: 0, isNegative: false, intensity: 0, color: "var(--bg3)", borderColor: "var(--bdr)", textColor: "var(--tx3)", pctDisplay: "—" };
    }
    const pct       = (previous != null && previous > 0) ? (current - previous) / previous : 0;
    const isNeg     = pct < 0;
    const rawInt    = Math.min(Math.abs(pct) / 0.5, 1);
    const intensity = isNeg ? Math.min(rawInt * 1.8, 1) : rawInt;
    const alpha     = 0.08 + intensity * 0.3;
    const color        = isNeg ? `rgba(248,113,113,${alpha})`   : `rgba(52,211,153,${alpha})`;
    const borderColor  = isNeg ? `rgba(248,113,113,${alpha*1.6})` : `rgba(52,211,153,${alpha*1.6})`;
    const textColor    = isNeg ? "#f87171" : "#34d399";
    const pctDisplay   = (previous != null && previous > 0) ? (Math.abs(pct) * 100).toFixed(1) : "—";
    return { label, current, previous, pct, isNegative: isNeg, intensity, color, borderColor, textColor, pctDisplay };
  };

  const assetValues   = report?.fragility?.asset_values ?? {};
  // Authoritative values from /api/balances — Cash (physical_cash) and Bank Savings are
  // distinct categories and must appear as separate cells in the heatmap.
  const physicalCash  = balances?.physical_cash   ?? null;
  const bankSavings   = balances?.bank_savings    ?? report?.summary?.cash_savings   ?? null;
  const emergencyFund = balances?.emergency_fund  ?? report?.summary?.emergency_fund ?? null;

  const heatmap = report ? {
    cells: [
      makeCell("Cash",          physicalCash,             null),  // physical cash on hand
      makeCell("Bank Savings",  bankSavings,              null),  // bank_savings = net current position
      makeCell("Crypto",        assetValues.crypto ?? null,  null),
      makeCell("Gold",          assetValues.gold   ?? null,  null),
      makeCell("Stocks",        assetValues.stock  ?? null,  null),
      makeCell("Emergency Fund", emergencyFund,            null),
    ],
    netWorth:   makeCell("Net Worth", report.summary?.net_worth ?? null, null),
    monthLabel: report.month_label ?? "",
    prevLabel:  "",
  } : null;

  return (
    <div>
      <h1 className="sr-only">{t("behavioral.sr_title")}</h1>
      {/* Header — description hidden on mobile to save space */}
      <div style={{ marginBottom: 14, display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10 }}>
        <div className="beh-header-desc">
          <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "1.2px", marginBottom: 4 }}>
            {t("behavioral.header_title")}
          </div>
          <div style={{ fontSize: 12, color: "var(--tx2)", lineHeight: 1.5, maxWidth: 540 }}>
            {t("behavioral.header_sub")}
          </div>
        </div>
        <AIPassiveStatus status={aiStatus} loading={aiStatusLoading} />
      </div>

      {/* Tab bar */}
      <TabBar active={tab} onChange={setTab} />

      {/* Content area */}
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : (
        <>
          {tab === "behavior" && <ImpulsiveSpending data={report} />}
          {tab === "risk"     && <RiskExposure     data={report}  />}
          {tab === "heatmap"  && <NetWorthHeatmap  data={heatmap} onReload={reload} />}
          {tab === "ai"       && <AIInsightPanel />}
        </>
      )}
    </div>
  );
}

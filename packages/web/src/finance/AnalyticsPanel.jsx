// ─── AnalyticsPanel.jsx ───────────────────────────────────────────────────────
// Phase 3 Analytics — three predictive/simulation panels:
//
//  1. ExpensePredictionPanel  — linear regression, next 3 months
//  2. SavingProjectionPanel   — compound savings projection, 5 years
//  3. PortfolioRiskPanel      — allocation + scenario simulation
//
// Also:
//  4. LifestyleInflationTrend — Phase 2.3 upgrade (6-month rolling LI)
//
// Architecture: pure UI, zero business logic. All maths live in api_server.py.
// Low Coupling  : each panel is self-contained, fetches its own data.
// High Cohesion : one concept per panel, one hook per endpoint.
// DRY           : shared StatBox, TrendBadge, EmptyState atoms.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect } from "react";
import { fmt, API_BASE }       from "./constants.js";
import TrendChart              from "./TrendChart.jsx";
import { _getToken }           from "./useApi.js";
import { IconBarChart, IconTarget, IconWarning, IconInfo, IconSuccess } from "../icons.jsx";
import { useI18n } from "../i18n/context.js";

// ── Shared atoms ──────────────────────────────────────────────────────────────

const fmtRp = n => {
  if (!n && n !== 0) return "—";
  if (Math.abs(n) >= 1_000_000_000) return `Rp ${(n / 1_000_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000_000)     return `Rp ${(n / 1_000_000).toFixed(1)}jt`;
  if (Math.abs(n) >= 1_000)         return `Rp ${(n / 1_000).toFixed(0)}K`;
  return `Rp ${Math.round(n)}`;
};
const sign = v => v >= 0 ? "+" : "";

function StatBox({ label, value, sub, color = "var(--acc)", small }) {
  return (
    <div style={{
      background: "var(--bg3)", border: "1px solid var(--bdr)",
      borderRadius: 10, padding: small ? "10px 12px" : "12px 16px",
    }}>
      <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 4 }}>{label}</div>
      <div style={{ fontFamily: "var(--mono)", fontSize: small ? 14 : 18, fontWeight: 800, color }}>{value}</div>
      {sub && <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 3, fontFamily: "var(--mono)" }}>{sub}</div>}
    </div>
  );
}

function SectionCard({ title, Icon, badge, children, accentColor }) {
  return (
    <div style={{
      background: "var(--bg2)", border: `1px solid ${accentColor || "var(--bdr2)"}28`,
      borderRadius: "var(--rl)", overflow: "hidden", marginBottom: 20,
    }}>
      {accentColor && <div style={{ height: 2, background: `linear-gradient(90deg, ${accentColor}, transparent)` }} />}
      <div style={{ padding: "18px 20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
          {Icon && <Icon size={17} color={accentColor || "var(--acc)"} />}
          <span style={{ fontWeight: 700, fontSize: 14 }}>{title}</span>
          {badge && <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--tx3)", fontFamily: "var(--mono)" }}>{badge}</span>}
        </div>
        {children}
      </div>
    </div>
  );
}

function EmptyState({ msg }) {
  return (
    <div style={{ textAlign: "center", color: "var(--tx3)", fontSize: 12, padding: "20px 0" }}>{msg}</div>
  );
}

function useFetch(path) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError(null);
    const token = _getToken();
    fetch(`${API_BASE}${path}`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    })
      .then(r => r.ok ? r.json() : Promise.reject(r.status))
      .then(d => { if (!cancelled) setData(d); })
      .catch(e => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [path]);
  return { data, loading, error };
}


// ══════════════════════════════════════════════════════════════════════════════
// § 1 — LIFESTYLE INFLATION TREND (Phase 2.3 upgrade)
// ══════════════════════════════════════════════════════════════════════════════

export function LifestyleInflationTrend() {
  const { data, loading } = useFetch("/behavioral/lifestyle-trend?months=6");
  const { t } = useI18n();

  const sevColor = {
    severe:   "var(--rd)",
    moderate: "#f97316",
    mild:     "var(--yl)",
    healthy:  "var(--gr)",
  };

  const sevKey = {
    severe:   "finance.sev_severe",
    moderate: "finance.moderate",
    mild:     "finance.sev_mild",
    healthy:  "finance.sev_healthy",
  };

  if (loading) return (
    <SectionCard title={t("finance.lifestyle_trend")} Icon={IconWarning} accentColor="var(--rd)">
      <EmptyState msg={t("common.loading")} />
    </SectionCard>
  );

  if (!data?.trend?.length) return (
    <SectionCard title={t("finance.lifestyle_trend")} Icon={IconWarning} accentColor="var(--yl)">
      <EmptyState msg={t("finance.need_two_months_data")} />
    </SectionCard>
  );

  const sev   = data.severity ?? "healthy";
  const color = sevColor[sev] || "var(--tx)";
  const trend = data.trend;
  const latest = trend[trend.length - 1];

  return (
    <SectionCard
      title={t("finance.lifestyle_trend")}
      Icon={IconWarning}
      badge={t("finance.li_badge", { months: trend.length, value: `${sign(data.avg_li_3mo)}${(data.avg_li_3mo * 100).toFixed(1)}` })}
      accentColor={color}
    >
      {/* Severity banner */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        background: `${color}12`, border: `1px solid ${color}28`,
        borderRadius: 8, padding: "10px 14px", marginBottom: 14,
      }}>
        <div style={{ fontSize: 12, fontWeight: 700, color }}>{t(sevKey[sev] || "finance.sev_healthy").toUpperCase()}</div>
        <div style={{ fontSize: 11, color: "var(--tx2)", flex: 1 }}>
          {sev === "severe"   && t("finance.li_severe")}
          {sev === "moderate" && t("finance.li_moderate")}
          {sev === "mild"     && t("finance.li_mild")}
          {sev === "healthy"  && t("finance.li_healthy")}
        </div>
        <div style={{ fontFamily: "var(--mono)", fontSize: 16, fontWeight: 900, color, flexShrink: 0 }}>
          {sign(data.avg_li_3mo)}{ (data.avg_li_3mo * 100).toFixed(1)}pp
        </div>
      </div>

      {/* Month-by-month LI bars */}
      <div style={{ display: "flex", gap: 6, alignItems: "flex-end", height: 80, marginBottom: 12 }}>
        {trend.map((m, i) => {
          const li = m.li_score;
          const pos = li >= 0;
          const barH = Math.min(60, Math.abs(li) * 300 + 6);
          const c = pos
            ? (li > 0.15 ? "var(--rd)" : li > 0.05 ? "#f97316" : "var(--yl)")
            : "var(--gr)";
          return (
            <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{ fontSize: 8, fontFamily: "var(--mono)", color: c, fontWeight: 700, marginBottom: 2, whiteSpace: "nowrap" }}>
                {sign(li)}{(li * 100).toFixed(0)}pp
              </div>
              <div style={{ width: "100%", minWidth: 14, height: barH, background: c, borderRadius: "3px 3px 0 0", opacity: 0.85 }} />
              <div style={{ width: "100%", height: 1.5, background: "var(--bdr2)" }} />
              <div style={{ fontSize: 8, color: "var(--tx3)", marginTop: 2, fontFamily: "var(--mono)" }}>
                {(m.label || "").slice(0, 3)}
              </div>
            </div>
          );
        })}
      </div>

      {/* Stat row */}
      <div className="analytics-stat-3" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
        <StatBox label={t("finance.expense_growth")} value={`${sign(latest.exp_growth)}${(latest.exp_growth * 100).toFixed(1)}%`}
          color={latest.exp_growth > 0.05 ? "var(--rd)" : "var(--gr)"} small />
        <StatBox label={t("finance.income_growth")}  value={`${sign(latest.inc_growth)}${(latest.inc_growth * 100).toFixed(1)}%`}
          color={latest.inc_growth > 0.05 ? "var(--gr)" : "var(--yl)"} small />
        <StatBox label={t("finance.li_score_latest")} value={`${sign(latest.li_score)}${(latest.li_score * 100).toFixed(1)}pp`}
          color={color} small />
      </div>
    </SectionCard>
  );
}


// ══════════════════════════════════════════════════════════════════════════════
// § 2 — EXPENSE PREDICTION
// ══════════════════════════════════════════════════════════════════════════════

export function ExpensePredictionPanel() {
  const { data, loading } = useFetch("/analytics/expense-prediction?months_history=6&months_ahead=3");

  const { t } = useI18n();

  if (loading) return (
    <SectionCard title={t("finance.expense_prediction")} Icon={IconBarChart} accentColor="#6b85ff">
      <EmptyState msg={t("common.loading")} />
    </SectionCard>
  );

  if (!data || data.insufficient_data) return (
    <SectionCard title={t("finance.expense_prediction")} Icon={IconBarChart} accentColor="#6b85ff">
      <EmptyState msg={t("finance.need_3mo_expense")} />
    </SectionCard>
  );

  const histSeries = data.history.map(h => ({ label: (h.label || "").slice(0, 6), value: h.amount }));
  const predSeries = data.predictions.map(p => ({ label: (p.label || "").slice(0, 6), value: p.amount }));
  const combined   = [...histSeries, ...predSeries];

  const trendColor = data.trend === "rising" ? "var(--rd)" : data.trend === "falling" ? "var(--gr)" : "var(--yl)";

  return (
    <SectionCard
      title={t("finance.expense_prediction")}
      Icon={IconBarChart}
      badge={t("finance.r2_badge", { r2: data.r_squared?.toFixed(2), trend: data.trend })}
      accentColor="#6b85ff"
    >
      {/* Trend indicator */}
      <div className="analytics-stat-3" style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap" }}>
        <StatBox label={t("finance.trend")} value={data.trend.toUpperCase()} color={trendColor} small />
        <StatBox label={t("finance.monthly_slope")} value={`${sign(data.slope)}${fmtRp(data.slope)}/mo`}
          color={trendColor} small />
        <StatBox label={t("finance.model_fit")} value={`${(data.r_squared * 100).toFixed(1)}%`}
          color={data.r_squared > 0.6 ? "var(--gr)" : "var(--yl)"} small />
      </div>

      {/* Combined history + prediction chart */}
      <TrendChart
        title=""
        height={140}
        fmt={fmt}
        series={[
          { key: "hist", label: t("finance.history"),    color: "var(--ind-b)", data: histSeries },
          { key: "pred", label: t("finance.prediction"), color: "var(--yl)",    data: predSeries.map((p, i) => ({ ...p, label: "~" + p.label })) },
        ]}
      />

      {/* Prediction table */}
      <div style={{ marginTop: 10 }}>
        <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--tx3)", marginBottom: 8 }}>
          {t("finance.forecast_months", { count: data.predictions.length })}
        </div>
        {data.predictions.map((p, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "8px 10px", background: "var(--bg3)", borderRadius: 7, marginBottom: 6,
            border: "1px solid var(--bdr)",
          }}>
            <span style={{ fontSize: 12, color: "var(--tx2)", fontFamily: "var(--mono)" }}>{p.label}</span>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontSize: 13, fontWeight: 700, fontFamily: "var(--mono)", color: "var(--yl)" }}>
                {fmtRp(p.amount)}
              </div>
              <div style={{ fontSize: 10, color: "var(--tx3)", fontFamily: "var(--mono)" }}>
                {fmtRp(p.lower)} – {fmtRp(p.upper)}
              </div>
            </div>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}


// ══════════════════════════════════════════════════════════════════════════════
// § 3 — SAVING PROJECTION
// ══════════════════════════════════════════════════════════════════════════════

export function SavingProjectionPanel() {
  const [years, setYears]   = useState(5);
  const [ret, setRet]       = useState(7);
  const { data, loading }   = useFetch(`/analytics/saving-projection?years=${years}&annual_return_pct=${ret}`);

  const { t } = useI18n();

  if (loading) return (
    <SectionCard title={t("finance.saving_projection")} Icon={IconTarget} accentColor="var(--gr)">
      <EmptyState msg={t("common.loading")} />
    </SectionCard>
  );

  const projs = data?.projections ?? [];

  return (
    <SectionCard
      title={t("finance.saving_projection")}
      Icon={IconTarget}
      badge={t("finance.years_return_badge", { years, ret })}
      accentColor="var(--gr)"
    >
      {/* Controls */}
      <div className="saving-proj-controls" style={{ display: "flex", gap: 12, marginBottom: 14, flexWrap: "wrap", alignItems: "center" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, color: "var(--tx3)" }}>{t("finance.years_label")}</span>
          {[3, 5, 10, 20].map(y => (
            <button key={y} onClick={() => setYears(y)} style={{
              padding: "3px 9px", borderRadius: 6, fontSize: 11, cursor: "pointer",
              background: years === y ? "var(--ind)" : "var(--bg3)",
              color: years === y ? "#fff" : "var(--tx2)",
              border: "1px solid var(--bdr)",
            }}>{y}y</button>
          ))}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 11, color: "var(--tx3)" }}>{t("finance.return_label")}</span>
          {[5, 7, 10, 15].map(r => (
            <button key={r} onClick={() => setRet(r)} style={{
              padding: "3px 9px", borderRadius: 6, fontSize: 11, cursor: "pointer",
              background: ret === r ? "var(--ind)" : "var(--bg3)",
              color: ret === r ? "#fff" : "var(--tx2)",
              border: "1px solid var(--bdr)",
            }}>{r}%</button>
          ))}
        </div>
      </div>

      {/* Key stats */}
      <div className="analytics-stat-3" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
        <StatBox label={t("finance.monthly_saving")}   value={fmtRp(data?.monthly_saving ?? null)}   color="var(--gr)" small />
        <StatBox label={t("finance.starting_balance")} value={fmtRp(data?.starting_balance ?? null)} color="var(--acc)" small />
        <StatBox label={t("finance.yr_projection", { years })} value={fmtRp(data?.final_total ?? null)} color="var(--gr)" small />
      </div>

      {/* Projection bar chart */}
      {projs.length > 0 && (
        <div className="saving-proj-chart">
        <TrendChart
          title=""
          height={180}
          fmt={fmt}
          series={[
            { key: "total",       label: t("finance.total"),       color: "var(--gr)",  data: projs.map(p => ({ label: p.label, value: p.total })) },
            { key: "contributed", label: t("finance.contributed"), color: "var(--ind)", data: projs.map(p => ({ label: p.label, value: p.contributed })) },
          ]}
        />
        </div>
      )}

      {/* Growth detail */}
      {projs.length > 0 && (
        <div style={{ marginTop: 10, fontSize: 11, color: "var(--tx3)", textAlign: "center", fontFamily: "var(--mono)" }}>
          {t("finance.investment_growth", { years })}{" "}<span style={{ color: "var(--gr)", fontWeight: 700 }}>
            {fmtRp(projs[projs.length - 1]?.growth ?? 0)}
          </span>
          {" "}{t("finance.at_annual_return", { ret })}
        </div>
      )}

      {(!data?.monthly_saving || data.monthly_saving <= 0) && (
        <div style={{ marginTop: 10, padding: "10px 14px", background: "rgba(251,191,36,.08)", border: "1px solid rgba(251,191,36,.2)", borderRadius: 8, fontSize: 11, color: "var(--yl)" }}>
          {t("finance.no_saving_detected")}
        </div>
      )}
    </SectionCard>
  );
}


// ══════════════════════════════════════════════════════════════════════════════
// § 4 — PORTFOLIO RISK SIMULATION
// ══════════════════════════════════════════════════════════════════════════════

const ASSET_COLOR = {
  crypto: "var(--yl)", stock: "#3b82f6", etf: "#60a5fa",
  reksa_dana: "#a78bfa", gold: "#f59e0b", other: "var(--tx3)",
};

export function PortfolioRiskPanel() {
  const { data, loading } = useFetch("/analytics/portfolio-risk");
  const { t } = useI18n();

  if (loading) return (
    <SectionCard title={t("finance.portfolio_risk")} Icon={IconInfo} accentColor="var(--yl)">
      <EmptyState msg={t("common.loading")} />
    </SectionCard>
  );

  if (!data || data.empty_portfolio) return (
    <SectionCard title={t("finance.portfolio_risk")} Icon={IconInfo} accentColor="var(--yl)">
      <EmptyState msg={t("finance.no_holdings")} />
    </SectionCard>
  );

  const riskColor = data.risk_score > 65 ? "var(--rd)" : data.risk_score > 40 ? "var(--yl)" : "var(--gr)";
  const riskLabel = data.risk_score > 65 ? t("finance.high_risk") : data.risk_score > 40 ? t("finance.moderate") : t("finance.conservative");

  return (
    <SectionCard
      title={t("finance.portfolio_risk")}
      Icon={IconInfo}
      badge={fmtRp(data.total_value)}
      accentColor={riskColor}
    >
      {/* Risk score ring + stats */}
      <div style={{ display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap", alignItems: "center" }}>
        {/* Risk score gauge */}
        <div style={{ textAlign: "center", flexShrink: 0 }}>
          <div className="risk-gauge-outer" style={{
            width: 76, height: 76, borderRadius: "50%",
            background: `conic-gradient(${riskColor} ${data.risk_score * 3.6}deg, var(--bg4) 0)`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <div className="risk-gauge-inner" style={{
              width: 56, height: 56, borderRadius: "50%",
              background: "var(--bg2)", display: "flex",
              alignItems: "center", justifyContent: "center",
              flexDirection: "column",
            }}>
              <div className="risk-gauge-score" style={{ fontFamily: "var(--mono)", fontSize: 18, fontWeight: 900, color: riskColor, lineHeight: 1 }}>
                {data.risk_score}
              </div>
              <div style={{ fontSize: 8, color: "var(--tx3)" }}>/ 100</div>
            </div>
          </div>
          <div style={{ fontSize: 10, color: riskColor, fontWeight: 700, marginTop: 5 }}>{riskLabel}</div>
        </div>

        {/* Key metrics */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, flex: 1 }}>
          <StatBox label={t("finance.expected_return")} value={`${data.weighted_return_pct?.toFixed(1)}%/yr`} color="var(--gr)" small />
          <StatBox label={t("finance.volatility")}  value={`${data.weighted_vol_pct?.toFixed(1)}%`}        color={riskColor} small />
          <StatBox label={t("finance.hhi")} value={data.concentration_hhi?.toFixed(2)}          color={data.concentration_hhi > 0.5 ? "var(--rd)" : "var(--yl)"} small />
          <StatBox label={t("finance.total_value")}     value={fmtRp(data.total_value)}                        color="var(--acc)" small />
        </div>
      </div>

      {/* Asset allocation */}
      {data.allocation?.length > 0 && (
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--tx3)", marginBottom: 8 }}>{t("finance.allocation")}</div>
          {data.allocation.map((a, i) => {
            const c = ASSET_COLOR[a.type] || "var(--tx3)";
            return (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 7 }}>
                <div style={{ width: "clamp(52px, 18vw, 70px)", fontSize: 11, color: "var(--tx2)", textTransform: "capitalize", flexShrink: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.type}</div>
                <div style={{ flex: 1, height: 6, background: "var(--bg4)", borderRadius: 99, overflow: "hidden" }}>
                  <div style={{ width: `${a.pct}%`, height: "100%", background: c, borderRadius: 99 }} />
                </div>
                <div style={{ width: "clamp(32px, 10vw, 42px)", textAlign: "right", fontSize: 11, fontFamily: "var(--mono)", color: c, fontWeight: 700, flexShrink: 0 }}>
                  {a.pct.toFixed(1)}%
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 1-year scenarios */}
      <div style={{ marginBottom: data.warnings?.length ? 14 : 0 }}>
        <div style={{ fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: "1px", color: "var(--tx3)", marginBottom: 8 }}>{t("finance.scenarios")}</div>
        <div className="portfolio-scenarios" style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
          {data.scenarios?.map((s, i) => {
            const c = s.return_pct < 0 ? "var(--rd)" : s.return_pct > 20 ? "var(--gr)" : "var(--yl)";
            return (
              <div key={i} style={{ background: "var(--bg3)", borderRadius: 8, padding: "10px 10px", border: "1px solid var(--bdr)", textAlign: "center" }}>
                <div style={{ fontSize: 9, color: "var(--tx3)", marginBottom: 4 }}>{s.label}</div>
                <div style={{ fontFamily: "var(--mono)", fontSize: 13, fontWeight: 800, color: c }}>
                  {sign(s.return_pct)}{s.return_pct}%
                </div>
                <div style={{ fontSize: 10, color: "var(--tx2)", fontFamily: "var(--mono)", marginTop: 2 }}>{fmtRp(s.value)}</div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Warnings */}
      {data.warnings?.length > 0 && (
        <div style={{ marginTop: 12 }}>
          {data.warnings.map((w, i) => (
            <div key={i} style={{
              display: "flex", gap: 8, alignItems: "flex-start",
              padding: "8px 10px", background: "rgba(248,113,113,.07)",
              border: "1px solid rgba(248,113,113,.2)", borderRadius: 7, marginBottom: 6,
            }}>
              <IconWarning size={13} color="var(--rd)" style={{ flexShrink: 0, marginTop: 1 }} />
              <span style={{ fontSize: 11, color: "var(--tx2)" }}>{w}</span>
            </div>
          ))}
        </div>
      )}
    </SectionCard>
  );
}

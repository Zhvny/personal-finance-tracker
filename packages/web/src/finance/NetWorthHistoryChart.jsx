// ─── NetWorthHistoryChart.jsx ─────────────────────────────────────────────────
// Phase 2: Net Worth Timeline + Saving Rate Graph
//
// Components exported:
//   NetWorthHistoryChart  — pulls /api/networth/history, renders multi-series
//                           line chart: total, cash, crypto, stocks, gold
//   SavingRateChart       — pulls /api/expenses/summary + /api/income/summary
//                           per month, renders 12-month saving rate % bar chart
//
// Design principles:
//   Low Coupling   : fetch own data, no props required beyond optional `days`.
//   High Cohesion  : only net-worth / saving-rate visualisation lives here.
//   DRY            : shared TrendChart for line rendering.

import { useState, useEffect } from "react";
import { fmt }                 from "./constants.js";
import { apiFetch }            from "./useApi.js";
import TrendChart              from "./TrendChart.jsx";
import { useI18n }             from "../i18n/context.js";

// ── Local helpers ─────────────────────────────────────────────────────────────

function fmtShortM(n) {
  if (!n && n !== 0) return "-";
  if (Math.abs(n) >= 1_000_000_000) return `${(n / 1_000_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000_000)     return `${(n / 1_000_000).toFixed(1)}jt`;
  if (Math.abs(n) >= 1_000)         return `${(n / 1_000).toFixed(0)}K`;
  return String(Math.round(n));
}

function pctColor(v) {
  if (v >= 30) return "var(--gr)";
  if (v >= 10) return "var(--yl)";
  return "var(--rd)";
}

// ══════════════════════════════════════════════════════════════════════════════
// § NET WORTH HISTORY CHART
// ══════════════════════════════════════════════════════════════════════════════

function useNetworthHistory(days = 90) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        // apiFetch attaches the Bearer token and handles 401; the endpoint is
        // auth-protected, so a raw fetch() here returned 401.
        const json = await apiFetch(`/networth/history?days=${days}`);
        // API returns { ok, history: [...] } or raw array
        const arr = Array.isArray(json) ? json : (json.history ?? []);
        if (!cancelled) setData(arr);
      } catch (e) {
        if (!cancelled) setError(e.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [days]);

  return { data, loading, error };
}

export function NetWorthHistoryChart({ days = 90 }) {
  const { data, loading, error } = useNetworthHistory(days);
  const { t } = useI18n();

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h"><span className="card-t">{t("finance.net_worth_history")}</span></div>
        <div style={{ padding: "20px 14px", textAlign: "center", color: "var(--tx3)", fontSize: 12 }}>
          {t("finance.loading_history")}
        </div>
      </div>
    );
  }

  if (error || !data || !Array.isArray(data) || data.length < 2) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h"><span className="card-t">{t("finance.net_worth_history")}</span></div>
        <div style={{ padding: "16px 14px", textAlign: "center", color: "var(--tx3)", fontSize: 12 }}>
          {data && data.length === 0
            ? t("finance.no_history")
            : data && data.length === 1
              ? t("finance.need_two_snapshots")
              : t("finance.history_unavailable")}
        </div>
      </div>
    );
  }

  // Build label: "DD/MM" from ISO date
  const label = (row) => {
    const d = row.date || "";
    return d.length >= 10 ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : d;
  };

  // Latest snapshot for summary row
  const latest  = data[data.length - 1];
  const earliest = data[0];
  const delta    = (latest.total_networth || 0) - (earliest.total_networth || 0);
  const deltaPos = delta >= 0;

  const series = [
    {
      key:   "total",
      label: t("finance.total"),
      color: "var(--acc)",
      data:  data.map(r => ({ label: label(r), value: r.total_networth || 0 })),
    },
    {
      key:   "cash",
      label: t("behavioral.asset_cash"),
      color: "var(--gr)",
      data:  data.map(r => ({ label: label(r), value: (r.cash || 0) + (r.bank_savings || 0) + (r.emergency_fund || 0) })),
    },
    {
      key:   "stocks",
      label: t("behavioral.asset_stocks"),
      color: "#3b82f6",
      data:  data.map(r => ({ label: label(r), value: r.stocks || 0 })),
    },
    {
      key:   "crypto",
      label: t("behavioral.asset_crypto"),
      color: "var(--yl)",
      data:  data.map(r => ({ label: label(r), value: r.crypto || 0 })),
    },
    {
      key:   "gold",
      label: t("behavioral.asset_gold"),
      color: "#f59e0b",
      data:  data.map(r => ({ label: label(r), value: r.gold || 0 })),
    },
  ].filter(s => s.data.some(d => d.value > 0)); // only show series with data

  return (
    <div style={{ marginBottom: 0 }}>
      {/* Summary bar */}
      <div className="card" style={{ marginBottom: 8 }}>
        <div className="card-h">
          <span className="card-t">{t("finance.net_worth_history")}</span>
          <span style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "var(--mono)" }}>
            {t("finance.snapshots_days", { count: data.length, days })}
          </span>
        </div>
        <div className="nw-summary-row" style={{ display: "flex", gap: 20, padding: "6px 14px 14px", flexWrap: "wrap" }}>
          <div>
            <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 2 }}>{t("finance.current")}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--mono)", color: "var(--acc)" }}>
              {fmt(latest.total_networth || 0)}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 2 }}>{t("finance.change_days", { days: data.length })}</div>
            <div style={{ fontSize: 15, fontWeight: 700, fontFamily: "var(--mono)", color: deltaPos ? "var(--gr)" : "var(--rd)" }}>
              {deltaPos ? "+" : ""}{fmt(delta)}
            </div>
          </div>
          {latest.cash > 0 || latest.bank_savings > 0 ? (
            <div>
              <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 2 }}>{t("behavioral.asset_cash")}</div>
              <div style={{ fontSize: 13, fontFamily: "var(--mono)", color: "var(--gr)" }}>
                {fmtShortM((latest.cash || 0) + (latest.bank_savings || 0) + (latest.emergency_fund || 0))}
              </div>
            </div>
          ) : null}
          {latest.stocks > 0 ? (
            <div>
              <div style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 2 }}>{t("behavioral.asset_stocks")}</div>
              <div style={{ fontSize: 13, fontFamily: "var(--mono)", color: "#3b82f6" }}>
                {fmtShortM(latest.stocks)}
              </div>
            </div>
          ) : null}
        </div>
      </div>

      {/* Chart */}
      <TrendChart
        title=""
        height={160}
        fmt={fmt}
        series={series}
      />
    </div>
  );
}


// ══════════════════════════════════════════════════════════════════════════════
// § SAVING RATE CHART
// ══════════════════════════════════════════════════════════════════════════════

export function SavingRateChart() {
  // Use the existing total_credit hook pattern — fetch income summary which
  // includes by_month with income + expense (from expense_tracker cross-ref)
  const [months, setMonths] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        // apiFetch attaches the Bearer token; endpoint is auth-protected.
        const json = await apiFetch(`/balances/total-credit`);
        const raw = json.by_month ?? [];
        if (!cancelled) {
          setMonths(raw.map(m => ({
            label:       m.label || "",
            income:      m.income  || 0,
            expense:     m.expense || 0,
            saving_rate: m.income > 0 ? ((m.income - m.expense) / m.income) * 100 : 0,
          })));
        }
      } catch {
        if (!cancelled) setMonths([]);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const { t } = useI18n();

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h"><span className="card-t">{t("finance.saving_rate_trend")}</span></div>
        <div style={{ padding: "20px", textAlign: "center", color: "var(--tx3)", fontSize: 12 }}>
          {t("common.loading")}
        </div>
      </div>
    );
  }

  const active = (months || []).filter(m => m.income > 0 || m.expense > 0);
  if (active.length < 2) {
    return (
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-h"><span className="card-t">{t("finance.saving_rate_trend")}</span></div>
        <div style={{ padding: "16px", textAlign: "center", color: "var(--tx3)", fontSize: 12 }}>
          {t("finance.need_two_months_income")}
        </div>
      </div>
    );
  }

  const avgRate = active.reduce((s, m) => s + m.saving_rate, 0) / active.length;
  const maxIncome = Math.max(...active.map(m => m.income), 1);

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-h">
        <span className="card-t">{t("finance.saving_rate_trend")}</span>
        <span style={{ fontSize: 11, color: "var(--tx3)", fontFamily: "var(--mono)" }}>
          {t("finance.avg_12mo", { rate: avgRate.toFixed(1) })}
        </span>
      </div>

      {/* Bar chart */}
      <div style={{ padding: "4px 14px 14px", overflowX: "auto" }}>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 6, minWidth: "min(240px, 100%)", height: 120, overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
          {active.map((m, i) => {
            const rate   = Math.max(-100, Math.min(100, m.saving_rate));
            const isPos  = rate >= 0;
            const barH   = Math.abs(rate) / 100 * 80; // max 80px
            const color  = pctColor(rate);

            return (
              <div key={i} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", position: "relative" }}>
                {/* Rate label above bar */}
                <div className="saving-rate-bar-label" style={{
                  fontSize: 9, fontFamily: "var(--mono)", color,
                  fontWeight: 700, marginBottom: 2, whiteSpace: "nowrap",
                  overflow: "hidden", textOverflow: "ellipsis", maxWidth: "100%",
                }}>
                  {rate >= 0 ? "+" : ""}{rate.toFixed(0)}%
                </div>

                {/* Bar */}
                <div style={{
                  width: "100%", minWidth: 18,
                  height: `${Math.max(barH, 4)}px`,
                  background: color,
                  borderRadius: "3px 3px 0 0",
                  opacity: 0.85,
                  transition: "height .3s",
                }} />

                {/* Baseline */}
                <div style={{ width: "100%", height: 1.5, background: "var(--bdr2)" }} />

                {/* Month label */}
                <div className="saving-rate-bar-month" style={{ fontSize: 8, color: "var(--tx3)", marginTop: 3, fontFamily: "var(--mono)" }}>
                  {(m.label || "").slice(0, 3)}
                </div>
              </div>
            );
          })}
        </div>

        {/* Legend */}
        <div style={{ display: "flex", gap: 16, marginTop: 8, fontSize: 10, color: "var(--tx3)" }}>
          <span style={{ color: "var(--gr)" }}>■ {t("finance.rate_good")}</span>
          <span style={{ color: "var(--yl)" }}>■ {t("finance.rate_ok")}</span>
          <span style={{ color: "var(--rd)" }}>■ {t("finance.rate_low")}</span>
        </div>
      </div>
    </div>
  );
}

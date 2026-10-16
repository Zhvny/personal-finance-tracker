// ─── dashboard.jsx ────────────────────────────────────────────────────────────
// Dashboard page — now fetches its own data independently for widget-level isolation.
// High Cohesion  : each widget manages its own loading state.
// Low Coupling   : depends only on useApi.js hooks and components.jsx UI atoms.

import React, { Suspense } from "react";
import { fmt, fmtS, pctChg, CAT_COLOR } from "../constants.js";
import { ApiError, WidgetSkeleton, DashboardSkeleton, StatCard, ErrorBoundary, Empty } from "../components.jsx";
import { CAT_ICON_JSX, ASSET_ICON_JSX, IconPieChart, IconBarChart, IconInfo, IconWarning, IconIncome, IconExpense, IconWallet, IconInvestment, IconInsight, IconRepeat, IconArrowRight, IconRefresh } from "../icons.jsx";
import { useTotalCredit, useMacro, useDashboard, useDashboardMetadata, useAppConfig, useSankeyData } from "../finance/useApi.js";
import TrendChart from "../finance/TrendChart.jsx";
import { NetWorthHistoryChart, SavingRateChart } from "../finance/NetWorthHistoryChart.jsx";
import SankeyChart from "../finance/SankeyChart.jsx";

// ── Widget: Macro Market Overview ───────────────────────────────────────────
function MacroMarketOverview() {
  const { data: macro, loading, error, reload } = useMacro();
  
  if (error) return <ApiError error={error} onRetry={reload} />;
  if (loading) return <WidgetSkeleton h={116} rows={1} />;

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-h">
        <span className="card-t" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <IconInsight size={14} /> Global Macro Market
        </span>
        <div style={{ fontSize: 10, color: "var(--tx3)", fontWeight: 700 }}>REAL-TIME VECTORS</div>
      </div>
      <div className="card-b" style={{ padding: "16px 20px" }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 16 }}>
          <div>
            <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1, marginBottom: 4 }}>REGIME</div>
            <div style={{ fontSize: 16, fontWeight: 900, color: "var(--cy)" }}>{macro?.regime || "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1, marginBottom: 4 }}>LIQUIDITY (LPI)</div>
            <div style={{ fontSize: 16, fontWeight: 900 }}>{macro?.lpi != null ? macro.lpi.toFixed(1) : "—"}</div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1, marginBottom: 4 }}>YIELD CURVE</div>
            <div style={{ fontSize: 16, fontWeight: 900, color: (macro?.ycmo ?? 0) >= 0 ? "var(--gr)" : "var(--rd)" }}>
              {macro?.ycmo != null ? macro.ycmo.toFixed(1) : "—"}
            </div>
          </div>
          <div>
            <div style={{ fontSize: 10, fontWeight: 900, color: "var(--tx3)", letterSpacing: 1, marginBottom: 4 }}>INFLATION (ICM)</div>
            <div style={{ fontSize: 16, fontWeight: 900, color: (macro?.icm ?? 0) > 0.4 ? "var(--rd)" : "var(--gr)" }}>
              {macro?.icm != null ? macro.icm.toFixed(1) : "—"}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Widget: 12-month trend chart ──────────────────────────────────────────────
function MonthlyTrendChart() {
  const { data, loading, error, reload } = useTotalCredit();
  
  if (error) return <ApiError error={error} onRetry={reload} />;
  if (loading) return <WidgetSkeleton h={190} rows={0} />;
  
  const months = data?.by_month ?? [];
  const active = months.filter(m => m.income > 0 || m.expense > 0);
  if (active.length < 2) return null;

  return (
    <TrendChart
      title="12-Month Trend"
      height={150}
      fmt={fmt}
      series={[
        { key: "income",  label: "Income",  color: "var(--gr)", data: active.map(m => ({ label: m.label, value: m.income  })) },
        { key: "expense", label: "Expense", color: "var(--rd)", data: active.map(m => ({ label: m.label, value: m.expense })) },
      ]}
    />
  );
}

// ── Widget: Category breakdown ───────────────────────────────────────────────
function CategoryBreakdown({ byCategory, loading }) {
  if (loading) return <WidgetSkeleton rows={4} h={200} />;

  const entries = Object.entries(byCategory || {}).sort((a, b) => b[1] - a[1]);
  const maxVal  = Math.max(...entries.map(([, v]) => v), 1);

  if (!entries.length) return (
    <Empty
      variant="expense"
      msg="Belum ada pengeluaran bulan ini."
      sub="Mulai catat pengeluaran untuk melihat breakdown per kategori."
    />
  );

  return (
    <>
      {entries.map(([cat, amt]) => (
        <div key={cat} className="cat-row">
          <div className="cat-lbl">{CAT_ICON_JSX[cat] ? <span style={{display:"inline-flex",verticalAlign:"middle",marginRight:5}}>{CAT_ICON_JSX[cat]({ size: 13 })}</span> : null} {cat}</div>
          <div className="cat-bw">
            <div className="cat-bf" style={{ width: `${(amt / maxVal) * 100}%`, background: CAT_COLOR[cat] || "#6b7280" }} />
          </div>
          <div className="cat-amt">{fmt(amt)}</div>
        </div>
      ))}
    </>
  );
}

// ── Widget: Cashflow Sankey ──────────────────────────────────────────────────
function CashflowSankey() {
  const { data: sankeyData, loading, error, reload } = useSankeyData();
  const [width, setWidth] = React.useState(600);
  const containerRef = React.useRef(null);

  React.useEffect(() => {
    if (!containerRef.current) return;
    const obs = new ResizeObserver(entries => {
      const w = entries[0].contentRect.width;
      if (w > 0) setWidth(w);
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, []);

  if (error) return <ApiError error={error} onRetry={reload} />;
  if (loading) return <WidgetSkeleton h={300} rows={0} />;
  if (!sankeyData || sankeyData.links.length === 0) return null;

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <div className="card-h">
        <span className="card-t" style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <IconIncome size={14} /> Cashflow Path
        </span>
        <div style={{ fontSize: 10, color: "var(--tx3)", fontWeight: 700 }}>MONTHLY FLOW</div>
      </div>
      <div className="card-b" ref={containerRef} style={{ padding: "16px 20px" }}>
        <SankeyChart data={sankeyData} width={width} height={320} />
      </div>
    </div>
  );
}

// ── Widget: Portfolio sidebar ───────────────────────────────────────────────
function PortfolioSidebar({ holdings, plTotal, loading, onNav }) {
  if (loading) return <WidgetSkeleton rows={5} h={350} />;

  return (
    <div className="card" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="card-h">
        <span className="card-t" style={{ display:"flex", alignItems:"center", gap:6 }}>
          <IconInvestment size={14} /> Portfolio
        </span>
        <button className="btn btn-g btn-s" onClick={() => onNav("investments")}>View →</button>
      </div>
      <div className="card-b" style={{ padding: "12px 14px", flex: 1, overflowY: "auto" }}>
        {!holdings?.length
          ? <Empty
              variant="investment"
              msg="Belum ada holdings aktif."
              sub="Beli aset pertama untuk memulai portfolio."
            />
          : holdings.map((inv, i) => (
            <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--bdr)", minWidth: 0 }}>
              <div style={{ minWidth: 0, flex: 1, marginRight: 8 }}>
                <div className="tkr" style={{ fontSize: 13, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{inv.ticker}</div>
                <div style={{ fontSize: 11, color: "var(--tx3)", display:"flex", alignItems:"center", gap:4 }}>
                  {ASSET_ICON_JSX[inv.asset_type] ? ASSET_ICON_JSX[inv.asset_type]({ size: 11 }) : null}
                  {Number(inv.qty).toFixed(4).replace(/\.?0+$/, "")}
                </div>
              </div>
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                {inv.pl !== null && inv.pl !== undefined
                  ? <>
                      <div style={{ fontSize: 12, fontFamily: "var(--mono)", color: inv.pl >= 0 ? "var(--gr)" : "var(--rd)", fontWeight: 700 }}>
                        {inv.pl >= 0 ? "+" : ""}{inv.pl_pct?.toFixed(1)}%
                      </div>
                      <div style={{ fontSize: 11, color: "var(--tx2)" }}>{fmtS(inv.pl)}</div>
                    </>
                  : <div style={{ fontSize: 11, color: "var(--tx3)" }}>no price</div>
                }
              </div>
            </div>
          ))
        }
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", padding: "10px 14px 14px", borderTop: "1px solid var(--bdr2)", flexShrink: 0 }}>
        <span style={{ fontSize: 11, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: ".5px" }}>Unrealized P/L</span>
        <span style={{ fontSize: 13, fontWeight: 700, fontFamily: "var(--mono)", color: plTotal >= 0 ? "var(--gr)" : "var(--rd)" }}>{fmtS(plTotal)}</span>
      </div>
    </div>
  );
}

// ── Widget: Hero Visuals ────────────────────────────────────────────────────
const HeroVisual = () => {
  return (
    <div className="card" style={{ 
      height: 120, marginBottom: 16, overflow: "hidden", position: "relative",
      background: "var(--bg2)", borderRadius: 24, border: "1px solid var(--bdr)"
    }}>
       <div style={{ 
         position: "absolute", inset: 0, 
         background: "linear-gradient(135deg, var(--bg2) 0%, var(--bg) 100%)",
         display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 32px"
       }}>
          <div style={{ fontSize: 22, fontWeight: 900, color: "var(--tx)", letterSpacing: -0.5 }}>Strategic Wealth</div>
          <div style={{ fontSize: 12, color: "var(--tx3)", maxWidth: 360, marginTop: 4, lineHeight: 1.4 }}>
            Building long-term equity through quantitative analysis and disciplined asset allocation.
          </div>
       </div>
    </div>
  );
};

// ── Main Dashboard ─────────────────────────────────────────────────────────────
export default function Dashboard({ onNav }) {
  // 1. Data hooks
  const { data: meta, loading: metaLoading, error: metaError, reload: reloadMeta } = useDashboardMetadata();
  const { data: dash, loading: dashLoading, error: dashError, reload: reloadDash } = useDashboard();
  const { data: config } = useAppConfig();
  const { data: goals } = useGoals();
  const { data: healthScore } = useHealthScore();
  const { data: safeToSpend } = useSafeToSpend();

  // 2. Refresh handler
  const handleReload = () => {
    reloadMeta();
    reloadDash();
  };

  if (metaError || dashError) {
    return <ApiError error={metaError || dashError} onRetry={handleReload} />;
  }

  // Derived values from dash (if available)
  const income      = dash?.income    ?? { total_this: 0, total_prev: 0 };
  const expense     = dash?.expense   ?? { total_this: 0, total_prev: 0, by_category: {} };
  const investments = dash?.investments ?? { holdings: [], pl_total: 0 };
  const monthLabel  = dash?.month_label ?? meta?.month_label ?? "...";

  const incVal = income.total_this;
  const expVal = expense.total_this;
  const net    = incVal - expVal;
  const ratio  = incVal > 0 ? (expVal / incVal) * 100 : 0;
  const rc     = ratio <= 50 ? "var(--gr)" : ratio <= 80 ? "var(--yl)" : "var(--rd)";
  const topCat = Object.entries(expense.by_category).sort((a, b) => b[1] - a[1])[0];

  const monthlyFixed   = dash?.recurring?.monthly_fixed_cost ?? 0;
  const confirmedCount = dash?.recurring?.confirmed_count    ?? 0;

  return (
    <div>
      <h1 className="sr-only">Finance Dashboard — Track Income, Expenses &amp; Investments</h1>
      {/* ── Sticky Toolbar ── */}
      <div className="db-toolbar">
        <button className="db-action-btn db-refresh-mobile-hide" onClick={handleReload} disabled={dashLoading}>
          <IconRefresh size={14} style={{ animation: dashLoading ? "comp-spin 1s linear infinite" : "none" }} />
          {dashLoading ? "Refreshing..." : "Refresh Data"}
        </button>
      </div>

      <HeroVisual />

      {/* ── Metric hierarchy: one focal hero + compact secondary strip ── */}
      {metaLoading && !dash ? (
        <DashboardSkeleton />
      ) : (
        <>
          {/* Focal metric — the month's bottom line. */}
          <div style={{ marginBottom: "var(--sp-4)" }}>
            <StatCard
              variant="hero"
              label={<><IconWallet size={13} /> Net Cash Flow — {monthLabel}</>}
              value={fmtS(net)}
              accent={net >= 0 ? "var(--gr)" : "var(--rd)"}
              color={net >= 0 ? "g" : "r"}
              sub={net >= 0 ? "Surplus this month" : "Deficit this month"}
            />
          </div>

          {/* Secondary strip — supporting metrics, compact + lighter. */}
          <div className="sg-4">
            <StatCard
              variant="compact"
              label={<><IconIncome size={11} /> Income</>}
              value={fmt(income.total_this)}
              color="g"
              className="clickable"
              sub={pctChg(income.total_this, income.total_prev) !== null
                ? `${pctChg(income.total_this, income.total_prev) >= 0 ? "▲" : "▼"} ${Math.abs(pctChg(income.total_this, income.total_prev)).toFixed(1)}%`
                : "no prior data"}
              onClick={() => onNav("income")}
            />
            <StatCard
              variant="compact"
              label={<><IconExpense size={11} /> Expenses</>}
              value={fmt(expense.total_this)}
              color="r"
              className="clickable"
              sub={pctChg(expense.total_this, expense.total_prev) !== null
                ? `${pctChg(expense.total_this, expense.total_prev) >= 0 ? "▲" : "▼"} ${Math.abs(pctChg(expense.total_this, expense.total_prev)).toFixed(1)}%`
                : "no prior data"}
              onClick={() => onNav("expenses")}
            />
            <StatCard
              variant="compact"
              label={<><IconRepeat size={11} /> Fixed Cost</>}
              value={fmtS(monthlyFixed)}
              color="y"
              className="clickable"
              sub={`${confirmedCount} recurring`}
              onClick={() => onNav("expenses")}
            />
            {/* Health score only when computed — no filler placeholder. */}
            {healthScore ? (
              <StatCard
                variant="compact"
                label={<><IconHealth size={11} /> Health</>}
                value={`${healthScore.total_score}`}
                color={healthScore.total_score >= 80 ? "g" : healthScore.total_score >= 60 ? "y" : "r"}
                sub={`Grade ${healthScore.grade}`}
              />
            ) : safeToSpend ? (
              <StatCard
                variant="compact"
                label={<><IconWallet size={11} /> Safe To Spend</>}
                value={fmtS(safeToSpend.safe_to_spend ?? 0)}
                color="g"
                sub={`Bal ${fmtS(safeToSpend.current_balance ?? 0)}`}
              />
            ) : goals?.length ? (
              <StatCard
                variant="compact"
                label={<><IconTarget size={11} /> Goals</>}
                value={`${goals.length}`}
                color="n"
                sub="active"
              />
            ) : null}
          </div>
        </>
      )}

      {/* Widget boundaries with localized error handling */}
      <ErrorBoundary>
        <MacroMarketOverview />
      </ErrorBoundary>

      <ErrorBoundary>
        <MonthlyTrendChart />
      </ErrorBoundary>

      <ErrorBoundary>
        <NetWorthHistoryChart days={90} />
      </ErrorBoundary>
      
      <ErrorBoundary>
        <SavingRateChart />
      </ErrorBoundary>

      <ErrorBoundary>
        <CashflowSankey />
      </ErrorBoundary>

      <div className="g3-1">
        <div>
          {/* ── Spending ratio ── */}
          <div className="ratio-box">
            <div className="ratio-row">
              <span style={{display:"flex",alignItems:"center",gap:5}}><IconPieChart size={13} />Spending Ratio</span>
              <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: "var(--tx3)" }}>
                {fmt(expVal)} / {fmt(incVal)}
              </span>
            </div>
            <div className="ratio-val" style={{ color: rc }}>{ratio.toFixed(1)}%</div>
            <div className="ratio-track">
              <div className="ratio-fill" style={{ width: `${Math.min(ratio, 100)}%`, background: rc }} />
              <div className="ratio-marker" style={{ left: "50%", background: "var(--gr)" }} title="50% — healthy threshold" />
              <div className="ratio-marker" style={{ left: "80%", background: "var(--yl)" }} title="80% — warning threshold" />
            </div>
            <div style={{ display:"flex", justifyContent:"space-between", marginTop: 5, fontSize: 10, color: "var(--tx3)", fontFamily: "var(--mono)" }}>
              <span style={{ color: "var(--gr)" }}>50% good</span>
              <span style={{ color: "var(--yl)" }}>80% warning</span>
              <span style={{ color: "var(--rd)" }}>100% critical</span>
            </div>
          </div>

          {/* Category breakdown */}
          <ErrorBoundary>
            <div className="card">
              <div className="card-h">
                <span className="card-t">Expenses by Category</span>
                <button className="btn btn-g btn-s" onClick={() => onNav("expenses")}>View all →</button>
              </div>
              <div className="card-b" style={{ paddingBottom: 8 }}>
                <CategoryBreakdown byCategory={expense.by_category} loading={dashLoading && !dash} />
              </div>
            </div>
          </ErrorBoundary>
        </div>

        {/* Portfolio panel */}
        <ErrorBoundary>
          <PortfolioSidebar
            holdings={investments.holdings}
            plTotal={investments.pl_total}
            loading={dashLoading && !dash}
            onNav={onNav}
          />
        </ErrorBoundary>
      </div>

      {/* ── Insights ── */}
      <div className="g2">
        <div className="ins">
          <div className="ins-ico" style={{ color: ratio <= 50 ? "var(--gr)" : ratio <= 80 ? "var(--yl)" : "var(--rd)" }}>
            {ratio > 80 ? <IconWarning size={17} /> : <IconInsight size={17} />}
          </div>
          <div className="ins-txt">
            <strong>Spending is {ratio <= 50 ? "healthy" : ratio <= 80 ? "moderate" : "high"}.</strong>{" "}
            You've spent <strong>{ratio.toFixed(0)}%</strong> of income this month —{" "}
            {ratio <= 50
              ? "well within the healthy 50% threshold."
              : ratio <= 80
                ? "approaching the 80% warning threshold."
                : "consider reducing discretionary spending."}
            <br />
            <span className="ins-action" onClick={() => onNav("expenses")}>
              View Expenses <IconArrowRight size={11} />
            </span>
          </div>
        </div>
        <div className="ins">
          <div className="ins-ico"><IconInfo size={17} /></div>
          <div className="ins-txt">
            {topCat
              ? <><strong>Top expense: {topCat[0]}</strong> — accounts for{" "}
                  {expense.total_this > 0 ? (topCat[1] / expense.total_this * 100).toFixed(0) : 0}% ({fmt(topCat[1])}) of total spending.</>
              : <><strong>No expenses recorded</strong> yet this month. Start tracking your spending!</>
            }
            <br />
            <span className="ins-action" onClick={() => onNav(topCat ? "expenses" : "receipt")}>
              {topCat ? "Set Budget →" : "Add Expense →"} <IconArrowRight size={11} />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

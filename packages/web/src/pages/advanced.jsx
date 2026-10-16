// ─── finance/advanced.jsx ─────────────────────────────────────────────────────
// Section 7 — Advanced Features (GUI display layer ONLY)
//
// Architecture:
//   GUI = pure renderer. Zero business logic.
//   All logic lives in CLI: advanced_features/{domain,application,interface}
//   GUI reads from API endpoints that proxy CLI use-cases.
//   High Cohesion : each component renders one concept (goals / forecast / budget).
//   Low Coupling  : no direct DB access; all data via apiFetch().
//   DRY           : ProgressBar, SectionCard, _rp defined once.
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from "react";
import { fmt, fmtS, thisYear, thisMonth } from "../finance/constants.js";
import { apiFetch } from "../finance/useApi.js";
import {
  LifestyleInflationTrend,
  ExpensePredictionPanel,
  SavingProjectionPanel,
  PortfolioRiskPanel,
} from "../finance/AnalyticsPanel.jsx";
import {
  IconAdd, IconDelete, IconTarget, IconBarChart,
  IconWarning, IconAlert, IconSuccess, IconInfo,
  IconCalendar, IconDown, IconUp, IconClose,
} from "../icons.jsx";
import { Tabs } from "../components.jsx";


// ── Shared UI atoms ────────────────────────────────────────────────────────────
function ProgressBar({ value, max, color = "var(--ind)", height = 8 }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div style={{ background:"var(--bg4)", borderRadius:99, height, overflow:"hidden", width:"100%" }}>
      <div style={{ width:`${pct}%`, height:"100%", borderRadius:99, background:color, transition:"width .4s ease" }} />
    </div>
  );
}

function SectionCard({ title, icon: Icon, children }) {
  return (
    <div style={{ background:"var(--bg2)", border:"1px solid var(--bdr2)", borderRadius:"var(--rl)", padding:"20px 22px", marginBottom:20 }}>
      <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:16 }}>
        {Icon && <Icon size={18} color="var(--ind-b)" />}
        <span style={{ fontWeight:700, fontSize:15 }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

function StatPill({ label, value, color }) {
  return (
    <div style={{ background:"var(--bg3)", borderRadius:10, padding:"10px 14px", border:"1px solid var(--bdr)", flex:"1 1 clamp(90px,25vw,130px)", minWidth:"clamp(80px,22vw,110px)" }}>
      <div style={{ fontSize:10, color:"var(--tx3)", textTransform:"uppercase", letterSpacing:".7px", marginBottom:3 }}>{label}</div>
      <div style={{ fontSize:15, fontFamily:"var(--mono)", fontWeight:700, color, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{value}</div>
    </div>
  );
}

// ── Goal Tracker (Premium UI/UX) ────────────────────────────────────────────

const GOAL_PALETTES = [
  { bar: "#6366f1", glow: "rgba(99,102,241,0.14)",  badge: "#818cf8" },
  { bar: "#06b6d4", glow: "rgba(6,182,212,0.14)",   badge: "#67e8f9" },
  { bar: "#f59e0b", glow: "rgba(245,158,11,0.14)",  badge: "#fcd34d" },
  { bar: "#ec4899", glow: "rgba(236,72,153,0.14)",  badge: "#f9a8d4" },
  { bar: "#8b5cf6", glow: "rgba(139,92,246,0.14)",  badge: "#c4b5fd" },
  { bar: "#14b8a6", glow: "rgba(20,184,166,0.14)",  badge: "#5eead4" },
];

function GoalCard({ goal, onDeposit, onDelete, index = 0 }) {
  const [dep, setDep]           = useState("");
  const [depositing, setDepositing] = useState(false);

  const goalName   = goal.name || goal.title || `Goal #${goal.id}`;
  const targetDate = goal.target_date || goal.deadline;
  const targetAmt  = Number(goal.target_amount)  || 0;
  const currentAmt = Number(goal.current_amount) || 0;

  const pct    = targetAmt > 0 ? Math.min(100, (currentAmt / targetAmt) * 100) : 0;
  const rem    = Math.max(0, targetAmt - currentAmt);
  const isDone = pct >= 100;

  const palette = isDone
    ? { bar: "#10b981", glow: "rgba(16,185,129,0.13)", badge: "#34d399" }
    : GOAL_PALETTES[index % GOAL_PALETTES.length];

  let reqMonthly = null, monthsLeft = null, daysLeft = null, isUrgent = false;
  if (targetDate) {
    const diff = new Date(targetDate) - new Date();
    if (diff > 0) {
      daysLeft   = Math.ceil(diff / 86400000);
      monthsLeft = diff / (86400000 * 30.44);
      reqMonthly = monthsLeft > 0 ? Math.ceil(rem / monthsLeft) : rem;
      isUrgent   = daysLeft < 60 && !isDone;
    }
  }

  const quickPresets = [100_000, 500_000, 1_000_000, 5_000_000];

  const handleDeposit = async () => {
    if (+dep <= 0) return;
    setDepositing(true);
    await onDeposit(goal.id, +dep);
    setDep("");
    setDepositing(false);
  };

  return (
    <div style={{
      background: "var(--bg2)",
      borderRadius: 16,
      border: `1px solid ${isDone ? "rgba(16,185,129,0.25)" : "var(--bdr)"}`,
      marginBottom: 12,
      overflow: "hidden",
      boxShadow: isDone ? "0 0 0 1px rgba(16,185,129,0.08), 0 4px 20px rgba(16,185,129,0.06)" : "0 2px 6px rgba(0,0,0,0.05)",
    }}>

      {/* Top accent strip */}
      <div style={{ height: 3, background: "var(--bg4)", position: "relative" }}>
        <div style={{
          position: "absolute", inset: 0, width: `${pct}%`,
          background: palette.bar,
          transition: "width 0.6s cubic-bezier(0.4,0,0.2,1)",
          borderRadius: "0 3px 3px 0",
        }} />
      </div>

      <div style={{ padding: "16px 18px 14px" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 13 }}>
          <div style={{ flex: 1, minWidth: 0, paddingRight: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 7, flexWrap: "wrap", marginBottom: 4 }}>
              <span style={{ fontWeight: 800, fontSize: 15, color: "var(--tx)", letterSpacing: "-0.3px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {goalName}
              </span>
              <span style={{
                fontSize: 9, fontWeight: 700, letterSpacing: "0.5px", textTransform: "uppercase",
                padding: "2px 8px", borderRadius: 99,
                background: isDone ? "rgba(16,185,129,0.15)" : palette.glow,
                color: isDone ? "#10b981" : palette.badge,
                flexShrink: 0,
              }}>
                {isDone ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                    <IconSuccess size={11} color="#10b981" /> Funded
                  </span>
                ) : isUrgent ? (
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 3 }}>
                    <IconWarning size={11} color={palette.badge} /> Urgent
                  </span>
                ) : (
                  "Active"
                )}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--tx3)", display: "flex", flexWrap: "wrap", gap: "3px 10px" }}>
              <span>Target <b style={{ color: "var(--tx2)", fontFamily: "var(--mono)" }}>{fmt(targetAmt)}</b></span>
              {targetDate && daysLeft !== null && (
                <span style={{ color: isUrgent ? "#fcd34d" : "var(--tx3)", display: "inline-flex", alignItems: "center", gap: 3 }}>
                  {isUrgent ? <IconWarning size={11} color="#fcd34d" /> : <IconCalendar size={11} />}{daysLeft}d left
                </span>
              )}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 7, flexShrink: 0 }}>
            <div style={{
              background: palette.glow, borderRadius: 10,
              padding: "6px 10px", minWidth: 54, textAlign: "center",
            }}>
              <div style={{ fontFamily: "var(--mono)", fontWeight: 900, fontSize: 17, color: palette.bar, lineHeight: 1 }}>
                {pct.toFixed(0)}%
              </div>
              <div style={{ fontSize: 8, color: "var(--tx3)", marginTop: 2, letterSpacing: "0.4px", textTransform: "uppercase" }}>funded</div>
            </div>
            <button onClick={() => onDelete(goal.id)} title="Delete"
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--tx3)", padding: "4px 2px", opacity: 0.6 }}>
              <IconDelete size={14} />
            </button>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ marginBottom: 13 }}>
          <ProgressBar value={currentAmt} max={targetAmt} color={palette.bar} height={6} />
          <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4, fontSize: 10, color: "var(--tx3)", fontFamily: "var(--mono)" }}>
            <span style={{ color: "#10b981" }}>{fmt(currentAmt)}</span>
            <span>{fmt(targetAmt)}</span>
          </div>
        </div>

        {/* Stats */}
        <div style={{ display: "flex", gap: 7, flexWrap: "wrap", marginBottom: 13 }}>
          <div style={{ flex: "1 1 85px", background: "var(--bg3)", borderRadius: 8, padding: "7px 10px", border: "1px solid var(--bdr)" }}>
            <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 2 }}>Remaining</div>
            <div style={{ fontSize: 12, fontWeight: 700, color: rem > 0 ? "var(--tx)" : "#10b981", fontFamily: "var(--mono)" }}>{fmt(rem)}</div>
          </div>
          {reqMonthly !== null && (
            <div style={{ flex: "1 1 85px", background: "var(--bg3)", borderRadius: 8, padding: "7px 10px", border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 2 }}>Need/Mo</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: palette.bar, fontFamily: "var(--mono)" }}>{fmt(reqMonthly)}</div>
            </div>
          )}
          {daysLeft !== null && (
            <div style={{ flex: "1 1 85px", background: "var(--bg3)", borderRadius: 8, padding: "7px 10px", border: `1px solid ${isUrgent ? "rgba(252,211,77,0.2)" : "var(--bdr)"}` }}>
              <div style={{ fontSize: 9, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 2 }}>Deadline</div>
              <div style={{ fontSize: 12, fontWeight: 700, color: isUrgent ? "#fcd34d" : "var(--tx2)", fontFamily: "var(--mono)" }}>
                {monthsLeft >= 1 ? `${Math.ceil(monthsLeft)}mo` : `${daysLeft}d`}
              </div>
            </div>
          )}
        </div>

        {/* Deposit panel */}
        {!isDone && (
          <div style={{ borderTop: "1px solid var(--bdr)", paddingTop: 11 }}>
            <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 7 }}>
              {quickPresets.map((preset) => (
                <button key={preset} type="button" onClick={() => onDeposit(goal.id, preset)}
                  style={{
                    background: "var(--bg3)", border: "1px solid var(--bdr)",
                    borderRadius: 7, padding: "4px 9px",
                    fontSize: 10, fontFamily: "var(--mono)",
                    color: "var(--tx2)", cursor: "pointer", fontWeight: 600,
                  }}
                  onMouseEnter={e => { e.currentTarget.style.background = palette.glow; e.currentTarget.style.color = palette.badge; }}
                  onMouseLeave={e => { e.currentTarget.style.background = "var(--bg3)"; e.currentTarget.style.color = "var(--tx2)"; }}
                >
                  +{fmt(preset)}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 7 }}>
              <input
                value={dep}
                onChange={(e) => setDep(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleDeposit()}
                placeholder="Custom amount (Rp)…"
                type="number"
                style={{
                  flex: 1, background: "var(--bg3)",
                  border: "1px solid var(--bdr)", borderRadius: 8,
                  padding: "8px 12px", color: "var(--tx)",
                  fontSize: 13, fontFamily: "var(--mono)", outline: "none", minWidth: 0,
                }}
              />
              <button className="btn btn-p btn-s"
                disabled={!dep || +dep <= 0 || depositing}
                onClick={handleDeposit}
                style={{ fontSize: 12, padding: "8px 14px", fontWeight: 700, borderRadius: 8, flexShrink: 0 }}
              >
                {depositing ? "…" : "+ Deposit"}
              </button>
            </div>
          </div>
        )}

        {isDone && (
          <div style={{
            borderTop: "1px solid rgba(16,185,129,0.2)", paddingTop: 10,
            fontSize: 12, color: "#10b981", fontWeight: 600,
            textAlign: "center", letterSpacing: "0.2px",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 6,
          }}>
            <IconSuccess size={14} color="#10b981" /> Goal fully funded — great work!
          </div>
        )}
      </div>
    </div>
  );
}

export function GoalTracker() {
  const [goals, setGoals]     = useState([]);
  const [adding, setAdding]   = useState(false);
  const [loading, setLoading] = useState(true);
  const [form, setForm]       = useState({ name: "", target_amount: "", target_date: "" });

  const load = useCallback(async () => {
    try {
      const d = await apiFetch("/goals");
      setGoals(d.goals || []);
    } catch {} finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async () => {
    if (!form.name || !form.target_amount) return;
    try {
      await apiFetch("/goals", {
        method: "POST",
        body: JSON.stringify({
          name: form.name, title: form.name,
          target_amount: +form.target_amount,
          target_date: form.target_date || null,
          deadline: form.target_date || null,
        }),
      });
      setForm({ name: "", target_amount: "", target_date: "" });
      setAdding(false);
      load();
    } catch {}
  };

  const handleDeposit = async (id, amount) => {
    const g = goals.find((g) => g.id === id);
    if (!g) return;
    const current = Number(g.current_amount) || 0;
    try {
      await apiFetch(`/goals/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ current_amount: current + amount }),
      });
      load();
    } catch {}
  };

  const handleDelete = async (id) => {
    try { await apiFetch(`/goals/${id}`, { method: "DELETE" }); load(); } catch {}
  };

  const totalTarget = goals.reduce((a, g) => a + (Number(g.target_amount)  || 0), 0);
  const totalSaved  = goals.reduce((a, g) => a + (Number(g.current_amount) || 0), 0);
  const overallPct  = totalTarget > 0 ? Math.min(100, (totalSaved / totalTarget) * 100) : 0;
  const doneCount   = goals.filter(g => Number(g.current_amount) >= Number(g.target_amount)).length;

  return (
    <SectionCard title="Goal-Based Savings" icon={IconTarget}>

      {/* Portfolio Hero Banner */}
      {goals.length > 0 && (
        <div style={{
          background: "linear-gradient(135deg, var(--bg3) 0%, var(--bg2) 100%)",
          borderRadius: 14, padding: "18px 20px", marginBottom: 18,
          border: "1px solid var(--bdr)", position: "relative", overflow: "hidden",
        }}>
          <div style={{ position: "absolute", inset: 0, opacity: 0.04, backgroundImage: "radial-gradient(circle at 80% 20%, #6366f1 0%, transparent 60%)", pointerEvents: "none" }} />

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12, marginBottom: 14, position: "relative" }}>
            <div>
              <div style={{ fontSize: 10, color: "var(--tx3)", textTransform: "uppercase", letterSpacing: "0.8px", marginBottom: 5 }}>
                Total Portfolio · {goals.length} Goals
              </div>
              <div style={{ fontFamily: "var(--mono)", fontWeight: 900, fontSize: 22, color: "var(--tx)", letterSpacing: "-0.5px", lineHeight: 1.1 }}>
                {fmt(totalSaved)}
              </div>
              <div style={{ fontSize: 11, color: "var(--tx3)", marginTop: 4 }}>
                of <span style={{ color: "var(--tx2)", fontFamily: "var(--mono)", fontWeight: 600 }}>{fmt(totalTarget)}</span> target
              </div>
            </div>
            <div style={{
              background: overallPct >= 100 ? "rgba(16,185,129,0.12)" : "rgba(99,102,241,0.12)",
              borderRadius: 12, padding: "10px 16px", textAlign: "center",
              border: `1px solid ${overallPct >= 100 ? "rgba(16,185,129,0.2)" : "rgba(99,102,241,0.2)"}`,
            }}>
              <div style={{ fontFamily: "var(--mono)", fontWeight: 900, fontSize: 26, color: overallPct >= 100 ? "#10b981" : "#818cf8", lineHeight: 1 }}>
                {overallPct.toFixed(1)}%
              </div>
              <div style={{ fontSize: 9, color: "var(--tx3)", marginTop: 3, letterSpacing: "0.5px", textTransform: "uppercase" }}>
                {doneCount}/{goals.length} done
              </div>
            </div>
          </div>

          <ProgressBar value={totalSaved} max={totalTarget} color={overallPct >= 100 ? "#10b981" : "#6366f1"} height={6} />

          {/* Per-goal chips */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 12 }}>
            {goals.map((g, i) => {
              const p   = Math.min(100, Number(g.target_amount) > 0 ? (Number(g.current_amount) / Number(g.target_amount)) * 100 : 0);
              const pal = p >= 100 ? { bar: "#10b981", badge: "#34d399" } : GOAL_PALETTES[i % GOAL_PALETTES.length];
              const name = g.name || g.title || `Goal #${g.id}`;
              return (
                <div key={g.id} style={{
                  display: "flex", alignItems: "center", gap: 5,
                  background: "var(--bg4)", borderRadius: 7, padding: "4px 9px",
                  border: "1px solid var(--bdr)", fontSize: 10, color: "var(--tx2)", fontWeight: 600,
                }}>
                  <div style={{ width: 6, height: 6, borderRadius: 2, background: pal.bar, flexShrink: 0 }} />
                  <span style={{ maxWidth: 90, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{name}</span>
                  <span style={{ color: pal.badge, fontFamily: "var(--mono)", fontWeight: 700 }}>{p.toFixed(0)}%</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty state */}
      {goals.length === 0 && !adding && !loading && (
        <div style={{
          textAlign: "center", padding: "32px 20px",
          background: "var(--bg3)", borderRadius: 14,
          border: "1px dashed var(--bdr)", marginBottom: 14,
        }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 10 }}>
            <IconTarget size={32} color="var(--ind-b)" />
          </div>
          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--tx)", marginBottom: 6 }}>No savings goals yet</div>
          <div style={{ fontSize: 12, color: "var(--tx3)", maxWidth: 260, margin: "0 auto" }}>
            Create your first goal to start tracking progress toward what matters most.
          </div>
        </div>
      )}

      {loading && !goals.length && (
        <div style={{ textAlign: "center", padding: 20, color: "var(--tx3)", fontSize: 13 }}>Loading goals…</div>
      )}

      {/* Goal cards */}
      {goals.map((g, i) => (
        <GoalCard key={g.id} goal={g} index={i} onDeposit={handleDeposit} onDelete={handleDelete} />
      ))}

      {/* Add form */}
      {adding ? (
        <div style={{
          background: "var(--bg3)", borderRadius: 14,
          padding: "18px 18px 16px",
          border: "1px solid var(--bdr)", marginTop: 6,
        }}>
          <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 14, color: "var(--tx)", display: "flex", alignItems: "center", gap: 6 }}>
            <IconTarget size={14} color="var(--ind-b)" /> New Savings Goal
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 10, marginBottom: 14 }}>
            {[
              { k: "name",          label: "Goal Name",           type: "text",   ph: "e.g. Japan Trip 2026" },
              { k: "target_amount", label: "Target Amount (Rp)",  type: "number", ph: "517750800" },
              { k: "target_date",   label: "Deadline (optional)", type: "date",   ph: "" },
            ].map((f) => (
              <div key={f.k}>
                <div style={{ fontSize: 10, color: "var(--tx3)", marginBottom: 5, textTransform: "uppercase", letterSpacing: "0.5px" }}>{f.label}</div>
                <input
                  type={f.type} placeholder={f.ph} value={form[f.k]}
                  onChange={(e) => setForm((p) => ({ ...p, [f.k]: e.target.value }))}
                  style={{
                    width: "100%", boxSizing: "border-box",
                    background: "var(--bg4)", border: "1px solid var(--bdr)",
                    borderRadius: 8, padding: "9px 12px",
                    color: "var(--tx)", fontSize: 13, outline: "none",
                  }}
                />
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-p btn-s"
              style={{ fontSize: 12, padding: "8px 18px", fontWeight: 700 }}
              onClick={handleAdd} disabled={!form.name || !form.target_amount}>
              <IconAdd size={13} /> Save Goal
            </button>
            <button className="btn btn-g btn-s" style={{ fontSize: 12, padding: "8px 14px" }} onClick={() => setAdding(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button className="btn btn-g btn-s"
          style={{ fontSize: 12, marginTop: 4, display: "flex", alignItems: "center", gap: 5 }}
          onClick={() => setAdding(true)}>
          <IconAdd size={13} /> New Goal
        </button>
      )}
    </SectionCard>
  );
}

// ── Cashflow Forecast ──────────────────────────────────────────────────────────

export function CashflowForecast() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/forecast?days=30").then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <SectionCard title="Cashflow Forecast" icon={IconBarChart}><div style={{color:"var(--tx3)",fontSize:13}}>Loading…</div></SectionCard>;
  if (!data) return null;

  const { forecast = [], warning, summary = {} } = data;
  const minBal = Math.min(...forecast.map(f => f.running_balance));
  const maxBal = Math.max(...forecast.map(f => f.running_balance));
  const range  = maxBal - minBal || 1;
  const H = 80;

  return (
    <SectionCard title="30-Day Cashflow Forecast" icon={IconBarChart}>
      {warning && (
        <div style={{ background:"rgba(248,113,113,.12)", border:"1px solid rgba(248,113,113,.3)", borderRadius:10, padding:"10px 14px", marginBottom:14, display:"flex", alignItems:"center", gap:8, fontSize:13 }}>
          <IconAlert size={16} color="var(--rd)" />
          <span style={{ color:"var(--rd)", fontWeight:600 }}>Negative balance predicted — review your spending.</span>
        </div>
      )}
      <div className="adv-stat-pills" style={{ display:"flex", gap:12, flexWrap:"wrap", marginBottom:18 }}>
        <StatPill label="Avg Daily Net"    value={fmtS(summary.avg_daily_net)}       color={summary.avg_daily_net >= 0 ? "var(--gr)" : "var(--rd)"} />
        <StatPill label="Projected 30d"    value={fmtS(summary.projected_month_net)} color={summary.projected_month_net >= 0 ? "var(--gr)" : "var(--rd)"} />
        <StatPill label="Avg Daily Income" value={fmt(summary.avg_daily_income)}     color="var(--cy)" />
        <StatPill label="Avg Daily Spend"  value={fmt(summary.avg_daily_expense)}    color="var(--yl)" />
      </div>
      <div style={{ position:"relative", marginBottom:8 }}>
        <svg width="100%" viewBox={`0 0 300 ${H}`} preserveAspectRatio="none" style={{ display:"block", width:"100%", height: H }}>
          <rect width="300" height={H} fill="transparent" />
          {minBal < 0 && <line x1="0" y1={H - ((0 - minBal)/range)*H} x2="300" y2={H - ((0 - minBal)/range)*H} stroke="rgba(248,113,113,.4)" strokeDasharray="4,3" strokeWidth={1} />}
          <polyline fill="none" stroke="var(--ind-b)" strokeWidth={2}
            points={forecast.map((f, i) => `${(i/(forecast.length-1))*300},${Math.max(2, Math.min(H - 2, H - ((f.running_balance-minBal)/range)*H))}`).join(" ")} />
        </svg>
        <div style={{ display:"flex", justifyContent:"space-between", fontSize:10, color:"var(--tx3)", marginTop:4 }}>
          {[0,7,14,21,29].map(i => <span key={i}>{forecast[i]?.date?.slice(5)||""}</span>)}
        </div>
      </div>
      {warning && (() => { const n = forecast.find(f => f.running_balance < 0); return n ? (
        <div style={{ fontSize:12, color:"var(--tx2)", marginTop:4, display:"flex", alignItems:"center", gap:5, flexWrap:"nowrap", whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>
          <IconWarning size={13} color="var(--yl)" style={{ flexShrink:0 }} />
          <span style={{ overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap" }}>
            First negative: <b style={{ color:"var(--rd)" }}>{n.date}</b> ({fmt(Math.abs(n.running_balance))} shortfall)
          </span>
        </div>
      ) : null; })()}
    </SectionCard>
  );
}

// ── Budget Planner ─────────────────────────────────────────────────────────────

export function BudgetPlanner({ year = thisYear(), month = thisMonth() }) {
  const [data, setData] = useState(null);
  const [setting, setSetting] = useState(null);
  const [inputVal, setInputVal] = useState("");

  const load = useCallback(async () => {
    try { const d = await apiFetch(`/budget/${year}/${month}`); setData(d); } catch {}
  }, [year, month]);

  useEffect(() => { load(); }, [load]);

  const cats = data?.categories || [];

  const handleSet = async (cat) => {
    const v = parseFloat(inputVal);
    if (!v || v <= 0) return;
    try { await apiFetch(`/budget/${year}/${month}`, { method:"POST", body: JSON.stringify({ category:cat, limit:v }) }); setSetting(null); setInputVal(""); load(); } catch {}
  };

  const handleDel = async (cat) => {
    try { await apiFetch(`/budget/${year}/${month}/${cat}`, { method:"DELETE" }); load(); } catch {}
  };

  return (
    <SectionCard title={`Budget Planner — ${year}/${String(month).padStart(2,"0")}`} icon={IconCalendar}>
      {cats.filter(c => c.recommendation).map(c => (
        <div key={c.category} style={{ background:"rgba(251,191,36,.08)", border:"1px solid rgba(251,191,36,.25)", borderRadius:10, padding:"8px 12px", marginBottom:8, display:"flex", alignItems:"center", gap:8, fontSize:12 }}>
          <IconInfo size={14} color="var(--yl)" />
          <span style={{ color:"var(--yl)" }}>{c.recommendation}</span>
        </div>
      ))}
      {cats.filter(c => c.over_limit).map(c => (
        <div key={c.category} style={{ background:"rgba(248,113,113,.1)", border:"1px solid rgba(248,113,113,.3)", borderRadius:10, padding:"8px 12px", marginBottom:8, display:"flex", alignItems:"center", gap:8, fontSize:12 }}>
          <IconAlert size={14} color="var(--rd)" />
          <span style={{ color:"var(--rd)" }}>Over budget: <b>{c.category}</b> — spent {fmt(c.current)}, limit {fmt(c.limit)}</span>
        </div>
      ))}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(min(270px,100%),1fr))", gap:10 }}>
        {cats.map(c => {
          const barCol = c.over_limit ? "var(--rd)" : c.near_limit ? "var(--yl)" : "var(--ind)";
          const isEditing = setting?.category === c.category;
          const pctUsed = c.limit ? Math.min(100, (c.current / c.limit) * 100) : 0;
          return (
            <div key={c.category} style={{ background:"var(--bg3)", borderRadius:12, border:`1px solid ${c.over_limit?"rgba(248,113,113,.4)":c.near_limit?"rgba(251,191,36,.3)":"var(--bdr)"}`, padding:"12px 14px" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:6 }}>
                <span style={{ fontWeight:600, fontSize:13, textTransform:"capitalize" }}>{c.category}</span>
                <div style={{ display:"flex", gap:5, alignItems:"center" }}>
                  {c.near_limit && !c.over_limit && <IconWarning size={13} color="var(--yl)" />}
                  {c.over_limit && <IconAlert size={13} color="var(--rd)" />}
                  {c.pct_change !== null && (
                    <span style={{ fontSize:10, fontFamily:"var(--mono)", color:c.pct_change>0?"var(--rd)":"var(--gr)", display:"flex", alignItems:"center", gap:2 }}>
                      {c.pct_change > 0 ? <IconUp size={10}/> : <IconDown size={10}/>}{Math.abs(c.pct_change).toFixed(0)}%
                    </span>
                  )}
                </div>
              </div>
              <div style={{ fontSize:11, color:"var(--tx2)", marginBottom:7 }}>
                <span style={{ color:"var(--tx)", fontFamily:"var(--mono)", fontSize:12 }}>{fmt(c.current)}</span>
                {c.limit && <span> / {fmt(c.limit)}</span>}
                {c.suggestion && !c.limit && <span style={{ marginLeft:6, color:"var(--tx3)" }}>Suggested: {fmt(c.suggestion)}</span>}
              </div>
              {c.limit && <ProgressBar value={c.current} max={c.limit} color={barCol} height={5} />}
              {isEditing ? (
                <div className="budget-edit-row">
                  <input autoFocus type="number" value={inputVal} onChange={e => setInputVal(e.target.value)}
                    placeholder={c.suggestion ? `Suggested: ${c.suggestion}` : "Limit"}
                    style={{ background:"var(--bg4)", border:"1px solid var(--bdr)", borderRadius:7, padding:"9px 10px", color:"var(--tx)", fontSize:16, minHeight:44 }} />
                  <button className="btn btn-p" style={{ fontSize:11, padding:"4px 10px" }} onClick={() => handleSet(c.category)}>Set</button>
                  <button className="btn btn-g" style={{ fontSize:11, padding:"4px 10px" }} onClick={() => { setSetting(null); setInputVal(""); }}><IconClose size={12} /></button>
                </div>
              ) : (
                <div style={{ display:"flex", gap:6, marginTop:9 }}>
                  <button className="btn btn-g" style={{ fontSize:11, padding:"4px 10px", flex:1 }}
                    onClick={() => { setSetting({ category:c.category }); setInputVal(c.limit ? String(c.limit) : c.suggestion ? String(c.suggestion) : ""); }}>
                    {c.limit ? "Edit Limit" : "Set Limit"}
                  </button>
                  {c.limit && <button className="btn btn-g" style={{ fontSize:11, padding:"4px 8px" }} onClick={() => handleDel(c.category)}><IconDelete size={12}/></button>}
                </div>
              )}
            </div>
          );
        })}
      </div>
      {cats.length === 0 && <div style={{ color:"var(--tx3)", fontSize:13 }}>No expense data for this month.</div>}
    </SectionCard>
  );
}

export default function AdvancedFeatures({ year, month }) {
  const [tab, setTab] = useState("goals");
  return (
    <div>
      <h1 className="sr-only">Advanced Features — Goal Tracking, Forecasting &amp; Budget Planning</h1>
      <div className="adv-header" style={{ marginBottom: 16 }}>
        <div style={{ fontSize: 18, fontWeight: 800, letterSpacing: "-.4px", marginBottom: 3 }}>Advanced Features</div>
        <div style={{ fontSize: 12, color: "var(--tx2)" }}>Goal tracking · 30-day cashflow forecast · Budget planning · Predictive analytics</div>
      </div>
      <Tabs
        tabs={[
          { key: "goals",     label: "Goals",       icon: <IconTarget    size={13} /> },
          { key: "forecast",  label: "Forecast",    icon: <IconBarChart  size={13} /> },
          { key: "budget",    label: "Budget",      icon: <IconCalendar  size={13} /> },
        ]}
        active={tab}
        onChange={setTab}
      />
      <div style={{ marginTop: 16 }}>
        {tab === "goals" && <GoalTracker />}
        {tab === "forecast" && <CashflowForecast />}
        {tab === "budget" && <BudgetPlanner year={year} month={month} />}
      </div>

      {/* Phase 2.3 — Lifestyle Inflation Trend */}
      <LifestyleInflationTrend />

      {/* Phase 3 — Predictive Analytics */}
      <div style={{ marginTop: 4, marginBottom: 8 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: "var(--tx2)", marginBottom: 4, letterSpacing: "-.2px" }}>
          Predictive Analytics
        </div>
        <div style={{ fontSize: 11, color: "var(--tx3)" }}>AI-assisted projections based on your transaction history</div>
      </div>
      <ExpensePredictionPanel />
      <SavingProjectionPanel />
      <PortfolioRiskPanel />
    </div>
  );
}

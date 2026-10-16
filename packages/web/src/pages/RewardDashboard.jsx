// ─── RewardDashboard.jsx ────────────────────────────────────────────────────────
// Main page — "Reward". Composes sub-sections, owns the useReward hook.
// Design Pattern: Composite + Facade. Zero business logic — all in rewardEngine.js
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useRef } from "react";
import "../rewards/rewards.css";
import { useReward } from "../rewards/useReward.js";
import RewardShop from "../rewards/RewardShop.jsx";
import SelfRewards from "../rewards/SelfRewards.jsx";
import { RANKS, REWARD_RULES, daysRemainingInSeason, currentSeason } from "../rewards/rewardEngine.js";
import { saveState } from "../rewards/rewardStore.js";
import { usePersistedTab } from "../finance/useApi.js";
import {
  IconStreak, IconMultiplier, IconCoin, IconTrophy, IconTarget, IconVexBolt,
  IconLeaf, IconUp, IconDown, IconWarning, IconPenalty, IconMilestone,
  IconSeason, IconMedal, IconAward, IconStar, IconCalStat, IconRepeat,
  IconRefresh, IconNoSpend, IconSparkles, IconSave, IconSword
, IconCheck, IconClose } from "../icons.jsx";

// ── Rank config (color in RANKS array directly) ───────────────────────────────
const rankColor = (rankId) => RANKS.find(r => r.id === rankId)?.color ?? "#fff";

// ── Earn rules — DRY, built from REWARD_RULES constants ─────────────────────────
const EARN_RULES = [
  { Icon: IconCoin,      title: "Save Rp100K",           val: `+${REWARD_RULES.SAVE_PER_100K}`,       pos: true  },
  { Icon: IconMilestone, title: "Milestone 500K",         val: `+${REWARD_RULES.MILESTONE_BONUS}`,     pos: true  },
  { Icon: IconStar,      title: "First Save of Day",      val: `+${REWARD_RULES.FIRST_SAVE_DAY}`,      pos: true  },
  { Icon: IconStreak,    title: "3-Day Streak",           val: `+${REWARD_RULES.STREAK_3D}`,           pos: true  },
  { Icon: IconVexBolt,   title: "7-Day Streak",           val: `+${REWARD_RULES.STREAK_7D}`,           pos: true  },
  { Icon: IconTrophy,    title: "30-Day Streak",          val: `+${REWARD_RULES.STREAK_30D}`,          pos: true  },
  { Icon: IconTarget,    title: "Weekly Goal Hit",        val: `+${REWARD_RULES.WEEKLY_GOAL}`,         pos: true  },
  { Icon: IconAward,     title: "Overachieve 150%",       val: `+${REWARD_RULES.WEEKLY_OVERACHIEVE}`,  pos: true  },
  { Icon: IconLeaf,      title: "Zero Non-Essential Day", val: `+${REWARD_RULES.NO_NONESSENTIAL_DAY}`, pos: true  },
  { Icon: IconUp,        title: "Saving Up 20%",          val: `+${REWARD_RULES.SAVING_UP_20PCT_MO}`,  pos: true  },
  { Icon: IconPenalty,   title: "Overspend 110–120%",     val: `${REWARD_RULES.PENALTY_SPEND_110_120}`,pos: false },
  { Icon: IconPenalty,   title: "Overspend 120–140%",     val: `${REWARD_RULES.PENALTY_SPEND_120_140}`,pos: false },
  { Icon: IconDown,      title: "Overspend 140%+",        val: `${REWARD_RULES.PENALTY_SPEND_140PLUS}`,pos: false },
  { Icon: IconCalStat,   title: "7 Days Without Saving",  val: `${REWARD_RULES.PENALTY_NO_SAVE_7D}`,   pos: false },
  { Icon: IconWarning,   title: "Weekly Goal Miss",       val: `${REWARD_RULES.PENALTY_WEEKLY_MISS}`,  pos: false },
  { Icon: IconRepeat,    title: "2x Consecutive Miss",    val: `${REWARD_RULES.PENALTY_WEEKLY_2X}`,    pos: false },
  { Icon: IconNoSpend,   title: "Spending Up 30%",        val: `${REWARD_RULES.PENALTY_SPEND_UP30}`,   pos: false },
];

// ── Loading skeleton ──────────────────────────────────────────────────────────
function GpSkeleton() {
  return (
    <div className="gp-root">
      <div style={{ padding: "40px 28px", display: "flex", flexDirection: "column", gap: 14 }}>
        {[180, 80, 120, 200].map((h, i) => (
          <div key={i} style={{ height: h, borderRadius: 16, background: "linear-gradient(90deg, var(--gp-bg2) 25%, var(--gp-bg3) 50%, var(--gp-bg2) 75%)", backgroundSize: "200% 100%", animation: "gp-shimmer 1.4s infinite linear" }} />
        ))}
      </div>
    </div>
  );
}

// ── Rank pills ────────────────────────────────────────────────────────────────
function RankPills({ currentRankId }) {
  return (
    <div className="gp-ranks-row">
      {RANKS.map(rank => {
        const isActive = rank.id === currentRankId;
        const color = rank.color;
        return (
          <div key={rank.id} className={"gp-rank-pill" + (isActive ? " active" : "")}
            style={{ color: isActive ? color : "var(--gp-tx3)", borderColor: isActive ? color : "var(--gp-border)", background: isActive ? color + "14" : "transparent", boxShadow: isActive ? "0 0 14px " + color + "30" : "none" }}>
            <IconMedal size={12} />
            <span>{rank.label}</span>
            <span className="gp-rank-pill-min">{rank.min >= 1000 ? (rank.min / 1000) + "K" : rank.min}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Hero section ──────────────────────────────────────────────────────────────
function Hero({ state, derived, snap, onRefresh }) {
  const rank = derived.rank;
  const color = rank.color;
  return (
    <div className="gp-hero">
      <div className="gp-hero-top">
        <div>
          <div className="gp-hero-eyebrow">
            <IconSword size={10} />
            <span>Reward</span>
          </div>
          <div className="gp-hero-title">Discipline is<br />your currency.</div>
          <div className="gp-hero-sub">Not paid with money — paid with the right financial behavior.</div>
        </div>
        <button className="gp-sync-btn" onClick={onRefresh}>
          <IconRefresh size={13} />
          <span>Sync</span>
        </button>
      </div>

      <div className="gp-reward-display">
        <div>
          <div className="gp-reward-num">{state.reward.toLocaleString("id-ID")}</div>
          <div className="gp-reward-label">
            <IconCoin size={14} />
            <span>REWARD</span>
          </div>
          <div className="gp-reward-lifetime">Lifetime: {state.lifetimeReward.toLocaleString("id-ID")} · Season: {state.seasonReward.toLocaleString("id-ID")}</div>
          {derived.multiplier > 1 && (
            <div className="gp-mult-badge">
              <IconMultiplier size={11} />
              {derived.multiplier}× multiplier active
            </div>
          )}
        </div>

        <div className="gp-rank-card" style={{ "--gp-rank-color": color }}>
          <div className="gp-rank-icon-wrap">
            <IconTrophy size={26} color={color} />
          </div>
          <div style={{ flex: 1 }}>
            <div className="gp-rank-name" style={{ color }}>{rank.label}</div>
            <div className="gp-rank-sub">
              {derived.nextRank ? (derived.rankPct * 100).toFixed(0) + "% → " + derived.nextRank.label : "MAX RANK"}
            </div>
            <div className="gp-rank-prog-wrap">
              <div className="gp-rank-prog-fill" style={{ width: (derived.rankPct * 100) + "%" }} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Stats row ─────────────────────────────────────────────────────────────────
function StatsRow({ state, derived, snap }) {
  const fmt = n => n >= 1_000_000 ? (n / 1_000_000).toFixed(1) + "M" : n >= 1000 ? (n / 1000).toFixed(0) + "K" : String(n);
  return (
    <div className="gp-stats">
      <div className="gp-stat fire">
        <div className="gp-stat-lbl"><IconStreak size={11} /><span>Streak</span></div>
        <div className="gp-stat-val">{state.streakDays}</div>
        <div className="gp-stat-sub">days consecutive</div>
      </div>
      <div className="gp-stat gold">
        <div className="gp-stat-lbl"><IconMultiplier size={11} /><span>Multiplier</span></div>
        <div className="gp-stat-val">{state.multiplier}×</div>
        <div className="gp-stat-sub">{state.multiplier >= 1.5 ? "max" : state.multiplier >= 1.2 ? "active" : "base"}</div>
      </div>
      <div className="gp-stat dim">
        <div className="gp-stat-lbl"><IconSeason size={11} /><span>Season Reward</span></div>
        <div className="gp-stat-val">{state.seasonReward.toLocaleString("id-ID")}</div>
        <div className="gp-stat-sub">{derived.daysLeft}d remaining</div>
      </div>
      <div className="gp-stat green">
        <div className="gp-stat-lbl"><IconSave size={11} /><span>Savings This Month</span></div>
        <div className="gp-stat-val">Rp{snap ? fmt(snap.savingsThis) : "—"}</div>
        <div className="gp-stat-sub">
          {snap && snap.savingGrowthPct !== 0
            ? (snap.savingGrowthPct >= 0 ? "↑" : "↓") + " " + Math.abs(snap.savingGrowthPct * 100).toFixed(0) + "% vs last"
            : "vs last month"}
        </div>
      </div>
    </div>
  );
}

// ── Activity log ──────────────────────────────────────────────────────────────
const LOG_ICON = {
  earn:      <IconCoin size={12} color="var(--gp-fire)" />,
  penalty:   <IconPenalty size={12} color="#6b7280" />,
  streak:    <IconStreak size={12} color="var(--gp-gold)" />,
  redeem:    <IconAward size={12} color="#a78bfa" />,
  season:    <IconSeason size={12} color="var(--gp-diamond)" />,
  milestone: <IconSparkles size={12} color="var(--gp-gold)" />,
  goal:      <IconTarget size={12} color="var(--gp-fire2)" />,
};

function ActivityLog({ log }) {
  if (!log?.length) {
    return (
      <div className="gp-empty">
        <IconCalStat size={32} color="var(--gp-tx3)" />
        <div className="gp-empty-txt">No activity yet.<br />Start saving to earn your first Reward!</div>
      </div>
    );
  }
  return (
    <div className="gp-log" role="log" aria-live="polite" aria-label="Alpha Log Cockpit activity">
      {log.map((entry, i) => (
        <div key={i} className="gp-log-item">
          <div className="gp-log-ico">{LOG_ICON[entry.type] ?? LOG_ICON.earn}</div>
          <div className="gp-log-label">{entry.label}</div>
          <div className={"gp-log-delta " + (entry.delta >= 0 ? "pos" : "neg")}>
            {entry.delta >= 0 ? "+" : ""}{entry.delta}
          </div>
          {entry.ts && (
            <time className="gp-log-ts" dateTime={entry.ts} title={new Date(entry.ts).toLocaleString("id-ID", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Jakarta" })}>
              {new Date(entry.ts).toLocaleDateString("id-ID", { day: "2-digit", month: "short", timeZone: "Asia/Jakarta" })}
            </time>
          )}
        </div>
      ))}
    </div>
  );
}

// ── Season & Rank panel ────────────────────────────────────────────────────────
function SeasonPanel({ state, derived }) {
  const pct = ((30 - derived.daysLeft) / 30 * 100).toFixed(0);
  return (
    <div>
      <div className="gp-season-card">
        <div className="gp-season-num">
          <IconSeason size={11} />
          <span>Season {derived.season + 1} · Active Now</span>
        </div>
        <div className="gp-season-title">The Discipline Arc</div>
        <div className="gp-season-desc">
          Season Reward resets every 30 days. Rank never resets — lifetime Reward keeps growing.
          Use this season to unlock exclusive rewards before rotation.
        </div>
        <div className="gp-season-meta">
          <span>Day {30 - derived.daysLeft} / 30</span>
          <span>{derived.daysLeft} days left</span>
        </div>
        <div className="gp-season-bar-wrap">
          <div className="gp-season-bar-fill" style={{ width: pct + "%" }} />
        </div>
      </div>

      <div className="gp-section-hd" style={{ marginBottom: 12 }}>Status Rank</div>
      <RankPills currentRankId={derived.rank.id} />

      <div style={{ marginTop: 20 }}>
        <div className="gp-section-hd" style={{ marginBottom: 12 }}>Rank Milestones</div>
        <div className="gp-rank-list">
          {RANKS.map(rank => {
            const reached = state.lifetimeReward >= rank.min;
            const isCurrent = derived.rank.id === rank.id;
            return (
              <div key={rank.id} className="gp-rank-row" style={{ background: isCurrent ? rank.color + "0d" : "var(--gp-bg2)", border: "1px solid " + (isCurrent ? rank.color + "30" : "var(--gp-border)") }}>
                <IconTrophy size={18} color={reached ? rank.color : "var(--gp-tx3)"} />
                <div style={{ flex: 1 }}>
                  <div className="gp-rank-row-name" style={{ color: reached ? rank.color : "var(--gp-tx3)" }}>{rank.label}</div>
                  <div className="gp-rank-row-min">{rank.min.toLocaleString("id-ID")} Lifetime Reward</div>
                </div>
                {reached && <div className="gp-rank-reached" style={{ color: rank.color }}><IconSparkles size={12} /> REACHED</div>}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Earn panel ────────────────────────────────────────────────────────────────
function EarnPanel({ state, setWeeklyGoal }) {
  const [goalInput, setGoalInput] = useState(state.weeklyGoal);
  const save = () => { const v = parseInt(goalInput, 10); if (!isNaN(v) && v > 0) setWeeklyGoal(v); };

  return (
    <div>
      <div className="gp-section-hd">Weekly Target</div>
      <div className="gp-goal-row">
        <div className="gp-goal-lbl"><IconTarget size={14} /><span>Weekly saving goal (Rp)</span></div>
        <input type="number" className="gp-goal-input" value={goalInput}
          onChange={e => setGoalInput(e.target.value)}
          onBlur={save} onKeyDown={e => e.key === "Enter" && save()}
          min={1} step={100000} />
      </div>

      <div className="gp-section-hd" style={{ marginTop: 20 }}>How to Earn Reward</div>
      <div className="gp-rules">
        {EARN_RULES.filter(r => r.pos).map(rule => (
          <div key={rule.title} className="gp-rule">
            <div className="gp-rule-ico"><rule.Icon size={18} color="var(--gp-fire2)" /></div>
            <div className="gp-rule-body">
              <div className="gp-rule-title">{rule.title}</div>
              <div className="gp-rule-val pos">+{rule.val} Reward</div>
            </div>
          </div>
        ))}
      </div>

      <div className="gp-section-hd" style={{ marginTop: 20 }}>Penalties</div>
      <div className="gp-rules">
        {EARN_RULES.filter(r => !r.pos).map(rule => (
          <div key={rule.title} className="gp-rule">
            <div className="gp-rule-ico"><rule.Icon size={18} color="var(--gp-tx3)" /></div>
            <div className="gp-rule-body">
              <div className="gp-rule-title">{rule.title}</div>
              <div className="gp-rule-val neg">{rule.val} Reward</div>
            </div>
          </div>
        ))}
      </div>

      <div className="gp-section-hd" style={{ marginTop: 20 }}>Streak Multiplier</div>
      <div className="gp-mult-cards">
        {[
          { label: "Base",    days: "0–6 days",  mult: "1×",   color: "var(--gp-tx2)",   Icon: IconCoin     },
          { label: "Rising",  days: "7–29 days", mult: "1.2×", color: "var(--gp-fire2)", Icon: IconVexBolt  },
          { label: "Blazing", days: "30+ days",  mult: "1.5×", color: "var(--gp-gold)",  Icon: IconMultiplier },
        ].map(({ label, days, mult, color, Icon }) => (
          <div key={label} className="gp-mult-card">
            <Icon size={20} color={color} />
            <div className="gp-mult-val" style={{ color }}>{mult}</div>
            <div className="gp-mult-label">{label}</div>
            <div className="gp-mult-days">{days}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Backup / Restore panel ────────────────────────────────────────────────────
function BackupPanel({ state, onRestore }) {
  const fileRef = useRef(null);
  const [msg, setMsg] = useState(null); // { text, ok }

  const flash = (text, ok) => {
    setMsg({ text, ok });
    setTimeout(() => setMsg(null), 3500);
  };

  // ── Export: download full state as .json ─────────────────────────────────
  const handleExport = () => {
    const payload = {
      _backup_version: 1,
      _exported_at:    new Date().toISOString(),
      state,
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `reward-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    flash("Backup berhasil didownload!", true);
  };

  // ── Import: read .json, validate, restore ────────────────────────────────
  const handleImport = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";          // reset so same file can be re-selected
    const reader = new FileReader();
    reader.onload = async (ev) => {
      try {
        const parsed = JSON.parse(ev.target.result);
        const raw = parsed.state ?? parsed;   // support both wrapped & raw format
        // Minimum validation
        if (typeof raw.reward !== "number" || !Array.isArray(raw.unlockedRewards)) {
          flash("File tidak valid — bukan backup reward yang benar.", false);
          return;
        }
        await saveState(raw);
        onRestore(raw);
        flash(`Restore berhasil! ${raw.unlockedRewards.length} reward terpulihkan.`, true);
      } catch {
        flash("Gagal membaca file backup. Pastikan format JSON benar.", false);
      }
    };
    reader.readAsText(file);
  };

  const unlockedCount = state.unlockedRewards?.length ?? 0;
  const exportedAt    = new Date().toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" });

  return (
    <div>
      <div className="gp-section-hd">Backup & Restore Data</div>

      {/* Info box */}
      <div style={{
        background: "rgba(79,110,247,.08)", border: "1px solid rgba(79,110,247,.2)",
        borderRadius: 12, padding: "14px 16px", marginBottom: 18, fontSize: 13,
        color: "var(--gp-tx2)", lineHeight: 1.7,
      }}>
        Data reward disimpan di server (<code style={{ fontSize: 11, opacity: .8 }}>goals.db</code>) dan lokal.
        Export backup secara berkala supaya <strong style={{ color: "var(--gp-tx)" }}>data unlock tidak hilang</strong> kalau file database corrupt atau terhapus.
      </div>

      {/* Status summary */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 18 }}>
        {[
          { label: "Reward Dibeli", val: unlockedCount, color: "#4ade80" },
          { label: "Total Reward",    val: state.reward.toLocaleString("id-ID"), color: "var(--gp-fire)" },
          { label: "Lifetime Reward", val: state.lifetimeReward.toLocaleString("id-ID"), color: "var(--gp-gold)" },
          { label: "Streak",        val: state.streakDays + " hari", color: "var(--gp-fire2)" },
        ].map(({ label, val, color }) => (
          <div key={label} style={{
            background: "var(--gp-bg3)", border: "1px solid var(--gp-border)",
            borderRadius: 10, padding: "12px 14px",
          }}>
            <div style={{ fontSize: 10, color: "var(--gp-tx3)", textTransform: "uppercase", letterSpacing: ".7px", marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "var(--gp-mono)", color }}>{val}</div>
          </div>
        ))}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <button
          onClick={handleExport}
          style={{
            width: "100%", padding: "11px 18px", borderRadius: 10, cursor: "pointer",
            background: "rgba(74,222,128,.12)", border: "1px solid rgba(74,222,128,.3)",
            color: "#4ade80", fontWeight: 700, fontSize: 14, fontFamily: "var(--gp-display)",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            transition: "all .15s",
          }}
          onMouseOver={e => e.currentTarget.style.background = "rgba(74,222,128,.22)"}
          onMouseOut={e  => e.currentTarget.style.background = "rgba(74,222,128,.12)"}
        >
          ↓ Export Backup (.json)
        </button>

        <button
          onClick={() => fileRef.current?.click()}
          style={{
            width: "100%", padding: "11px 18px", borderRadius: 10, cursor: "pointer",
            background: "rgba(79,110,247,.10)", border: "1px solid rgba(79,110,247,.25)",
            color: "#6b85ff", fontWeight: 700, fontSize: 14, fontFamily: "var(--gp-display)",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            transition: "all .15s",
          }}
          onMouseOver={e => e.currentTarget.style.background = "rgba(79,110,247,.2)"}
          onMouseOut={e  => e.currentTarget.style.background = "rgba(79,110,247,.10)"}
        >
          ↑ Import Backup
        </button>
        <input ref={fileRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleImport} />
      </div>

      {/* Feedback toast */}
      {msg && (
        <div style={{
          marginTop: 14, padding: "10px 14px", borderRadius: 9, fontSize: 13,
          background: msg.ok ? "rgba(74,222,128,.12)" : "rgba(248,113,113,.12)",
          border: `1px solid ${msg.ok ? "rgba(74,222,128,.3)" : "rgba(248,113,113,.3)"}`,
          color: msg.ok ? "#4ade80" : "#f87171",
          fontFamily: "var(--gp-mono)", fontWeight: 600,
        }}>
          {msg.ok ? <><IconCheck size={12} color="var(--gr)" /> </> : <><IconClose size={12} color="var(--rd)" /> </>}{msg.text}
        </div>
      )}

      {/* Tip */}
      <div style={{ marginTop: 18, fontSize: 11, color: "var(--gp-tx3)", lineHeight: 1.7 }}>
        <strong>Tip:</strong> Simpan file backup di Google Drive / cloud storage.
        Import otomatis memulihkan semua reward yang pernah dibeli, Reward, streak, dan riwayat aktivitas.
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function RewardDashboard() {
  const [tab, setTab] = usePersistedTab("reward", "earn");
  const { state, snap, loading, derived, redeemReward, setWeeklyGoal, refresh, setState } = useReward();

  if (loading || !state || !derived) return <GpSkeleton />;

  const TABS = [
    { id: "earn",       label: "Earn",          Icon: IconCoin      },
    { id: "shop",       label: "Shop",          Icon: IconAward     },
    { id: "myrewards",  label: "My Rewards",    Icon: IconSparkles  },
    { id: "season",     label: "Season & Rank", Icon: IconSeason    },
    { id: "log",        label: "Activity",      Icon: IconCalStat   },
    { id: "backup",     label: "Backup",        Icon: IconSave      },
  ];

  return (
    <div className="gp-root">
      <div className="gp-page">
        <h1 className="sr-only">Earn Rewards — Gamified Financial Goals &amp; Milestones</h1>
        <Hero     state={state} derived={derived} snap={snap} onRefresh={refresh} />
        <StatsRow state={state} derived={derived} snap={snap} />

        <div className="gp-tabs">
          {TABS.map(t => (
            <div key={t.id} className={"gp-tab" + (tab === t.id ? " act" : "")} onClick={() => setTab(t.id)}>
              <t.Icon size={13} />
              <span>{t.label}</span>
            </div>
          ))}
        </div>

        <div className="gp-panel">
          {tab === "earn"      && <EarnPanel   state={state} setWeeklyGoal={setWeeklyGoal} />}
          {tab === "shop"      && <RewardShop    reward={state.reward} unlockedRewards={state.unlockedRewards} onRedeem={redeemReward} />}
          {tab === "myrewards" && <SelfRewards rewardPoints={state.reward} />}
          {tab === "season"    && <SeasonPanel state={state} derived={derived} />}
          {tab === "log"       && <ActivityLog log={state.log} />}
          {tab === "backup"    && <BackupPanel state={state} onRestore={setState} />}
        </div>
      </div>
    </div>
  );
}

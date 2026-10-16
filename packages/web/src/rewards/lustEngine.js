// ─── lustEngine.js ────────────────────────────────────────────────────────────
// Pure computation layer — no React, no storage, no side-effects.
// Clean Architecture: innermost ring. All Lust math lives here once.
// SOLID / DRY: every rule is a named constant + pure function. Zero duplication.
// ─────────────────────────────────────────────────────────────────────────────

// ══════════════════════════════════════════════════════════════════════════════
// § 1  RULE CONSTANTS — single source of truth
//      Exported as RULES (canonical) + LUST_RULES (alias for legacy compat)
// ══════════════════════════════════════════════════════════════════════════════

export const RULES = Object.freeze({
  // ── Earning ──────────────────────────────────────────────────────────────
  SAVE_PER_100K:         1000, // Increased from 100
  MILESTONE_BONUS:       2000, // Increased from 200
  MILESTONE_INTERVAL:  500_000,
  FIRST_SAVE_DAY:         200, // Increased from 20
  STREAK_3D:              500, // Increased from 50
  STREAK_7D:             1200, // Increased from 120
  STREAK_30D:            5000, // Increased from 500
  WEEKLY_GOAL_HIT:       1500, // Increased from 150
  WEEKLY_OVERACHIEVE:    3000, // Increased from 300
  NO_NONESSENTIAL_DAY:    300, // Increased from 30
  NO_NONESSENTIAL_5X:    1000, // Increased from 100
  SAVING_UP_20PCT:       4000, // Increased from 400

  // ── Penalties (all negative) ──────────────────────────────────────────────
  PEN_SPEND_110_120:      -25,
  PEN_SPEND_120_140:      -75,
  PEN_SPEND_140_PLUS:    -150,
  PEN_NO_SAVE_7D:        -100,
  PEN_WEEKLY_MISS:       -100,
  PEN_WEEKLY_2X_MISS:    -250,
  PEN_SPEND_UP30_NOSAVE: -120,

  // ── Multipliers ───────────────────────────────────────────────────────────
  MULT_BASE:  1.0,
  MULT_7D:    2.5, // Increased from 1.2
  MULT_30D:   5.0, // Increased from 1.5
});

// Legacy alias — LustDashboard.jsx uses LUST_RULES; maps to same object
export const LUST_RULES = {
  SAVE_PER_100K:         RULES.SAVE_PER_100K,
  MILESTONE_BONUS:       RULES.MILESTONE_BONUS,
  FIRST_SAVE_DAY:        RULES.FIRST_SAVE_DAY,
  STREAK_3D:             RULES.STREAK_3D,
  STREAK_7D:             RULES.STREAK_7D,
  STREAK_30D:            RULES.STREAK_30D,
  WEEKLY_GOAL:           RULES.WEEKLY_GOAL_HIT,
  WEEKLY_OVERACHIEVE:    RULES.WEEKLY_OVERACHIEVE,
  NO_NONESSENTIAL_DAY:   RULES.NO_NONESSENTIAL_DAY,
  SAVING_UP_20PCT_MO:    RULES.SAVING_UP_20PCT,
  PENALTY_SPEND_110_120: RULES.PEN_SPEND_110_120,
  PENALTY_SPEND_120_140: RULES.PEN_SPEND_120_140,
  PENALTY_SPEND_140PLUS: RULES.PEN_SPEND_140_PLUS,
  PENALTY_NO_SAVE_7D:    RULES.PEN_NO_SAVE_7D,
  PENALTY_WEEKLY_MISS:   RULES.PEN_WEEKLY_MISS,
  PENALTY_WEEKLY_2X:     RULES.PEN_WEEKLY_2X_MISS,
  PENALTY_SPEND_UP30:    RULES.PEN_SPEND_UP30_NOSAVE,
};

// Non-essential spend categories
export const NON_ESSENTIAL = new Set(["entertainment", "shopping"]);

// ══════════════════════════════════════════════════════════════════════════════
// § 2  RANK SYSTEM — status only, no leaderboard
//      Field: "min" = lifetime Lust threshold to reach this rank
// ══════════════════════════════════════════════════════════════════════════════

export const RANKS = [
  { id: "bronze",   label: "Bronze",   icon: "III", min: 0,        color: "#cd7f32" },
  { id: "silver",   label: "Silver",   icon: "II", min: 2_000,    color: "#c0c0c0" },
  { id: "gold",     label: "Gold",     icon: "I", min: 8_000,    color: "#f5c842" },
  { id: "platinum", label: "Platinum", icon: "Pt", min: 25_000,   color: "#e5e4e2" },
  { id: "diamond",  label: "Diamond",  icon: "Di", min: 75_000,   color: "#b9f2ff" },
  { id: "pure",     label: "Pure",     icon: "P", min: 200_000,  color: "#ffe4fc" },
];

export const resolveRank = (lifetime) =>
  [...RANKS].reverse().find(r => lifetime >= r.min) ?? RANKS[0];

export const nextRank = (lifetime) => {
  const cur = resolveRank(lifetime);
  return RANKS[RANKS.findIndex(r => r.id === cur.id) + 1] ?? null;
};

export const rankProgress = (lifetime) => {
  const cur  = resolveRank(lifetime);
  const next = nextRank(lifetime);
  if (!next) return 1;
  return Math.min(1, (lifetime - cur.min) / (next.min - cur.min));
};

// ══════════════════════════════════════════════════════════════════════════════
// § 3  SEASON SYSTEM  (Monthly cycles resetting on the 28th)
// ══════════════════════════════════════════════════════════════════════════════

export const currentSeason = () => {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();
  // Season 1 started in March 2026 (year 2026, month 2)
  const monthsSinceEpoch = (year - 2026) * 12 + (month - 2);
  return monthsSinceEpoch + (now.getDate() >= 28 ? 1 : 0);
};

export const daysRemainingInSeason = () => {
  const now = new Date();
  const next28 = new Date(now.getFullYear(), now.getMonth(), 28);
  if (now.getDate() >= 28) {
    next28.setMonth(next28.getMonth() + 1);
  }
  const diff = next28.getTime() - now.getTime();
  return Math.max(1, Math.ceil(diff / (24 * 60 * 60 * 1000)));
};

export const seasonProgress = () => {
  const now = new Date();
  const cur28 = new Date(now.getFullYear(), now.getMonth(), 28);
  if (now.getDate() < 28) {
    cur28.setMonth(cur28.getMonth() - 1);
  }
  const next28 = new Date(cur28.getFullYear(), cur28.getMonth() + 1, 28);
  const total = next28.getTime() - cur28.getTime();
  const elapsed = now.getTime() - cur28.getTime();
  return Math.min(1, Math.max(0, elapsed / total));
};

// ══════════════════════════════════════════════════════════════════════════════
// § 4  PURE COMPUTATION FUNCTIONS
// ══════════════════════════════════════════════════════════════════════════════

/** Lust earned from a savings amount (raw, before multiplier) */
export const lustFromSave = (amount) =>
  Math.floor(amount / 100_000) * RULES.SAVE_PER_100K;

/** Milestone bonuses when cumulative total crosses 500K intervals */
export const milestoneBonuses = (prevTotal, addAmount) => {
  const prev = Math.floor(prevTotal / RULES.MILESTONE_INTERVAL);
  const next = Math.floor((prevTotal + addAmount) / RULES.MILESTONE_INTERVAL);
  return Math.max(0, next - prev) * RULES.MILESTONE_BONUS;
};

/** Streak multiplier based on consecutive days */
export const streakMultiplier = (days) =>
  days >= 30 ? RULES.MULT_30D : days >= 7 ? RULES.MULT_7D : RULES.MULT_BASE;

/** One-time flat bonus at exact streak milestones */
export const streakBonus = (days) =>
  days === 30 ? RULES.STREAK_30D : days === 7 ? RULES.STREAK_7D : days === 3 ? RULES.STREAK_3D : 0;

/** Weekly goal bonus — returns 0, WEEKLY_GOAL_HIT, or WEEKLY_OVERACHIEVE */
export const weeklyBonus = (goal, actual) => {
  if (goal <= 0) return 0;
  const r = actual / goal;
  if (r >= 1.5) return RULES.WEEKLY_OVERACHIEVE;
  if (r >= 1.0) return RULES.WEEKLY_GOAL_HIT;
  return 0;
};

/** Spending overage penalty (returns ≤ 0) */
export const spendOveragePenalty = (budgeted, actual) => {
  if (!budgeted || budgeted <= 0) return 0;
  const r = actual / budgeted;
  if (r > 1.40) return RULES.PEN_SPEND_140_PLUS;
  if (r > 1.20) return RULES.PEN_SPEND_120_140;
  if (r > 1.10) return RULES.PEN_SPEND_110_120;
  return 0;
};

/** Apply deltas to current Lust, floored at 0 (can never go negative) */
export const applyDeltas = (current, deltas) =>
  Math.max(0, Math.round(deltas.reduce((s, d) => s + d, current)));

/** Lifetime Lust only increases — drives rank, never resets */
export const updateLifetime = (prev, deltas) =>
  prev + deltas.filter(d => d > 0).reduce((s, d) => s + d, 0);

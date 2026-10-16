// ─── useLust.js ───────────────────────────────────────────────────────────────
// Application layer — Facade Pattern.
// Bridges: lustStore ↔ lustEngine ↔ financial API → clean component interface.
//
// IDEMPOTENCY DESIGN: every event type is guarded by a "last applied" key in
// state so re-running computeEvents on the same data never double-counts.
//
// Keys used for idempotency:
//   state.lastSaveDate         — daily events (first-save-of-day, streak, lust-from-save)
//   state.lastSavingGrowthMonth— monthly saving-growth bonus (YYYY-MM)
//   state.lastSpendPenaltyMonth— monthly spend-overage penalty (YYYY-MM)
//   state.lastSpendGrowthMonth — monthly spend-growth penalty (YYYY-MM)
//   state.weeklyGoalApplied    — weekly goal check (ISO week string)
//   state.noSavePenaltyDate    — 7-day-no-save penalty (date applied)
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useEffect, useCallback } from "react";
import { apiFetch } from "../finance/useApi.js";
import {
  RULES, lustFromSave, milestoneBonuses, streakMultiplier, streakBonus,
  weeklyBonus, spendOveragePenalty, resolveRank, nextRank, rankProgress,
  currentSeason, daysRemainingInSeason, seasonProgress, applyDeltas, updateLifetime,
} from "./lustEngine.js";
import {
  loadState, saveState, rolloverSeason, pushLog,
  isoWeek, todayISO, mergeAutoUnlocked,
} from "./lustStore.js";

// ── Current month key (YYYY-MM) ───────────────────────────────────────────────
const monthKey = () => new Date().toISOString().slice(0, 7);

// ── Yesterday ISO string ───────────────────────────────────────────────────────
const yesterdayISO = () => new Date(Date.now() - 86400000).toISOString().slice(0, 10);

// ── Financial data fetcher ─────────────────────────────────────────────────────
async function fetchSnapshot() {
  try {
    // apiFetch attaches the Bearer token; /dashboard is auth-protected.
    const dash = await apiFetch(`/dashboard`).catch(() => null);
    if (!dash) return null;

    const incThis  = dash.income?.total_this  ?? 0;
    const incPrev  = dash.income?.total_prev  ?? 0;
    const expThis  = dash.expense?.total_this ?? 0;
    const expPrev  = dash.expense?.total_prev ?? 0;
    const byCat    = dash.expense?.by_category ?? {};

    const savingsThis  = Math.max(0, incThis - expThis);
    const savingsPrev  = Math.max(0, incPrev - expPrev);
    const nonEssential = (byCat.entertainment ?? 0) + (byCat.shopping ?? 0);

    return {
      savingsThis,
      savingsPrev,
      expThis,
      expPrev,
      nonEssential,
      byCat,
      savingGrowthPct: savingsPrev > 0 ? (savingsThis - savingsPrev) / savingsPrev : 0,
      spendGrowthPct:  expPrev    > 0  ? (expThis - expPrev) / expPrev             : 0,
      // budgetBaseline = prev month spend; if no prev data, use current as fallback
      budgetBaseline:  expPrev || expThis,
    };
  } catch {
    return null;
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// § IDEMPOTENT EVENT ENGINE
//   Every rule has a guard that prevents re-application on the same period.
//   Returns { newState, events[] } — pure, no side effects.
// ══════════════════════════════════════════════════════════════════════════════
function computeEvents(state, snap) {
  if (!snap) return { newState: state, events: [] };

  const today    = todayISO();
  const yesterday = yesterdayISO();
  const thisWeek = isoWeek();
  const thisMonth = monthKey();

  let s = { ...state };
  const ev = [];

  // ── RULE 1: Daily saving events (guard: lastSaveDate !== today) ────────────
  // Covers: streak, first-save-of-day, lust-from-savings, milestone
  if (snap.savingsThis > 0 && s.lastSaveDate !== today) {
    // Streak logic
    const continued = s.lastSaveDate === yesterday;
    const newStreak  = continued ? s.streakDays + 1 : 1;
    s.streakDays     = newStreak;
    s.multiplier     = streakMultiplier(newStreak);
    s.lastSaveDate   = today;

    // First save of day bonus (only if this is a new day)
    ev.push({ type: "earn", label: "First save of the day", delta: RULES.FIRST_SAVE_DAY });

    // Streak milestone bonus (3, 7, 30)
    const sb = streakBonus(newStreak);
    if (sb > 0)
      ev.push({ type: "streak", label: `${newStreak}-day streak bonus!`, delta: sb });

    // If streak was broken, reset multiplier (already set above to base via streakMultiplier(1))
    if (!continued && s.streakDays > 1) {
      // multiplier already reset to 1.0 by streakMultiplier(1) call above
      ev.push({ type: "penalty", label: "Streak terputus — multiplier reset", delta: 0 });
    }

    // Lust from savings amount (with multiplier)
    const base = lustFromSave(snap.savingsThis);
    if (base > 0) {
      const earned = Math.round(base * s.multiplier);
      ev.push({ type: "earn", label: `Nabung Rp${snap.savingsThis.toLocaleString("id-ID")}`, delta: earned });
    }

    // Milestone bonus
    const milestone = milestoneBonuses(s.totalSavedCumulative, snap.savingsThis);
    s.totalSavedCumulative += snap.savingsThis;
    if (milestone > 0)
      ev.push({ type: "milestone", label: "Milestone Rp500K tercapai!", delta: milestone });
  }

  // ── RULE 2: 7-day no-save penalty (guard: noSavePenaltyDate !== today) ────
  // Only fires once per day, only if no savings and streak was > 0
  if (snap.savingsThis === 0 && s.lastSaveDate && s.lastSaveDate < yesterday &&
      s.noSavePenaltyDate !== today) {
    const daysMissed = Math.floor((Date.now() - new Date(s.lastSaveDate).getTime()) / 86400000);
    if (daysMissed >= 7) {
      ev.push({ type: "penalty", label: "7 hari tanpa saving", delta: RULES.PEN_NO_SAVE_7D });
      s.streakDays = 0;
      s.multiplier = RULES.MULT_BASE;
      s.noSavePenaltyDate = today;
    }
  }

  // ── RULE 3: Monthly saving growth bonus (guard: lastSavingGrowthMonth) ────
  if (snap.savingGrowthPct >= 0.20 && s.lastSavingGrowthMonth !== thisMonth) {
    ev.push({ type: "earn", label: "Saving naik 20%+ vs bulan lalu", delta: RULES.SAVING_UP_20PCT });
    s.lastSavingGrowthMonth = thisMonth;
  }

  // ── RULE 4: Monthly spending overage penalty (guard: lastSpendPenaltyMonth)
  if (s.lastSpendPenaltyMonth !== thisMonth) {
    const overPen = spendOveragePenalty(snap.budgetBaseline, snap.expThis);
    if (overPen < 0) {
      const pct = snap.budgetBaseline > 0 ? Math.round(snap.expThis / snap.budgetBaseline * 100) : 0;
      ev.push({ type: "penalty", label: `Pengeluaran ${pct}% dari bulan lalu`, delta: overPen });
      s.lastSpendPenaltyMonth = thisMonth;
    }
  }

  // ── RULE 5: Monthly spend growth without saving improvement (guard: lastSpendGrowthMonth)
  if (snap.spendGrowthPct > 0.30 && snap.savingGrowthPct <= 0 &&
      s.lastSpendGrowthMonth !== thisMonth) {
    ev.push({ type: "penalty", label: "Pengeluaran naik 30%+ tanpa saving naik", delta: RULES.PEN_SPEND_UP30_NOSAVE });
    s.lastSpendGrowthMonth = thisMonth;
  }

  // ── RULE 6: Weekly goal check (guard: weeklyGoalApplied !== thisWeek) ──────
  if (s.weeklyGoalApplied !== thisWeek) {
    const wb = weeklyBonus(s.weeklyGoal, snap.savingsThis);
    if (wb > 0) {
      const label = wb === RULES.WEEKLY_OVERACHIEVE ? "Overachieve 150%!" : "Weekly goal tercapai!";
      ev.push({ type: "goal", label, delta: wb });
      s.consecutiveWeekMiss = 0;
    } else {
      s.consecutiveWeekMiss = (s.consecutiveWeekMiss ?? 0) + 1;
      const miss = s.consecutiveWeekMiss >= 2 ? RULES.PEN_WEEKLY_2X_MISS : RULES.PEN_WEEKLY_MISS;
      ev.push({ type: "penalty", label: `Weekly goal missed (${s.consecutiveWeekMiss}x streak)`, delta: miss });
    }
    s.weeklyGoalApplied = thisWeek;
  }

  return { newState: s, events: ev };
}

// ── Apply events to state ──────────────────────────────────────────────────────
function applyEvents(state, events) {
  if (events.length === 0) return state;
  const deltas = events.map(e => e.delta);
  return {
    ...state,
    lust:         applyDeltas(state.lust, deltas),
    lifetimeLust: updateLifetime(state.lifetimeLust, deltas),
    seasonLust:   Math.max(0, state.seasonLust + deltas.reduce((a, b) => a + b, 0)),
    log:          events.reduce((l, e) => pushLog(l, e), state.log),
  };
}

// ══════════════════════════════════════════════════════════════════════════════
// § MAIN HOOK
// ══════════════════════════════════════════════════════════════════════════════
export function useLust() {
  const [state,   setState]   = useState(null);
  const [snap,    setSnap]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  // ── Boot: load persisted state + fetch financial snapshot ─────────────────
  useEffect(() => {
    (async () => {
      try {
        const [raw, financial] = await Promise.all([loadState(), fetchSnapshot()]);
        const afterRollover    = rolloverSeason(raw);
        const { newState, events } = computeEvents(afterRollover, financial);
        const final = applyEvents(newState, events);

        await saveState(final);
        setState(final);
        setSnap(financial);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Redeem reward ─────────────────────────────────────────────────────────
  const redeemReward = useCallback(async (reward) => {
    if (!state) return { ok: false };
    if (state.lust < reward.cost)                   return { ok: false, reason: "Insufficient Lust" };
    if (state.unlockedRewards.includes(reward.id))  return { ok: false, reason: "Sudah di-unlock" };

    const next = {
      ...state,
      lust:            Math.max(0, state.lust - reward.cost),
      unlockedRewards: [...state.unlockedRewards, reward.id],
      log: pushLog(state.log, { type: "redeem", label: `Unlocked: ${reward.title}`, delta: -reward.cost }),
    };
    await saveState(next);
    setState(next);
    return { ok: true };
  }, [state]);

  // ── Set weekly goal ───────────────────────────────────────────────────────
  const setWeeklyGoal = useCallback(async (amount) => {
    if (!state || isNaN(amount) || amount <= 0) return;
    const next = { ...state, weeklyGoal: amount };
    await saveState(next);
    setState(next);
  }, [state]);

  // ── Process auto-unlock payload from API response ─────────────────────────
  // Call this after any POST /api/income, /api/expenses, /api/receipt/export.
  // auto_unlocked = response.auto_unlocked (array from server, may be empty/null)
  const processAutoUnlock = useCallback(async (autoUnlocked) => {
    if (!state || !autoUnlocked?.length) return [];
    const next = mergeAutoUnlocked(state, autoUnlocked);
    if (next === state) return [];                      // nothing changed
    await saveState(next);
    setState(next);
    return next.log.slice(0, 1);                       // return the new log entry
  }, [state]);

  // ── Manual refresh: re-fetch snap only, recompute events idempotently ─────
  const refresh = useCallback(async () => {
    if (!state) return;
    setLoading(true);
    try {
      const financial = await fetchSnapshot();
      setSnap(financial);
      // computeEvents is idempotent — guards ensure no double-counting
      const { newState, events } = computeEvents(state, financial);
      const final = applyEvents(newState, events);
      await saveState(final);
      setState(final);
    } finally {
      setLoading(false);
    }
  }, [state]);

  // ── Derived values (computed fresh, never stale) ──────────────────────────
  const derived = state ? {
    rank:       resolveRank(state.lifetimeLust),
    nextRank:   nextRank(state.lifetimeLust),
    rankPct:    rankProgress(state.lifetimeLust),
    season:     currentSeason(),
    daysLeft:   daysRemainingInSeason(),
    seasonPct:  seasonProgress(),
    multiplier: state.multiplier,
  } : null;

  return { state, snap, loading, error, derived, redeemReward, setWeeklyGoal, refresh, setState, processAutoUnlock };
}

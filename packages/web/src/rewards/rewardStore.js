// ─── rewardStore.js ─────────────────────────────────────────────────────────────
// Persistence adapter — Adapter Pattern.
// Single Responsibility: ONLY reads/writes. Zero computation. Zero React.
//
// Storage hierarchy (priority order):
//   1. Server API  → PUT/GET /api/rewards/state  (cross-device, network)
//   2. window.storage fallback                   (local, offline)
//
// The server is the source of truth. On load, server wins over local.
// On save, both are written; a server failure does NOT block the local write.
// ─────────────────────────────────────────────────────────────────────────────

import { currentSeason } from "./rewardEngine.js";
import { API_BASE }       from "../finance/constants.js";
import { _getToken }       from "../finance/useApi.js";

const LOCAL_KEY = "gp:v2:state";   // versioned local key

// ── ISO week helper (YYYY-Www) ─────────────────────────────────────────────────
export const isoWeek = (d = new Date()) => {
  const date = new Date(d);
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + 4 - (date.getDay() || 7));
  const year = date.getFullYear();
  const wk   = Math.ceil((((date - new Date(year, 0, 1)) / 86400000) + 1) / 7);
  return `${year}-W${String(wk).padStart(2, "0")}`;
};

export const todayISO = () => new Date().toISOString().slice(0, 10);

// ── Default state ─────────────────────────────────────────────────────────────
export const DEFAULT_STATE = {
  reward:                  0,
  lifetimeReward:          0,
  seasonReward:            0,
  lastSeasonSeen:        -1,
  streakDays:            0,
  lastSaveDate:          null,
  hasSavedToday:         false,
  multiplier:            1.0,
  totalSavedCumulative:  0,
  weeklyGoal:            500_000,
  weeklyGoalApplied:     null,
  consecutiveWeekMiss:   0,
  noSpendDaysThisWeek:   0,
  noSpendWeekApplied:    null,
  noSavePenaltyDate:     null,
  lastSavingGrowthMonth: null,
  lastSpendPenaltyMonth: null,
  lastSpendGrowthMonth:  null,
  unlockedRewards:       [],
  log:                   [],
};

// ── Storage helpers ────────────────────────────────────────────────────────────
const hasLocalStorage = () => typeof window !== "undefined" && window.storage?.get;

async function readLocal() {
  if (!hasLocalStorage()) return null;
  try {
    const result = await window.storage.get(LOCAL_KEY);
    if (!result?.value) return null;
    return JSON.parse(result.value);
  } catch {
    return null;
  }
}

async function writeLocal(state) {
  if (!hasLocalStorage()) return;
  try { await window.storage.set(LOCAL_KEY, JSON.stringify(state)); }
  catch (e) { console.warn("[rewardStore] local save failed", e); }
}

async function readServer() {
  try {
    const token = _getToken();
    const res = await fetch(`${API_BASE}/rewards/state`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) return null;
    const data = await res.json();
    // Server returns {} when no state is saved yet
    if (!data || Object.keys(data).length === 0) return null;
    return data;
  } catch {
    return null;
  }
}

async function writeServer(state) {
  try {
    const token = _getToken();
    await fetch(`${API_BASE}/rewards/state`, {
      method:  "PUT",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body:    JSON.stringify(state),
    });
  } catch (e) {
    console.warn("[rewardStore] server save failed (offline?)", e);
  }
}

// ── Public API ─────────────────────────────────────────────────────────────────

/**
 * Load state. Server is source of truth; falls back to local storage.
 * Merges with DEFAULT_STATE so new keys always have safe defaults.
 */
export async function loadState() {
  const [serverData, localData] = await Promise.all([readServer(), readLocal()]);

  // Server wins; local is the fallback
  const raw = serverData ?? localData;
  if (!raw) return { ...DEFAULT_STATE };
  return { ...DEFAULT_STATE, ...raw };
}

/**
 * Persist state. Writes to BOTH server and local storage.
 * Server failure is non-fatal — local write still happens.
 */
export async function saveState(state) {
  await Promise.all([
    writeServer(state),
    writeLocal(state),
  ]);
}

// ── Log entry append (max 40, FIFO) ───────────────────────────────────────────
export const pushLog = (log, entry) =>
  [{ ...entry, ts: new Date().toISOString() }, ...log].slice(0, 40);

// ── Auto-unlock merge — called when server returns auto_unlocked list ─────────
/**
 * Merge server-auto-unlocked reward IDs into local state.
 * Idempotent: duplicate IDs are filtered out.
 * Returns new state (does NOT save — caller must call saveState).
 */
export const mergeAutoUnlocked = (state, autoUnlocked) => {
  if (!autoUnlocked?.length) return state;
  const existing = new Set(state.unlockedRewards ?? []);
  const added    = [];
  for (const item of autoUnlocked) {
    const id = typeof item === "string" ? item : item.reward_id;
    if (id && !existing.has(id)) { existing.add(id); added.push(id); }
  }
  if (!added.length) return state;
  return {
    ...state,
    unlockedRewards: [...existing],
    log: pushLog(state.log ?? [], {
      type:  "auto_unlock",
      label: `Auto-unlocked: ${added.join(", ")}`,
      delta: 0,
    }),
  };
};

// ── Season rollover mutation ───────────────────────────────────────────────────
export const rolloverSeason = (state) => {
  const season = currentSeason();
  if (state.lastSeasonSeen === season) return state;
  return {
    ...state,
    lastSeasonSeen: season,
    seasonReward:     0,
    unlockedRewards: state.unlockedRewards ?? [],
    log: pushLog(state.log, {
      type:  "season",
      label: `Season ${season + 1} started — seasonal Reward reset (rewards preserved)`,
      delta: 0,
    }),
  };
};

// ── Self-Reward API helpers ────────────────────────────────────────────────────

/** Fetch all self-rewards (embedded in state.selfRewards from /api/rewards/state). */
export async function fetchSelfRewards() {
  try {
    const token = _getToken();
    const res = await fetch(`${API_BASE}/rewards/state`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data?.selfRewards ?? [];
  } catch {
    return [];
  }
}

/** Create a new self-reward via the API. */
export async function createSelfReward({ title, cost, rewardType = "reward", description = "", icon = "gift" }) {
  const token = _getToken();
  const res = await fetch(`${API_BASE}/rewards/self-reward`, {
    method:  "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body:    JSON.stringify({ title, cost, rewardType, description, icon }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create self-reward");
  }
  return res.json();
}

/** Redeem a self-reward by ID. */
export async function redeemSelfReward(rewardId) {
  const token = _getToken();
  const res = await fetch(`${API_BASE}/rewards/self-reward/${rewardId}/redeem`, {
    method:  "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to redeem self-reward");
  }
  return res.json();
}

/** Delete a self-reward by ID. */
export async function deleteSelfReward(rewardId) {
  const token = _getToken();
  const res = await fetch(`${API_BASE}/rewards/self-reward/${rewardId}`, {
    method:  "DELETE",
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to delete self-reward");
  }
  return res.json();
}


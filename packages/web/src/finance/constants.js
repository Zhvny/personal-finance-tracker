// â”€â”€â”€ finance/constants.js â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Pure JS constants only â€” NO JSX here (this is a .js file, not .jsx).
// JSX icon maps live in finance/icon-maps.jsx
// High Cohesion: only constant definitions and pure functions.
// Low Coupling : zero dependencies on React or icons.

// API base resolves at runtime (window.__API_BASE__ or same-origin /api).
import { getRuntimeApiBase } from "../runtime-config.js";

export const API_BASE = getRuntimeApiBase();

console.log("[FT] API_BASE:", API_BASE);

export const CAT_COLOR = {
  "Food & Drink": "#f59e0b",
  transport:     "#06b6d4",
  housing:       "#3b82f6",
  entertainment: "#a855f7",
  health:        "#10b981",
  shopping:      "#ef4444",
  education:     "#60a5fa",
  investment:    "#f59e0b",
  other:         "#6b7280",
};

export const TYPE_COLOR = {
  stock:  "var(--ind-b)",
  crypto: "var(--pu)",
  gold:   "var(--yl)",
};

// Payment methods list â€” mirrors expense_tracker/core/models.py PaymentMethod enum exactly.
export const PAY_LIST = [
  "cash", "debit-card", "credit-card", "e-wallet", "bank-transfer",
  "ovo", "gopay", "shopeepay", "qris",
];

export const INC_TYPES = ["salary", "freelance", "investment", "side-hustle", "transfer", "other"];

export const RECURRING_PERIODS = ["daily", "weekly", "monthly", "yearly"];

export const CATEGORIES = [
  "Food & Drink", "transport", "housing", "entertainment",
  "health", "shopping", "education", "investment", "other",
];

// â”€â”€â”€ Formatters (pure functions, no side-effects) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export const fmt  = n => {
  if (n === null || n === undefined) return "—";
  return `Rp${Math.abs(n).toLocaleString("id-ID")}`;
};
export const fmtS = (n, isUSD = false) => {
  if (n === null || n === undefined) return "—";
  const sign = n >= 0 ? "+" : "-";
  if (isUSD) {
    return `${sign}$${Math.abs(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${sign}${fmt(n)}`;
};
export const fmtRp = n => {
  if (n === null || n === undefined) return "—";
  return `Rp${Math.abs(n).toLocaleString("id-ID")}`;
};
export const fmtShortM = n => {
  if (n === null || n === undefined) return "—";
  const val = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (val >= 1e9) return `${sign}Rp${(val / 1e9).toFixed(2)}M`;
  if (val >= 1e6) return `${sign}Rp${(val / 1e6).toFixed(1)}jt`;
  return sign + fmt(val);
};
export const pctChg = (c, p) => p === 0 ? null : (c - p) / p * 100;
export const today     = () => new Date().toISOString().slice(0, 10);
export const thisYear  = () => new Date().getFullYear();
export const thisMonth = () => new Date().getMonth() + 1;

// Dynamic year range: from DATA_START_YEAR up to current year + 1.
// Avoids hardcoded [2024, 2025, 2026, 2027] that expires every year.
const DATA_START_YEAR = 2024;
export const yearRange = () => {
  const end = new Date().getFullYear() + 1;
  return Array.from({ length: end - DATA_START_YEAR + 1 }, (_, i) => DATA_START_YEAR + i);
};

/**
 * Maps a signal string to a semantic color class (g, r, y).
 * g = green (buy), r = red (sell), y = yellow (neutral).
 * Handles: Strong Buy, Buy, Sell, Strong Sell, Neutral, Hold, Wait.
 */
export const getSignalVariant = (signal) => {
  const s = String(signal || "").toUpperCase();
  if (s.includes("BUY") || s.includes("BULL") || s.includes("ACCUMULATE")) return "g";
  if (s.includes("SELL") || s.includes("BEAR") || s.includes("AVOID")) return "r";
  if (s.includes("HOLD") || s.includes("NEUTRAL") || s.includes("WAIT")) return "y";
  return "y"; // Fallback to yellow
};


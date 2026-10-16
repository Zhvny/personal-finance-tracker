// ─── src/constants.js ─────────────────────────────────────────────────────────
// Re-exports pure JS constants for backward compatibility.
// JSX icon maps are in finance/icon-maps.jsx — import directly from there.
export {
  API_BASE,
  CAT_COLOR, TYPE_COLOR,
  PAY_LIST, INC_TYPES, CATEGORIES,
  fmt, fmtS, fmtRp, pctChg, today, thisYear, thisMonth, yearRange,
} from "./finance/constants.js";

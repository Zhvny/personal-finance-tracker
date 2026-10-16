// ─── behavioralEngine.js ──────────────────────────────────────────────────────
// Pure computation layer — ZERO React, ZERO fetch, ZERO side-effects.
//
// Clean Architecture : innermost ring — no framework dependencies.
// Single Responsibility : one exported fn = one computation concern.
// DRY  : clamp / normalize / weightedScore defined once, used everywhere.
// YAGNI: only what the 3 features need.
//
// Theory annotations:
//   [PT]  Prospect Theory      — Kahneman & Tversky (1979)
//   [PB]  Present Bias         — Laibson (1997)
//   [MA]  Mental Accounting    — Thaler (1999)
//   [FF]  Financial Fragility  — Housel (2020)
// ─────────────────────────────────────────────────────────────────────────────

// ══ § 0  SHARED MATH  (module-private) ══════════════════════════════════════
const clamp      = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, v));
const mean       = arr => arr.length ? arr.reduce((s, v) => s + v, 0) / arr.length : 0;
// Normalize raw value to 0–1 over practical [lo, hi]. Clamped.
const normalize  = (v, lo, hi) => clamp((v - lo) / ((hi - lo) || 1));
// Weighted sum: items [{value:0–1, weight:0–1}] → 0–100 score
const weightedScore = items =>
  items.reduce((s, { value, weight }) => s + clamp(value) * weight, 0) * 100;


// ══ § 1  IMPULSIVE SPENDING ENGINE  =========================================
//    Theory: [PB] Present Bias + [MA] Mental Accounting

/** [MA] Category Risk — discretionary > non-discretionary */
const CATEGORY_RISK = {
  entertainment: 1.00, shopping: 0.90, "Food & Drink": 0.60,
  transport:     0.40, health:   0.20, housing:   0.10,
  education:     0.10, investment:0.00, other:    0.50,
};

/** [PB] Time Risk — weekend/night = short-term reward seeking */
const timeRisk = dateStr => {
  const d   = new Date(dateStr);
  const day = d.getDay(); // 0=Sun,6=Sat
  return ((day === 0 || day === 6) ? 0.5 : 0) + ((d.getHours() >= 22 || d.getHours() < 6) ? 0.5 : 0);
};

/**
 * Impulsivity Score for one transaction.
 * IS = w1·CatRisk + w2·TimeRisk + w3·DeviationMean + w4·FreqSpike
 */
export function computeIS(tx, catMean, catFreqDay, dayMean) {
  const W = { cat: 0.35, time: 0.25, dev: 0.25, freq: 0.15 };
  return clamp(
    W.cat  * (CATEGORY_RISK[tx.category] ?? 0.5) +
    W.time * timeRisk(tx.date) +
    W.dev  * (catMean  > 0 ? normalize(tx.amount / catMean  - 1, 0, 3) : 0) +
    W.freq * (dayMean  > 0 ? normalize(catFreqDay / dayMean - 1, 0, 2) : 0)
  );
}

/**
 * Monthly Impulsivity Index = Σ(IS) / total_tx
 * @returns {{ index:number, perTx:Array<{tx,is}>, breakdown:Record<string,number> }}
 */
export function computeImpulsivityIndex(expenses) {
  if (!expenses.length) return { index: 0, perTx: [], breakdown: {} };

  const catGroups = {};
  const dayCatCount = {};
  const dayTotals = {};

  for (const tx of expenses) {
    (catGroups[tx.category] ??= []).push(tx.amount);
    const day = tx.date?.slice(0, 10) ?? "";
    const key = `${day}::${tx.category}`;
    dayCatCount[key] = (dayCatCount[key] ?? 0) + 1;
    dayTotals[day]   = (dayTotals[day]   ?? 0) + 1;
  }

  const catMeans  = Object.fromEntries(Object.entries(catGroups).map(([k, v]) => [k, mean(v)]));
  const avgPerDay = mean(Object.values(dayTotals));

  const perTx = expenses.map(tx => {
    const day = tx.date?.slice(0, 10) ?? "";
    const is  = computeIS(tx, catMeans[tx.category] ?? 0, dayCatCount[`${day}::${tx.category}`] ?? 1, avgPerDay);
    return { tx, is };
  });

  const catBuckets = {};
  for (const { tx, is } of perTx) (catBuckets[tx.category] ??= []).push(is);

  return {
    index:     perTx.reduce((s, { is }) => s + is, 0) / perTx.length,
    perTx,
    breakdown: Object.fromEntries(Object.entries(catBuckets).map(([k, v]) => [k, mean(v)])),
  };
}

/** LI Score = expense_growth_rate − income_growth_rate. Positive = inflation. */
export function computeLifestyleInflation(expThis, expPrev, incThis, incPrev) {
  const expGrowth = expPrev > 0 ? (expThis - expPrev) / expPrev : 0;
  const incGrowth = incPrev > 0 ? (incThis - incPrev) / incPrev : 0;
  return { liScore: expGrowth - incGrowth, expGrowth, incGrowth };
}

/** Emotional Spending Ratio — entertainment+shopping / total */
export function computeEmotionalRatio(byCat) {
  const total    = Object.values(byCat).reduce((s, v) => s + v, 0);
  const emoTotal = (byCat.entertainment ?? 0) + (byCat.shopping ?? 0);
  return total > 0 ? emoTotal / total : 0;
}

/**
 * Financial Behaviour Score (FBS) — 0–100, higher = healthier.
 * FBS = Σ(weight × normalized_metric)
 * | Component           | Weight |
 * |---------------------|--------|
 * | Saving rate         |  30%   |
 * | Impulsivity Index   |  25%   |
 * | Emotional Spending  |  15%   |
 * | Lifestyle Inflation |  15%   |
 * | Budget Adherence    |  15%   |
 */
export function computeFBS({ savingRate, impulsivityIndex, emotionalRatio, liScore, budgetAdherence }) {
  return weightedScore([
    { value: normalize(savingRate,             0,    0.50), weight: 0.30 },
    { value: 1 - normalize(impulsivityIndex,   0,    0.70), weight: 0.25 }, // inverse
    { value: 1 - normalize(emotionalRatio,     0,    0.50), weight: 0.15 }, // inverse
    { value: 1 - normalize(liScore + 0.2,      0,    0.70), weight: 0.15 }, // inverse; negative LI = good
    { value: normalize(budgetAdherence,         0,    1.00), weight: 0.15 },
  ]);
}

/** FBS grade → { label, color, tier } */
export function fbsGrade(score) {
  if (score >= 80) return { label: "Excellent",  color: "#34d399", tier: "A" };
  if (score >= 65) return { label: "Good",        color: "#6b85ff", tier: "B" };
  if (score >= 50) return { label: "Fair",         color: "#fbbf24", tier: "C" };
  if (score >= 35) return { label: "Needs Work",  color: "#f97316", tier: "D" };
  return               { label: "Critical",       color: "#f87171", tier: "F" };
}


// ══ § 2  FINANCIAL FRAGILITY ENGINE  ========================================
//    Theory: [FF] Risk Diversification + Financial Fragility

/** Asset allocation breakdown — all values as % of total assets. */
export function computeAssetAllocation({ cashSavings, investments }) {
  const sumType = t => investments.filter(i => i.asset_type === t).reduce((s, i) => s + (i.current_idr ?? 0), 0);
  const crypto  = sumType("crypto");
  const stock   = sumType("stock");
  const gold    = sumType("gold");
  const total   = cashSavings + crypto + stock + gold;
  const pct     = n => total > 0 ? (n / total) * 100 : 0;
  return { cash: pct(cashSavings), crypto: pct(crypto), stock: pct(stock), gold: pct(gold), highRisk: pct(crypto), totalAssets: total };
}

/** Income Dependency Ratio = largest_source / total_income */
export function computeIncomeDependency(incomeBySource) {
  const vals  = Object.values(incomeBySource);
  const total = vals.reduce((s, v) => s + v, 0);
  if (!total) return { ratio: 0, primarySource: null, total: 0 };
  const max   = Math.max(...vals);
  return { ratio: max / total, primarySource: Object.keys(incomeBySource).find(k => incomeBySource[k] === max) ?? null, total };
}

/**
 * Financial Fragility Score (0–100) — HIGHER = MORE STABLE.
 * | Factor                  | Weight |
 * |-------------------------|--------|
 * | Emergency fund coverage |  30%   |
 * | Income diversification  |  20%   |
 * | High-risk asset %       |  20%   |
 * | Debt ratio              |  20%   |
 * | Saving rate stability   |  10%   |
 */
export function computeFragilityScore({ monthlyExpense, cashSavings, incomeDependency, highRiskPct, debtRatio, savingRateStddev }) {
  return weightedScore([
    { value: normalize(monthlyExpense > 0 ? cashSavings / monthlyExpense : 0, 0, 6), weight: 0.30 },
    { value: 1 - normalize(incomeDependency,  0, 1),    weight: 0.20 },
    { value: 1 - normalize(highRiskPct,       0, 100),  weight: 0.20 },
    { value: 1 - normalize(debtRatio,         0, 0.5),  weight: 0.20 },
    { value: 1 - normalize(savingRateStddev,  0, 0.3),  weight: 0.10 },
  ]);
}

/** Fragility grade → { label, color } */
export function fragilityGrade(score) {
  if (score >= 75) return { label: "Very Stable",  color: "#34d399" };
  if (score >= 55) return { label: "Stable",        color: "#6b85ff" };
  if (score >= 40) return { label: "Moderate Risk", color: "#fbbf24" };
  if (score >= 25) return { label: "Fragile",       color: "#f97316" };
  return               { label: "Critical",        color: "#f87171" };
}


// ══ § 3  NET WORTH HEATMAP ENGINE  ==========================================
//    Theory: [PT] Prospect Theory — losses weighted 1.8× visually

/**
 * Heatmap cell from current vs previous.
 * [PT] Loss Aversion: isNegative cells get 1.8× intensity multiplier.
 */
export function computeHeatmapCell(current, previous, label, isLiability = false) {
  const LOSS_AVERSION = 1.8; // [PT]
  const pct        = previous !== 0 ? (current - previous) / Math.abs(previous) : 0;
  const isNegative = isLiability ? pct > 0 : pct < 0;
  const raw        = normalize(Math.abs(pct), 0, 0.5);
  const intensity  = isNegative ? clamp(raw * LOSS_AVERSION) : raw;

  const r = isNegative ? Math.round(180 + intensity * 75) : Math.round(22  + intensity * 10);
  const g = isNegative ? Math.round(50  - intensity * 20) : Math.round(155 + intensity * 56);
  const b = isNegative ? Math.round(50  - intensity * 20) : Math.round(80  + intensity * 10);

  return {
    label, current, previous, pct, isNegative, intensity,
    pctDisplay:  (pct * 100).toFixed(1),
    color:       `rgba(${r},${g},${b},${0.12 + intensity * 0.60})`,
    borderColor: isNegative ? `rgba(248,113,113,${0.25 + intensity * 0.55})` : `rgba(52,211,153,${0.25 + intensity * 0.55})`,
    textColor:   isNegative ? "#f87171" : "#34d399",
  };
}

/** Full heatmap from { current, previous } snapshots. */
export function buildNetWorthHeatmap({ current, previous }) {
  const cells = [
    computeHeatmapCell(current.cash,          previous.cash,          "Cash"),
    computeHeatmapCell(current.stocks,        previous.stocks,        "Stocks"),
    computeHeatmapCell(current.crypto,        previous.crypto,        "Crypto"),
    computeHeatmapCell(current.gold,          previous.gold,          "Gold"),
    computeHeatmapCell(current.emergencyFund, previous.emergencyFund, "Emergency Fund"),
    computeHeatmapCell(current.debt,          previous.debt,          "Debt", true),
  ];
  const nwCurr = current.cash  + current.stocks  + current.crypto  + current.gold  + current.emergencyFund  - current.debt;
  const nwPrev = previous.cash + previous.stocks + previous.crypto + previous.gold + previous.emergencyFund - previous.debt;
  return { cells, netWorth: { current: nwCurr, previous: nwPrev, ...computeHeatmapCell(nwCurr, nwPrev, "Net Worth") } };
}

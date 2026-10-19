// ─── BusinessAnalytics.jsx ───────────────────────────────────────────────────
// Business Intelligence & Business Analytics (BI/BA) Cockpit for Vite Web App.
// Full 10-section analytical suite — every figure computed from live API data.
// No mock/fallback numbers: empty states are shown when an endpoint has no data.

import { useState, useEffect, useCallback, useMemo } from "react";
import DOMPurify from "dompurify";
import { apiFetch } from "../finance/useApi.js";
import {
  IconBarChart, IconPieChart, IconLineChart, IconHeatmap, IconRisk,
  IconTarget, IconSuccess, IconWarning, IconInfo, IconRefresh,
  IconSearch, IconFilter, IconCalendar, IconUp, IconDown, IconDownload,
  IconCheck, IconClose
} from "../icons.jsx";
import { useI18n } from "../i18n/context.js";

const fmtIDR = n => "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(n || 0));
const fmtCompact = n => {
  if (n === null || n === undefined || isNaN(n)) return "Rp 0";
  if (Math.abs(n) >= 1e9) return `Rp ${(n / 1e9).toFixed(2)}M`;
  if (Math.abs(n) >= 1e6) return `Rp ${(n / 1e6).toFixed(1)}jt`;
  return fmtIDR(n);
};
const num = v => { const n = Number(v); return isNaN(n) ? 0 : n; };
const round2 = n => Math.round((n + Number.EPSILON) * 100) / 100;
const monthPrefix = (y, m) => `${y}-${String(m).padStart(2, "0")}`;

export default function BusinessAnalytics() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState("overview");
  const [dashData, setDashData]     = useState(null);
  const [allExpenses, setAllExpenses] = useState([]);
  const [allIncomes, setAllIncomes]   = useState([]);
  const [budgetMap, setBudgetMap]     = useState(null);
  const [expPred, setExpPred]         = useState(null);
  const [activeProfile, setActiveProfile] = useState(null);
  const [loading, setLoading]     = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [reportModal, setReportModal] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const now = new Date();
      const ok = r => r.status === "fulfilled" && r.value && !r.value.__aborted;
      const items = r => (ok(r) && Array.isArray(r.value?.items)) ? r.value.items : [];

      const [dRes, expAllRes, incAllRes, expPredRes, profRes] = await Promise.allSettled([
        apiFetch("/dashboard"),
        apiFetch("/expenses?limit=1000"),
        apiFetch("/income?limit=1000"),
        apiFetch("/analytics/expense-prediction?months_history=6&months_ahead=3"),
        apiFetch("/profile/")
      ]);

      if (ok(dRes)) setDashData(dRes.value);
      setAllExpenses(items(expAllRes));
      setAllIncomes(items(incAllRes));
      if (ok(expPredRes)) setExpPred(expPredRes.value);
      if (ok(profRes)) setActiveProfile(profRes.value);

      const selY = ok(dRes) ? (dRes.value?.selected_year ?? now.getFullYear()) : now.getFullYear();
      const selM = ok(dRes) ? (dRes.value?.selected_month ?? now.getMonth() + 1) : now.getMonth() + 1;

      const budRes = await Promise.resolve(apiFetch(`/expenses/budget/${selY}/${selM}`)).catch(() => null);
      if (budRes && !budRes.__aborted && budRes && typeof budRes === "object") setBudgetMap(budRes);
    } catch (e) {
      console.error("Error loading BI/BA real data", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Periode aktif (bulan laporan dari backend / fallback bulan terakhir) ──
  const dash = useMemo(() => {
    const now = new Date();
    const selYear = dashData?.selected_year ?? now.getFullYear();
    const selMonth = dashData?.selected_month ?? now.getMonth() + 1;
    const monthLabel = dashData?.month_label ||
      new Date(selYear, selMonth - 1, 1).toLocaleString("id-ID", { month: "long", year: "numeric" });

    const inc = num(dashData?.income?.total_this);
    const exp = num(dashData?.expense?.total_this);
    const prevInc = num(dashData?.income?.total_prev);
    const prevExp = num(dashData?.expense?.total_prev);

    const profit = inc - exp;
    const margin = inc > 0 ? (profit / inc) * 100 : 0;
    const productivity = exp > 0 ? (profit / exp) * 100 : 0;
    const incMoM = prevInc > 0 ? ((inc - prevInc) / prevInc) * 100 : null;
    const expMoM = prevExp > 0 ? ((exp - prevExp) / prevExp) * 100 : null;

    return { selYear, selMonth, monthLabel, inc, exp, prevInc, prevExp, profit, margin, productivity, incMoM, expMoM };
  }, [dashData]);

  // ── Data transaksi bulan laporan (disaring dari list riil, bukan mock) ──
  const currentExpenses = useMemo(() => {
    const key = monthPrefix(dash.selYear, dash.selMonth);
    return allExpenses.filter(e => (e.date || "").slice(0, 7) === key);
  }, [allExpenses, dash.selYear, dash.selMonth]);

  const currentIncomes = useMemo(() => {
    const key = monthPrefix(dash.selYear, dash.selMonth);
    return allIncomes.filter(i => (i.date || "").slice(0, 7) === key);
  }, [allIncomes, dash.selYear, dash.selMonth]);

  // ── Tren bulanan riil (pemasukan tidak termasuk transfer — konsisten dgn summary) ──
  const trendSeries = useMemo(() => {
    const map = {};
    allExpenses.forEach(e => {
      const k = (e.date || "").slice(0, 7);
      if (!k) return;
      map[k] = map[k] || { label: k, exp: 0, inc: 0 };
      map[k].exp += num(e.amount);
    });
    allIncomes.forEach(i => {
      if (String(i.income_type || "").toLowerCase() === "transfer") return;
      const k = (i.date || "").slice(0, 7);
      if (!k) return;
      map[k] = map[k] || { label: k, exp: 0, inc: 0 };
      map[k].inc += num(i.amount);
    });
    return Object.keys(map).sort().map(k => {
      const t = map[k];
      const [yy, mm] = k.split("-").map(Number);
      return {
        label: new Date(yy, mm - 1, 1).toLocaleString("id-ID", { month: "short", year: "numeric" }),
        key: k,
        exp: round2(t.exp),
        inc: round2(t.inc),
        net: round2(t.inc - t.exp)
      };
    });
  }, [allExpenses, allIncomes]);

  // ── Heatmap intensitas belanja harian (W1–W4) dari transaksi riil ──
  const heatmapData = useMemo(() => {
    const days = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"];
    const matrix = days.map(day => ({ day, w1: 0, w2: 0, w3: 0, w4: 0 }));
    let hasData = false;
    currentExpenses.forEach(e => {
      if (!e.date) return;
      const dt = new Date(e.date);
      if (isNaN(dt.getTime())) return;
      const dayIdx = (dt.getDay() + 6) % 7;
      const wIdx = Math.min(4, Math.max(1, Math.ceil(dt.getDate() / 7)));
      const wKey = `w${wIdx}`;
      if (matrix[dayIdx] && matrix[dayIdx][wKey] !== undefined) {
        matrix[dayIdx][wKey] = round2(matrix[dayIdx][wKey] + num(e.amount));
        hasData = true;
      }
    });
    return hasData ? matrix : [];
  }, [currentExpenses]);

  // ── Target vs Actual per kategori (dari endpoint budget riil) ──
  const budgetActual = useMemo(() => {
    if (!budgetMap || typeof budgetMap !== "object") return [];
    return Object.entries(budgetMap)
      .filter(([k]) => String(k).toLowerCase() !== "total")
      .map(([name, v]) => {
        const target = num(v?.budget);
        const actual = num(v?.actual);
        const pct = target > 0 ? (actual / target) * 100 : 0;
        return {
          name,
          target,
          actual,
          pct: round2(pct),
          status: pct > 100 ? "over" : pct >= 80 ? "warning" : "under"
        };
      })
      .sort((a, b) => b.actual - a.actual);
  }, [budgetMap]);

  // ── Segmentasi pengeluaran & pemasukan (dari transaksi riil) ──
  const expenseSegments = useMemo(() => {
    const sums = {};
    currentExpenses.forEach(e => {
      const c = e.category || "other";
      sums[c] = sums[c] || 0;
      sums[c] += num(e.amount);
    });
    const total = Object.values(sums).reduce((a, b) => a + b, 0);
    return Object.entries(sums)
      .map(([name, amount]) => ({ name, amount: round2(amount), pct: total > 0 ? (amount / total) * 100 : 0 }))
      .sort((a, b) => b.amount - a.amount);
  }, [currentExpenses]);

  const incomeSegments = useMemo(() => {
    const sums = {};
    currentIncomes.forEach(i => {
      if (String(i.income_type || "").toLowerCase() === "transfer") return;
      const s = i.source || "Lainnya";
      sums[s] = sums[s] || 0;
      sums[s] += num(i.amount);
    });
    const total = Object.values(sums).reduce((a, b) => a + b, 0);
    return Object.entries(sums)
      .map(([name, amount]) => ({ name, amount: round2(amount), pct: total > 0 ? (amount / total) * 100 : 0 }))
      .sort((a, b) => b.amount - a.amount);
  }, [currentIncomes]);

  // ── Forecasting 3 bulan (regresi linear atas tren riil, expense prefer dari API) ──
  const forecastData = useMemo(() => {
    const fit = pts => {
      const n = pts.length;
      if (n < 2) return null;
      const sx = pts.reduce((a, p) => a + p.x, 0), sy = pts.reduce((a, p) => a + p.y, 0);
      const sxy = pts.reduce((a, p) => a + p.x * p.y, 0), sxx = pts.reduce((a, p) => a + p.x * p.x, 0);
      const d = n * sxx - sx * sx;
      if (d === 0) return null;
      const slope = (n * sxy - sx * sy) / d;
      const intercept = (sy - slope * sx) / n;
      return { slope, intercept, baseIdx: n };
    };
    const incPts = trendSeries.map((t, i) => ({ x: i, y: t.inc })).filter(p => p.y > 0);
    const expPts = trendSeries.map((t, i) => ({ x: i, y: t.exp })).filter(p => p.y > 0);
    const fInc = fit(incPts), fExp = fit(expPts);

    const predList = Array.isArray(expPred?.predictions) ? expPred.predictions : [];
    const out = [];
    const start = new Date(dash.selYear, dash.selMonth, 1);
    for (let i = 1; i <= 3; i++) {
      const d = new Date(start.getFullYear(), start.getMonth() + i, 1);
      const label = d.toLocaleString("id-ID", { month: "long", year: "numeric" });
      const inc = fInc ? Math.max(0, fInc.intercept + fInc.slope * (fInc.baseIdx - 1 + i)) : (i === 1 ? dash.inc : null);
      const exp = fExp ? Math.max(0, fExp.intercept + fExp.slope * (fExp.baseIdx - 1 + i)) : (i === 1 ? dash.exp : null);
      out.push({
        label,
        inc: inc === null ? null : Math.round(inc),
        exp: exp === null ? null : Math.round(exp),
        net: inc === null || exp === null ? null : Math.round(inc - exp),
        source: predList[i - 1]?.source || "Regresi Linear"
      });
    }
    return out;
  }, [trendSeries, expPred, dash]);

  // ── Deteksi anomali statistik (Z-score/IQR-style) atas transaksi riil ──
  const detectedAnomalies = useMemo(() => {
    const result = [];
    const catData = {};
    allExpenses.forEach(e => {
      const c = e.category || "other";
      catData[c] = catData[c] || [];
      catData[c].push(num(e.amount));
    });

    Object.entries(catData).forEach(([cat, amounts]) => {
      if (amounts.length < 2) return;
      const sorted = [...amounts].sort((a, b) => a - b);
      const mean = amounts.reduce((a, b) => a + b, 0) / amounts.length;
      const variance = amounts.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / amounts.length;
      const std = Math.sqrt(variance);
      const q1 = sorted[Math.floor(sorted.length * 0.25)];
      const q3 = sorted[Math.floor(sorted.length * 0.75)];
      const iqr = q3 - q1;
      allExpenses.forEach(e => {
        if ((e.category || "other") !== cat) return;
        const amt = num(e.amount);
        if (amt <= 0) return;
        const zHigh = std > 0 && amt > mean + 2.2 * std;
        const iqrHigh = iqr > 0 && amt > q3 + 1.5 * iqr;
        if (zHigh || iqrHigh) {
          result.push({
            txId: `EXP-${e.id}`,
            date: (e.date || "").slice(0, 10),
            title: t("business.anom_expense_title", { category: e.category || "other", amount: fmtIDR(amt) }),
            detail: t("business.anom_expense_detail", { description: e.description || e.category || t("business.anom_fallback_expense"), test: zHigh ? t("business.anom_zscore") : t("business.anom_iqr"), category: cat, mean: fmtIDR(round2(mean)) }),
            severity: "high"
          });
        }
      });
    });

    if (dash.expMoM !== null && dash.expMoM > 20) {
      result.push({
        txId: null,
        date: dash.monthLabel,
        title: t("business.anom_rise_title", { value: dash.expMoM.toFixed(1) }),
        detail: t("business.anom_rise_detail", { expense: fmtIDR(dash.exp), value: dash.expMoM.toFixed(1), previous: fmtIDR(dash.prevExp) }),
        severity: "high"
      });
    }
    if (dash.profit < 0) {
      result.push({
        txId: null,
        date: dash.monthLabel,
        title: t("business.anom_deficit_title", { amount: fmtIDR(Math.abs(dash.profit)) }),
        detail: t("business.anom_deficit_detail", { expense: fmtIDR(dash.exp), income: fmtIDR(dash.inc), margin: dash.margin.toFixed(1), productivity: dash.productivity.toFixed(1) }),
        severity: "critical"
      });
    }
    return result.sort((a, b) => a.date.localeCompare(b.date));
  }, [allExpenses, dash, t]);

  // ── Rekomendasi terstruktur (berbasis metrik riil) ──
  const recommendations = useMemo(() => {
    const recs = [];
    const overBudgetCats = budgetActual.filter(b => b.pct > 100);

    if (dash.profit > 0) {
      recs.push({
        priority: t("business.rec_surplus_priority"),
        action: t("business.rec_surplus_action", { amount: fmtIDR(dash.profit) }),
        tone: "gr"
      });
    } else if (dash.profit < 0) {
      recs.push({
        priority: t("business.rec_deficit_priority"),
        action: t("business.rec_deficit_action", { deficit: fmtIDR(Math.abs(dash.profit)), expense: fmtIDR(dash.exp), income: fmtIDR(dash.inc), category: expenseSegments[0]?.name || "-", categoryAmount: fmtIDR(expenseSegments[0]?.amount || 0) }),
        tone: "rd"
      });
    }

    if (dash.expMoM !== null && dash.expMoM > 10) {
      recs.push({
        priority: t("business.rec_cost_priority"),
        action: t("business.rec_cost_action", { value: dash.expMoM.toFixed(1) }),
        tone: "yl"
      });
    }
    if (dash.margin >= 0 && dash.margin < 20) {
      recs.push({
        priority: t("business.rec_margin_priority"),
        action: t("business.rec_margin_action", { margin: dash.margin.toFixed(1) }),
        tone: "yl"
      });
    }
    overBudgetCats.slice(0, 2).forEach(b => {
      recs.push({
        priority: t("business.rec_overbudget_priority", { category: b.name }),
        action: t("business.rec_overbudget_action", { actual: fmtIDR(b.actual), percent: b.pct.toFixed(0), target: fmtIDR(b.target) }),
        tone: "rd"
      });
    });

    if (recs.length === 0) {
      recs.push({
        priority: t("business.rec_stable_priority"),
        action: t("business.rec_stable_action"),
        tone: "gr"
      });
    }
    return recs;
  }, [dash, budgetActual, expenseSegments, t]);

  // ── Ledger transaksi riil dengan penanda anomali ──
  const transactionFeed = useMemo(() => {
    const list = [
      ...allExpenses.map(e => ({
        id: `EXP-${e.id}`,
        date: (e.date || "").slice(0, 10),
        type: "expense",
        category: e.category || "other",
        description: e.description || t("business.tx_fallback_expense"),
        amount: num(e.amount),
        status: "normal",
        segment: e.payment_method ? t("business.tx_method", { method: e.payment_method }) : t("business.tx_opex")
      })),
      ...allIncomes.map(i => ({
        id: `INC-${i.id}`,
        date: (i.date || "").slice(0, 10),
        type: "income",
        category: i.income_type || "other",
        description: i.source || i.description || t("business.tx_fallback_income"),
        amount: num(i.amount),
        status: "normal",
        segment: t("business.tx_real_income")
      }))
    ];
    const anomalyIds = new Set(detectedAnomalies.filter(a => a.txId).map(a => a.txId));
    list.forEach(t => { if (anomalyIds.has(t.id)) t.status = "anomaly"; });
    return list.sort((a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
  }, [allExpenses, allIncomes, detectedAnomalies, t]);

  const filteredTx = useMemo(() => {
    const q = searchQuery.toLowerCase();
    return transactionFeed.filter(t =>
      (t.description || "").toLowerCase().includes(q) ||
      (t.category || "").toLowerCase().includes(q) ||
      t.id.toLowerCase().includes(q)
    );
  }, [transactionFeed, searchQuery]);

  // ── KPI: target diturunkan dari data riil (bukan konstanta) ──
  const kpi = useMemo(() => {
    const incHistory = trendSeries.map(t => t.inc).filter(v => v > 0);
    const last3Inc = incHistory.slice(-3);
    const incomeTarget = last3Inc.length
      ? Math.round(last3Inc.reduce((a, b) => a + b, 0) / last3Inc.length)
      : Math.round(Math.max(dash.inc, dash.prevInc));

    const budgetEntries = budgetMap && typeof budgetMap === "object"
      ? Object.entries(budgetMap).filter(([k]) => String(k).toLowerCase() !== "total")
      : [];
    const expenseTarget = budgetEntries.length
      ? Math.round(budgetEntries.reduce((a, [k, v]) => a + num(v?.budget), 0))
      : Math.round(Math.max(dash.exp, dash.prevExp));

    const netHistory = trendSeries.map(t => t.net);
    const last3Net = netHistory.slice(-3);
    const savingsTarget = last3Net.length
      ? Math.max(0, Math.round(last3Net.reduce((a, b) => a + b, 0) / last3Net.length))
      : Math.max(0, dash.profit);

    const pctOf = (actual, target) => target > 0 ? ((actual - target) / target) * 100 : 0;
    const incDev = pctOf(dash.inc, incomeTarget);
    const expDev = pctOf(dash.exp, expenseTarget);
    const savDev = pctOf(dash.profit, savingsTarget);

    const incStatus = dash.inc >= incomeTarget ? "EXCEEDED" : dash.inc >= incomeTarget * 0.9 ? "ON TRACK" : "BEHIND";
    const expStatus = dash.exp <= expenseTarget ? "ON TRACK" : dash.exp <= expenseTarget * 1.15 ? "WARNING" : "OVER BUDGET";
    const savStatus = dash.profit >= savingsTarget ? "OPTIMAL" : dash.profit >= 0 ? "MODERATE" : "DEFICIT";

    return {
      incomeTarget, expenseTarget, savingsTarget,
      incDev, expDev, savDev,
      incStatus, expStatus, savStatus,
      incMethod: t("business.kpi_inc_method"),
      expMethod: t("business.kpi_exp_method"),
      savMethod: t("business.kpi_sav_method")
    };
  }, [trendSeries, budgetMap, dash, t]);

  const execCondition = useMemo(() => {
    if (dash.profit > 0 && dash.margin >= 20) return { label: t("business.cond_vhealthy"), tone: "var(--gr)" };
    if (dash.profit > 0) return { label: t("business.cond_healthy"), tone: "var(--cy)" };
    if (dash.profit === 0) return { label: t("business.cond_breakeven"), tone: "var(--yl)" };
    return { label: t("business.cond_deficit"), tone: "var(--rd)" };
  }, [dash, t]);

  const execInsight = useMemo(() => {
    const parts = [];
    if (dash.profit > 0) {
      parts.push(t("business.insight_surplus", { month: dash.monthLabel, amount: fmtIDR(dash.profit), margin: dash.margin.toFixed(1) }));
    } else if (dash.profit < 0) {
      parts.push(t("business.insight_deficit", { month: dash.monthLabel, deficit: fmtIDR(Math.abs(dash.profit)), expense: fmtIDR(dash.exp), income: fmtIDR(dash.inc) }));
    } else {
      parts.push(t("business.insight_breakeven", { month: dash.monthLabel }));
    }
    if (dash.incMoM !== null) parts.push(t("business.insight_inc_mom", { value: (dash.incMoM >= 0 ? "+" : "") + dash.incMoM.toFixed(1) }));
    if (dash.expMoM !== null) parts.push(dash.expMoM <= 0 ? t("business.insight_exp_down", { value: Math.abs(dash.expMoM).toFixed(1) }) : t("business.insight_exp_up", { value: Math.abs(dash.expMoM).toFixed(1) }));
    if (dash.productivity < 0) parts.push(t("business.insight_prod_neg"));
    else if (dash.productivity >= 20) parts.push(t("business.insight_prod_pos"));
    else if (dash.inc > 0) parts.push(t("business.insight_prod_low"));
    return parts.join(" ");
  }, [dash, t]);

  const tabs = [
    { id: "overview",        label: t("business.tab_overview") },
    { id: "kpi",             label: t("business.tab_kpi") },
    { id: "trends",          label: t("business.tab_trends") },
    { id: "target",          label: t("business.tab_target") },
    { id: "segmentation",    label: t("business.tab_segmentation") },
    { id: "forecast",        label: t("business.tab_forecast") },
    { id: "anomalies",       label: t("business.tab_anomalies") },
    { id: "recommendations", label: t("business.tab_recommendations") },
    { id: "drilldown",       label: t("business.tab_drilldown") },
    { id: "methodology",     label: t("business.tab_methodology") },
  ];

  const statusPill = (status) => {
    const map = {
      EXCEEDED: "g", "ON TRACK": "g", OPTIMAL: "g", MODERATE: "y",
      BEHIND: "r", "OVER BUDGET": "r", DEFICIT: "r", WARNING: "y"
    };
    return <span className={`pill ${map[status] || "y"}`}>{status}</span>;
  };

  const pctColor = p => p > 100 ? "var(--rd)" : p >= 80 ? "var(--yl)" : "var(--gr)";

  const handlePrintPDF = () => {
    const win = window.open("", "_blank");
    if (win) {
      const rows = [
        [t("business.kpi_row_income"), kpi.incomeTarget, dash.inc, kpi.incStatus],
        [t("business.kpi_row_expense"), kpi.expenseTarget, dash.exp, kpi.expStatus],
        [t("business.kpi_row_net"), kpi.savingsTarget, dash.profit, kpi.savStatus]
      ].map(([label, target, actual, status]) =>
        `<tr><td>${label}</td><td>${fmtIDR(target)}</td><td>${fmtIDR(actual)}</td><td>${status}</td></tr>`
      ).join("");
      win.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>${t("business.report_doc_title")}</title>
          <style>
            @media print { @page { margin: 15mm; size: A4; } }
            body { font-family: -apple-system, sans-serif; padding: 24px; color: #111; line-height: 1.6; }
            h1 { color: #000; border-bottom: 2px solid #333; padding-bottom: 8px; }
            .kpi-table { width: 100%; border-collapse: collapse; margin-top: 16px; }
            .kpi-table th, .kpi-table td { border: 1px solid #ccc; padding: 8px 12px; text-align: left; }
            .kpi-table th { background: #f4f4f4; }
          </style>
        </head>
        <body onload="window.print()">
          <h1>${t("business.report_h1")}</h1>
          <p><strong>${t("business.report_period")}:</strong> ${dash.monthLabel} | <strong>${t("business.report_generated")}:</strong> ${new Date().toLocaleDateString('id-ID')} | <strong>${t("business.report_profile")}:</strong> ${activeProfile?.active || "-"}</p>
          <h2>${t("business.report_summary_h")}</h2>
          <p>${t("business.report_income_label")}: <strong>${fmtIDR(dash.inc)}</strong> | ${t("business.report_expense_label")}: <strong>${fmtIDR(dash.exp)}</strong> | ${t("business.report_net_label")}: <strong>${fmtIDR(dash.profit)}</strong></p>
          <p>${t("business.report_margin_label")}: <strong>${dash.margin.toFixed(1)}%</strong> | ${t("business.report_productivity_label")}: <strong>${dash.productivity.toFixed(1)}%</strong> | ${t("business.report_condition_label")}: <strong>${execCondition.label}</strong></p>

          <h2>${t("business.report_kpi_h")}</h2>
          <table class="kpi-table">
            <thead>
              <tr><th>${t("business.kpi_indicator")}</th><th>${t("business.kpi_target")}</th><th>${t("business.kpi_actual")}</th><th>${t("business.kpi_status")}</th></tr>
            </thead>
            <tbody>
              ${rows}
            </tbody>
          </table>
        </body>
        </html>
      `);
      win.document.close();
    }
  };

  const handleDownloadFile = (ext, content, mime) => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `BI_Executive_Report_${new Date().toISOString().slice(0, 10)}.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderTrendBars = () => {
    if (trendSeries.length === 0) {
      return <p style={{ fontSize: 12, color: "var(--tx3)" }}>Belum ada data tren bulanan. Tambahkan transaksi terlebih dahulu.</p>;
    }
    const max = Math.max(...trendSeries.map(t => Math.max(t.inc, t.exp)), 1);
  const netLabel = t("business.net");
  const incomeLabel = t("business.income");
  const expenseLabel = t("business.expense");
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {trendSeries.map(t => (
          <div key={t.key} style={{ background: "var(--bg3)", padding: 12, borderRadius: 12, border: "1px solid var(--bdr)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
              <span style={{ fontWeight: 700 }}>{t.label}</span>
              <span style={{ color: "var(--tx3)" }}>
                {netLabel}: <strong style={{ color: t.net >= 0 ? "var(--gr)" : "var(--rd)" }}>{fmtCompact(t.net)}</strong>
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 52, fontSize: 10, color: "var(--tx3)" }}>{incomeLabel}</span>
                <div style={{ flex: 1, background: "var(--bg4)", height: 10, borderRadius: 99, overflow: "hidden" }}>
                  <div style={{ width: `${(t.inc / max) * 100}%`, height: "100%", background: "var(--gr)", borderRadius: 99 }} />
                </div>
                <span style={{ width: 64, textAlign: "right", fontSize: 10, fontFamily: "var(--mono)" }}>{fmtCompact(t.inc)}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 52, fontSize: 10, color: "var(--tx3)" }}>{expenseLabel}</span>
                <div style={{ flex: 1, background: "var(--bg4)", height: 10, borderRadius: 99, overflow: "hidden" }}>
                  <div style={{ width: `${(t.exp / max) * 100}%`, height: "100%", background: "var(--yl)", borderRadius: 99 }} />
                </div>
                <span style={{ width: 64, textAlign: "right", fontSize: 10, fontFamily: "var(--mono)" }}>{fmtCompact(t.exp)}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div style={{ padding: "4px 0" }}>
      {/* Header Bar */}
      <div style={{
        background: "var(--bg2)", border: "1px solid var(--bdr2)", borderRadius: "var(--rl)",
        padding: "20px 24px", marginBottom: 20, display: "flex", justifyContent: "space-between",
        alignItems: "center", flexWrap: "wrap", gap: 16
      }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ background: "rgba(245,158,11,0.15)", color: "#f59e0b", padding: "8px 12px", borderRadius: 12 }}>
              <IconBarChart size={24} />
            </div>
            <div>
              <h1 style={{ fontSize: 20, fontWeight: 900, letterSpacing: "-0.5px", margin: 0 }}>
                {t("business.title")}
              </h1>
              <div style={{ fontSize: 12, color: "var(--tx3)", marginTop: 2 }}>
                {t("business.subtitle", { period: dash.monthLabel, profile: activeProfile?.active || "—" })}
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button className="btn btn-g btn-s" onClick={loadData} disabled={loading} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <IconRefresh size={14} className={loading ? "spin" : ""} /> {t("common.refresh")}
          </button>
          <button className="btn btn-p btn-s" onClick={() => setReportModal(true)} style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700 }}>
            <IconDownload size={14} /> {t("business.export_report")}
          </button>
        </div>
      </div>

      {/* Tabs Bar */}
      <div style={{ display: "flex", gap: 6, overflowX: "auto", paddingBottom: 8, marginBottom: 20 }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: "8px 16px", borderRadius: 99, fontSize: 12, fontWeight: activeTab === t.id ? 800 : 500,
              background: activeTab === t.id ? "var(--ind)" : "var(--bg3)",
              color: activeTab === t.id ? "#fff" : "var(--tx2)",
              border: `1px solid ${activeTab === t.id ? "var(--ind)" : "var(--bdr)"}`,
              cursor: "pointer", whiteSpace: "nowrap", transition: "all 0.2s ease"
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* 1. OVERVIEW / EXECUTIVE SUMMARY */}
      {activeTab === "overview" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
            <div style={{ background: "var(--bg2)", borderLeft: "4px solid var(--gr)", borderRadius: 14, padding: 18, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>{t("business.total_income")}</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: "var(--gr)", marginTop: 6 }}>{fmtCompact(dash.inc)}</div>
              <div style={{ fontSize: 11, color: dash.incMoM === null ? "var(--tx3)" : (dash.incMoM >= 0 ? "var(--gr)" : "var(--rd)"), marginTop: 4 }}>
                {dash.incMoM === null ? t("business.mom_na") : t("business.mom_change", { value: (dash.incMoM >= 0 ? "+" : "") + dash.incMoM.toFixed(1) })}
              </div>
            </div>
            <div style={{ background: "var(--bg2)", borderLeft: "4px solid var(--yl)", borderRadius: 14, padding: 18, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>{t("business.total_expense")}</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: "var(--yl)", marginTop: 6 }}>{fmtCompact(dash.exp)}</div>
              <div style={{ fontSize: 11, color: dash.expMoM === null ? "var(--tx3)" : (dash.expMoM <= 0 ? "var(--gr)" : "var(--rd)"), marginTop: 4 }}>
                {dash.expMoM === null ? t("business.mom_na") : t("business.mom_expense", { value: (dash.expMoM <= 0 ? "-" : "+") + Math.abs(dash.expMoM).toFixed(1), suffix: dash.expMoM <= 0 ? t("business.efficiency_paren") : "" })}
              </div>
            </div>
            <div style={{ background: "var(--bg2)", borderLeft: "4px solid var(--cy)", borderRadius: 14, padding: 18, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>{t("business.net_profit")}</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: dash.profit >= 0 ? "var(--cy)" : "var(--rd)", marginTop: 6 }}>{fmtCompact(dash.profit)}</div>
              <div style={{ fontSize: 11, color: "var(--tx2)", marginTop: 4 }}>{t("business.margin", { value: dash.margin.toFixed(1) })}</div>
            </div>
            <div style={{ background: "var(--bg2)", borderLeft: "4px solid var(--pu)", borderRadius: 14, padding: 18, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>{t("business.productivity_index")}</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: dash.productivity >= 0 ? "var(--pu)" : "var(--rd)", marginTop: 6 }}>{dash.productivity.toFixed(1)}%</div>
              <div style={{ fontSize: 11, color: "var(--tx3)", marginTop: 4 }}>{t("business.per_100_cost")}</div>
            </div>
          </div>

          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.insight_title")}</h3>
            <p style={{ fontSize: 13, color: "var(--tx2)", lineHeight: 1.6 }}>
              {t("business.condition_prefix")} <strong>{dash.monthLabel}</strong>: <strong style={{ color: execCondition.tone }}>{execCondition.label}</strong>.{" "}
              <span dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(execInsight) }} />
            </p>
          </div>
        </div>
      )}

      {/* 2. KPI & METRICS */}
      {activeTab === "kpi" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 16 }}>{t("business.kpi_matrix")}</h3>
          <p style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 16 }}>
            {t("business.kpi_note", { methods: kpi.incMethod + "; " + kpi.expMethod + "; " + kpi.savMethod, period: dash.monthLabel })}
          </p>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--bdr)", color: "var(--tx3)", textTransform: "uppercase" }}>
                  <th style={{ padding: "10px" }}>{t("business.kpi_indicator")}</th>
                  <th style={{ padding: "10px" }}>{t("business.kpi_target")}</th>
                  <th style={{ padding: "10px" }}>{t("business.kpi_actual")}</th>
                  <th style={{ padding: "10px" }}>{t("business.kpi_deviation")}</th>
                  <th style={{ padding: "10px" }}>{t("business.kpi_status")}</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: "1px solid var(--bdr)" }}>
                  <td style={{ padding: "12px 10px", fontWeight: 700 }}>{t("business.kpi_row_income")}</td>
                  <td style={{ padding: "12px 10px", color: "var(--tx3)" }}>{fmtIDR(kpi.incomeTarget)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 800, color: "var(--gr)" }}>{fmtIDR(dash.inc)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 700, color: kpi.incDev >= 0 ? "var(--gr)" : "var(--rd)" }}>
                    {kpi.incDev >= 0 ? "+" : ""}{kpi.incDev.toFixed(1)}%
                  </td>
                  <td style={{ padding: "12px 10px" }}>{statusPill(kpi.incStatus)}</td>
                </tr>
                <tr style={{ borderBottom: "1px solid var(--bdr)" }}>
                  <td style={{ padding: "12px 10px", fontWeight: 700 }}>{t("business.kpi_row_expense")}</td>
                  <td style={{ padding: "12px 10px", color: "var(--tx3)" }}>{fmtIDR(kpi.expenseTarget)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 800, color: "var(--yl)" }}>{fmtIDR(dash.exp)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 700, color: kpi.expDev <= 0 ? "var(--gr)" : "var(--rd)" }}>
                    {kpi.expDev >= 0 ? "+" : ""}{kpi.expDev.toFixed(1)}% {kpi.expDev <= 0 ? t("business.saved_paren") : ""}
                  </td>
                  <td style={{ padding: "12px 10px" }}>{statusPill(kpi.expStatus)}</td>
                </tr>
                <tr style={{ borderBottom: "1px solid var(--bdr)" }}>
                  <td style={{ padding: "12px 10px", fontWeight: 700 }}>{t("business.kpi_row_net")}</td>
                  <td style={{ padding: "12px 10px", color: "var(--tx3)" }}>{fmtIDR(kpi.savingsTarget)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 800, color: dash.profit >= 0 ? "var(--cy)" : "var(--rd)" }}>{fmtIDR(dash.profit)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 700, color: kpi.savDev >= 0 ? "var(--gr)" : "var(--rd)" }}>
                    {kpi.savDev >= 0 ? "+" : ""}{kpi.savDev.toFixed(1)}%
                  </td>
                  <td style={{ padding: "12px 10px" }}>{statusPill(kpi.savStatus)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3. VISUALISASI & TREN + HEATMAP */}
      {activeTab === "trends" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.trend_title")}</h3>
            {renderTrendBars()}
          </div>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.heatmap_title", { month: dash.monthLabel })}</h3>
            {heatmapData.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--tx3)" }}>{t("business.heatmap_empty", { month: dash.monthLabel })}</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, textAlign: "center" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--bdr)", color: "var(--tx3)" }}>
                      <th style={{ padding: 10, textAlign: "left" }}>{t("business.day")}</th>
                      <th style={{ padding: 10 }}>{t("business.week", { n: 1 })}</th>
                      <th style={{ padding: 10 }}>{t("business.week", { n: 2 })}</th>
                      <th style={{ padding: 10 }}>{t("business.week", { n: 3 })}</th>
                      <th style={{ padding: 10 }}>{t("business.week", { n: 4 })}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {heatmapData.map((r, i) => (
                      <tr key={i} style={{ borderBottom: "1px solid var(--bdr)" }}>
                        <td style={{ padding: 10, textAlign: "left", fontWeight: 700 }}>{r.day}</td>
                        {[r.w1, r.w2, r.w3, r.w4].map((v, idx) => {
                          const bg = v > 2000000 ? "rgba(239,68,68,.3)" : v > 1000000 ? "rgba(245,158,11,.2)" : "rgba(16,185,129,.15)";
                          const col = v > 2000000 ? "var(--rd)" : v > 1000000 ? "var(--yl)" : "var(--gr)";
                          return (
                            <td key={idx} style={{ padding: 8 }}>
                              <div style={{ background: bg, color: col, borderRadius: 8, padding: "6px 8px", fontWeight: 700 }}>
                                {fmtCompact(v)}
                              </div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 4. TARGET VS ACTUAL */}
      {activeTab === "target" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 16 }}>{t("business.target_title", { month: dash.monthLabel })}</h3>
          {budgetActual.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>{t("business.target_empty")}</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {budgetActual.map(c => {
                const pct = c.pct;
                const isOver = pct > 100;
                return (
                  <div key={c.name} style={{ background: "var(--bg3)", padding: 14, borderRadius: 12, border: "1px solid var(--bdr)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6, fontSize: 12 }}>
                      <span style={{ fontWeight: 700 }}>{c.name}</span>
                      <span>
                        {t("business.actual_label")}: <strong style={{ color: isOver ? "var(--rd)" : pct >= 80 ? "var(--yl)" : "var(--gr)" }}>{fmtIDR(c.actual)}</strong> / {fmtIDR(c.target)} ({pct.toFixed(1)}%)
                      </span>
                    </div>
                    <div style={{ background: "var(--bg4)", height: 8, borderRadius: 99, overflow: "hidden" }}>
                      <div style={{ width: `${Math.min(100, pct)}%`, height: "100%", background: pctColor(pct), borderRadius: 99 }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* 5. SEGMENTASI */}
      {activeTab === "segmentation" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 16 }}>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.seg_income_title", { month: dash.monthLabel })}</h3>
            {incomeSegments.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--tx3)" }}>{t("business.seg_income_empty")}</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {incomeSegments.map(s => (
                  <div key={s.name} style={{ background: "var(--bg3)", padding: 12, borderRadius: 10, display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>{s.name}</div>
                      <div style={{ fontSize: 10, color: "var(--tx3)" }}>{t("business.pct_of_total", { value: s.pct.toFixed(1) })}</div>
                    </div>
                    <div style={{ fontWeight: 800, color: "var(--gr)" }}>{fmtIDR(s.amount)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.seg_expense_title", { month: dash.monthLabel })}</h3>
            {expenseSegments.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--tx3)" }}>{t("business.seg_expense_empty")}</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {expenseSegments.map(s => (
                  <div key={s.name} style={{ background: "var(--bg3)", padding: 12, borderRadius: 10, display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>{s.name}</div>
                      <div style={{ fontSize: 10, color: "var(--tx3)" }}>{t("business.pct_of_total", { value: s.pct.toFixed(1) })}</div>
                    </div>
                    <div style={{ fontWeight: 800, color: "var(--yl)" }}>{fmtIDR(s.amount)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* 6. FORECASTING */}
      {activeTab === "forecast" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.forecast_title")}</h3>
          <p style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 16 }}>
            {t("business.forecast_sub", { months: trendSeries.length })}
          </p>
          {forecastData.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>{t("business.forecast_empty")}</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
              {forecastData.map(f => (
                <div key={f.label} style={{ background: "var(--bg3)", padding: 14, borderRadius: 12, border: "1px solid var(--bdr)" }}>
                  <div style={{ fontSize: 11, color: "var(--tx3)", fontWeight: 700 }}>{f.label}</div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "var(--gr)", marginTop: 4 }}>
                    {t("business.revenue_label")}: {f.inc === null ? "N/A" : fmtCompact(f.inc)}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--yl)", marginTop: 2 }}>
                    {t("business.cost_label")}: {f.exp === null ? "N/A" : fmtCompact(f.exp)}
                  </div>
                  <div style={{ fontSize: 12, marginTop: 2, fontWeight: 700, color: f.net === null ? "var(--tx3)" : (f.net >= 0 ? "var(--cy)" : "var(--rd)") }}>
                    {t("business.net")}: {f.net === null ? "N/A" : fmtCompact(f.net)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 7. ANOMALI */}
      {activeTab === "anomalies" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12, color: "var(--rd)" }}>{t("business.anomalies_title")}</h3>
          {detectedAnomalies.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>{t("business.anomalies_empty")}</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {detectedAnomalies.map((a, i) => (
                <div key={i} style={{
                  background: a.severity === "critical" ? "rgba(239,68,68,.1)" : "rgba(245,158,11,.08)",
                  border: a.severity === "critical" ? "1px solid rgba(239,68,68,.35)" : "1px solid rgba(245,158,11,.25)",
                  borderRadius: 12, padding: 14
                }}>
                  <div style={{ fontWeight: 700, color: a.severity === "critical" ? "var(--rd)" : "var(--yl)", fontSize: 13 }}>
                    {a.severity === "critical" ? t("business.sev_critical") : t("business.sev_high")}{a.title}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--tx2)", marginTop: 4 }}>{a.detail}</div>
                  <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 4 }}>{t("business.period_label")}: {a.date} {a.txId ? `| ID: ${a.txId}` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 8. REKOMENDASI */}
      {activeTab === "recommendations" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.recs_title")}</h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {recommendations.map((r, i) => (
              <div key={i} style={{ background: "var(--bg3)", padding: 14, borderRadius: 12, borderLeft: `4px solid var(--${r.tone})` }}>
                <div style={{ fontWeight: 700, fontSize: 13 }}>{i + 1}. {r.priority}</div>
                <div style={{ fontSize: 12, color: "var(--tx2)", marginTop: 4 }}>{r.action}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 9. DRILL DOWN */}
      {activeTab === "drilldown" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14, flexWrap: "wrap", gap: 10 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800 }}>{t("business.drilldown_title")}</h3>
            <input
              type="text"
              placeholder={t("business.search_placeholder")}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 8, padding: "6px 12px", color: "var(--tx)", fontSize: 12 }}
            />
          </div>
          {transactionFeed.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>{t("business.drilldown_empty")}</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--bdr)", color: "var(--tx3)" }}>
                    <th style={{ padding: 8 }}>{t("business.col_id_date")}</th>
                    <th style={{ padding: 8 }}>{t("business.col_type")}</th>
                    <th style={{ padding: 8 }}>{t("business.col_desc_segment")}</th>
                    <th style={{ padding: 8 }}>{t("business.kpi_status")}</th>
                    <th style={{ padding: 8, textAlign: "right" }}>{t("business.col_amount")}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTx.map(tx => (
                    <tr key={tx.id} style={{ borderBottom: "1px solid var(--bdr)" }}>
                      <td style={{ padding: 8, fontFamily: "var(--mono)" }}><strong>{tx.id}</strong><div style={{ color: "var(--tx3)", fontSize: 10 }}>{tx.date}</div></td>
                      <td style={{ padding: 8 }}><span className={`pill ${tx.type === "income" ? "g" : "r"}`}>{tx.type}</span></td>
                      <td style={{ padding: 8 }}><strong>{tx.description}</strong><div style={{ color: "var(--tx3)", fontSize: 10 }}>{tx.segment}</div></td>
                      <td style={{ padding: 8 }}>
                        {tx.status === "anomaly"
                          ? <span className="pill r">{t("business.badge_anomaly")}</span>
                          : <span className="pill g">{t("business.badge_normal")}</span>}
                      </td>
                      <td style={{ padding: 8, textAlign: "right", fontWeight: 700, fontFamily: "var(--mono)", color: tx.type === "income" ? "var(--gr)" : "var(--tx)" }}>
                        {tx.type === "income" ? "+" : "-"}{fmtIDR(tx.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* 10. METODOLOGI */}
      {activeTab === "methodology" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>{t("business.methodology_title")}</h3>
          <div style={{ fontSize: 12, color: "var(--tx2)", lineHeight: 1.8 }}>
            <p>
              {t("business.method_intro")} <strong>{activeProfile?.active || "—"}</strong>
              {activeProfile?.active_type ? t("business.method_type", { type: activeProfile.active_type }) : ""}.
            </p>
            <ul style={{ paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
              <li><strong>{t("business.method_mom_label")}:</strong> {t("business.method_mom_text")}</li>
              <li><strong>{t("business.method_kpi_label")}:</strong> {t("business.method_kpi_text")}</li>
              <li><strong>{t("business.method_trend_label")}:</strong> {t("business.method_trend_text")}</li>
              <li><strong>{t("business.method_heatmap_label")}:</strong> {t("business.method_heatmap_text")}</li>
              <li><strong>{t("business.method_target_label")}:</strong> {t("business.method_target_text")}</li>
              <li><strong>{t("business.method_seg_label")}:</strong> {t("business.method_seg_text")}</li>
              <li><strong>{t("business.method_forecast_label")}:</strong> {t("business.method_forecast_text")}</li>
              <li><strong>{t("business.method_anomaly_label")}:</strong> {t("business.method_anomaly_text")}</li>
              <li><strong>{t("business.method_rec_label")}:</strong> {t("business.method_rec_text")}</li>
              <li><strong>{t("business.method_drill_label")}:</strong> {t("business.method_drill_text")}</li>
            </ul>
          </div>
        </div>
      )}

      {/* Export Report Modal */}
      {reportModal && (
        <div style={{ position: "fixed", inset: 0, zIndex: 3000, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 20, width: "100%", maxWidth: 500, padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 16, fontWeight: 900, margin: 0 }}>{t("business.export_modal_title")}</h3>
              <button className="btn btn-g btn-s" onClick={() => setReportModal(false)}><IconClose size={14} /></button>
            </div>
            <p style={{ fontSize: 12, color: "var(--tx2)", marginBottom: 20 }}>{t("business.export_modal_sub")}</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <button className="btn btn-p" onClick={() => { handleDownloadFile("md", `# ${t("business.export_md_title")}\n\n- ${t("business.report_period")}: ${dash.monthLabel}\n- ${t("business.report_income_label")}: ${fmtIDR(dash.inc)}\n- ${t("business.report_expense_label")}: ${fmtIDR(dash.exp)}\n- ${t("business.kpi_row_net")}: ${fmtIDR(dash.profit)}\n- ${t("business.report_margin_label")}: ${dash.margin.toFixed(1)}%\n- ${t("business.report_condition_label")}: ${execCondition.label}\n- ${t("business.report_kpi_target_label")}: ${fmtIDR(kpi.incomeTarget)} / ${fmtIDR(kpi.expenseTarget)} / ${fmtIDR(kpi.savingsTarget)}`, "text/markdown"); setReportModal(false); }}>
                {t("business.export_md")}
              </button>
              <button className="btn btn-g" onClick={() => { handleDownloadFile("html", `<html><body><h1>${t("business.export_md_title")}</h1><p>${t("business.report_period")}: ${dash.monthLabel}</p><p>${t("business.report_income_label")}: ${fmtIDR(dash.inc)}</p><p>${t("business.report_expense_label")}: ${fmtIDR(dash.exp)}</p><p>${t("business.net")}: ${fmtIDR(dash.profit)}</p></body></html>`, "text/html"); setReportModal(false); }}>
                {t("business.export_html")}
              </button>
              <button className="btn btn-g" onClick={() => { handlePrintPDF(); setReportModal(false); }}>
                {t("business.export_pdf")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

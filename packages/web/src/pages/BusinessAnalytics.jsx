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
            title: `Anomali Pengeluaran ${e.category || "other"} — ${fmtIDR(amt)}`,
            detail: `Transaksi "${e.description || e.category || "pengeluaran"}" melewati batas toleransi statistik (${zHigh ? "Z-score > 2.2σ" : "outlier IQR"} terhadap rata-rata kategori ${cat}: ${fmtIDR(round2(mean))}).`,
            severity: "high"
          });
        }
      });
    });

    if (dash.expMoM !== null && dash.expMoM > 20) {
      result.push({
        txId: null,
        date: dash.monthLabel,
        title: `Kenaikan Beban Bulanan +${dash.expMoM.toFixed(1)}%`,
        detail: `Total pengeluaran bulan ini ${fmtIDR(dash.exp)} melonjak +${dash.expMoM.toFixed(1)}% dibanding bulan sebelumnya (${fmtIDR(dash.prevExp)}), melebihi ambang toleransi 20%.`,
        severity: "high"
      });
    }
    if (dash.profit < 0) {
      result.push({
        txId: null,
        date: dash.monthLabel,
        title: `Defisit Bulanan ${fmtIDR(Math.abs(dash.profit))}`,
        detail: `Pengeluaran ${fmtIDR(dash.exp)} melebihi pemasukan ${fmtIDR(dash.inc)} sehingga terjadi defisit. Margin ${dash.margin.toFixed(1)}%, indeks produktivitas ${dash.productivity.toFixed(1)}%.`,
        severity: "critical"
      });
    }
    return result.sort((a, b) => a.date.localeCompare(b.date));
  }, [allExpenses, dash]);

  // ── Rekomendasi terstruktur (berbasis metrik riil) ──
  const recommendations = useMemo(() => {
    const recs = [];
    const overBudgetCats = budgetActual.filter(b => b.pct > 100);

    if (dash.profit > 0) {
      recs.push({
        priority: "Kunci Alokasi Investment Surplus",
        action: `Alokasikan 40–50% dari net surplus ${fmtIDR(dash.profit)} ke instrumen yield-bearing (DCA emas/indeXT/obligasi ritel), sisanya untuk cadangan dana darurat minimal 6 bulan.`,
        tone: "gr"
      });
    } else if (dash.profit < 0) {
      recs.push({
        priority: "Koreksi Defisit Bulanan (Prioritas Utama)",
        action: `Defisit ${fmtIDR(Math.abs(dash.profit))} berarti pengeluaran ${fmtIDR(dash.exp)} melampaui pemasukan ${fmtIDR(dash.inc)}. Pangkas kategori terbesar (${(expenseSegments[0]?.name || "-")} sebesar ${fmtIDR(expenseSegments[0]?.amount || 0)}) dan/atau dorong pertumbuhan omzet.`,
        tone: "rd"
      });
    }

    if (dash.expMoM !== null && dash.expMoM > 10) {
      recs.push({
        priority: "Pengendalian Biaya",
        action: `Beban naik +${dash.expMoM.toFixed(1)}% MoM. Tinjau ulang setiap pengeluaran tak terencana dan terapkan sistem persetujuan untuk nominal di atas ambang kategori.`,
        tone: "yl"
      });
    }
    if (dash.margin >= 0 && dash.margin < 20) {
      recs.push({
        priority: "Peningkatan Profitabilitas",
        action: `Margin ${dash.margin.toFixed(1)}% masih tipis. Naikkan tarif/layanan bernilai tambah atau kurangi biaya tetap agar margin > 20%.`,
        tone: "yl"
      });
    }
    overBudgetCats.slice(0, 2).forEach(b => {
      recs.push({
        priority: `Anggaran ${b.name} Melewati Batas`,
        action: `Realisasi ${fmtIDR(b.actual)} sudah ${b.pct.toFixed(0)}% dari target ${fmtIDR(b.target)}. Evaluasi apakah batas perlu direvisi atau perlu pembatasan transaksi kategori ini.`,
        tone: "rd"
      });
    });

    if (recs.length === 0) {
      recs.push({
        priority: "Pertahankan Kondisi Stabil",
        action: `Tidak ada koreksi signifikan. Pertahankan tren pengeluaran dan pertimbangkan menaikkan target tabungan bulan depan.`,
        tone: "gr"
      });
    }
    return recs;
  }, [dash, budgetActual, expenseSegments]);

  // ── Ledger transaksi riil dengan penanda anomali ──
  const transactionFeed = useMemo(() => {
    const list = [
      ...allExpenses.map(e => ({
        id: `EXP-${e.id}`,
        date: (e.date || "").slice(0, 10),
        type: "expense",
        category: e.category || "other",
        description: e.description || "Pengeluaran",
        amount: num(e.amount),
        status: "normal",
        segment: e.payment_method ? `Metode: ${e.payment_method}` : "OpEx / COGS"
      })),
      ...allIncomes.map(i => ({
        id: `INC-${i.id}`,
        date: (i.date || "").slice(0, 10),
        type: "income",
        category: i.income_type || "other",
        description: i.source || i.description || "Pemasukan",
        amount: num(i.amount),
        status: "normal",
        segment: "Pemasukan Riil"
      }))
    ];
    const anomalyIds = new Set(detectedAnomalies.filter(a => a.txId).map(a => a.txId));
    list.forEach(t => { if (anomalyIds.has(t.id)) t.status = "anomaly"; });
    return list.sort((a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id));
  }, [allExpenses, allIncomes, detectedAnomalies]);

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
      incMethod: "Rata-rata pemasukan riil 3 bulan terakhir",
      expMethod: "Total batas anggaran bulan berjalan",
      savMethod: "Rata-rata surplus bersih 3 bulan terakhir (min. 0)"
    };
  }, [trendSeries, budgetMap, dash]);

  const execCondition = useMemo(() => {
    if (dash.profit > 0 && dash.margin >= 20) return { label: "SANGAT SEHAT (OPTIMAL)", tone: "var(--gr)" };
    if (dash.profit > 0) return { label: "SEHAT (STABIL)", tone: "var(--cy)" };
    if (dash.profit === 0) return { label: "IMPAS (NETRAL)", tone: "var(--yl)" };
    return { label: "DEFISIT (BUTUH KOREKSI)", tone: "var(--rd)" };
  }, [dash]);

  const execInsight = useMemo(() => {
    const parts = [];
    if (dash.profit > 0) {
      parts.push(`Bulan ${dash.monthLabel} ditutup dengan net surplus <strong>${fmtIDR(dash.profit)}</strong> dan profit margin <strong>${dash.margin.toFixed(1)}%</strong>.`);
    } else if (dash.profit < 0) {
      parts.push(`Bulan ${dash.monthLabel} ditutup dengan defisit <strong>${fmtIDR(Math.abs(dash.profit))}</strong> — pengeluaran <strong>${fmtIDR(dash.exp)}</strong> melebihi pemasukan <strong>${fmtIDR(dash.inc)}</strong>.`);
    } else {
      parts.push(`Bulan ${dash.monthLabel} tercatat impas (net surplus Rp 0).`);
    }
    if (dash.incMoM !== null) parts.push(`Omzet berubah <strong>${dash.incMoM >= 0 ? "+" : ""}${dash.incMoM.toFixed(1)}%</strong> dibanding bulan sebelumnya.`);
    if (dash.expMoM !== null) parts.push(`Beban biaya <strong>${dash.expMoM <= 0 ? "turun" : "naik"} ${Math.abs(dash.expMoM).toFixed(1)}% MoM</strong>.`);
    if (dash.productivity < 0) parts.push("Indeks produktivitas negatif: setiap Rp 100 biaya menghasilkan kerugian, sehingga prioritas utama adalah pemangkasan beban dan/atau pertumbuhan pemasukan.");
    else if (dash.productivity >= 20) parts.push("Indeks produktivitas positif: setiap Rp 100 biaya menghasilkan keuntungan di atas ambang sehat 20%.");
    else if (dash.inc > 0) parts.push("Indeks produktivitas masih di bawah ambang sehat 20%.");
    return parts.join(" ");
  }, [dash]);

  const tabs = [
    { id: "overview",        label: "Executive Summary" },
    { id: "kpi",             label: "KPI & Metrics" },
    { id: "trends",          label: "Visualisasi & Tren" },
    { id: "target",          label: "Target vs Actual" },
    { id: "segmentation",    label: "Segmentasi" },
    { id: "forecast",        label: "Forecasting" },
    { id: "anomalies",       label: "Anomali & Exception" },
    { id: "recommendations", label: "Rekomendasi" },
    { id: "drilldown",       label: "Drill-down Detail" },
    { id: "methodology",     label: "Metodologi Data" },
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
        ["Total Income", kpi.incomeTarget, dash.inc, kpi.incStatus],
        ["Total Expense Limit", kpi.expenseTarget, dash.exp, kpi.expStatus],
        ["Net Profit / Tabungan", kpi.savingsTarget, dash.profit, kpi.savStatus]
      ].map(([label, target, actual, status]) =>
        `<tr><td>${label}</td><td>${fmtIDR(target)}</td><td>${fmtIDR(actual)}</td><td>${status}</td></tr>`
      ).join("");
      win.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
          <title>Executive BI/BA Report — Alpha Finance</title>
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
          <h1>Executive Performance &amp; BI Analytics Report</h1>
          <p><strong>Periode:</strong> ${dash.monthLabel} | <strong>Generated:</strong> ${new Date().toLocaleDateString('id-ID')} | <strong>Profil:</strong> ${activeProfile?.active || "-"}</p>
          <h2>Ringkasan Eksekutif</h2>
          <p>Omzet Bulan Ini: <strong>${fmtIDR(dash.inc)}</strong> | Total Biaya: <strong>${fmtIDR(dash.exp)}</strong> | Net Surplus: <strong>${fmtIDR(dash.profit)}</strong></p>
          <p>Profit Margin: <strong>${dash.margin.toFixed(1)}%</strong> | Produktivitas: <strong>${dash.productivity.toFixed(1)}%</strong> | Kondisi: <strong>${execCondition.label}</strong></p>

          <h2>Metrik KPI Utilitas</h2>
          <table class="kpi-table">
            <thead>
              <tr><th>Indikator KPI</th><th>Target</th><th>Realisasi</th><th>Status</th></tr>
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
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {trendSeries.map(t => (
          <div key={t.key} style={{ background: "var(--bg3)", padding: 12, borderRadius: 12, border: "1px solid var(--bdr)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6 }}>
              <span style={{ fontWeight: 700 }}>{t.label}</span>
              <span style={{ color: "var(--tx3)" }}>
                Net: <strong style={{ color: t.net >= 0 ? "var(--gr)" : "var(--rd)" }}>{fmtCompact(t.net)}</strong>
              </span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 52, fontSize: 10, color: "var(--tx3)" }}>Income</span>
                <div style={{ flex: 1, background: "var(--bg4)", height: 10, borderRadius: 99, overflow: "hidden" }}>
                  <div style={{ width: `${(t.inc / max) * 100}%`, height: "100%", background: "var(--gr)", borderRadius: 99 }} />
                </div>
                <span style={{ width: 64, textAlign: "right", fontSize: 10, fontFamily: "var(--mono)" }}>{fmtCompact(t.inc)}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ width: 52, fontSize: 10, color: "var(--tx3)" }}>Expense</span>
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
                Business Intelligence &amp; Analytics (BI/BA) Cockpit
              </h1>
              <div style={{ fontSize: 12, color: "var(--tx3)", marginTop: 2 }}>
                Executive Suite — Periode: <strong>{dash.monthLabel}</strong> · Profil: <strong>{activeProfile?.active || "—"}</strong>
              </div>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button className="btn btn-g btn-s" onClick={loadData} disabled={loading} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <IconRefresh size={14} className={loading ? "spin" : ""} /> Refresh
          </button>
          <button className="btn btn-p btn-s" onClick={() => setReportModal(true)} style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 700 }}>
            <IconDownload size={14} /> Export Report (.MD / .HTML / .PDF)
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
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>Total Omzet / Income</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: "var(--gr)", marginTop: 6 }}>{fmtCompact(dash.inc)}</div>
              <div style={{ fontSize: 11, color: dash.incMoM === null ? "var(--tx3)" : (dash.incMoM >= 0 ? "var(--gr)" : "var(--rd)"), marginTop: 4 }}>
                {dash.incMoM === null ? "MoM: N/A (tidak ada data bulan sebelumnya)" : `${dash.incMoM >= 0 ? "+" : ""}${dash.incMoM.toFixed(1)}% MoM`}
              </div>
            </div>
            <div style={{ background: "var(--bg2)", borderLeft: "4px solid var(--yl)", borderRadius: 14, padding: 18, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>Total Biaya / Expense</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: "var(--yl)", marginTop: 6 }}>{fmtCompact(dash.exp)}</div>
              <div style={{ fontSize: 11, color: dash.expMoM === null ? "var(--tx3)" : (dash.expMoM <= 0 ? "var(--gr)" : "var(--rd)"), marginTop: 4 }}>
                {dash.expMoM === null ? "MoM: N/A (tidak ada data bulan sebelumnya)" : `${dash.expMoM <= 0 ? "-" : "+"}${Math.abs(dash.expMoM).toFixed(1)}% MoM ${dash.expMoM <= 0 ? "(Efisiensi)" : ""}`}
              </div>
            </div>
            <div style={{ background: "var(--bg2)", borderLeft: "4px solid var(--cy)", borderRadius: 14, padding: 18, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>Net Profit / Surplus</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: dash.profit >= 0 ? "var(--cy)" : "var(--rd)", marginTop: 6 }}>{fmtCompact(dash.profit)}</div>
              <div style={{ fontSize: 11, color: "var(--tx2)", marginTop: 4 }}>Margin: {dash.margin.toFixed(1)}%</div>
            </div>
            <div style={{ background: "var(--bg2)", borderLeft: "4px solid var(--pu)", borderRadius: 14, padding: 18, border: "1px solid var(--bdr)" }}>
              <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--tx3)", fontWeight: 700 }}>Indeks Produktivitas</div>
              <div style={{ fontSize: 22, fontWeight: 900, fontFamily: "var(--mono)", color: dash.productivity >= 0 ? "var(--pu)" : "var(--rd)", marginTop: 6 }}>{dash.productivity.toFixed(1)}%</div>
              <div style={{ fontSize: 11, color: "var(--tx3)", marginTop: 4 }}>Hasil per 100 Biaya</div>
            </div>
          </div>

          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Executive Insight &amp; Kondisi Bisnis</h3>
            <p style={{ fontSize: 13, color: "var(--tx2)", lineHeight: 1.6 }}>
              Kondisi bulan <strong>{dash.monthLabel}</strong>: <strong style={{ color: execCondition.tone }}>{execCondition.label}</strong>.{" "}
              <span dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(execInsight) }} />
            </p>
          </div>
        </div>
      )}

      {/* 2. KPI & METRICS */}
      {activeTab === "kpi" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 16 }}>Matriks Key Performance Indicators (KPI)</h3>
          <p style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 16 }}>
            Target dihitung dari data riil ({kpi.incMethod}; {kpi.expMethod}; {kpi.savMethod}). Periode: {dash.monthLabel}.
          </p>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--bdr)", color: "var(--tx3)", textTransform: "uppercase" }}>
                  <th style={{ padding: "10px" }}>Indikator KPI</th>
                  <th style={{ padding: "10px" }}>Target</th>
                  <th style={{ padding: "10px" }}>Realisasi</th>
                  <th style={{ padding: "10px" }}>Deviasi</th>
                  <th style={{ padding: "10px" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: "1px solid var(--bdr)" }}>
                  <td style={{ padding: "12px 10px", fontWeight: 700 }}>Total Omzet (Income)</td>
                  <td style={{ padding: "12px 10px", color: "var(--tx3)" }}>{fmtIDR(kpi.incomeTarget)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 800, color: "var(--gr)" }}>{fmtIDR(dash.inc)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 700, color: kpi.incDev >= 0 ? "var(--gr)" : "var(--rd)" }}>
                    {kpi.incDev >= 0 ? "+" : ""}{kpi.incDev.toFixed(1)}%
                  </td>
                  <td style={{ padding: "12px 10px" }}>{statusPill(kpi.incStatus)}</td>
                </tr>
                <tr style={{ borderBottom: "1px solid var(--bdr)" }}>
                  <td style={{ padding: "12px 10px", fontWeight: 700 }}>Batas Pengeluaran (Expense)</td>
                  <td style={{ padding: "12px 10px", color: "var(--tx3)" }}>{fmtIDR(kpi.expenseTarget)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 800, color: "var(--yl)" }}>{fmtIDR(dash.exp)}</td>
                  <td style={{ padding: "12px 10px", fontWeight: 700, color: kpi.expDev <= 0 ? "var(--gr)" : "var(--rd)" }}>
                    {kpi.expDev >= 0 ? "+" : ""}{kpi.expDev.toFixed(1)}% {kpi.expDev <= 0 ? "(Hemat)" : ""}
                  </td>
                  <td style={{ padding: "12px 10px" }}>{statusPill(kpi.expStatus)}</td>
                </tr>
                <tr style={{ borderBottom: "1px solid var(--bdr)" }}>
                  <td style={{ padding: "12px 10px", fontWeight: 700 }}>Net Profit / Savings</td>
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
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Tren Bulanan Income vs Expense (Data Riil)</h3>
            {renderTrendBars()}
          </div>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Heatmap Intensitas Belanja Harian (W1–W4) — {dash.monthLabel}</h3>
            {heatmapData.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--tx3)" }}>Belum ada transaksi pengeluaran pada periode {dash.monthLabel}.</p>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, textAlign: "center" }}>
                  <thead>
                    <tr style={{ borderBottom: "1px solid var(--bdr)", color: "var(--tx3)" }}>
                      <th style={{ padding: 10, textAlign: "left" }}>Hari</th>
                      <th style={{ padding: 10 }}>Minggu 1</th>
                      <th style={{ padding: 10 }}>Minggu 2</th>
                      <th style={{ padding: 10 }}>Minggu 3</th>
                      <th style={{ padding: 10 }}>Minggu 4</th>
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
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 16 }}>Evaluasi Target Anggaran per Kategori — {dash.monthLabel}</h3>
          {budgetActual.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>Belum ada skema anggaran untuk periode ini.</p>
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
                        Realisasi: <strong style={{ color: isOver ? "var(--rd)" : pct >= 80 ? "var(--yl)" : "var(--gr)" }}>{fmtIDR(c.actual)}</strong> / {fmtIDR(c.target)} ({pct.toFixed(1)}%)
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
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Segmentasi Sumber Pendapatan — {dash.monthLabel}</h3>
            {incomeSegments.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--tx3)" }}>Tidak ada pemasukan riil pada periode ini.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {incomeSegments.map(s => (
                  <div key={s.name} style={{ background: "var(--bg3)", padding: 12, borderRadius: 10, display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>{s.name}</div>
                      <div style={{ fontSize: 10, color: "var(--tx3)" }}>{s.pct.toFixed(1)}% dari total</div>
                    </div>
                    <div style={{ fontWeight: 800, color: "var(--gr)" }}>{fmtIDR(s.amount)}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Segmentasi Pengeluaran per Kategori — {dash.monthLabel}</h3>
            {expenseSegments.length === 0 ? (
              <p style={{ fontSize: 12, color: "var(--tx3)" }}>Tidak ada pengeluaran pada periode ini.</p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {expenseSegments.map(s => (
                  <div key={s.name} style={{ background: "var(--bg3)", padding: 12, borderRadius: 10, display: "flex", justifyContent: "space-between", fontSize: 12 }}>
                    <div>
                      <div style={{ fontWeight: 700 }}>{s.name}</div>
                      <div style={{ fontSize: 10, color: "var(--tx3)" }}>{s.pct.toFixed(1)}% dari total</div>
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
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Proyeksi Performansi 3 Bulan Ke Depan</h3>
          <p style={{ fontSize: 11, color: "var(--tx3)", marginBottom: 16 }}>
            Proyeksi berdasarkan regresi linear atas tren riil {trendSeries.length} bulan terakhir (pemasukan tanpa transfer).
          </p>
          {forecastData.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>Data histori belum cukup untuk memproyeksikan tren.</p>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
              {forecastData.map(f => (
                <div key={f.label} style={{ background: "var(--bg3)", padding: 14, borderRadius: 12, border: "1px solid var(--bdr)" }}>
                  <div style={{ fontSize: 11, color: "var(--tx3)", fontWeight: 700 }}>{f.label}</div>
                  <div style={{ fontSize: 14, fontWeight: 800, color: "var(--gr)", marginTop: 4 }}>
                    Omzet: {f.inc === null ? "N/A" : fmtCompact(f.inc)}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--yl)", marginTop: 2 }}>
                    Biaya: {f.exp === null ? "N/A" : fmtCompact(f.exp)}
                  </div>
                  <div style={{ fontSize: 12, marginTop: 2, fontWeight: 700, color: f.net === null ? "var(--tx3)" : (f.net >= 0 ? "var(--cy)" : "var(--rd)") }}>
                    Net: {f.net === null ? "N/A" : fmtCompact(f.net)}
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
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12, color: "var(--rd)" }}>Deteksi Anomali &amp; Exception Analysis</h3>
          {detectedAnomalies.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>Semua transaksi dalam batas normal (tidak ada anomali statistik terdeteksi).</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {detectedAnomalies.map((a, i) => (
                <div key={i} style={{
                  background: a.severity === "critical" ? "rgba(239,68,68,.1)" : "rgba(245,158,11,.08)",
                  border: a.severity === "critical" ? "1px solid rgba(239,68,68,.35)" : "1px solid rgba(245,158,11,.25)",
                  borderRadius: 12, padding: 14
                }}>
                  <div style={{ fontWeight: 700, color: a.severity === "critical" ? "var(--rd)" : "var(--yl)", fontSize: 13 }}>
                    {a.severity === "critical" ? "CRITICAL: " : "HIGH: "}{a.title}
                  </div>
                  <div style={{ fontSize: 11, color: "var(--tx2)", marginTop: 4 }}>{a.detail}</div>
                  <div style={{ fontSize: 10, color: "var(--tx3)", marginTop: 4 }}>Periode: {a.date} {a.txId ? `| ID: ${a.txId}` : ""}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 8. REKOMENDASI */}
      {activeTab === "recommendations" && (
        <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 16, padding: 20 }}>
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Rekomendasi Tindakan Terstruktur</h3>
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
            <h3 style={{ fontSize: 15, fontWeight: 800 }}>Drill-down Transaksi Level Mikro</h3>
            <input
              type="text"
              placeholder="Cari transaksi..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{ background: "var(--bg3)", border: "1px solid var(--bdr)", borderRadius: 8, padding: "6px 12px", color: "var(--tx)", fontSize: 12 }}
            />
          </div>
          {transactionFeed.length === 0 ? (
            <p style={{ fontSize: 12, color: "var(--tx3)" }}>Belum ada transaksi untuk ditampilkan.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, textAlign: "left" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--bdr)", color: "var(--tx3)" }}>
                    <th style={{ padding: 8 }}>ID/Tanggal</th>
                    <th style={{ padding: 8 }}>Tipe</th>
                    <th style={{ padding: 8 }}>Deskripsi &amp; Segment</th>
                    <th style={{ padding: 8 }}>Status</th>
                    <th style={{ padding: 8, textAlign: "right" }}>Jumlah</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTx.map(t => (
                    <tr key={t.id} style={{ borderBottom: "1px solid var(--bdr)" }}>
                      <td style={{ padding: 8, fontFamily: "var(--mono)" }}><strong>{t.id}</strong><div style={{ color: "var(--tx3)", fontSize: 10 }}>{t.date}</div></td>
                      <td style={{ padding: 8 }}><span className={`pill ${t.type === "income" ? "g" : "r"}`}>{t.type}</span></td>
                      <td style={{ padding: 8 }}><strong>{t.description}</strong><div style={{ color: "var(--tx3)", fontSize: 10 }}>{t.segment}</div></td>
                      <td style={{ padding: 8 }}>
                        {t.status === "anomaly"
                          ? <span className="pill r">ANOMALY</span>
                          : <span className="pill g">NORMAL</span>}
                      </td>
                      <td style={{ padding: 8, textAlign: "right", fontWeight: 700, fontFamily: "var(--mono)", color: t.type === "income" ? "var(--gr)" : "var(--tx)" }}>
                        {t.type === "income" ? "+" : "-"}{fmtIDR(t.amount)}
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
          <h3 style={{ fontSize: 15, fontWeight: 800, marginBottom: 12 }}>Sumber Data &amp; Metodologi KPI</h3>
          <div style={{ fontSize: 12, color: "var(--tx2)", lineHeight: 1.8 }}>
            <p>
              Seluruh angka dihitung dari data riil skema PostgreSQL profile aktif: <strong>{activeProfile?.active || "—"}</strong>
              {activeProfile?.active_type ? ` (tipe: ${activeProfile.active_type})` : ""}.
            </p>
            <ul style={{ paddingLeft: 18, display: "flex", flexDirection: "column", gap: 4 }}>
              <li><strong>Ringkasan / MoM:</strong> `/api/dashboard` (total_this &amp; total_prev); pemasukan tidak termasuk transfer, konsisten dengan repositori income.</li>
              <li><strong>KPI:</strong> Target omzet = rata-rata pemasukan riil 3 bulan terakhir; target pengeluaran = total batas anggaran bulan berjalan; target tabungan = rata-rata surplus 3 bulan terakhir (min. 0). Status: Income ≥100% EXCEEDED / ≥90% ON TRACK / sisanya BEHIND; Expense ≤100% ON TRACK / ≤115% WARNING / &gt;115% OVER BUDGET; Savings ≥100% OPTIMAL / ≥0 MODERATE / &lt;0 DEFICIT.</li>
              <li><strong>Tren:</strong> Grup transaksi riil per bulan (`/expenses`, `/income`).</li>
              <li><strong>Heatmap:</strong> Agregasi transaksi pengeluaran periode terpilih per hari &amp; minggu (W1–W4).</li>
              <li><strong>Target vs Actual:</strong> `/expenses/budget/{'{tahun}'}/{'{bulan}'}` per kategori.</li>
              <li><strong>Segmentasi:</strong> Agregasi item riil per sumber pemasukan dan per kategori pengeluaran.</li>
              <li><strong>Forecast:</strong> Regresi linear atas tren 3 bulan ke depan (pemasukan &amp; pengeluaran); fallback `/analytics/expense-prediction` bila tersedia.</li>
              <li><strong>Anomali:</strong> Deteksi statistik Z-score &gt; 2.2σ dan outlier IQR (Q3 + 1.5×IQR) per kategori, plus pemicu makro (kenaikan biaya MoM &gt; 20% dan defisit bulanan).</li>
              <li><strong>Rekomendasi:</strong> Aturan berbasis metrik riil (surplus/defisit, kenaikan MoM, kategori melewati anggaran, margin).</li>
              <li><strong>Drill-down:</strong> Seluruh item `/expenses` dan `/income` (limit 1000) dengan penanda anomali.</li>
            </ul>
          </div>
        </div>
      )}

      {/* Export Report Modal */}
      {reportModal && (
        <div style={{ position: "fixed", inset: 0, zIndex: 3000, background: "rgba(0,0,0,0.6)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}>
          <div style={{ background: "var(--bg2)", border: "1px solid var(--bdr)", borderRadius: 20, width: "100%", maxWidth: 500, padding: 24 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
              <h3 style={{ fontSize: 16, fontWeight: 900, margin: 0 }}>Export Executive Report</h3>
              <button className="btn btn-g btn-s" onClick={() => setReportModal(false)}><IconClose size={14} /></button>
            </div>
            <p style={{ fontSize: 12, color: "var(--tx2)", marginBottom: 20 }}>Pilih format laporan yang ingin di-download:</p>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <button className="btn btn-p" onClick={() => { handleDownloadFile("md", `# Executive Report\n\n- Periode: ${dash.monthLabel}\n- Omzet: ${fmtIDR(dash.inc)}\n- Biaya: ${fmtIDR(dash.exp)}\n- Net Profit: ${fmtIDR(dash.profit)}\n- Margin: ${dash.margin.toFixed(1)}%\n- Kondisi: ${execCondition.label}\n- KPI Target: ${fmtIDR(kpi.incomeTarget)} / ${fmtIDR(kpi.expenseTarget)} / ${fmtIDR(kpi.savingsTarget)}`, "text/markdown"); setReportModal(false); }}>
                Download .MD (Markdown File)
              </button>
              <button className="btn btn-g" onClick={() => { handleDownloadFile("html", `<html><body><h1>Executive Report</h1><p>Periode: ${dash.monthLabel}</p><p>Omzet: ${fmtIDR(dash.inc)}</p><p>Biaya: ${fmtIDR(dash.exp)}</p><p>Net: ${fmtIDR(dash.profit)}</p></body></html>`, "text/html"); setReportModal(false); }}>
                Download .HTML (Printable Web)
              </button>
              <button className="btn btn-g" onClick={() => { handlePrintPDF(); setReportModal(false); }}>
                Download / Print .PDF Document
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

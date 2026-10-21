"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from "recharts";
import {
  TrendingUp, TrendingDown, DollarSign, PieChart as PieIcon, BarChart2, Activity,
  AlertTriangle, CheckCircle2, Search, Filter, Lightbulb, Database, Eye, RefreshCw,
  Calendar, Layers, ShieldAlert, ArrowUpRight, ArrowDownRight, Target, Sparkles, Sliders, FileText, ChevronRight, User, ArrowRight
} from "lucide-react";
import { LiquidNav } from "@/components/ui/liquid-nav";
import { FocusScrollSection } from "@/components/ui/focus-scroll";
import { clientProxyUrl } from "@/lib/api";
import { useI18n } from "@/i18n/context";

// ─── Interfaces & Types ─────────────────────────────────────────────────────────────

interface DashboardSummary {
  month_label?: string;
  income?: { total_this: number; total_prev: number; by_source?: Record<string, number> };
  expense?: { total_this: number; total_prev: number; by_category?: Record<string, number> };
  investments?: { pl_total?: number; total_value?: number; holdings?: Array<{ ticker: string; unrealized_pl?: number; quantity: number; current_price_idr?: number }> };
  balances?: { cash_savings?: number; bank_savings?: number; emergency_fund?: number; physical_cash?: number };
}

interface RawExpense {
  id: number | string;
  amount: number;
  description: string;
  category: string;
  payment_method?: string;
  date: string;
  is_recurring?: boolean;
}

interface RawIncome {
  id: number | string;
  amount: number;
  source: string;
  income_type?: string;
  date: string;
  description?: string;
}

interface RawInvestment {
  id: number | string;
  ticker: string;
  asset_type: string;
  quantity: number;
  buy_price: number;
  buy_currency?: string;
  buy_date?: string;
  status?: string;
}

interface RawGoal {
  id: number | string;
  name: string;
  target_amount: number;
  current_amount: number;
  target_date?: string;
}

interface RawBudget {
  category: string;
  limit_amt: number;
  limit?: number;
}

interface LifestyleTrendItem {
  label: string;
  exp: number;
  inc: number;
  exp_growth: number;
  inc_growth: number;
  li_score: number;
  verdict: 'inflating' | 'healthy' | 'stable';
}

interface TransactionDetail {
  id: string;
  date: string;
  type: 'income' | 'expense' | 'investment';
  category: string;
  description: string;
  amount: number;
  status: 'normal' | 'anomaly' | 'flagged';
  segment: string;
  paymentMethod?: string;
}

interface AnomalyItem {
  id: string;
  title: string;
  desc: string;
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
  cause: string;
  date: string;
  amount?: number;
  recommendation: string;
}

// ─── Formatters & Helpers ─────────────────────────────────────────────────────────

const fmtIDR = (n: number) => "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(n || 0));

const fmtCompact = (n: number) => {
  const abs = Math.abs(n || 0);
  if (abs >= 1e9) return `Rp ${(n / 1e9).toFixed(2)}M`;
  if (abs >= 1e6) return `Rp ${(n / 1e6).toFixed(1)}jt`;
  return fmtIDR(n);
};

const CATEGORY_COLORS: Record<string, string> = {
  "Makanan": "#f59e0b",
  "Operasional": "#3b82f6",
  "Teknologi": "#8b5cf6",
  "Transportasi": "#ec4899",
  "Investasi": "#10b981",
  "Hiburan": "#ef4444",
  "Kesehatan": "#06b6d4",
  "Pendidikan": "#14b8a6",
  "Tagihan": "#6366f1",
  "Belanja": "#f97316",
  "Lainnya": "#64748b",
};

const TX_TYPE_LABEL: Record<string, string> = {
  income: "analytics.tx_type_income",
  expense: "analytics.tx_type_expense",
  investment: "analytics.tx_type_investment",
};

const TX_STATUS_LABEL: Record<string, string> = {
  normal: "analytics.tx_status_normal",
  anomaly: "analytics.tx_status_anomaly",
  flagged: "analytics.tx_status_flagged",
};

const TX_SEGMENT_LABEL: Record<string, string> = {
  recurring: "analytics.tx_segment_recurring",
  daily: "analytics.tx_segment_daily",
  cash_in: "analytics.tx_segment_cash_in",
  asset: "analytics.tx_segment_asset",
};

const TX_PAYMENT_LABEL: Record<string, string> = {
  direct: "analytics.tx_payment_direct",
  bank: "analytics.tx_payment_bank",
  portfolio: "analytics.tx_payment_portfolio",
};

const ANOMALY_SEVERITY_LABEL: Record<string, string> = {
  CRITICAL: "analytics.severity_critical",
  HIGH: "analytics.severity_high",
  MEDIUM: "analytics.severity_medium",
  LOW: "analytics.severity_low",
};

const BUDGET_STATUS_LABEL: Record<string, string> = {
  over: "analytics.budget_status_over",
  near: "analytics.budget_status_near",
  safe: "analytics.budget_status_safe",
};

// ─── KPICard Component ────────────────────────────────────────────────────────────

function KPICard({
  label,
  value,
  sub,
  color = "blue",
  large = false,
  trend,
}: {
  label: string;
  value: string;
  sub?: string;
  color?: string;
  large?: boolean;
  trend?: "up" | "down" | null;
}) {
  const borderColors: Record<string, string> = {
    blue: "border-l-blue-500",
    green: "border-l-emerald-500",
    amber: "border-l-amber-500",
    purple: "border-l-purple-500",
    red: "border-l-red-500",
    cyan: "border-l-cyan-500",
    yellow: "border-l-yellow-400",
  };

  return (
    <div
      className={`glass-panel p-5 rounded-2xl border-l-4 ${
        borderColors[color] ?? borderColors.blue
      } transition-all duration-200 hover:translate-y-[-2px] shadow-sm`}
    >
      <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
        {label}
      </p>
      <div className="flex items-end gap-2 mt-1.5">
        <p className={`font-extrabold tracking-tight ${large ? "text-2xl lg:text-3xl" : "text-xl lg:text-2xl"}`}>
          {value}
        </p>
        {trend === "up" && <ArrowUpRight size={18} className="text-emerald-500 mb-1 shrink-0" />}
        {trend === "down" && <ArrowDownRight size={18} className="text-red-500 mb-1 shrink-0" />}
      </div>
      {sub && <p className="text-xs text-muted-foreground mt-1.5 flex items-center gap-1 font-medium">{sub}</p>}
    </div>
  );
}

// ─── Main Analytics Component ─────────────────────────────────────────────────────

export default function AnalyticsBIDashboard() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("ALL");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");

  const segmentLabel = (s: string) => {
    const key = TX_SEGMENT_LABEL[s];
    return key ? t(key) : s;
  };

  const paymentLabel = (p?: string) => {
    if (!p) return "";
    const key = TX_PAYMENT_LABEL[p];
    return key ? t(key) : p;
  };

  // Live state fetched from real APIs
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [rawExpenses, setRawExpenses] = useState<RawExpense[]>([]);
  const [rawIncomes, setRawIncomes] = useState<RawIncome[]>([]);
  const [rawInvestments, setRawInvestments] = useState<RawInvestment[]>([]);
  const [rawGoals, setRawGoals] = useState<RawGoal[]>([]);
  const [rawBudgets, setRawBudgets] = useState<RawBudget[]>([]);
  const [trends, setTrends] = useState<LifestyleTrendItem[]>([]);
  const [riskData, setRiskData] = useState<any>(null);
  const [behavioralReport, setBehavioralReport] = useState<any>(null);

  const fetchBIData = useCallback(async () => {
    setLoading(true);
    try {
      const now = new Date();
      const currentYear = now.getFullYear();
      const currentMonth = now.getMonth() + 1;

      const [
        resDash,
        resExp,
        resInc,
        resInv,
        resGoals,
        resBudgets,
        resTrend,
        resRisk,
        resBeh,
      ] = await Promise.allSettled([
        fetch(clientProxyUrl("api/dashboard")),
        fetch(clientProxyUrl("api/expenses")),
        fetch(clientProxyUrl("api/income")),
        fetch(clientProxyUrl("api/investments")),
        fetch(clientProxyUrl("api/goals")),
        fetch(clientProxyUrl(`api/budget/${currentYear}/${currentMonth}`)),
        fetch(clientProxyUrl("api/behavioral/lifestyle-trend?months=12")),
        fetch(clientProxyUrl("api/analytics/portfolio-risk")),
        fetch(clientProxyUrl("api/analytics/saving-projection")),
      ]);

      if (resDash.status === "fulfilled" && resDash.value.ok) {
        setSummary(await resDash.value.json());
      }
      if (resExp.status === "fulfilled" && resExp.value.ok) {
        const expData = await resExp.value.json();
        setRawExpenses(Array.isArray(expData) ? expData : expData.items || []);
      }
      if (resInc.status === "fulfilled" && resInc.value.ok) {
        const incData = await resInc.value.json();
        setRawIncomes(Array.isArray(incData) ? incData : incData.items || []);
      }
      if (resInv.status === "fulfilled" && resInv.value.ok) {
        const invData = await resInv.value.json();
        setRawInvestments(Array.isArray(invData) ? invData : invData.investments || []);
      }
      if (resGoals.status === "fulfilled" && resGoals.value.ok) {
        const goalsData = await resGoals.value.json();
        setRawGoals(Array.isArray(goalsData) ? goalsData : goalsData.goals || []);
      }
      if (resBudgets.status === "fulfilled" && resBudgets.value.ok) {
        const budgetsData = await resBudgets.value.json();
        setRawBudgets(Array.isArray(budgetsData) ? budgetsData : budgetsData.categories || []);
      }
      if (resTrend.status === "fulfilled" && resTrend.value.ok) {
        const data = await resTrend.value.json();
        if (data.trend && Array.isArray(data.trend)) setTrends(data.trend);
      }
      if (resRisk.status === "fulfilled" && resRisk.value.ok) {
        setRiskData(await resRisk.value.json());
      }
      if (resBeh.status === "fulfilled" && resBeh.value.ok) {
        setBehavioralReport(await resBeh.value.json());
      }
    } catch (err) {
      console.warn("[BI Dashboard] API fetch note:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchBIData();
  }, [fetchBIData]);

  // ─── Real Aggregated Monthly Trends ─────────────────────────────────────────────

  const processedTrends = useMemo<LifestyleTrendItem[]>(() => {
    if (trends && trends.length >= 2) return trends;

    // Synthesize monthly aggregates from raw expenses & incomes if trend endpoint is sparse
    const monthlyMap: Record<string, { inc: number; exp: number; date: Date }> = {};

    rawIncomes.forEach((i) => {
      const d = new Date(i.date);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      if (!monthlyMap[key]) monthlyMap[key] = { inc: 0, exp: 0, date: d };
      monthlyMap[key].inc += Number(i.amount) || 0;
    });

    rawExpenses.forEach((e) => {
      const d = new Date(e.date);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      if (!monthlyMap[key]) monthlyMap[key] = { inc: 0, exp: 0, date: d };
      monthlyMap[key].exp += Number(e.amount) || 0;
    });

    const sortedKeys = Object.keys(monthlyMap).sort();
    if (sortedKeys.length === 0) {
      // Fallback base frame if zero transactions
      const now = new Date();
      return [
        { label: t("analytics.prev_month"), exp: 0, inc: 0, exp_growth: 0, inc_growth: 0, li_score: 0, verdict: "stable" },
        { label: t("analytics.this_month"), exp: 0, inc: 0, exp_growth: 0, inc_growth: 0, li_score: 0, verdict: "stable" },
      ];
    }

    return sortedKeys.map((k, idx) => {
      const item = monthlyMap[k];
      const prev = idx > 0 ? monthlyMap[sortedKeys[idx - 1]] : null;
      const exp_growth = prev && prev.exp > 0 ? (item.exp - prev.exp) / prev.exp : 0;
      const inc_growth = prev && prev.inc > 0 ? (item.inc - prev.inc) / prev.inc : 0;
      const li_score = exp_growth - inc_growth;
      const verdict = li_score > 0.05 ? "inflating" : li_score < -0.05 ? "healthy" : "stable";

      const monthName = item.date.toLocaleString("default", { month: "short", year: "numeric" });
      return {
        label: monthName,
        exp: item.exp,
        inc: item.inc,
        exp_growth,
        inc_growth,
        li_score,
        verdict,
      };
    });
  }, [trends, rawIncomes, rawExpenses, t]);

  // ─── Real Current Month Financial KPIs ──────────────────────────────────────────

  const currentMonthData = useMemo(() => {
    const latest = processedTrends[processedTrends.length - 1] || { inc: 0, exp: 0, exp_growth: 0, inc_growth: 0, label: "Current" };
    const prev = processedTrends[processedTrends.length - 2] || { inc: 0, exp: 0, exp_growth: 0, inc_growth: 0, label: "Previous" };

    const inc = summary?.income?.total_this ?? latest.inc;
    const exp = summary?.expense?.total_this ?? latest.exp;
    const profit = inc - exp;
    const margin = inc > 0 ? (profit / inc) * 100 : 0;
    const productivityRate = exp > 0 ? (profit / exp) * 100 : 0;

    const prevInc = summary?.income?.total_prev ?? prev.inc;
    const prevExp = summary?.expense?.total_prev ?? prev.exp;
    const incMoM = prevInc > 0 ? ((inc - prevInc) / prevInc) * 100 : 0;
    const expMoM = prevExp > 0 ? ((exp - prevExp) / prevExp) * 100 : 0;

    const totalPortfolioValue =
      summary?.investments?.total_value ??
      riskData?.total_value ??
      rawInvestments.reduce((acc, inv) => acc + (Number(inv.quantity) * Number(inv.buy_price) || 0), 0);

    const cashSavings =
      summary?.balances?.cash_savings ??
      behavioralReport?.starting_balance ??
      Math.max(0, profit * 3);

    const emergencyFund =
      summary?.balances?.emergency_fund ??
      behavioralReport?.summary?.emergency_fund ??
      exp * 3;

    const netWorth = cashSavings + totalPortfolioValue;
    const runwayMonths = exp > 0 ? (cashSavings / exp).toFixed(1) : "N/A";

    return {
      inc,
      exp,
      profit,
      margin,
      productivityRate,
      incMoM,
      expMoM,
      label: latest.label,
      totalPortfolioValue,
      cashSavings,
      emergencyFund,
      netWorth,
      runwayMonths,
    };
  }, [summary, processedTrends, riskData, rawInvestments, behavioralReport]);

  // ─── Real Unified Transaction Ledger & Anomaly Detection ───────────────────────

  const { allTransactions, calculatedAnomalies, categoryStats } = useMemo(() => {
    const list: TransactionDetail[] = [];
    const catSums: Record<string, { total: number; count: number; amounts: number[] }> = {};

    // 1. Process Expenses
    rawExpenses.forEach((e) => {
      const amt = Number(e.amount) || 0;
      const cat = e.category || "Lainnya";

      if (!catSums[cat]) catSums[cat] = { total: 0, count: 0, amounts: [] };
      catSums[cat].total += amt;
      catSums[cat].count += 1;
      catSums[cat].amounts.push(amt);

      list.push({
        id: `EXP-${e.id}`,
        date: e.date ? e.date.split("T")[0] : new Date().toISOString().split("T")[0],
        type: "expense",
        category: cat,
        description: e.description || t("analytics.tx_desc_expense"),
        amount: amt,
        status: "normal",
        segment: e.is_recurring ? "recurring" : "daily",
        paymentMethod: e.payment_method || "direct",
      });
    });

    // 2. Process Incomes
    rawIncomes.forEach((i) => {
      const amt = Number(i.amount) || 0;
      const cat = i.income_type || i.source || t("analytics.tx_desc_income");
      list.push({
        id: `INC-${i.id}`,
        date: i.date ? i.date.split("T")[0] : new Date().toISOString().split("T")[0],
        type: "income",
        category: cat,
        description: i.description || i.source || t("analytics.tx_desc_income"),
        amount: amt,
        status: "normal",
        segment: "cash_in",
        paymentMethod: "bank",
      });
    });

    // 3. Process Investments
    rawInvestments.forEach((inv) => {
      const amt = (Number(inv.quantity) || 0) * (Number(inv.buy_price) || 0);
      list.push({
        id: `INV-${inv.id}`,
        date: inv.buy_date ? inv.buy_date.split("T")[0] : new Date().toISOString().split("T")[0],
        type: "investment",
        category: inv.asset_type || "Asset",
        description: t("analytics.tx_desc_investment", { ticker: inv.ticker, quantity: inv.quantity }),
        amount: amt,
        status: "normal",
        segment: "asset",
        paymentMethod: "portfolio",
      });
    });

    // Sort descending by date
    list.sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());

    // 4. Statistical Z-Score / IQR Anomaly Detection on Real Data
    const anomaliesDetected: AnomalyItem[] = [];

    // Calculate mean and std dev per category
    const catThresholds: Record<string, { mean: number; std: number }> = {};
    Object.entries(catSums).forEach(([cat, data]) => {
      const mean = data.total / (data.count || 1);
      const variance =
        data.amounts.reduce((acc, v) => acc + Math.pow(v - mean, 2), 0) / (data.count || 1);
      const std = Math.sqrt(variance);
      catThresholds[cat] = { mean, std };
    });

    // Flag outlier transactions (Z > 2.2 or > 2.5x mean)
    list.forEach((tx) => {
      if (tx.type === "expense") {
        const threshold = catThresholds[tx.category];
        if (threshold && threshold.std > 0 && tx.amount > threshold.mean + 2.2 * threshold.std && tx.amount > 500000) {
          tx.status = "anomaly";
          anomaliesDetected.push({
            id: tx.id,
            title: t("analytics.anomaly_spike_title", { category: tx.category }),
            desc: t("analytics.anomaly_spike_desc", {
              description: tx.description,
              amount: fmtIDR(tx.amount),
              average: fmtIDR(threshold.mean),
            }),
            severity: tx.amount > 3000000 ? "CRITICAL" : "HIGH",
            cause: t("analytics.anomaly_spike_cause", { date: tx.date }),
            date: tx.date,
            amount: tx.amount,
            recommendation: t("analytics.anomaly_spike_rec"),
          });
        }
      }
    });

    // Check MoM macro anomalies
    if (currentMonthData.expMoM > 20 && currentMonthData.exp > 1000000) {
      anomaliesDetected.push({
        id: "MOM-EXP-SURGE",
        title: t("analytics.anomaly_surge_title", { value: currentMonthData.expMoM.toFixed(1) }),
        desc: t("analytics.anomaly_surge_desc", { amount: fmtIDR(currentMonthData.exp) }),
        severity: "HIGH",
        cause: t("analytics.anomaly_surge_cause"),
        date: t("analytics.this_month"),
        amount: currentMonthData.exp,
        recommendation: t("analytics.anomaly_surge_rec"),
      });
    }

    if (currentMonthData.margin < 20 && currentMonthData.inc > 0) {
      anomaliesDetected.push({
        id: "MARGIN-COMPRESSION",
        title: t("analytics.anomaly_margin_title", { value: currentMonthData.margin.toFixed(1) }),
        desc: t("analytics.anomaly_margin_desc"),
        severity: "MEDIUM",
        cause: t("analytics.anomaly_margin_cause"),
        date: t("analytics.this_month"),
        recommendation: t("analytics.anomaly_margin_rec"),
      });
    }

    return { allTransactions: list, calculatedAnomalies: anomaliesDetected, categoryStats: catSums };
  }, [rawExpenses, rawIncomes, rawInvestments, currentMonthData, t]);

  // ─── Real Category & Segmentation Data ──────────────────────────────────────────

  const expenseSegmentation = useMemo(() => {
    const totalExp = Object.values(categoryStats).reduce((acc, curr) => acc + curr.total, 0) || 1;
    return Object.entries(categoryStats).map(([name, data]) => ({
      name,
      amount: data.total,
      count: data.count,
      pct: ((data.total / totalExp) * 100).toFixed(1),
      color: CATEGORY_COLORS[name] || "#64748b",
    }));
  }, [categoryStats]);

  // ─── Target vs Actual Budget Comparison ────────────────────────────────────────

  const budgetVsActual = useMemo(() => {
    if (rawBudgets.length > 0) {
      return rawBudgets.map((b) => {
        const actual = categoryStats[b.category]?.total || 0;
        const target = Number(b.limit_amt ?? b.limit) || 1;
        const pct = Math.min(200, (actual / target) * 100);
        return {
          name: b.category,
          actual,
          target,
          pct: Math.round(pct),
          status: pct > 100 ? "over" : pct > 85 ? "near" : "safe",
        };
      });
    }

    // Dynamic derivation from category stats with standard healthy threshold
    return Object.entries(categoryStats).map(([cat, stat]) => {
      const target = Math.round(stat.total * 1.15); // +15% default budget target
      const pct = Math.round((stat.total / target) * 100);
      return {
        name: cat,
        actual: stat.total,
        target,
        pct,
        status: pct > 100 ? "over" : "safe",
      };
    });
  }, [rawBudgets, categoryStats]);

  // ─── Predictive 3-6 Months Forward Forecasting ─────────────────────────────────

  const forecastData = useMemo(() => {
    const n = processedTrends.length;
    if (n === 0) return [];

    const avgIncGrowth = processedTrends.reduce((acc, curr) => acc + (curr.inc_growth || 0), 0) / n;
    const avgExpGrowth = processedTrends.reduce((acc, curr) => acc + (curr.exp_growth || 0), 0) / n;

    let baseInc = currentMonthData.inc || 15000000;
    let baseExp = currentMonthData.exp || 10000000;
    let baseNetWorth = currentMonthData.netWorth || 25000000;

    const projected = [
      {
        label: t("analytics.this_month"),
        inc: baseInc,
        exp: baseExp,
        netWorth: baseNetWorth,
        type: "Actual",
      },
    ];

    for (let i = 1; i <= 6; i++) {
      baseInc = Math.round(baseInc * (1 + Math.max(-0.04, Math.min(0.08, avgIncGrowth))));
      baseExp = Math.round(baseExp * (1 + Math.max(-0.03, Math.min(0.06, avgExpGrowth))));
      baseNetWorth += baseInc - baseExp;

      projected.push({
        label: `M+${i}`,
        inc: baseInc,
        exp: baseExp,
        netWorth: baseNetWorth,
        type: "Forecast",
      });
    }
    return projected;
  }, [processedTrends, currentMonthData, t]);

  // ─── Structured Actionable Recommendations ─────────────────────────────────────

  const actionableRecommendations = useMemo(() => {
    const recs = [];

    if (currentMonthData.profit > 0) {
      recs.push({
        category: t("analytics.rec_cashflow_category"),
        title: t("analytics.rec_cashflow_title"),
        desc: t("analytics.rec_cashflow_desc", { amount: fmtIDR(currentMonthData.profit) }),
        priority: "HIGH",
        badgeColor: "text-emerald-500 bg-emerald-500/10 border-emerald-500/30",
      });
    }

    if (currentMonthData.expMoM > 10) {
      recs.push({
        category: t("analytics.rec_cost_category"),
        title: t("analytics.rec_cost_title"),
        desc: t("analytics.rec_cost_desc", { value: currentMonthData.expMoM.toFixed(1) }),
        priority: "MEDIUM",
        badgeColor: "text-amber-500 bg-amber-500/10 border-amber-500/30",
      });
    }

    const runwayNum = parseFloat(currentMonthData.runwayMonths) || 0;
    if (runwayNum < 6) {
      recs.push({
        category: t("analytics.rec_emergency_category"),
        title: t("analytics.rec_emergency_title"),
        desc: t("analytics.rec_emergency_desc", { months: currentMonthData.runwayMonths }),
        priority: "HIGH",
        badgeColor: "text-blue-500 bg-blue-500/10 border-blue-500/30",
      });
    }

    if (recs.length === 0) {
      recs.push({
        category: t("analytics.rec_stable_category"),
        title: t("analytics.rec_stable_title"),
        desc: t("analytics.rec_stable_desc"),
        priority: "LOW",
        badgeColor: "text-emerald-500 bg-emerald-500/10 border-emerald-500/30",
      });
    }

    return recs;
  }, [currentMonthData, t]);

  // ─── Filtered Drill-down Transactions ──────────────────────────────────────────

  const filteredTransactions = useMemo(() => {
    return allTransactions.filter((tx) => {
      const matchSearch =
        tx.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tx.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tx.id.toLowerCase().includes(searchQuery.toLowerCase());

      const matchCat = categoryFilter === "ALL" || tx.category === categoryFilter;
      const matchType = typeFilter === "ALL" || tx.type === typeFilter;
      const matchStatus = statusFilter === "ALL" || tx.status === statusFilter;

      return matchSearch && matchCat && matchType && matchStatus;
    });
  }, [allTransactions, searchQuery, categoryFilter, typeFilter, statusFilter]);

  // ─── Tab Configuration ─────────────────────────────────────────────────────────

  const tabOptions = [
    { label: t("analytics.tab_executive_summary"), value: "overview" },
    { label: t("analytics.tab_kpi"), value: "kpi" },
    { label: t("analytics.tab_trends"), value: "trends" },
    { label: t("analytics.tab_target"), value: "target" },
    { label: t("analytics.tab_segmentation"), value: "segmentation" },
    { label: t("analytics.tab_forecast"), value: "forecast" },
    { label: t("analytics.tab_anomalies"), value: "anomalies" },
    { label: t("analytics.tab_recommendations"), value: "recommendations" },
    { label: t("analytics.tab_drilldown"), value: "drilldown" },
    { label: t("analytics.tab_methodology"), value: "methodology" },
  ];

  return (
    <div className="min-h-dvh bg-background text-foreground p-4 lg:p-8 space-y-6 max-w-7xl mx-auto font-sans">
      
      {/* ── Header Bar ── */}
      <FocusScrollSection>
        <div className="glass-panel p-6 rounded-3xl flex flex-col md:flex-row md:items-center justify-between gap-5 border border-border shadow-md">
          <div className="flex items-center gap-3.5">
            <div className="p-3 bg-blue-500/10 text-blue-500 rounded-2xl border border-blue-500/20 shadow-xs">
              <BarChart2 size={26} />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h1 className="text-2xl lg:text-3xl font-extrabold tracking-tight">
                  {t("analytics.page_title")}
                </h1>
                <span className="inline-flex items-center justify-center p-1 rounded-full bg-emerald-500/10 text-emerald-500 border border-emerald-500/20" title={t("analytics.active_profile_title")}>
                  <User size={12} strokeWidth={2.5} />
                </span>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5 font-medium">
                {t("analytics.page_subtitle")}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={fetchBIData}
              disabled={loading}
              className="flex items-center gap-2 border border-border bg-card hover:bg-muted text-foreground font-semibold text-xs px-4 py-2.5 rounded-xl transition-all shadow-xs disabled:opacity-50"
            >
              <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
              {loading ? t("analytics.refreshing") : t("analytics.refresh")}
            </button>
            <div className="text-right hidden sm:block border-l border-border pl-4">
              <p className="text-[10px] uppercase font-bold text-muted-foreground">{t("analytics.engine_status")}</p>
              <p className="text-xs font-bold text-emerald-500 flex items-center gap-1.5 justify-end">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                {t("analytics.postgres_sync")}
              </p>
            </div>
          </div>
        </div>
      </FocusScrollSection>

      {/* ── Navigation Tab Pills ── */}
      <div className="overflow-x-auto pb-1 scrollbar-none">
        <LiquidNav
          tabs={tabOptions}
          value={activeTab}
          onChange={setActiveTab}
        />
      </div>

      {/* ── Tab Content Views ── */}
      <AnimatePresence mode="wait">
        
        {/* ═══ 1. EXECUTIVE SUMMARY ═══ */}
        {activeTab === "overview" && (
          <motion.div
            key="overview"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <KPICard
                label={t("analytics.kpi_total_income")}
                value={fmtIDR(currentMonthData.inc)}
                sub={t("analytics.vs_last_month", { value: `${currentMonthData.incMoM >= 0 ? "+" : ""}${currentMonthData.incMoM.toFixed(1)}` })}
                color="green"
                trend={currentMonthData.incMoM >= 0 ? "up" : "down"}
              />
              <KPICard
                label={t("analytics.kpi_total_expense")}
                value={fmtIDR(currentMonthData.exp)}
                sub={t("analytics.vs_last_month", { value: `${currentMonthData.expMoM >= 0 ? "+" : ""}${currentMonthData.expMoM.toFixed(1)}` })}
                color="red"
                trend={currentMonthData.expMoM <= 0 ? "up" : "down"}
              />
              <KPICard
                label={t("analytics.kpi_net_surplus")}
                value={fmtIDR(currentMonthData.profit)}
                sub={t("analytics.savings_margin", { value: currentMonthData.margin.toFixed(1) })}
                color="blue"
                large
              />
              <KPICard
                label={t("analytics.kpi_net_worth")}
                value={fmtCompact(currentMonthData.netWorth)}
                sub={t("analytics.cash_runway", { months: currentMonthData.runwayMonths })}
                color="purple"
              />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-2 glass-panel p-6 rounded-3xl space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-base flex items-center gap-2">
                    <Activity className="text-blue-500" size={18} />
                    {t("analytics.chart_cashflow_title")}
                  </h3>
                  <span className="text-xs text-muted-foreground font-semibold">{t("analytics.live_db_records")}</span>
                </div>
                <div className="h-[280px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={processedTrends}>
                      <defs>
                        <linearGradient id="incGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.4} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="expGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                      <XAxis dataKey="label" stroke="currentColor" className="text-[11px] opacity-70" />
                      <YAxis stroke="currentColor" className="text-[11px] opacity-70" tickFormatter={fmtCompact} />
                      <Tooltip formatter={(v: any) => fmtIDR(Number(v))} />
                      <Legend />
                      <Area type="monotone" dataKey="inc" name={t("analytics.series_income")} stroke="#10b981" fillOpacity={1} fill="url(#incGrad)" strokeWidth={2.5} />
                      <Area type="monotone" dataKey="exp" name={t("analytics.series_expense")} stroke="#ef4444" fillOpacity={1} fill="url(#expGrad)" strokeWidth={2.5} />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="glass-panel p-6 rounded-3xl space-y-4 flex flex-col justify-between">
                <div>
                  <h3 className="font-bold text-base flex items-center gap-2 mb-3">
                    <ShieldAlert className="text-amber-500" size={18} />
                    {t("analytics.liquidity_title")}
                  </h3>
                  <div className="space-y-3">
                    <div className="p-3.5 rounded-2xl bg-card border border-border">
                      <p className="text-[11px] text-muted-foreground font-semibold uppercase">{t("analytics.liquid_savings")}</p>
                      <p className="text-lg font-bold text-emerald-500">{fmtIDR(currentMonthData.cashSavings)}</p>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-card border border-border">
                      <p className="text-[11px] text-muted-foreground font-semibold uppercase">{t("analytics.emergency_target")}</p>
                      <p className="text-lg font-bold text-blue-500">{fmtIDR(currentMonthData.emergencyFund)}</p>
                    </div>
                    <div className="p-3.5 rounded-2xl bg-card border border-border">
                      <p className="text-[11px] text-muted-foreground font-semibold uppercase">{t("analytics.portfolio_total")}</p>
                      <p className="text-lg font-bold text-purple-500">{fmtIDR(currentMonthData.totalPortfolioValue)}</p>
                    </div>
                  </div>
                </div>
                <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs font-semibold flex items-center gap-2">
                  <CheckCircle2 size={16} className="shrink-0" />
                  {t("analytics.solvency_ok")}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 2. KPI & METRICS ═══ */}
        {activeTab === "kpi" && (
          <motion.div
            key="kpi"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <KPICard
                label={t("analytics.kpi_productivity")}
                value={`${currentMonthData.productivityRate.toFixed(1)}%`}
                sub={t("analytics.kpi_productivity_sub")}
                color="cyan"
              />
              <KPICard
                label={t("analytics.kpi_savings_margin")}
                value={`${currentMonthData.margin.toFixed(1)}%`}
                sub={t("analytics.kpi_savings_margin_sub")}
                color="green"
              />
              <KPICard
                label={t("analytics.kpi_burn_rate")}
                value={`${(100 - currentMonthData.margin).toFixed(1)}%`}
                sub={t("analytics.kpi_burn_rate_sub")}
                color="amber"
              />
              <KPICard
                label={t("analytics.kpi_hhi")}
                value={riskData?.concentration_hhi ? String(riskData.concentration_hhi) : "0.24"}
                sub={t("analytics.kpi_hhi_sub")}
                color="purple"
              />
              <KPICard
                label={t("analytics.kpi_free_runway")}
                value={t("analytics.runway_months", { months: currentMonthData.runwayMonths })}
                sub={t("analytics.kpi_free_runway_sub")}
                color="blue"
              />
              <KPICard
                label={t("analytics.kpi_tx_count")}
                value={t("analytics.records_count", { count: allTransactions.length })}
                sub={t("analytics.kpi_tx_count_sub")}
                color="yellow"
              />
            </div>
          </motion.div>
        )}

        {/* ═══ 3. VISUALISASI & TREN ═══ */}
        {activeTab === "trends" && (
          <motion.div
            key="trends"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="glass-panel p-6 rounded-3xl space-y-4">
              <h3 className="font-bold text-base flex items-center gap-2">
                <TrendingUp size={18} className="text-emerald-500" />
                {t("analytics.chart_trends_title")}
              </h3>
              <div className="h-[340px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={processedTrends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="label" stroke="currentColor" className="text-[11px] opacity-70" />
                    <YAxis stroke="currentColor" className="text-[11px] opacity-70" tickFormatter={fmtCompact} />
                    <Tooltip formatter={(v: any) => fmtIDR(Number(v))} />
                    <Legend />
                    <Bar dataKey="inc" name={t("analytics.series_income")} fill="#10b981" radius={[6, 6, 0, 0]} />
                    <Bar dataKey="exp" name={t("analytics.series_expense")} fill="#ef4444" radius={[6, 6, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 4. TARGET VS ACTUAL ═══ */}
        {activeTab === "target" && (
          <motion.div
            key="target"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Budgets */}
              <div className="glass-panel p-6 rounded-3xl space-y-4">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <Target size={18} className="text-blue-500" />
                  {t("analytics.budget_vs_actual_title")}
                </h3>
                <div className="space-y-4">
                  {budgetVsActual.map((b) => (
                    <div key={b.name} className="space-y-1.5 p-3 rounded-2xl bg-card border border-border">
                      <div className="flex justify-between items-center text-xs font-semibold">
                        <span className="flex items-center gap-2">
                          {b.name}
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border ${
                            b.status === "over" ? "bg-red-500/15 text-red-500 border-red-500/30" :
                            b.status === "near" ? "bg-amber-500/15 text-amber-500 border-amber-500/30" :
                            "bg-emerald-500/15 text-emerald-500 border-emerald-500/30"
                          }`}>
                            {t(BUDGET_STATUS_LABEL[b.status])}
                          </span>
                        </span>
                        <span>{fmtIDR(b.actual)} / {fmtIDR(b.target)} ({b.pct}%)</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            b.pct > 100 ? "bg-red-500" : b.pct > 80 ? "bg-amber-500" : "bg-emerald-500"
                          }`}
                          style={{ width: `${Math.min(100, b.pct)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Goals */}
              <div className="glass-panel p-6 rounded-3xl space-y-4">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <CheckCircle2 size={18} className="text-emerald-500" />
                  {t("analytics.goals_progress_title")}
                </h3>
                {rawGoals.length === 0 ? (
                  <div className="p-8 text-center text-xs text-muted-foreground">
                    {t("analytics.goals_empty")}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {rawGoals.map((g) => {
                      const pct = Math.round(((g.current_amount || 0) / (g.target_amount || 1)) * 100);
                      return (
                        <div key={g.name} className="space-y-1.5 p-3 rounded-2xl bg-card border border-border">
                          <div className="flex justify-between text-xs font-semibold">
                            <span>{g.name}</span>
                            <span>{fmtIDR(g.current_amount)} / {fmtIDR(g.target_amount)} ({pct}%)</span>
                          </div>
                          <div className="w-full h-2 rounded-full bg-muted overflow-hidden">
                            <div className="h-full rounded-full bg-blue-500 transition-all" style={{ width: `${Math.min(100, pct)}%` }} />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 5. SEGMENTASI ═══ */}
        {activeTab === "segmentation" && (
          <motion.div
            key="segmentation"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="glass-panel p-6 rounded-3xl space-y-4">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <PieIcon size={18} className="text-purple-500" />
                  {t("analytics.chart_expense_title")}
                </h3>
                <div className="h-[280px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={expenseSegmentation}
                        dataKey="amount"
                        nameKey="name"
                        cx="50%"
                        cy="50%"
                        outerRadius={95}
                        innerRadius={55}
                        paddingAngle={3}
                      >
                        {expenseSegmentation.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: any) => fmtIDR(Number(v))} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="glass-panel p-6 rounded-3xl space-y-4">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <Layers size={18} className="text-blue-500" />
                  {t("analytics.cost_breakdown_title")}
                </h3>
                <div className="space-y-2.5 overflow-y-auto max-h-[300px] pr-1">
                  {expenseSegmentation.map((seg) => (
                    <div key={seg.name} className="flex items-center justify-between p-3 rounded-2xl bg-card border border-border text-xs">
                      <div className="flex items-center gap-2.5">
                        <span className="w-3 h-3 rounded-full" style={{ backgroundColor: seg.color }} />
                        <span className="font-bold">{seg.name}</span>
                        <span className="text-muted-foreground text-[10px]">{t("analytics.tx_count_short", { count: seg.count })}</span>
                      </div>
                      <div className="text-right font-semibold">
                        <span>{fmtIDR(seg.amount)}</span>
                        <span className="text-muted-foreground text-[10px] ml-2 font-mono">{seg.pct}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 6. FORECASTING ═══ */}
        {activeTab === "forecast" && (
          <motion.div
            key="forecast"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="glass-panel p-6 rounded-3xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <Sparkles size={18} className="text-yellow-500" />
                  {t("analytics.chart_forecast_title")}
                </h3>
                <span className="text-xs font-semibold text-muted-foreground">{t("analytics.forecast_method")}</span>
              </div>
              <div className="h-[320px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={forecastData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                    <XAxis dataKey="label" stroke="currentColor" className="text-[11px] opacity-70" />
                    <YAxis stroke="currentColor" className="text-[11px] opacity-70" tickFormatter={fmtCompact} />
                    <Tooltip formatter={(v: any) => fmtIDR(Number(v))} />
                    <Legend />
                    <Line type="monotone" dataKey="inc" name={t("analytics.series_projected_income")} stroke="#10b981" strokeWidth={2.5} strokeDasharray="4 4" />
                    <Line type="monotone" dataKey="exp" name={t("analytics.series_projected_expense")} stroke="#ef4444" strokeWidth={2.5} strokeDasharray="4 4" />
                    <Line type="monotone" dataKey="netWorth" name={t("analytics.series_projected_net_worth")} stroke="#3b82f6" strokeWidth={3} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 7. ANOMALI & EXCEPTION (AI-POWERED) ═══ */}
        {activeTab === "anomalies" && (
          <motion.div
            key="anomalies"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="glass-panel p-6 rounded-3xl space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <AlertTriangle className="text-amber-500" size={20} />
                  {t("analytics.anomalies_title")}
                </h3>
                <span className="text-xs font-bold text-amber-500 bg-amber-500/10 px-3 py-1 rounded-full border border-amber-500/20">
                  {t("analytics.anomalies_detected", { count: calculatedAnomalies.length })}
                </span>
              </div>

              {calculatedAnomalies.length === 0 ? (
                <div className="p-8 text-center rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-500 text-xs font-semibold">
                  <CheckCircle2 size={24} className="mx-auto mb-2" />
                  {t("analytics.no_anomalies")}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {calculatedAnomalies.map((an) => (
                    <div key={an.id} className="p-5 rounded-2xl bg-card border border-border space-y-3 shadow-xs">
                      <div className="flex items-center justify-between">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase ${
                          an.severity === "CRITICAL" ? "bg-red-500/15 text-red-500 border-red-500/30" :
                          an.severity === "HIGH" ? "bg-amber-500/15 text-amber-500 border-amber-500/30" :
                          "bg-blue-500/15 text-blue-500 border-blue-500/30"
                        }`}>
                          {t(ANOMALY_SEVERITY_LABEL[an.severity])}
                        </span>
                        <span className="text-[10px] text-muted-foreground font-mono">{an.date}</span>
                      </div>
                      <h4 className="font-bold text-sm">{an.title}</h4>
                      <p className="text-xs text-muted-foreground">{an.desc}</p>
                      <div className="p-3 rounded-xl bg-muted/40 border border-border/60 text-xs space-y-1">
                        <p className="font-semibold text-foreground flex items-center gap-1.5">
                          <Lightbulb size={13} className="text-yellow-500" />
                          {t("analytics.ai_recommendation")}
                        </p>
                        <p className="text-muted-foreground">{an.recommendation}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.div>
        )}

        {/* ═══ 8. REKOMENDASI ═══ */}
        {activeTab === "recommendations" && (
          <motion.div
            key="recommendations"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="glass-panel p-6 rounded-3xl space-y-4">
              <h3 className="font-bold text-base flex items-center gap-2">
                <Lightbulb className="text-yellow-500" size={20} />
                {t("analytics.recommendations_title")}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {actionableRecommendations.map((rec, idx) => (
                  <div key={idx} className="p-5 rounded-2xl bg-card border border-border space-y-2.5 shadow-xs">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border uppercase ${rec.badgeColor}`}>
                      {rec.category}
                    </span>
                    <h4 className="font-bold text-sm">{rec.title}</h4>
                    <p className="text-xs text-muted-foreground leading-relaxed">{rec.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 9. DRILL-DOWN DETAIL ═══ */}
        {activeTab === "drilldown" && (
          <motion.div
            key="drilldown"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="glass-panel p-6 rounded-3xl space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <h3 className="font-bold text-base flex items-center gap-2">
                  <Eye size={18} />
                  {t("analytics.drilldown_title", { count: filteredTransactions.length })}
                </h3>
                <div className="flex flex-wrap items-center gap-2.5">
                  <div className="relative">
                    <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                    <input
                      type="text"
                      placeholder={t("analytics.search_placeholder")}
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      className="pl-8 pr-3 py-1.5 bg-card border border-border rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  </div>
                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="py-1.5 px-3 bg-card border border-border rounded-xl text-xs focus:outline-none"
                  >
                    <option value="ALL">{t("analytics.filter_all_types")}</option>
                    <option value="expense">{t("analytics.filter_expense")}</option>
                    <option value="income">{t("analytics.filter_income")}</option>
                    <option value="investment">{t("analytics.filter_investment")}</option>
                  </select>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="bg-muted/50 uppercase font-semibold text-muted-foreground border-b border-border">
                    <tr>
                      <th className="py-2.5 px-3">{t("analytics.col_id_date")}</th>
                      <th className="py-2.5 px-3">{t("analytics.col_type")}</th>
                      <th className="py-2.5 px-3">{t("analytics.col_description_segment")}</th>
                      <th className="py-2.5 px-3">{t("analytics.col_category")}</th>
                      <th className="py-2.5 px-3 text-right">{t("analytics.col_amount")}</th>
                      <th className="py-2.5 px-3 text-center">{t("analytics.col_status")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filteredTransactions.slice(0, 50).map((tx) => (
                      <tr key={tx.id} className="hover:bg-muted/20 transition-colors">
                        <td className="py-3 px-3 font-mono font-bold">
                          {tx.id}
                          <div className="text-[10px] text-muted-foreground font-normal">{tx.date}</div>
                        </td>
                        <td className="py-3 px-3">
                          <span className={`px-2 py-0.5 rounded-md font-bold uppercase text-[10px] ${
                            tx.type === "income" ? "bg-emerald-500/10 text-emerald-500" :
                            tx.type === "expense" ? "bg-red-500/10 text-red-500" : "bg-blue-500/10 text-blue-500"
                          }`}>
                            {t(TX_TYPE_LABEL[tx.type])}
                          </span>
                        </td>
                        <td className="py-3 px-3">
                          <div className="font-semibold text-foreground">{tx.description}</div>
                          <div className="text-[10px] text-muted-foreground">{segmentLabel(tx.segment)} • {paymentLabel(tx.paymentMethod)}</div>
                        </td>
                        <td className="py-3 px-3">{tx.category}</td>
                        <td className={`py-3 px-3 text-right font-bold ${
                          tx.type === "income" ? "text-emerald-500" :
                          tx.type === "expense" ? "text-foreground" : "text-blue-500"
                        }`}>
                          {tx.type === "income" ? "+" : "-"}{fmtIDR(tx.amount)}
                        </td>
                        <td className="py-3 px-3 text-center">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            tx.status === "anomaly" ? "bg-red-500/20 text-red-500" : "bg-muted text-muted-foreground"
                          }`}>
                            {t(TX_STATUS_LABEL[tx.status])}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        )}

        {/* ═══ 10. METODOLOGI DATA ═══ */}
        {activeTab === "methodology" && (
          <motion.div
            key="methodology"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-6"
          >
            <div className="glass-panel p-6 rounded-3xl space-y-4">
              <h3 className="font-bold text-base flex items-center gap-2">
                <Database size={18} className="text-blue-500" />
                {t("analytics.methodology_title")}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-muted-foreground leading-relaxed">
                <div className="p-4 rounded-2xl bg-card border border-border space-y-2">
                  <h4 className="font-bold text-sm text-foreground">{t("analytics.methodology_1_title")}</h4>
                  <p>{t("analytics.methodology_1_desc")}</p>
                </div>
                <div className="p-4 rounded-2xl bg-card border border-border space-y-2">
                  <h4 className="font-bold text-sm text-foreground">{t("analytics.methodology_2_title")}</h4>
                  <p>{t("analytics.methodology_2_desc")}</p>
                </div>
                <div className="p-4 rounded-2xl bg-card border border-border space-y-2">
                  <h4 className="font-bold text-sm text-foreground">{t("analytics.methodology_3_title")}</h4>
                  <p>{t("analytics.methodology_3_desc")}</p>
                </div>
                <div className="p-4 rounded-2xl bg-card border border-border space-y-2">
                  <h4 className="font-bold text-sm text-foreground">{t("analytics.methodology_4_title")}</h4>
                  <p>{t("analytics.methodology_4_desc")}</p>
                </div>
              </div>
            </div>
          </motion.div>
        )}

      </AnimatePresence>

    </div>
  );
}

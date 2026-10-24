"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
  ReferenceLine, Cell, PieChart, Pie,
} from "recharts";
import {
  Building2, Plus, FileText, TrendingUp, TrendingDown,
  AlertTriangle, CheckCircle2, Clock, Users, DollarSign,
  Download, RefreshCw, ChevronDown, X, Target, Zap,
  BarChart2, Activity, Search, Info, Lightbulb, Database,
  ArrowUpRight, ArrowDownRight, Eye,
} from "lucide-react";
import { PeriodFilter } from "@/components/ui/period-filter";
import { LiquidNav } from "@/components/ui/liquid-nav";
import { FocusScrollSection } from "@/components/ui/focus-scroll";
import { clientProxyUrl } from "@/lib/api";
import { useI18n } from "@/i18n/context";

// ── Types ───────────────────────────────────────────────────────────────────

interface Project {
  id: number;
  name: string;
  code: string;
  budget: number;
  status: string;
  startDate: string;
  endDate: string;
}

interface EVM {
  pv: number; ev: number; ac: number;
  cpi: number; spi: number;
  cv: number; sv: number;
  eac: number; etc: number;
}

interface Analytics {
  project_id: number;
  project_name: string;
  project_code: string;
  budget: number;
  status_badge: "ON_TRACK" | "WARNING" | "CRITICAL";
  executive_summary: {
    headline: string;
    status: string;
    cpi: number; spi: number;
    progress_deviation: number;
  };
  kpi_metrics: {
    revenue_ev: number;
    cost_ac: number;
    gross_profit: number;
    profit_margin_pct: number;
    productivity: number;
    target_fulfillment_pct: number;
  };
  evm: EVM;
  progress: { planned_pct: number; actual_pct: number; deviation_pct: number };
  s_curve: {
    date: string; planned_pct: number; actual_pct: number;
    planned_value: number; earned_value: number;
    actual_cost: number; daily_cost: number; headcount: number; work_hours: number;
  }[];
  labor: { total_man_hours: number; avg_attendance_pct: number };
  milestones: { total: number; completed: number; items: { id: number; title: string; target_date: string; weight: number; is_completed: boolean }[] };
  trend: { velocity_7d_pct_per_day: number };
  root_cause_analysis: { category: string; severity: string; primary_factor: string; trigger: string }[];
  anomalies: { date: string; type: string; severity: string; description: string }[];
  forecasting: {
    est_days_to_complete: number;
    forecast_30d_pct: number;
    projected_final_cost_eac: number;
    cost_overrun_projected: number;
  };
  recommendations: string[];
  drill_down: {
    id: number; date: string;
    planned_pct: number; actual_pct: number; actual_cost: number;
    headcount: number; work_hours: number; tasks_completed: string; notes: string;
  }[];
  methodology: { framework: string; data_source: string; calculated_at: string };
}

// ── Constants ────────────────────────────────────────────────────────────────

const BADGE_STYLES: Record<string, string> = {
  ON_TRACK: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-400",
  WARNING:  "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-400",
  CRITICAL: "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400",
};

const BADGE_ICONS: Record<string, React.ReactNode> = {
  ON_TRACK: <CheckCircle2 size={14} />,
  WARNING:  <AlertTriangle size={14} />,
  CRITICAL: <AlertTriangle size={14} />,
};

const SEVERITY_STYLES: Record<string, string> = {
  HIGH:     "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-red-200 dark:border-red-900/40",
  MEDIUM:   "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border-amber-200 dark:border-amber-900/40",
  LOW:      "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900/40",
  WARNING:  "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 border-amber-200 dark:border-amber-900/40",
  CRITICAL: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 border-red-200 dark:border-red-900/40",
};

const fmt = (n: number) =>
  "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(n));

const fmtCompact = (n: number) => {
  if (n >= 1e9) return `Rp ${(n / 1e9).toFixed(1)}M`;
  if (n >= 1e6) return `Rp ${(n / 1e6).toFixed(1)}jt`;
  return fmt(n);
};

// ── Daily Progress Input Modal ───────────────────────────────────────────────

function DailyInputModal({ projectId, onClose, onSuccess }: {
  projectId: number;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [form, setForm] = useState({
    log_date: new Date().toISOString().slice(0, 10),
    planned_pct: "", actual_pct: "", actual_cost: "",
    headcount: "", work_hours: "8", tasks_completed: "", notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const sanitizeText = (str: string) => str ? str.replace(/<[^>]*>?/gm, "").trim().slice(0, 500) : null;
      const res = await fetch(clientProxyUrl("api/business/daily-log"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id:     projectId,
          log_date:       form.log_date,
          planned_pct:    Math.min(100, Math.max(0, parseFloat(form.planned_pct) || 0)),
          actual_pct:     Math.min(100, Math.max(0, parseFloat(form.actual_pct) || 0)),
          actual_cost:    Math.max(0, parseFloat(form.actual_cost) || 0),
          headcount:      Math.max(0, parseInt(form.headcount) || 0),
          work_hours:     Math.min(24, Math.max(0, parseFloat(form.work_hours) || 8)),
          tasks_completed: sanitizeText(form.tasks_completed),
          notes:          sanitizeText(form.notes),
        }),
      });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || t("common.error")); }
      onSuccess(); onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("common.error"));
    } finally { setSubmitting(false); }
  };

  const field = "w-full bg-background border border-border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary transition-all";

  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
      initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        className="relative w-full max-w-md bg-card border border-border rounded-3xl shadow-2xl overflow-hidden"
        initial={{ scale: 0.93, y: 20 }} animate={{ scale: 1, y: 0 }}
        exit={{ scale: 0.93, y: 20 }}
        transition={{ type: "spring", stiffness: 420, damping: 36 }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-bold text-base">{t("business.daily_log_title")}</h2>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-muted transition-colors"><X size={17} /></button>
        </div>
        <form onSubmit={submit} className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_date")}</label>
              <input type="date" value={form.log_date} onChange={(e) => setForm((f) => ({ ...f, log_date: e.target.value }))} className={field} required />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_headcount")}</label>
              <input type="number" min="0" value={form.headcount} onChange={(e) => setForm((f) => ({ ...f, headcount: e.target.value }))} placeholder="0" className={field} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_planned_pct")}</label>
              <input type="number" min="0" max="100" step="0.01" value={form.planned_pct} onChange={(e) => setForm((f) => ({ ...f, planned_pct: e.target.value }))} placeholder="0.00" className={field} required />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_actual_pct")}</label>
              <input type="number" min="0" max="100" step="0.01" value={form.actual_pct} onChange={(e) => setForm((f) => ({ ...f, actual_pct: e.target.value }))} placeholder="0.00" className={field} required />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_actual_cost")}</label>
              <input type="number" min="0" value={form.actual_cost} onChange={(e) => setForm((f) => ({ ...f, actual_cost: e.target.value }))} placeholder="0" className={field} required />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_work_hours")}</label>
              <input type="number" min="0" max="24" step="0.5" value={form.work_hours} onChange={(e) => setForm((f) => ({ ...f, work_hours: e.target.value }))} className={field} />
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_tasks_completed")}</label>
            <input type="text" value={form.tasks_completed} onChange={(e) => setForm((f) => ({ ...f, tasks_completed: e.target.value }))} placeholder={t("business.ph_tasks_completed")} className={field} />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-foreground mb-1 block">{t("business.field_notes")}</label>
            <textarea
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
              rows={2}
              placeholder={t("business.ph_notes")}
              className="w-full bg-background border border-border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none transition-all"
            />
          </div>
          {error && (
            <div className="p-3 rounded-xl bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900/50 text-sm text-red-600 dark:text-red-400">
              {error}
            </div>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-foreground text-background font-semibold py-3 rounded-xl hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {submitting ? (
              <><RefreshCw size={16} className="animate-spin" /> {t("business.saving")}</>
            ) : (
              <><Plus size={16} /> {t("business.save_progress")}</>
            )}
          </button>
        </form>
      </motion.div>
    </motion.div>
  );
}

// ── KPI Card ─────────────────────────────────────────────────────────────────

function KPICard({ label, value, sub, color = "blue", large = false, trend }: {
  label: string; value: string; sub?: string; color?: string; large?: boolean;
  trend?: "up" | "down" | null;
}) {
  const colors: Record<string, string> = {
    blue:   "border-l-blue-500",
    green:  "border-l-emerald-500",
    amber:  "border-l-amber-500",
    purple: "border-l-purple-500",
    red:    "border-l-red-500",
    slate:  "border-l-slate-400",
    cyan:   "border-l-cyan-500",
  };
  return (
    <div className={`glass-panel p-5 rounded-2xl border-l-4 ${colors[color] ?? colors.blue}`}>
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">{label}</p>
      <div className="flex items-end gap-2 mt-1.5">
        <p className={`font-bold ${large ? "text-3xl" : "text-2xl"}`}>{value}</p>
        {trend === "up" && <ArrowUpRight size={16} className="text-emerald-500 mb-1" />}
        {trend === "down" && <ArrowDownRight size={16} className="text-red-500 mb-1" />}
      </div>
      {sub && <p className="text-xs text-muted-foreground mt-1">{sub}</p>}
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function BusinessCockpitPage() {
  const [projects, setProjects]     = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [analytics, setAnalytics]   = useState<Analytics | null>(null);
  const [loadingProj, setLoadingProj] = useState(true);
  const [loadingAna, setLoadingAna]   = useState(false);
  const [showModal, setShowModal]     = useState(false);
  const [activeTab, setActiveTab]     = useState("overview");
  const [showReport, setShowReport]   = useState(false);
  const [report, setReport]           = useState<{ markdown: string; html: string } | null>(null);
  const [reportPeriod, setReportPeriod] = useState("weekly");
  const [drillPage, setDrillPage]     = useState(0);
  const [profileType, setProfileType] = useState<string | null>(null);
  const DRILL_PAGE_SIZE = 10;

  const { t } = useI18n();
  const STATUS_LABEL: Record<string, string> = {
    ON_TRACK: t("business.status_on_track"),
    WARNING: t("business.status_warning"),
    CRITICAL: t("business.status_critical"),
  };
  const SEVERITY_LABEL: Record<string, string> = {
    HIGH: t("business.severity_high"),
    MEDIUM: t("business.severity_medium"),
    LOW: t("business.severity_low"),
    WARNING: t("business.severity_warning"),
    CRITICAL: t("business.severity_critical"),
  };

  const apiHeaders = useCallback((): HeadersInit => ({}), []);

  const fetchProfileType = useCallback(async () => {
    try {
      const res = await fetch(clientProxyUrl("api/profile/"), { headers: apiHeaders() });
      if (res.ok) {
        const data = await res.json();
        setProfileType(data.active_type || "business");
      } else {
        setProfileType("business");
      }
    } catch {
      setProfileType("business");
    }
  }, [apiHeaders]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void fetchProfileType();
  }, [fetchProfileType]);

  const fetchProjects = useCallback(async () => {
    try {
      setLoadingProj(true);
      const res = await fetch(clientProxyUrl("api/business/projects"), { headers: apiHeaders() });
      const data: Project[] = await res.json();
      setProjects(data);
      if (data.length > 0 && selectedId === null) setSelectedId(data[0].id);
    } catch { /* API offline in dev */ } finally { setLoadingProj(false); }
  }, [apiHeaders, selectedId]);

  const fetchAnalytics = useCallback(async (id: number) => {
    try {
      setLoadingAna(true);
      const res = await fetch(clientProxyUrl(`api/business/analytics/${id}`), { headers: apiHeaders() });
      if (!res.ok) throw new Error();
      setAnalytics(await res.json());
    } catch { setAnalytics(null); } finally { setLoadingAna(false); }
  }, [apiHeaders]);

  const fetchReport = useCallback(async () => {
    if (!selectedId) return;
    const res = await fetch(
      clientProxyUrl(`api/business/reports/generate?project_id=${selectedId}&period=${reportPeriod}`),
      { headers: apiHeaders() }
    );
    const data = await res.json();
    setReport(data);
    setShowReport(true);
  }, [selectedId, reportPeriod, apiHeaders]);

  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { void fetchProjects(); }, []);
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { if (selectedId) void fetchAnalytics(selectedId); }, [selectedId]);

  const tabOptions = [
    { label: t("business.tab_overview"),  value: "overview"     },
    { label: t("business.tab_kpi"),       value: "kpi"          },
    { label: t("business.tab_trackers"),  value: "trackers"     },
    { label: t("business.tab_scurve"),    value: "s_curve"      },
    { label: t("business.tab_forecast"),  value: "forecast"     },
    { label: t("business.tab_anomalies"), value: "anomalies"    },
    { label: t("business.tab_recs"),      value: "recs"         },
    { label: t("business.tab_drilldown"), value: "drilldown"    },
    { label: t("business.tab_methodology"), value: "methodology" },
  ];

  const evm  = analytics?.evm;
  const prog = analytics?.progress;

  if (profileType === "personal") {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center p-6 text-center max-w-md mx-auto space-y-4">
        <div className="p-4 rounded-2xl bg-amber-500/10 text-amber-500 border border-amber-500/20">
          <Building2 size={36} />
        </div>
        <h1 className="text-xl font-bold">{t("business.personal_guard_title")}</h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {t("business.personal_guard_desc")} <span className="font-semibold text-foreground">Business</span>.
        </p>
        <div className="pt-2 flex flex-col sm:flex-row gap-2.5 w-full">
          <Link
            href="/"
            className="flex-1 px-4 py-2.5 rounded-xl border border-border bg-card text-sm font-semibold hover:bg-muted transition-colors"
          >
            {t("business.back_to_dashboard")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-background text-foreground p-5 lg:p-8 space-y-6 max-w-7xl mx-auto">

      {/* ── Page Header ── */}
      <FocusScrollSection>
        <div className="glass-panel p-6 rounded-3xl flex flex-col md:flex-row md:items-center justify-between gap-5">
          <div>
            <h1 className="text-2xl lg:text-3xl font-bold flex items-center gap-3">
              <div className="p-2 bg-foreground/8 rounded-xl">
                <BarChart2 size={26} className="text-foreground" />
              </div>
              {t("business.page_title")}
            </h1>
            <p className="text-sm text-muted-foreground mt-1.5">
              {t("business.page_subtitle")}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative">
              <select
                value={selectedId ?? ""}
                onChange={(e) => setSelectedId(Number(e.target.value))}
                disabled={loadingProj || projects.length === 0}
                className="appearance-none bg-card border border-border rounded-xl pl-4 pr-10 py-2.5
                  text-sm font-semibold shadow-sm focus:outline-none focus:ring-2 focus:ring-primary
                  cursor-pointer disabled:opacity-50 min-w-[200px]"
              >
                {projects.length === 0
                  ? <option value="">{t("business.no_projects")}</option>
                  : projects.map((p) => (
                      <option key={p.id} value={p.id}>{p.name} ({p.code})</option>
                    ))
                }
              </select>
              <ChevronDown size={14} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none" />
            </div>

            <button
              onClick={() => setShowModal(true)}
              disabled={!selectedId}
              className="flex items-center gap-2 bg-foreground text-background font-semibold text-sm
                px-4 py-2.5 rounded-xl hover:opacity-90 transition-opacity disabled:opacity-40"
            >
              <Plus size={16} />
              {t("business.daily_log")}
            </button>

            <div className="flex items-center gap-2">
              <select
                value={reportPeriod}
                onChange={(e) => setReportPeriod(e.target.value)}
                className="bg-card border border-border rounded-xl px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary cursor-pointer font-semibold"
              >
                <option value="daily">{t("business.period_daily")}</option>
                <option value="weekly">{t("business.period_weekly")}</option>
                <option value="monthly">{t("business.period_monthly")}</option>
              </select>
              <button
                onClick={fetchReport}
                disabled={!selectedId}
                className="flex items-center gap-2 border border-border bg-card text-foreground
                  font-semibold text-sm px-4 py-2.5 rounded-xl hover:bg-muted transition-colors
                  disabled:opacity-40"
              >
                <FileText size={16} />
                {t("business.generate_report")}
              </button>
            </div>
          </div>
        </div>
      </FocusScrollSection>

      {/* ── Loading skeleton ── */}
      {loadingAna && (
        <div className="glass-panel p-8 rounded-3xl text-center text-muted-foreground text-sm">
          <RefreshCw size={20} className="animate-spin mx-auto mb-3" />
          {t("business.loading_analytics")}
        </div>
      )}

      {/* ── Executive Summary Banner ── */}
      {analytics && analytics.executive_summary && (
        <FocusScrollSection>
          <div className={`rounded-2xl border p-5 ${BADGE_STYLES[analytics.status_badge]}`}>
            <div className="flex items-start gap-3">
              <div className="mt-0.5 shrink-0">{BADGE_ICONS[analytics.status_badge]}</div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wider opacity-70 mb-1">
                  {t("business.exec_summary")} · {analytics.project_name} ({analytics.project_code})
                </p>
                <p className="text-sm font-medium leading-relaxed">
                  {analytics.executive_summary.headline}
                </p>
                <div className="flex flex-wrap gap-4 mt-3 text-xs font-semibold opacity-80">
                  <span>CPI {analytics.executive_summary.cpi.toFixed(2)}</span>
                  <span>SPI {analytics.executive_summary.spi.toFixed(2)}</span>
                  <span>{t("business.deviation")} {analytics.executive_summary.progress_deviation >= 0 ? "+" : ""}{analytics.executive_summary.progress_deviation.toFixed(1)}%</span>
                  <span>{t("business.budget")} {fmt(analytics.budget)}</span>
                </div>
              </div>
            </div>
          </div>
        </FocusScrollSection>
      )}

      {/* ── Tabs + Content ── */}
      {analytics && evm && prog && (
        <FocusScrollSection>
          <div className="space-y-5">
            <div className="overflow-x-auto">
              <LiquidNav
                tabs={tabOptions}
                value={activeTab}
                onChange={setActiveTab}
                className="w-fit"
              />
            </div>

            <AnimatePresence mode="wait">
              {/* ─── 1. OVERVIEW ─── */}
              {activeTab === "overview" && (
                <motion.div key="overview"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  {/* Status + badge */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-bold ${BADGE_STYLES[analytics.status_badge]}`}>
                      {BADGE_ICONS[analytics.status_badge]}
                      {STATUS_LABEL[analytics.status_badge] ?? analytics.status_badge}
                    </span>
                    {analytics.trend.velocity_7d_pct_per_day > 0 && (
                      <span className="flex items-center gap-1 text-xs text-emerald-600 font-semibold">
                        <TrendingUp size={13} />
                        {t("business.velocity_7d", { value: analytics.trend.velocity_7d_pct_per_day.toFixed(2) })}
                      </span>
                    )}
                  </div>

                  {/* EVM KPI Cards */}
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <KPICard label={t("business.kpi_pv")} value={fmtCompact(evm.pv)} sub={t("business.planned_pct_suffix", { value: prog.planned_pct })} color="blue" />
                    <KPICard label={t("business.kpi_ev")} value={fmtCompact(evm.ev)} sub={t("business.actual_pct_suffix", { value: prog.actual_pct })} color="green" />
                    <KPICard label={t("business.kpi_cpi")} value={evm.cpi.toFixed(2)} sub={evm.cpi >= 1 ? t("business.within_budget") : t("business.over_budget")} color={evm.cpi >= 1 ? "green" : "red"} large trend={evm.cpi >= 1 ? "up" : "down"} />
                    <KPICard label={t("business.kpi_spi")} value={evm.spi.toFixed(2)} sub={evm.spi >= 1 ? t("business.on_schedule") : t("business.behind_schedule")} color={evm.spi >= 1 ? "green" : "amber"} large trend={evm.spi >= 1 ? "up" : "down"} />
                  </div>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <KPICard label={t("business.kpi_ac")} value={fmtCompact(evm.ac)} color="amber" />
                    <KPICard label={t("business.kpi_cv")} value={fmtCompact(evm.cv)} sub={evm.cv >= 0 ? t("business.variance_surplus") : t("business.variance_deficit")} color={evm.cv >= 0 ? "green" : "red"} />
                    <KPICard label={t("business.kpi_sv")} value={fmtCompact(evm.sv)} sub={evm.sv >= 0 ? t("business.schedule_ahead") : t("business.schedule_behind")} color={evm.sv >= 0 ? "green" : "amber"} />
                    <KPICard label={t("business.kpi_eac")} value={fmtCompact(evm.eac)} color="purple" />
                  </div>

                  {/* Progress bars */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <div className="flex justify-between text-sm mb-3">
                      <span className="font-semibold">{t("business.progress_title")}</span>
                      <span className={`font-bold text-xs ${prog.deviation_pct >= 0 ? "text-emerald-600" : "text-amber-500"}`}>
                        {t("business.deviation_label")} {prog.deviation_pct >= 0 ? "+" : ""}{prog.deviation_pct.toFixed(1)}%
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div>
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                          <span>{t("business.planned")}</span><span>{prog.planned_pct}%</span>
                        </div>
                        <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                          <div className="h-full rounded-full bg-blue-500 transition-all duration-700"
                            style={{ width: `${prog.planned_pct}%` }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-xs text-muted-foreground mb-1">
                          <span>{t("business.actual")}</span><span>{prog.actual_pct}%</span>
                        </div>
                        <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                          <div className={`h-full rounded-full transition-all duration-700
                            ${prog.actual_pct >= prog.planned_pct ? "bg-emerald-500" : "bg-amber-500"}`}
                            style={{ width: `${prog.actual_pct}%` }} />
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Milestones summary */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="font-bold text-base">{t("business.milestones")}</h2>
                      <span className="text-sm font-semibold text-muted-foreground">
                        {t("business.milestones_progress", { completed: analytics.milestones.completed, total: analytics.milestones.total })}
                      </span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden mb-4">
                      <div className="h-full rounded-full bg-emerald-500 transition-all duration-700"
                        style={{ width: `${analytics.milestones.total > 0 ? (analytics.milestones.completed / analytics.milestones.total * 100) : 0}%` }} />
                    </div>
                    {analytics.milestones.items.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-4">{t("business.milestones_empty")}</p>
                    ) : (
                      <div className="space-y-2">
                        {analytics.milestones.items.slice(0, 5).map((m) => (
                          <div key={m.id} className={`flex items-center gap-3 p-3 rounded-xl border
                            ${m.is_completed ? "border-emerald-200 bg-emerald-50 dark:border-emerald-900/50 dark:bg-emerald-950/20" : "border-border bg-muted/30"}`}
                          >
                            <div className={`shrink-0 h-5 w-5 rounded-full flex items-center justify-center
                              ${m.is_completed ? "bg-emerald-500" : "border-2 border-muted-foreground"}`}>
                              {m.is_completed && <CheckCircle2 size={12} className="text-white" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className={`text-sm font-medium ${m.is_completed ? "line-through text-muted-foreground" : ""}`}>{m.title}</p>
                              <p className="text-xs text-muted-foreground">{t("business.milestone_target", { date: m.target_date })}</p>
                            </div>
                            <span className="text-xs text-muted-foreground shrink-0">{t("business.milestone_weight", { weight: m.weight })}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </motion.div>
              )}

              {/* ─── 2. KPI & METRIK ─── */}
              {activeTab === "kpi" && (
                <motion.div key="kpi"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  <h2 className="font-bold text-base">{t("business.kpi_title")}</h2>
                  <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
                    <KPICard label={t("business.kpi_revenue_ev")} value={fmtCompact(analytics.kpi_metrics.revenue_ev)} color="green" sub={t("business.kpi_revenue_ev_sub")} />
                    <KPICard label={t("business.kpi_cost_ac")} value={fmtCompact(analytics.kpi_metrics.cost_ac)} color="amber" sub={t("business.kpi_cost_ac_sub")} />
                    <KPICard label={t("business.kpi_gross_profit")} value={fmtCompact(analytics.kpi_metrics.gross_profit)} color={analytics.kpi_metrics.gross_profit >= 0 ? "green" : "red"} trend={analytics.kpi_metrics.gross_profit >= 0 ? "up" : "down"} />
                    <KPICard label={t("business.kpi_profit_margin")} value={`${analytics.kpi_metrics.profit_margin_pct.toFixed(1)}%`} color={analytics.kpi_metrics.profit_margin_pct >= 0 ? "green" : "red"} />
                    <KPICard label={t("business.kpi_productivity")} value={`${analytics.kpi_metrics.productivity.toFixed(2)}`} color="cyan" sub={t("business.kpi_productivity_sub")} />
                    <KPICard label={t("business.kpi_target_fulfillment")} value={`${analytics.kpi_metrics.target_fulfillment_pct.toFixed(1)}%`} color={analytics.kpi_metrics.target_fulfillment_pct >= 95 ? "green" : "amber"} sub={t("business.kpi_target_fulfillment_sub")} />
                  </div>

                  {/* Target vs Actual breakdown */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-4">{t("business.target_vs_actual_title")}</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-xs text-muted-foreground font-semibold border-b border-border">
                            <th className="text-left pb-2 pr-4">{t("business.col_metric")}</th>
                            <th className="text-right pb-2 pr-4">{t("business.col_target_plan")}</th>
                            <th className="text-right pb-2 pr-4">{t("business.col_actual")}</th>
                            <th className="text-right pb-2">{t("business.col_deviation")}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          <tr>
                            <td className="py-2.5 pr-4 font-medium">{t("business.row_cumulative_progress")}</td>
                            <td className="text-right pr-4">{prog.planned_pct}%</td>
                            <td className="text-right pr-4">{prog.actual_pct}%</td>
                            <td className={`text-right font-bold ${prog.deviation_pct >= 0 ? "text-emerald-600" : "text-amber-500"}`}>
                              {prog.deviation_pct >= 0 ? "+" : ""}{prog.deviation_pct.toFixed(1)}%
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 pr-4 font-medium">{t("business.row_planned_value")}</td>
                            <td className="text-right pr-4">{fmtCompact(evm.pv)}</td>
                            <td className="text-right pr-4">{fmtCompact(evm.ev)}</td>
                            <td className={`text-right font-bold ${evm.sv >= 0 ? "text-emerald-600" : "text-amber-500"}`}>
                              {evm.sv >= 0 ? "+" : ""}{fmtCompact(evm.sv)}
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 pr-4 font-medium">{t("business.row_cost_eac_budget")}</td>
                            <td className="text-right pr-4">{fmtCompact(analytics.budget)}</td>
                            <td className="text-right pr-4">{fmtCompact(evm.eac)}</td>
                            <td className={`text-right font-bold ${evm.cv >= 0 ? "text-emerald-600" : "text-red-500"}`}>
                              {evm.cv >= 0 ? "−" : "+"}{fmtCompact(Math.abs(evm.eac - analytics.budget))}
                            </td>
                          </tr>
                          <tr>
                            <td className="py-2.5 pr-4 font-medium">{t("business.kpi_target_fulfillment")}</td>
                            <td className="text-right pr-4">100%</td>
                            <td className="text-right pr-4">{analytics.kpi_metrics.target_fulfillment_pct.toFixed(1)}%</td>
                            <td className={`text-right font-bold ${analytics.kpi_metrics.target_fulfillment_pct >= 95 ? "text-emerald-600" : "text-amber-500"}`}>
                              {(analytics.kpi_metrics.target_fulfillment_pct - 100).toFixed(1)}%
                            </td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>

                  {/* Attendance stats */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-4">{t("business.productivity_attendance_title")}</h3>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="p-4 rounded-xl bg-muted/40 text-center">
                        <p className="text-2xl font-bold">{analytics.labor.total_man_hours}</p>
                        <p className="text-xs text-muted-foreground mt-1">{t("business.total_man_hours")}</p>
                      </div>
                      <div className="p-4 rounded-xl bg-muted/40 text-center">
                        <p className="text-2xl font-bold">{analytics.labor.avg_attendance_pct}%</p>
                        <p className="text-xs text-muted-foreground mt-1">{t("business.avg_attendance")}</p>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* ─── 3. TRACKERS BA/BI (Business Aligned) ─── */}
              {activeTab === "trackers" && (
                <motion.div key="trackers"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-6"
                >
                  <div className="glass-panel p-6 rounded-3xl space-y-2 border-l-4 border-l-amber-500">
                    <h2 className="font-bold text-lg flex items-center gap-2">
                      <Building2 size={20} className="text-amber-500" />
                      {t("business.trackers_title")}
                    </h2>
                    <p className="text-sm text-muted-foreground">
                      {t("business.trackers_desc")}
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* 1. Investment Tracker (Business Aligned) */}
                    <div className="glass-panel p-5 rounded-2xl space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-500">
                            <TrendingUp size={18} />
                          </div>
                          <div>
                            <h3 className="font-bold text-sm">{t("business.tracker_investment_title")}</h3>
                            <p className="text-xs text-muted-foreground">{t("business.tracker_investment_desc")}</p>
                          </div>
                        </div>
                        <span className={`text-xs font-semibold px-2 py-1 rounded-md ${
                          evm.cv >= 0
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-red-500/10 text-red-600 dark:text-red-400"
                        }`}>
                          {evm.cv >= 0 ? t("business.under_budget") : t("business.over_budget_badge")}
                        </span>
                      </div>
                      <div className="p-4 rounded-xl bg-muted/30 border border-border/50 space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.total_budget_bac")}</span>
                          <span className="font-bold">{fmtCompact(analytics.budget)}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.cost_efficiency_cpi")}</span>
                          <span className={`font-bold ${evm.cpi >= 1 ? "text-emerald-500" : "text-red-500"}`}>
                            {evm.cpi.toFixed(3)} — {evm.cpi >= 1 ? t("business.saving_amount", { amount: fmtCompact(evm.cv) }) : t("business.over_amount", { amount: fmtCompact(Math.abs(evm.cv)) })}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.remaining_budget_etc")}</span>
                          <span className={`font-semibold ${evm.etc >= 0 ? "text-blue-500" : "text-red-500"}`}>
                            {fmtCompact(Math.max(0, evm.etc))}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t("business.eac_projection", { amount: fmtCompact(evm.eac) })} {evm.cv >= 0 ? t("business.surplus_treasury", { amount: fmtCompact(evm.cv) }) : t("business.cost_overrun_mitigation")}
                      </p>
                    </div>

                    {/* 2. Expense Tracker (Business Aligned) */}
                    <div className="glass-panel p-5 rounded-2xl space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-amber-500/10 text-amber-500">
                            <DollarSign size={18} />
                          </div>
                          <div>
                            <h3 className="font-bold text-sm">{t("business.tracker_expense_title")}</h3>
                            <p className="text-xs text-muted-foreground">{t("business.tracker_expense_desc")}</p>
                          </div>
                        </div>
                        <span className="text-xs font-semibold px-2 py-1 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400">
                          CPI: {evm.cpi.toFixed(2)}
                        </span>
                      </div>
                      <div className="p-4 rounded-xl bg-muted/30 border border-border/50 space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.total_actual_cost")}</span>
                          <span className="font-bold">{fmtCompact(evm.ac)}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.kpi_cv")}</span>
                          <span className={`font-bold ${evm.cv >= 0 ? "text-emerald-500" : "text-red-500"}`}>
                            {evm.cv >= 0 ? "+" : ""}{fmtCompact(evm.cv)}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.daily_avg_ac")}</span>
                          <span className="font-semibold">{fmtCompact(evm.ac / Math.max(1, analytics.s_curve.length))}</span>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t("business.tracker_expense_note")}
                      </p>
                    </div>

                    {/* 3. Income Tracker (Business Aligned) */}
                    <div className="glass-panel p-5 rounded-2xl space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-blue-500/10 text-blue-500">
                            <TrendingUp size={18} />
                          </div>
                          <div>
                            <h3 className="font-bold text-sm">{t("business.tracker_income_title")}</h3>
                            <p className="text-xs text-muted-foreground">{t("business.tracker_income_desc")}</p>
                          </div>
                        </div>
                        <span className="text-xs font-semibold px-2 py-1 rounded-md bg-blue-500/10 text-blue-600 dark:text-blue-400">
                          SPI: {evm.spi.toFixed(2)}
                        </span>
                      </div>
                      <div className="p-4 rounded-xl bg-muted/30 border border-border/50 space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.kpi_ev")}</span>
                          <span className="font-bold">{fmtCompact(evm.ev)}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.schedule_variance")}</span>
                          <span className={`font-bold ${evm.sv >= 0 ? "text-emerald-500" : "text-amber-500"}`}>
                            {evm.sv >= 0 ? "+" : ""}{fmtCompact(evm.sv)}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.milestones_billed")}</span>
                          <span className="font-semibold">{t("business.milestones_billed_count", { completed: analytics.milestones.completed, total: analytics.milestones.total })}</span>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t("business.tracker_income_note")}
                      </p>
                    </div>

                    {/* 4. Receipt Reader (Business Aligned) */}
                    <div className="glass-panel p-5 rounded-2xl space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2.5">
                          <div className="p-2 rounded-xl bg-purple-500/10 text-purple-500">
                            <FileText size={18} />
                          </div>
                          <div>
                            <h3 className="font-bold text-sm">{t("business.tracker_receipt_title")}</h3>
                            <p className="text-xs text-muted-foreground">{t("business.tracker_receipt_desc")}</p>
                          </div>
                        </div>
                        <span className="text-xs font-semibold px-2 py-1 rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400">
                          {t("business.log_entries", { count: analytics.drill_down.length })}
                        </span>
                      </div>
                      <div className="p-4 rounded-xl bg-muted/30 border border-border/50 space-y-2">
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.total_ac_entered")}</span>
                          <span className="font-bold">{fmtCompact(evm.ac)}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.daily_log_entries")}</span>
                          <span className="font-bold text-purple-500">{t("business.days_entered", { count: analytics.drill_down.length })}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-muted-foreground">{t("business.avg_ac_per_log")}</span>
                          <span className="font-semibold">
                            {fmtCompact(analytics.drill_down.length > 0 ? evm.ac / analytics.drill_down.length : 0)}
                          </span>
                        </div>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {t("business.tracker_receipt_note", { count: analytics.drill_down.length })}
                      </p>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* ─── 3. TREN & KURVA S ─── */}
              {activeTab === "s_curve" && (
                <motion.div key="s_curve"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  {/* S-Curve area chart */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h2 className="font-bold text-base mb-1">{t("business.scurve_title")}</h2>
                    <p className="text-xs text-muted-foreground mb-4">{t("business.scurve_desc")}</p>
                    <ResponsiveContainer width="100%" height={300}>
                      <AreaChart data={analytics.s_curve} margin={{ left: 10, right: 10 }}>
                        <defs>
                          <linearGradient id="gradPlanned" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.02} />
                          </linearGradient>
                          <linearGradient id="gradActual" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0.02} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} />
                        <YAxis yAxisId="pct" domain={[0, 100]} tick={{ fontSize: 11 }} tickLine={false} unit="%" />
                        <YAxis yAxisId="cost" orientation="right" tick={{ fontSize: 11 }} tickLine={false} tickFormatter={(v) => `${(v / 1e6).toFixed(0)}M`} />
                        <Tooltip
                          contentStyle={{ borderRadius: "12px", border: "1px solid var(--border)", fontSize: 12 }}
                          formatter={(v: number | string, _name: string, item: { dataKey?: string | number }) => {
                            const key = item?.dataKey;
                            if (key === "actual_cost") return [`Rp ${Number(v).toLocaleString("id-ID")}`, t("business.chart_actual_cost")];
                            return [`${v}%`, key === "planned_pct" ? t("business.chart_planned_pct") : t("business.chart_actual_pct")];
                          }}
                        />
                        <Legend />
                        <Area yAxisId="pct" type="monotone" dataKey="planned_pct" name={t("business.chart_planned_pct")} stroke="#3b82f6" strokeWidth={2} fill="url(#gradPlanned)" dot={false} />
                        <Area yAxisId="pct" type="monotone" dataKey="actual_pct"  name={t("business.chart_actual_pct")}  stroke="#10b981" strokeWidth={2} fill="url(#gradActual)"  dot={false} />
                        <Bar  yAxisId="cost" dataKey="actual_cost" name={t("business.chart_actual_cost")} fill="#f59e0b" opacity={0.5} radius={[3,3,0,0]} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>

                  {/* Daily cost bar */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h2 className="font-bold text-base mb-1">{t("business.daily_cost_headcount_title")}</h2>
                    <p className="text-xs text-muted-foreground mb-4">{t("business.daily_cost_headcount_desc")}</p>
                    <ResponsiveContainer width="100%" height={240}>
                      <BarChart data={analytics.s_curve} margin={{ left: 0, right: 10 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} />
                        <YAxis yAxisId="cost" tick={{ fontSize: 11 }} tickLine={false} tickFormatter={(v) => `${(v/1e6).toFixed(0)}M`} />
                        <YAxis yAxisId="hc" orientation="right" tick={{ fontSize: 11 }} tickLine={false} />
                        <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid var(--border)", fontSize: 12 }}
                          formatter={(v: number | string, _name: string, item: { dataKey?: string | number }) => item?.dataKey === "daily_cost" ? [`Rp ${Number(v).toLocaleString("id-ID")}`, t("business.chart_daily_cost")] : [v, t("business.chart_headcount")]}
                        />
                        <Legend />
                        <Bar yAxisId="cost" dataKey="daily_cost"  name={t("business.chart_daily_cost")}  fill="#f59e0b" radius={[4,4,0,0]} />
                        <Bar yAxisId="hc"   dataKey="headcount"   name={t("business.chart_headcount")}   fill="#8b5cf6" radius={[4,4,0,0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  {/* MoM/Weekly trend table */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-3">{t("business.daily_trend_table_title")}</h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-muted-foreground border-b border-border font-semibold">
                            <th className="text-left pb-2 pr-3">{t("business.col_date")}</th>
                            <th className="text-right pb-2 pr-3">{t("business.col_planned_pct")}</th>
                            <th className="text-right pb-2 pr-3">{t("business.col_actual_pct")}</th>
                            <th className="text-right pb-2 pr-3">{t("business.col_deviation")}</th>
                            <th className="text-right pb-2 pr-3">{t("business.col_ev_rp")}</th>
                            <th className="text-right pb-2">{t("business.col_daily_cost")}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {analytics.s_curve.slice(-14).map((pt) => {
                            const dev = pt.actual_pct - pt.planned_pct;
                            return (
                              <tr key={pt.date}>
                                <td className="py-2 pr-3 font-medium">{pt.date}</td>
                                <td className="text-right pr-3">{pt.planned_pct}%</td>
                                <td className="text-right pr-3">{pt.actual_pct}%</td>
                                <td className={`text-right pr-3 font-semibold ${dev >= 0 ? "text-emerald-600" : "text-amber-500"}`}>{dev >= 0 ? "+" : ""}{dev.toFixed(1)}%</td>
                                <td className="text-right pr-3">{fmtCompact(pt.earned_value)}</td>
                                <td className="text-right">{fmtCompact(pt.daily_cost)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </motion.div>
              )}

              {/* ─── 4. FORECASTING ─── */}
              {activeTab === "forecast" && (
                <motion.div key="forecast"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  <h2 className="font-bold text-base">{t("business.forecast_title")}</h2>
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
                    <KPICard
                      label={t("business.kpi_est_days")}
                      value={analytics.forecasting.est_days_to_complete >= 999 ? "N/A" : t("business.days_unit", { count: analytics.forecasting.est_days_to_complete })}
                      color="blue"
                      sub={t("business.kpi_est_days_sub")}
                    />
                    <KPICard
                      label={t("business.kpi_forecast_30d")}
                      value={`${analytics.forecasting.forecast_30d_pct}%`}
                      color="cyan"
                      sub={t("business.kpi_forecast_30d_sub")}
                    />
                    <KPICard
                      label={t("business.kpi_eac_projection")}
                      value={fmtCompact(analytics.forecasting.projected_final_cost_eac)}
                      color="purple"
                      sub={t("business.budget_amount", { amount: fmtCompact(analytics.budget) })}
                    />
                    <KPICard
                      label={t("business.kpi_cost_overrun")}
                      value={analytics.forecasting.cost_overrun_projected > 0 ? fmtCompact(analytics.forecasting.cost_overrun_projected) : t("business.none")}
                      color={analytics.forecasting.cost_overrun_projected > 0 ? "red" : "green"}
                      trend={analytics.forecasting.cost_overrun_projected > 0 ? "down" : "up"}
                    />
                  </div>

                  {/* Forecast line chart */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-4">{t("business.forecast_chart_title")}</h3>
                    <ResponsiveContainer width="100%" height={240}>
                      <BarChart
                        data={[
                          { name: t("business.chart_budget"), value: analytics.budget, fill: "#3b82f6" },
                          { name: t("business.chart_eac"), value: analytics.forecasting.projected_final_cost_eac, fill: analytics.forecasting.cost_overrun_projected > 0 ? "#ef4444" : "#10b981" },
                          { name: t("business.chart_etc"), value: evm.etc, fill: "#8b5cf6" },
                          { name: t("business.chart_ac_spent"), value: evm.ac, fill: "#f59e0b" },
                        ]}
                        margin={{ left: 10, right: 10 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                        <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                        <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v/1e9).toFixed(1)}M`} />
                        <Tooltip contentStyle={{ borderRadius: "12px", border: "1px solid var(--border)", fontSize: 12 }}
                          formatter={(v: number | string) => [`Rp ${Number(v).toLocaleString("id-ID")}`, t("business.chart_value")]}
                        />
                        <Bar dataKey="value" radius={[6,6,0,0]}>
                          {[
                            { fill: "#3b82f6" },
                            { fill: analytics.forecasting.cost_overrun_projected > 0 ? "#ef4444" : "#10b981" },
                            { fill: "#8b5cf6" },
                            { fill: "#f59e0b" },
                          ].map((entry, index) => (
                            <Cell key={`cell-${index}`} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="glass-panel p-5 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-3">{t("business.forecast_assumptions_title")}</h3>
                    <ul className="space-y-2 text-sm text-muted-foreground">
                      <li className="flex gap-2"><span className="text-foreground font-medium">{t("business.forecast_label_velocity")}</span> {t("business.forecast_desc_velocity", { value: analytics.trend.velocity_7d_pct_per_day })}</li>
                      <li className="flex gap-2"><span className="text-foreground font-medium">{t("business.forecast_label_eac")}</span> {t("business.forecast_desc_eac")}</li>
                      <li className="flex gap-2"><span className="text-foreground font-medium">{t("business.forecast_label_30d")}</span> {t("business.forecast_desc_30d")}</li>
                      <li className="flex gap-2"><span className="text-foreground font-medium">{t("business.forecast_label_overrun")}</span> {t("business.forecast_desc_overrun")}</li>
                    </ul>
                  </div>
                </motion.div>
              )}

              {/* ─── 5. ANOMALI ─── */}
              {activeTab === "anomalies" && (
                <motion.div key="anomalies"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  <div className="flex items-center gap-3">
                    <h2 className="font-bold text-base">{t("business.anomalies_title")}</h2>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${
                      analytics.anomalies.length === 0
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
                        : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                    }`}>
                      {t("business.findings_count", { count: analytics.anomalies.length })}
                    </span>
                  </div>

                  {/* Root cause analysis */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-3 flex items-center gap-2"><Search size={14} /> {t("business.root_cause_title")}</h3>
                    <div className="space-y-3">
                      {analytics.root_cause_analysis.map((rc, i) => (
                        <div key={i} className={`p-4 rounded-xl border ${SEVERITY_STYLES[rc.severity]}`}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-semibold text-sm">{rc.category}</span>
                            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${SEVERITY_STYLES[rc.severity]}`}>{SEVERITY_LABEL[rc.severity] ?? rc.severity}</span>
                          </div>
                          <p className="text-sm opacity-90 mb-1">{rc.primary_factor}</p>
                          <p className="text-xs opacity-70 flex items-center gap-1"><Lightbulb size={11} /> {t("business.trigger_label", { trigger: rc.trigger })}</p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Anomaly list */}
                  {analytics.anomalies.length === 0 ? (
                    <div className="glass-panel p-8 rounded-2xl text-center">
                      <CheckCircle2 size={32} className="text-emerald-500 mx-auto mb-3" />
                      <p className="font-semibold text-sm">{t("business.anomalies_empty_title")}</p>
                      <p className="text-xs text-muted-foreground mt-1">{t("business.anomalies_empty_desc")}</p>
                    </div>
                  ) : (
                    <div className="glass-panel p-5 rounded-2xl space-y-3">
                      <h3 className="font-semibold text-sm">{t("business.anomalies_list_title")}</h3>
                      {analytics.anomalies.map((a, i) => (
                        <div key={i} className={`p-4 rounded-xl border ${SEVERITY_STYLES[a.severity]}`}>
                          <div className="flex items-center gap-2 mb-1">
                            <AlertTriangle size={14} />
                            <span className="font-semibold text-sm">{a.type.replace("_", " ")}</span>
                            <span className="text-xs opacity-70 ml-auto">{a.date}</span>
                          </div>
                          <p className="text-sm opacity-85">{a.description}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </motion.div>
              )}

              {/* ─── 6. REKOMENDASI ─── */}
              {activeTab === "recs" && (
                <motion.div key="recs"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  <h2 className="font-bold text-base">{t("business.recs_title")}</h2>
                  <div className="space-y-3">
                    {analytics.recommendations.map((rec, i) => (
                      <div key={i} className="glass-panel p-5 rounded-2xl flex gap-4 items-start">
                        <div className="shrink-0 w-8 h-8 rounded-full bg-foreground/8 flex items-center justify-center">
                          <span className="text-sm font-bold">{i + 1}</span>
                        </div>
                        <div>
                          <p className="text-sm font-medium leading-relaxed">{rec}</p>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Performance summary for context */}
                  <div className="glass-panel p-5 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-3 flex items-center gap-2"><Info size={14} /> {t("business.analysis_basis_title")}</h3>
                    <div className="grid grid-cols-2 lg:grid-cols-3 gap-3 text-xs">
                      {[
                        ["CPI", evm.cpi.toFixed(2), evm.cpi >= 1 ? "text-emerald-600" : "text-red-500"],
                        ["SPI", evm.spi.toFixed(2), evm.spi >= 1 ? "text-emerald-600" : "text-amber-500"],
                        [t("business.attendance_short"), `${analytics.labor.avg_attendance_pct}%`, analytics.labor.avg_attendance_pct >= 80 ? "text-emerald-600" : "text-amber-500"],
                        [t("business.deviation_short"), `${prog.deviation_pct >= 0 ? "+" : ""}${prog.deviation_pct.toFixed(1)}%`, prog.deviation_pct >= 0 ? "text-emerald-600" : "text-amber-500"],
                        [t("business.etc_short"), fmtCompact(evm.etc), "text-foreground"],
                        [t("business.velocity_short"), `${analytics.trend.velocity_7d_pct_per_day}%/hari`, "text-foreground"],
                      ].map(([label, val, cls]) => (
                        <div key={label} className="p-3 rounded-xl bg-muted/40">
                          <p className="text-muted-foreground">{label}</p>
                          <p className={`font-bold text-base mt-0.5 ${cls}`}>{val}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}

              {/* ─── 7. DRILL-DOWN ─── */}
              {activeTab === "drilldown" && (
                <motion.div key="drilldown"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  <div className="flex items-center justify-between">
                    <h2 className="font-bold text-base flex items-center gap-2"><Eye size={16} /> {t("business.drilldown_title")}</h2>
                    <span className="text-xs text-muted-foreground">{t("business.entries_count", { count: analytics.drill_down.length })}</span>
                  </div>

                  <div className="glass-panel rounded-2xl overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="bg-muted/50 text-muted-foreground font-semibold border-b border-border">
                            <th className="text-left py-3 px-4">{t("business.col_date")}</th>
                            <th className="text-right px-3">{t("business.col_planned_pct")}</th>
                            <th className="text-right px-3">{t("business.col_actual_pct")}</th>
                            <th className="text-right px-3">{t("business.col_deviation")}</th>
                            <th className="text-right px-3">{t("business.col_cost")}</th>
                            <th className="text-right px-3">{t("business.col_headcount")}</th>
                            <th className="text-right px-3">{t("business.col_hours")}</th>
                            <th className="text-left px-4">{t("business.col_tasks")}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-border">
                          {analytics.drill_down
                            .slice(drillPage * DRILL_PAGE_SIZE, (drillPage + 1) * DRILL_PAGE_SIZE)
                            .map((log) => {
                              const dev = log.actual_pct - log.planned_pct;
                              return (
                                <tr key={log.id} className="hover:bg-muted/30 transition-colors">
                                  <td className="py-2.5 px-4 font-medium">{log.date}</td>
                                  <td className="text-right px-3">{log.planned_pct.toFixed(1)}%</td>
                                  <td className="text-right px-3">{log.actual_pct.toFixed(1)}%</td>
                                  <td className={`text-right px-3 font-semibold ${dev >= 0 ? "text-emerald-600" : "text-amber-500"}`}>
                                    {dev >= 0 ? "+" : ""}{dev.toFixed(1)}%
                                  </td>
                                  <td className="text-right px-3">{fmtCompact(log.actual_cost)}</td>
                                  <td className="text-right px-3">{log.headcount}</td>
                                  <td className="text-right px-3">{log.work_hours}h</td>
                                  <td className="px-4 max-w-[160px] truncate text-muted-foreground">{log.tasks_completed}</td>
                                </tr>
                              );
                            })}
                        </tbody>
                      </table>
                    </div>
                    {analytics.drill_down.length > DRILL_PAGE_SIZE && (
                      <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                        <button
                          onClick={() => setDrillPage(Math.max(0, drillPage - 1))}
                          disabled={drillPage === 0}
                          className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-40 transition-colors"
                        >{t("business.prev")}</button>
                        <span className="text-xs text-muted-foreground">
                          {t("business.pagination", { page: drillPage + 1, total: Math.ceil(analytics.drill_down.length / DRILL_PAGE_SIZE) })}
                        </span>
                        <button
                          onClick={() => setDrillPage(Math.min(Math.ceil(analytics.drill_down.length / DRILL_PAGE_SIZE) - 1, drillPage + 1))}
                          disabled={(drillPage + 1) * DRILL_PAGE_SIZE >= analytics.drill_down.length}
                          className="text-xs font-semibold px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-40 transition-colors"
                        >{t("business.next")}</button>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}

              {/* ─── 8. METODOLOGI ─── */}
              {activeTab === "methodology" && (
                <motion.div key="methodology"
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  className="space-y-4"
                >
                  <h2 className="font-bold text-base flex items-center gap-2"><Database size={16} /> {t("business.methodology_title")}</h2>

                  <div className="glass-panel p-6 rounded-2xl space-y-4">
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">{t("business.field_framework")}</p>
                      <p className="text-sm font-medium">{analytics.methodology.framework}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">{t("business.field_data_source")}</p>
                      <p className="text-sm font-medium">{analytics.methodology.data_source}</p>
                    </div>
                    <div>
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">{t("business.field_calculated_at")}</p>
                      <p className="text-sm font-medium">{new Date(analytics.methodology.calculated_at).toLocaleString("id-ID")}</p>
                    </div>
                  </div>

                  <div className="glass-panel p-6 rounded-2xl">
                    <h3 className="font-semibold text-sm mb-4">{t("business.definitions_title")}</h3>
                    <div className="space-y-3">
                      {[
                        [t("business.def_pv_term"), t("business.def_pv")],
                        [t("business.def_ev_term"), t("business.def_ev")],
                        [t("business.def_ac_term"), t("business.def_ac")],
                        [t("business.def_cpi_term"), t("business.def_cpi")],
                        [t("business.def_spi_term"), t("business.def_spi")],
                        [t("business.def_cv_term"), t("business.def_cv")],
                        [t("business.def_sv_term"), t("business.def_sv")],
                        [t("business.def_eac_term"), t("business.def_eac")],
                        [t("business.def_etc_term"), t("business.def_etc")],
                        [t("business.def_velocity_term"), t("business.def_velocity")],
                        [t("business.def_target_term"), t("business.def_target")],
                        [t("business.def_anomaly_term"), t("business.def_anomaly")],
                      ].map(([term, def]) => (
                        <div key={term} className="p-3 rounded-xl bg-muted/40">
                          <p className="text-xs font-bold mb-1">{term}</p>
                          <p className="text-xs text-muted-foreground">{def}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </FocusScrollSection>
      )}

      {/* ── Empty state ── */}
      {!loadingProj && projects.length === 0 && (
        <div className="glass-panel p-12 rounded-3xl text-center">
          <Building2 size={40} className="text-muted-foreground mx-auto mb-4" />
          <h2 className="font-bold text-lg mb-2">{t("business.empty_projects_title")}</h2>
          <p className="text-sm text-muted-foreground">{t("business.empty_projects_desc")}</p>
        </div>
      )}

      {/* ── Daily Input Modal ── */}
      <AnimatePresence>
        {showModal && selectedId && (
          <DailyInputModal
            projectId={selectedId}
            onClose={() => setShowModal(false)}
            onSuccess={() => fetchAnalytics(selectedId!)}
          />
        )}
      </AnimatePresence>

      {/* ── Executive Report Modal ── */}
      <AnimatePresence>
        {showReport && report && (
          <motion.div
            className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-4"
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          >
            <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setShowReport(false)} />
            <motion.div
              className="relative w-full max-w-3xl max-h-[85vh] bg-card border border-border rounded-3xl shadow-2xl flex flex-col overflow-hidden"
              initial={{ scale: 0.92, y: 30 }} animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.92, y: 30 }}
              transition={{ type: "spring", stiffness: 400, damping: 34 }}
            >
              <div className="flex items-center justify-between px-6 py-4 border-b border-border shrink-0">
                <div>
                  <h2 className="font-bold text-lg">{t("business.report_title")}</h2>
                  <p className="text-xs text-muted-foreground capitalize">{t("business.period_" + reportPeriod)} · {analytics?.project_name}</p>
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={`data:text/markdown;charset=utf-8,${encodeURIComponent(report.markdown)}`}
                    download={`report_${selectedId}_${reportPeriod}.md`}
                    className="flex items-center gap-1.5 text-xs font-semibold border border-border px-3 py-1.5 rounded-lg hover:bg-muted transition-colors"
                  >
                    <Download size={13} /> .MD
                  </a>
                  <a
                    href={`data:text/html;charset=utf-8,${encodeURIComponent(report.html)}`}
                    download={`report_${selectedId}_${reportPeriod}.html`}
                    className="flex items-center gap-1.5 text-xs font-semibold border border-border px-3 py-1.5 rounded-lg hover:bg-muted transition-colors"
                  >
                    <Download size={13} /> .HTML
                  </a>
                  <button
                    onClick={() => {
                      const printWin = window.open("", "_blank");
                      if (printWin) {
                        printWin.document.write(`
                          <!DOCTYPE html>
                          <html>
                          <head>
                            <title>Executive Report - ${analytics?.project_name}</title>
                            <style>
                              @media print { @page { margin: 15mm; size: A4; } }
                              body { font-family: sans-serif; padding: 24px; color: #111; }
                            </style>
                          </head>
                          <body onload="window.print();">
                            ${report.html}
                          </body>
                          </html>
                        `);
                        printWin.document.close();
                      }
                    }}
                    className="flex items-center gap-1.5 text-xs font-semibold border border-primary bg-primary text-primary-foreground px-3 py-1.5 rounded-lg hover:opacity-90 transition-opacity"
                  >
                    <Download size={13} /> .PDF
                  </button>
                  <button onClick={() => setShowReport(false)} className="p-1.5 rounded-lg hover:bg-muted transition-colors">
                    <X size={18} />
                  </button>
                </div>
              </div>
              <div className="overflow-y-auto p-6">
                <pre className="text-xs text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed">
                  {report.markdown}
                </pre>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

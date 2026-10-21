"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/i18n/context";

// ─── API data shapes (canonical ledger endpoints, Phases 5-15) ───────────────

export interface HealthScore {
  ok?: boolean;
  as_of?: string;
  total_score?: number;
  grade?: string;
  components?: Array<{ key: string; name?: string; score: number; weight: number; explanation?: string }>;
}

export interface NetWorth {
  ok?: boolean;
  as_of?: string;
  cash_assets?: number;
  per_account?: Array<{ account_id: number; name: string; balance: number }>;
  investments?: number;
  net_worth?: number;
  transfers_transparent?: boolean;
}

export interface SafeToSpend {
  ok?: boolean;
  as_of?: string;
  horizon_days?: number;
  current_balance?: number;
  expected_outflows?: number;
  estimated_outflows?: number;
  upcoming_outflows?: number;
  buffer_pct?: number;
  buffer_amount?: number;
  safe_to_spend?: number;
  sources?: Array<{ source: string; amount: number }>;
}

export interface ForecastPoint {
  day?: number;
  date?: string;
  type?: string;
  amount?: number;
  balance?: number;
}

export interface Forecast {
  ok?: boolean;
  days?: number;
  start_balance?: number;
  planned?: number;
  cashflow?: ForecastPoint[];
  final_balance?: number;
  low_point?: number;
  insight?: { warning?: boolean; message?: string } | null;
}

export interface InsightCard {
  type?: string;
  severity?: string;
  title?: string;
  explanation?: string;
  refs?: { endpoint?: string };
}

export interface Insights {
  ok?: boolean;
  as_of?: string;
  summary?: { alert?: number; warning?: number; positive?: number; info?: number };
  insights?: InsightCard[];
}

export interface Anomaly {
  rule?: string;
  severity?: string;
  category?: string;
  explanation?: string;
  avg?: number;
  delta?: number;
}

export interface AnomaliesStatus {
  ok?: boolean;
  window_days?: number;
  baseline_days?: number;
  window_start?: string;
  anomalies?: Anomaly[];
}

export interface BudgetCategory {
  category?: string;
  limit?: number;
  actual?: number;
  pct?: number;
  level?: string;
}

export interface BudgetStatus {
  ok?: boolean;
  year?: number;
  month?: number;
  categories?: BudgetCategory[];
}

// ─── Formatters ───────────────────────────────────────────────────────────────

const fmtIDR = (n: number | undefined) =>
  "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(n || 0));

const SEVERITY_LABEL: Record<string, string> = {
  alert: "overview.severity_alert",
  warning: "overview.severity_warning",
  info: "overview.severity_info",
  positive: "overview.severity_positive",
  high: "overview.severity_high",
  medium: "overview.severity_medium",
};

type Translate = (key: string) => string;

function severityLabel(t: Translate, severity?: string): string {
  const key = severity ? SEVERITY_LABEL[severity] : undefined;
  return key ? t(key) : (severity ?? "");
}

// ─── Section shells ───────────────────────────────────────────────────────────

function Section({
  title,
  children,
  status,
}: {
  title: string;
  children?: ReactNode;
  status?: "offline" | "empty";
}) {
  const { t } = useI18n();
  return (
    <section
      aria-labelledby={title}
      className="rounded-2xl border border-border bg-card p-5 space-y-3"
    >
      <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">
        {title}
      </h2>
      {status === "offline" ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          {t("overview.section_offline")}
        </p>
      ) : status === "empty" ? (
        <p className="text-xs text-muted-foreground">
          {t("overview.section_empty")}
        </p>
      ) : (
        children
      )}
    </section>
  );
}

function HealthScoreSection({ data }: { data: HealthScore | null }) {
  const { t } = useI18n();
  const title = t("overview.section_health");
  if (!data) return <Section title={title} status="offline" />;
  return (
    <Section title={title}>
      <div className="flex items-end gap-3">
        <p className="text-4xl font-extrabold">{data.total_score ?? 0}</p>
        <p className="text-lg font-bold text-blue-600 dark:text-blue-400">
          {data.grade ?? "—"}
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {(data.components ?? []).map((c) => (
          <div key={c.key} className="rounded-xl bg-muted/50 border border-border p-3">
            <div className="flex justify-between text-xs font-semibold">
              <span>{c.name ?? c.key}</span>
              <span>
                {t("overview.score_weight", { score: c.score, weight: c.weight })}
              </span>
            </div>
            {c.explanation && (
              <p className="text-[11px] text-muted-foreground mt-1">{c.explanation}</p>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

function NetWorthSection({ data }: { data: NetWorth | null }) {
  const { t } = useI18n();
  const title = t("overview.section_net_worth");
  if (!data) return <Section title={title} status="offline" />;
  return (
    <Section title={title}>
      <div className="flex items-end gap-3">
        <p className="text-3xl font-extrabold">{fmtIDR(data.net_worth)}</p>
        <p className="text-xs text-muted-foreground">
          {t("overview.net_worth_breakdown", {
            cash: fmtIDR(data.cash_assets),
            investments: fmtIDR(data.investments),
          })}
        </p>
      </div>
      <ul className="text-xs space-y-1">
        {(data.per_account ?? []).map((a) => (
          <li key={a.account_id} className="flex justify-between">
            <span className="text-muted-foreground">{a.name}</span>
            <span className="font-semibold">{fmtIDR(a.balance)}</span>
          </li>
        ))}
      </ul>
      {data.transfers_transparent === false && (
        <p className="text-[11px] font-bold text-red-600 dark:text-red-400">
          {t("overview.transfers_mismatch")}
        </p>
      )}
    </Section>
  );
}

function SafeToSpendSection({ data }: { data: SafeToSpend | null }) {
  const { t } = useI18n();
  if (!data) {
    return <Section title={t("overview.section_safe_to_spend")} status="offline" />;
  }
  const safe = data.safe_to_spend ?? 0;
  return (
    <Section
      title={t("overview.safe_to_spend_title", {
        days: data.horizon_days ?? 30,
        buffer: data.buffer_pct ?? 10,
      })}
    >
      <p
        className={`text-3xl font-extrabold ${
          safe < 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"
        }`}
      >
        {fmtIDR(safe)}
      </p>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl bg-muted/50 border border-border p-3">
          <p className="text-muted-foreground">{t("overview.current_balance")}</p>
          <p className="font-bold">{fmtIDR(data.current_balance)}</p>
        </div>
        <div className="rounded-xl bg-muted/50 border border-border p-3">
          <p className="text-muted-foreground">{t("overview.upcoming_outflows")}</p>
          <p className="font-bold">{fmtIDR(data.upcoming_outflows)}</p>
        </div>
      </div>
    </Section>
  );
}

function ForecastSection({ data }: { data: Forecast | null }) {
  const { t } = useI18n();
  if (!data) return <Section title={t("overview.section_forecast")} status="offline" />;
  const points = data.cashflow ?? [];
  return (
    <Section title={t("overview.forecast_title", { days: data.days ?? 30 })}>
      <p className="text-xs text-muted-foreground">
        {t("overview.forecast_start_end", {
          start: fmtIDR(data.start_balance),
          end: fmtIDR(data.final_balance),
        })}
      </p>
      {data.insight?.message && (
        <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-400">
          {data.insight.message}
        </p>
      )}
      {points.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("overview.no_data")}</p>
      ) : (
        <div className="max-h-48 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground uppercase text-[10px]">
              <tr>
                <th className="py-1 pr-2">{t("overview.table_day")}</th>
                <th className="py-1 pr-2">{t("overview.table_type")}</th>
                <th className="py-1 pr-2 text-right">{t("overview.table_amount")}</th>
                <th className="py-1 text-right">{t("overview.table_balance")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {points.map((p, idx) => (
                <tr key={idx}>
                  <td className="py-1 pr-2">{p.day ?? p.date ?? ""}</td>
                  <td className="py-1 pr-2">{p.type ?? ""}</td>
                  <td className="py-1 pr-2 text-right font-semibold">{fmtIDR(p.amount)}</td>
                  <td className="py-1 text-right text-muted-foreground">{fmtIDR(p.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Section>
  );
}

function InsightsSection({ data }: { data: Insights | null }) {
  const { t } = useI18n();
  const title = t("overview.section_insights");
  if (!data) return <Section title={title} status="offline" />;
  const cards = data.insights ?? [];
  if (cards.length === 0) return <Section title={title} status="empty" />;
  return (
    <Section title={title}>
      <p className="text-xs text-muted-foreground">
        {t("overview.insights_summary", {
          alert: data.summary?.alert ?? 0,
          warning: data.summary?.warning ?? 0,
          positive: data.summary?.positive ?? 0,
          info: data.summary?.info ?? 0,
        })}
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {cards.map((c) => (
          <div key={c.type} className="rounded-xl bg-muted/50 border border-border p-3">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border border-current">
                {severityLabel(t, c.severity ?? "info")}
              </span>
              <h3 className="text-xs font-bold">{c.title ?? c.type}</h3>
            </div>
            {c.explanation && (
              <p className="text-[11px] text-muted-foreground mt-1">{c.explanation}</p>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

function AnomaliesSection({ data }: { data: AnomaliesStatus | null }) {
  const { t } = useI18n();
  const title = t("overview.section_anomalies");
  if (!data) return <Section title={title} status="offline" />;
  const anomalies = data.anomalies ?? [];
  if (anomalies.length === 0) return <Section title={title} status="empty" />;
  return (
    <Section
      title={t("overview.anomalies_title", {
        window: data.window_days ?? 30,
        baseline: data.baseline_days ?? 90,
      })}
    >
      <div className="space-y-2">
        {anomalies.map((a, idx) => (
          <div key={idx} className="rounded-xl bg-muted/50 border border-border p-3">
            <div className="flex items-center gap-2 text-xs">
              <span
                className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border border-current ${
                  a.severity === "high" ? "text-red-500" : "text-amber-500"
                }`}
              >
                {severityLabel(t, a.severity ?? "")}
              </span>
              <span className="font-bold">{a.category}</span>
              <span className="text-muted-foreground">{a.rule}</span>
            </div>
            {a.explanation && (
              <p className="text-[11px] text-muted-foreground mt-1">{a.explanation}</p>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

function BudgetSection({ data }: { data: BudgetStatus | null }) {
  const { t } = useI18n();
  const title = t("overview.section_budget");
  if (!data) return <Section title={title} status="offline" />;
  const cats = data.categories ?? [];
  if (cats.length === 0) return <Section title={title} status="empty" />;
  return (
    <Section title={t("overview.budget_title", { month: data.month ?? "-", year: data.year ?? "-" })}>
      <div className="space-y-2">
        {cats.map((c) => {
          const pct = Math.min(200, c.pct ?? 0);
          const color =
            pct > 100 ? "bg-red-500" : pct > 80 ? "bg-amber-500" : "bg-emerald-500";
          return (
            <div key={c.category} className="space-y-1">
              <div className="flex justify-between text-xs font-semibold">
                <span>{c.category}</span>
                <span>
                  {fmtIDR(c.actual)} / {fmtIDR(c.limit)} ({Math.round(pct)}%)
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted overflow-hidden">
                <div
                  className={`h-full rounded-full ${color}`}
                  style={{ width: `${Math.min(100, pct)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Section>
  );
}

// ─── View ─────────────────────────────────────────────────────────────────────

export default function OverviewView({
  health,
  netWorth,
  safeToSpend,
  forecast,
  insights,
  anomalies,
  budget,
}: {
  health: HealthScore | null;
  netWorth: NetWorth | null;
  safeToSpend: SafeToSpend | null;
  forecast: Forecast | null;
  insights: Insights | null;
  anomalies: AnomaliesStatus | null;
  budget: BudgetStatus | null;
}) {
  const { t } = useI18n();
  return (
    <div className="min-h-dvh bg-background text-foreground p-4 md:p-8 font-sans">
      <main className="max-w-5xl mx-auto space-y-6">
        <header className="rounded-2xl border border-border bg-card p-6 shadow-md">
          <h1 className="text-2xl font-extrabold tracking-tight">
            {t("overview.page_title")}
          </h1>
          <p className="text-sm text-muted-foreground">
            {t("overview.page_subtitle")}
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <HealthScoreSection data={health} />
          <NetWorthSection data={netWorth} />
          <SafeToSpendSection data={safeToSpend} />
          <BudgetSection data={budget} />
        </div>

        <ForecastSection data={forecast} />
        <InsightsSection data={insights} />
        <AnomaliesSection data={anomalies} />

        <footer className="text-center text-xs text-muted-foreground">
          {t("overview.footer_endpoints")}
        </footer>
      </main>
    </div>
  );
}

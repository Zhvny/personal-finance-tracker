"use client";

import type { ReactNode } from "react";
import { useI18n } from "@/i18n/context";

// ─── API data shapes (canonical ledger endpoints) ────────────────────────────

export interface HealthScore {
  ok?: boolean;
  as_of?: string;
  total_score?: number;
  grade?: string;
  components?: Array<{ key: string; name?: string; score: number; weight: number; explanation?: string }>;
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
  evidence?: string;
}

export interface AnomaliesStatus {
  ok?: boolean;
  window_days?: number;
  baseline_days?: number;
  anomalies?: Anomaly[];
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

const SEVERITY_LABEL: Record<string, string> = {
  alert: "behavioral.severity_alert",
  warning: "behavioral.severity_warning",
  info: "behavioral.severity_info",
  positive: "behavioral.severity_positive",
  high: "behavioral.severity_high",
  medium: "behavioral.severity_medium",
};

type Translate = (key: string, fallbackOrParams?: string | Record<string, string | number>) => string;

function severityLabel(t: Translate, severity?: string): string {
  const key = severity ? SEVERITY_LABEL[severity] : undefined;
  return key ? t(key) : (severity ?? "");
}

// ─── Section shells ───────────────────────────────────────────────────────────

function Card({
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
    <section aria-labelledby={title} className="rounded-2xl border border-border bg-card p-5 space-y-3">
      <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">{title}</h2>
      {status === "offline" ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          {t("behavioral.section_offline")}
        </p>
      ) : status === "empty" ? (
        <p className="text-xs text-muted-foreground">{t("behavioral.section_empty")}</p>
      ) : (
        children
      )}
    </section>
  );
}

function HealthCard({ data }: { data: HealthScore | null }) {
  const { t } = useI18n();
  const title = t("behavioral.section_health");
  if (!data) return <Card title={title} status="offline" />;
  return (
    <Card title={title}>
      <div className="flex items-end gap-3">
        <p className="text-4xl font-extrabold">{data.total_score ?? 0}</p>
        <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{data.grade ?? "—"}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {(data.components ?? []).map((c) => (
          <div key={c.key} className="rounded-xl bg-muted/50 border border-border p-3">
            <div className="flex justify-between text-xs font-semibold">
              <span>{c.name ?? c.key}</span>
              <span>{t("behavioral.score_weight", { score: c.score, weight: c.weight })}</span>
            </div>
            {c.explanation && (
              <p className="text-[11px] text-muted-foreground mt-1">{c.explanation}</p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function InsightsCard({ data }: { data: Insights | null }) {
  const { t } = useI18n();
  const title = t("behavioral.section_insights");
  if (!data) return <Card title={title} status="offline" />;
  const cards = data.insights ?? [];
  if (cards.length === 0) return <Card title={title} status="empty" />;
  return (
    <Card title={title}>
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
    </Card>
  );
}

function AnomaliesCard({ data }: { data: AnomaliesStatus | null }) {
  const { t } = useI18n();
  const title = t("behavioral.section_anomalies");
  if (!data) return <Card title={title} status="offline" />;
  const anomalies = data.anomalies ?? [];
  if (anomalies.length === 0) return <Card title={title} status="empty" />;
  return (
    <Card
      title={t("behavioral.anomalies_title", {
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
            {a.evidence && (
              <p className="text-[10px] font-mono text-muted-foreground mt-1">
                {t("behavioral.evidence_label", { evidence: a.evidence })}
              </p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── View ─────────────────────────────────────────────────────────────────────

export default function BehavioralView({
  health,
  insights,
  anomalies,
}: {
  health: HealthScore | null;
  insights: Insights | null;
  anomalies: AnomaliesStatus | null;
}) {
  const { t } = useI18n();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{t("behavioral.page_title")}</h1>
        <p className="text-muted-foreground mt-1">{t("behavioral.page_subtitle")}</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <HealthCard data={health} />
        <AnomaliesCard data={anomalies} />
      </div>
      <InsightsCard data={insights} />
    </div>
  );
}

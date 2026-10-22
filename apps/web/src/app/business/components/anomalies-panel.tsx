"use client";

import { CheckCircle2, Lightbulb, Search } from "lucide-react";
import { SEVERITY_STYLES, type Analytics } from "../types";
import { useI18n } from "@/i18n/context";

const SEVERITY_LABEL: Record<string, string> = {
  HIGH: "business.severity_high",
  MEDIUM: "business.severity_medium",
  LOW: "business.severity_low",
  WARNING: "business.severity_warning",
  CRITICAL: "business.severity_critical",
};

export function AnomaliesPanel({ analytics }: { analytics: Analytics }) {
  const { t } = useI18n();
  return (
    <div className="space-y-4">
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
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${SEVERITY_STYLES[rc.severity]}`}>{SEVERITY_LABEL[rc.severity] ? t(SEVERITY_LABEL[rc.severity]) : rc.severity}</span>
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
          {analytics.anomalies.map((a, i) => (
            <div key={i} className={`p-4 rounded-xl border ${SEVERITY_STYLES[a.severity]}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="font-semibold text-sm">{a.type}</span>
                <span className="text-xs text-muted-foreground">{a.date}</span>
              </div>
              <p className="text-sm opacity-90">{a.description}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

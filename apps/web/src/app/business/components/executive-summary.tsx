"use client";

import { BADGE_ICONS, BADGE_STYLES, type Analytics } from "../types";

export function ExecutiveSummary({ analytics, fmt }: { analytics: Analytics; fmt: (n: number) => string }) {
  if (!analytics.executive_summary) return null;

  return (
    <div className={`rounded-2xl border p-5 ${BADGE_STYLES[analytics.status_badge]}`}>
      <div className="flex items-start gap-3">
        <div className="mt-0.5 shrink-0">{BADGE_ICONS[analytics.status_badge]}</div>
        <div>
          <p className="text-xs font-bold uppercase tracking-wider opacity-70 mb-1">
            Executive Summary · {analytics.project_name} ({analytics.project_code})
          </p>
          <p className="text-sm font-medium leading-relaxed">
            {analytics.executive_summary.headline}
          </p>
          <div className="flex flex-wrap gap-4 mt-3 text-xs font-semibold opacity-80">
            <span>CPI {analytics.executive_summary.cpi.toFixed(2)}</span>
            <span>SPI {analytics.executive_summary.spi.toFixed(2)}</span>
            <span>Deviasi {analytics.executive_summary.progress_deviation >= 0 ? "+" : ""}{analytics.executive_summary.progress_deviation.toFixed(1)}%</span>
            <span>Budget {fmt(analytics.budget)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

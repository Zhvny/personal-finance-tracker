"use client";

import { useState } from "react";
import type { Analytics } from "../types";
import { useI18n } from "@/i18n/context";

const DRILL_PAGE_SIZE = 10;

export function DrilldownTable({ analytics, fmtCompact }: { analytics: Analytics; fmtCompact: (n: number) => string }) {
  const { t } = useI18n();
  const [drillPage, setDrillPage] = useState(0);

  if (!analytics.drill_down || analytics.drill_down.length === 0) return null;

  const start = drillPage * DRILL_PAGE_SIZE;
  const pageData = analytics.drill_down.slice(start, start + DRILL_PAGE_SIZE);

  return (
    <div className="glass-panel p-5 rounded-2xl">
      <h3 className="font-semibold text-sm mb-4">{t("business.drilldown_table_title")}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted-foreground font-semibold border-b border-border">
              <th className="text-left pb-2 px-3">{t("business.col_date")}</th>
              <th className="text-right pb-2 px-3">{t("business.col_planned_pct")}</th>
              <th className="text-right pb-2 px-3">{t("business.col_actual_pct")}</th>
              <th className="text-right pb-2 px-3">{t("business.col_cost")}</th>
              <th className="text-right pb-2 px-3">{t("business.col_headcount")}</th>
              <th className="text-right pb-2 px-3">{t("business.col_hours")}</th>
              <th className="text-left pb-2 px-3">{t("business.col_tasks")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {pageData.map((log) => (
              <tr key={log.id} className="hover:bg-muted/30 transition-colors">
                <td className="py-2.5 px-3 text-xs font-medium">{log.date}</td>
                <td className="text-right px-3">{log.planned_pct.toFixed(1)}%</td>
                <td className="text-right px-3">{log.actual_pct.toFixed(1)}%</td>
                <td className="text-right px-3">{fmtCompact(log.actual_cost)}</td>
                <td className="text-right px-3">{log.headcount}</td>
                <td className="text-right px-3">{log.work_hours}h</td>
                <td className="px-4 max-w-[160px] truncate text-muted-foreground">{log.tasks_completed}</td>
              </tr>
            ))}
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
  );
}

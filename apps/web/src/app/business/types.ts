import { ReactNode } from "react";

export interface Project {
  id: number;
  name: string;
  code: string;
  budget: number;
  status: string;
  startDate: string;
  endDate: string;
}

export interface EVM {
  pv: number; ev: number; ac: number;
  cpi: number; spi: number;
  cv: number; sv: number;
  eac: number; etc: number;
}

export interface Analytics {
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
  milestones: { total: number; completed: number; items: any[] };
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
    planned_pct: number; actual_pct: number;
    actual_cost: number; headcount: number; work_hours: number;
    tasks_completed: string; notes: string;
  }[];
  methodology: {
    framework: string;
    data_source: string;
    calculated_at: string;
  };
}

export const BADGE_ICONS: Record<string, ReactNode> = {
  ON_TRACK: null,
  WARNING: null,
  CRITICAL: null,
};

export const BADGE_STYLES: Record<string, string> = {
  ON_TRACK: "bg-emerald-50 dark:bg-emerald-950/20 border-emerald-200 dark:border-emerald-800",
  WARNING:  "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800",
  CRITICAL: "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800",
};

export const SEVERITY_STYLES: Record<string, string> = {
  LOW:      "bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800",
  MEDIUM:   "bg-amber-50 dark:bg-amber-950/20 border-amber-200 dark:border-amber-800",
  HIGH:     "bg-red-50 dark:bg-red-950/20 border-red-200 dark:border-red-800",
  CRITICAL: "bg-red-100 dark:bg-red-900/30 border-red-300 dark:border-red-700",
};

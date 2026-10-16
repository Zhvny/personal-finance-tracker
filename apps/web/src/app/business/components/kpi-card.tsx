"use client";

import { ArrowUpRight, ArrowDownRight } from "lucide-react";

export function KPICard({ label, value, sub, color = "blue", large = false, trend }: {
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

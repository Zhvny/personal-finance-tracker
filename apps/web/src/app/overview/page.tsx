import type { Metadata } from "next";
import { resolveApiBase } from "@/lib/api";

import OverviewView, {
  type HealthScore,
  type NetWorth,
  type SafeToSpend,
  type Forecast,
  type Insights,
  type AnomaliesStatus,
  type BudgetStatus,
} from "./overview-view";

export const metadata: Metadata = {
  title: "Finance Overview",
  description:
    "Canonical finance overview: health score, net worth, safe-to-spend, forecast, insights, and anomalies — all computed by the deterministic backend engine.",
};

// ─── Safe fetch helper (mirrors page.tsx: abort, no error leakage) ───────────

async function safeFetch<T>(path: string): Promise<T | null> {
  try {
    const apiUrl = resolveApiBase();
    const apiKey = process.env.FINANCE_TRACKER_API_KEY || "";
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const headers: Record<string, string> = {};
    if (apiKey) headers["Authorization"] = `Bearer ${apiKey}`;

    const res = await fetch(`${apiUrl}${path}`, {
      next: { revalidate: 60 },
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      console.error(`[Overview] API error: ${res.status} ${path}`);
      return null;
    }
    const data = await res.json();
    return data as T;
  } catch (error) {
    console.error(`[Overview] Fetch failed: ${path}`, error);
    return null;
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default async function OverviewPage() {
  const [health, netWorth, safeToSpend, forecast, insights, anomalies, budget] =
    await Promise.all([
      safeFetch<HealthScore>("/api/health-score"),
      safeFetch<NetWorth>("/api/net-worth"),
      safeFetch<SafeToSpend>("/api/safe-to-spend"),
      safeFetch<Forecast>("/api/forecast"),
      safeFetch<Insights>("/api/insights"),
      safeFetch<AnomaliesStatus>("/api/anomalies/status"),
      safeFetch<BudgetStatus>("/api/budget/status"),
    ]);

  return (
    <OverviewView
      health={health}
      netWorth={netWorth}
      safeToSpend={safeToSpend}
      forecast={forecast}
      insights={insights}
      anomalies={anomalies}
      budget={budget}
    />
  );
}

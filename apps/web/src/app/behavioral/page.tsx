import type { Metadata } from "next";
import { resolveApiBase } from "@/lib/api";

import BehavioralView, {
  type HealthScore,
  type Insights,
  type AnomaliesStatus,
} from "./behavioral-view";

export const metadata: Metadata = {
  title: "Behavioral Insights",
  description:
    "Explainable behavioral finance from the canonical ledger: health score, insight cards, and anomaly detection — deterministic numbers only.",
  alternates: { canonical: "/behavioral" },
  openGraph: {
    title: "Behavioral Insights | Alpha",
    description: "Health score, insights, and anomalies computed by the deterministic engine.",
    url: "/behavioral",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "Alpha Behavioral Insights" }],
  },
  twitter: {
    card: "summary_large_image",
    title: "Behavioral Insights | Alpha",
    description: "Health score, insights, and anomalies computed by the deterministic engine.",
  },
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
      console.error(`[Behavioral] API error: ${res.status} ${path}`);
      return null;
    }
    return (await res.json()) as T;
  } catch (error) {
    console.error(`[Behavioral] Fetch failed: ${path}`, error);
    return null;
  }
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default async function BehavioralPage() {
  const [health, insights, anomalies] = await Promise.all([
    safeFetch<HealthScore>("/api/health-score"),
    safeFetch<Insights>("/api/insights"),
    safeFetch<AnomaliesStatus>("/api/anomalies/status"),
  ]);

  return (
    <BehavioralView
      health={health}
      insights={insights}
      anomalies={anomalies}
    />
  );
}

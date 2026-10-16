import type { Metadata } from "next";
import { resolveApiBase } from "@/lib/api";

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

// ─── Canonical endpoint shapes (Phases 12-14) ─────────────────────────────────

interface HealthScore {
  ok?: boolean;
  as_of?: string;
  total_score?: number;
  grade?: string;
  components?: Array<{ key: string; name?: string; score: number; weight: number; explanation?: string }>;
}

interface InsightCard {
  type?: string;
  severity?: string;
  title?: string;
  explanation?: string;
  refs?: { endpoint?: string };
}

interface Insights {
  ok?: boolean;
  as_of?: string;
  summary?: { alert?: number; warning?: number; positive?: number; info?: number };
  insights?: InsightCard[];
}

interface Anomaly {
  rule?: string;
  severity?: string;
  category?: string;
  explanation?: string;
  evidence?: string;
}

interface AnomaliesStatus {
  ok?: boolean;
  window_days?: number;
  baseline_days?: number;
  anomalies?: Anomaly[];
}

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

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SEVERITY_LABEL: Record<string, string> = {
  alert: "Alert",
  warning: "Perhatian",
  info: "Info",
  positive: "Positif",
  high: "Tinggi",
  medium: "Sedang",
};

function Card({
  title,
  children,
  status,
}: {
  title: string;
  children?: React.ReactNode;
  status?: "offline" | "empty";
}) {
  return (
    <section aria-labelledby={title} className="rounded-2xl border border-border bg-card p-5 space-y-3">
      <h2 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">{title}</h2>
      {status === "offline" ? (
        <p className="text-xs text-amber-700 dark:text-amber-400">
          API tidak tersedia atau gagal dimuat.
        </p>
      ) : status === "empty" ? (
        <p className="text-xs text-muted-foreground">Belum ada data.</p>
      ) : (
        children
      )}
    </section>
  );
}

function HealthCard({ data }: { data: HealthScore | null }) {
  if (!data) return <Card title="Skor Kesehatan Keuangan" status="offline" />;
  return (
    <Card title="Skor Kesehatan Keuangan">
      <div className="flex items-end gap-3">
        <p className="text-4xl font-extrabold">{data.total_score ?? 0}</p>
        <p className="text-lg font-bold text-blue-600 dark:text-blue-400">{data.grade ?? "—"}</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {(data.components ?? []).map((c) => (
          <div key={c.key} className="rounded-xl bg-muted/50 border border-border p-3">
            <div className="flex justify-between text-xs font-semibold">
              <span>{c.name ?? c.key}</span>
              <span>
                {c.score} / 100 (bobot {c.weight})
              </span>
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
  if (!data) return <Card title="Wawasan Perilaku" status="offline" />;
  const cards = data.insights ?? [];
  if (cards.length === 0) return <Card title="Wawasan Perilaku" status="empty" />;
  return (
    <Card title="Wawasan Perilaku">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        {cards.map((c) => (
          <div key={c.type} className="rounded-xl bg-muted/50 border border-border p-3">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase border border-current">
                {SEVERITY_LABEL[c.severity ?? "info"] ?? c.severity}
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
  if (!data) return <Card title="Deteksi Anomali Perilaku" status="offline" />;
  const anomalies = data.anomalies ?? [];
  if (anomalies.length === 0) return <Card title="Deteksi Anomali Perilaku" status="empty" />;
  return (
    <Card
      title={`Deteksi Anomali Perilaku — window ${data.window_days ?? 30} hari vs baseline ${data.baseline_days ?? 90} hari`}
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
                {SEVERITY_LABEL[a.severity ?? ""] ?? a.severity}
              </span>
              <span className="font-bold">{a.category}</span>
              <span className="text-muted-foreground">{a.rule}</span>
            </div>
            {a.explanation && (
              <p className="text-[11px] text-muted-foreground mt-1">{a.explanation}</p>
            )}
            {a.evidence && (
              <p className="text-[10px] font-mono text-muted-foreground mt-1">Bukti: {a.evidence}</p>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default async function BehavioralPage() {
  const [health, insights, anomalies] = await Promise.all([
    safeFetch<HealthScore>("/api/health-score"),
    safeFetch<Insights>("/api/insights"),
    safeFetch<AnomaliesStatus>("/api/anomalies/status"),
  ]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Behavioral Insights</h1>
        <p className="text-muted-foreground mt-1">
          Skor kesehatan, wawasan, dan anomali dihitung oleh engine deterministik dari ledger
          kanonikal — setiap angka memiliki penjelasan dan sumber endpoint.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <HealthCard data={health} />
        <AnomaliesCard data={anomalies} />
      </div>
      <InsightsCard data={insights} />
    </div>
  );
}
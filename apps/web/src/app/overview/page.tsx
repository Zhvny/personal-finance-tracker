import type { Metadata } from "next";
import { resolveApiBase } from "@/lib/api";

export const metadata: Metadata = {
  title: "Finance Overview",
  description:
    "Canonical finance overview: health score, net worth, safe-to-spend, forecast, insights, and anomalies — all computed by the deterministic backend engine.",
};

// ─── API data shapes (canonical ledger endpoints, Phases 5-15) ───────────────

interface HealthScore {
  ok?: boolean;
  as_of?: string;
  total_score?: number;
  grade?: string;
  components?: Array<{ key: string; name?: string; score: number; weight: number; explanation?: string }>;
}

interface NetWorth {
  ok?: boolean;
  as_of?: string;
  cash_assets?: number;
  per_account?: Array<{ account_id: number; name: string; balance: number }>;
  investments?: number;
  net_worth?: number;
  transfers_transparent?: boolean;
}

interface SafeToSpend {
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

interface ForecastPoint {
  day?: number;
  date?: string;
  type?: string;
  amount?: number;
  balance?: number;
}

interface Forecast {
  ok?: boolean;
  days?: number;
  start_balance?: number;
  planned?: number;
  cashflow?: ForecastPoint[];
  final_balance?: number;
  low_point?: number;
  insight?: { warning?: boolean; message?: string } | null;
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
  avg?: number;
  delta?: number;
}

interface AnomaliesStatus {
  ok?: boolean;
  window_days?: number;
  baseline_days?: number;
  window_start?: string;
  anomalies?: Anomaly[];
}

interface BudgetCategory {
  category?: string;
  limit?: number;
  actual?: number;
  pct?: number;
  level?: string;
}

interface BudgetStatus {
  ok?: boolean;
  year?: number;
  month?: number;
  categories?: BudgetCategory[];
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

// ─── Formatters ───────────────────────────────────────────────────────────────

const fmtIDR = (n: number | undefined) =>
  "Rp " + new Intl.NumberFormat("id-ID").format(Math.round(n || 0));

const SEVERITY_LABEL: Record<string, string> = {
  alert: "Alert",
  warning: "Perhatian",
  info: "Info",
  positive: "Positif",
  high: "Tinggi",
  medium: "Sedang",
};

// ─── Section shells ───────────────────────────────────────────────────────────

function Section({
  title,
  children,
  status,
}: {
  title: string;
  children?: React.ReactNode;
  status?: "offline" | "empty";
}) {
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
          API tidak tersedia atau gagal dimuat. Data belum ditampilkan.
        </p>
      ) : status === "empty" ? (
        <p className="text-xs text-muted-foreground">
          Belum ada data untuk ditampilkan.
        </p>
      ) : (
        children
      )}
    </section>
  );
}

function HealthScoreSection({ data }: { data: HealthScore | null }) {
  if (!data) return <Section title="Skor Kesehatan Keuangan" status="offline" />;
  return (
    <Section title="Skor Kesehatan Keuangan">
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
                {c.score} / 100 (bobot {c.weight})
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
  if (!data) return <Section title="Kekayaan Bersih" status="offline" />;
  return (
    <Section title="Kekayaan Bersih">
      <div className="flex items-end gap-3">
        <p className="text-3xl font-extrabold">{fmtIDR(data.net_worth)}</p>
        <p className="text-xs text-muted-foreground">
          kas {fmtIDR(data.cash_assets)} + investasi {fmtIDR(data.investments)}
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
          Ketidaksesuaian: total kas tidak sama dengan pemasukan dikurangi pengeluaran.
        </p>
      )}
    </Section>
  );
}

function SafeToSpendSection({ data }: { data: SafeToSpend | null }) {
  if (!data) return <Section title="Saldo Aman (Safe-to-Spend)" status="offline" />;
  const safe = data.safe_to_spend ?? 0;
  return (
    <Section title={`Saldo Aman — horizon ${data.horizon_days ?? 30} hari (buffer ${data.buffer_pct ?? 10}%)`}>
      <p
        className={`text-3xl font-extrabold ${
          safe < 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400"
        }`}
      >
        {fmtIDR(safe)}
      </p>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-xl bg-muted/50 border border-border p-3">
          <p className="text-muted-foreground">Saldo saat ini</p>
          <p className="font-bold">{fmtIDR(data.current_balance)}</p>
        </div>
        <div className="rounded-xl bg-muted/50 border border-border p-3">
          <p className="text-muted-foreground">Outflow mendatang</p>
          <p className="font-bold">{fmtIDR(data.upcoming_outflows)}</p>
        </div>
      </div>
    </Section>
  );
}

function ForecastSection({ data }: { data: Forecast | null }) {
  if (!data) return <Section title="Proyeksi Arus Kas" status="offline" />;
  const points = data.cashflow ?? [];
  return (
    <Section title={`Proyeksi Arus Kas — ${data.days ?? 30} hari`}>
      <p className="text-xs text-muted-foreground">
        Saldo awal {fmtIDR(data.start_balance)} — saldo akhir{" "}
        <span className="font-bold">{fmtIDR(data.final_balance)}</span>
      </p>
      {data.insight?.message && (
        <p className="text-[11px] font-semibold text-amber-700 dark:text-amber-400">
          {data.insight.message}
        </p>
      )}
      {points.length === 0 ? (
        <p className="text-xs text-muted-foreground">Belum ada data.</p>
      ) : (
        <div className="max-h-48 overflow-y-auto">
          <table className="w-full text-xs">
            <thead className="text-left text-muted-foreground uppercase text-[10px]">
              <tr>
                <th className="py-1 pr-2">Hari</th>
                <th className="py-1 pr-2">Jenis</th>
                <th className="py-1 pr-2 text-right">Jumlah</th>
                <th className="py-1 text-right">Saldo</th>
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
  if (!data) return <Section title="Wawasan Keuangan" status="offline" />;
  const cards = data.insights ?? [];
  if (cards.length === 0) return <Section title="Wawasan Keuangan" status="empty" />;
  return (
    <Section title="Wawasan Keuangan">
      <p className="text-xs text-muted-foreground">
        {data.summary?.alert ?? 0} alert, {data.summary?.warning ?? 0} perhatian,{" "}
        {data.summary?.positive ?? 0} positif, {data.summary?.info ?? 0} info
      </p>
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
    </Section>
  );
}

function AnomaliesSection({ data }: { data: AnomaliesStatus | null }) {
  if (!data) return <Section title="Deteksi Anomali" status="offline" />;
  const anomalies = data.anomalies ?? [];
  if (anomalies.length === 0) return <Section title="Deteksi Anomali" status="empty" />;
  return (
    <Section
      title={`Deteksi Anomali — window ${data.window_days ?? 30} hari vs baseline ${data.baseline_days ?? 90} hari`}
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
          </div>
        ))}
      </div>
    </Section>
  );
}

function BudgetSection({ data }: { data: BudgetStatus | null }) {
  if (!data) return <Section title="Status Anggaran" status="offline" />;
  const cats = data.categories ?? [];
  if (cats.length === 0) return <Section title="Status Anggaran" status="empty" />;
  return (
    <Section title={`Status Anggaran — ${data.month}/${data.year}`}>
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
    <div className="min-h-dvh bg-background text-foreground p-4 md:p-8 font-sans">
      <main className="max-w-5xl mx-auto space-y-6">
        <header className="rounded-2xl border border-border bg-card p-6 shadow-md">
          <h1 className="text-2xl font-extrabold tracking-tight">
            Finance Overview — Canonical Engine
          </h1>
          <p className="text-sm text-muted-foreground">
            Deterministic, explainable numbers dari ledger utama (transfer tidak
            mengubah kekayaan; anomali & insight dari data terverifikasi).
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
          Endpoint kanonikal: health-score, net-worth, safe-to-spend, forecast,
          insights, anomalies, budget — semua read-only.
        </footer>
      </main>
    </div>
  );
}

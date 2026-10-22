import type { Metadata } from 'next';
import { Expense } from "@finance-tracker/types";
import { resolveApiBase } from "@/lib/api";
import HomeView from "./home-view";

export const metadata: Metadata = {
  title: 'Dashboard',
  description: 'Track your personal finances, expenses, and investments in one place. AI-powered insights to help you spend smarter.',
  openGraph: {
    title: 'Finance Tracker Dashboard',
    description: 'Track your personal finances, expenses, and investments in one place.',
    url: '/',
    images: [{ url: '/og-image.png', width: 1200, height: 630, alt: 'Finance Tracker Dashboard' }],
  },
};

async function getExpenses(): Promise<Expense[]> {
  try {
    const apiUrl = resolveApiBase();
    // SECURITY: use a SERVER-ONLY secret. Public-prefixed vars are inlined into the
    // browser bundle, so a public key var would expose the key
    // to every visitor. This dashboard renders server-side, so the key stays on
    // the server. Set FINANCE_TRACKER_API_KEY in the Next.js runtime env instead.
    const apiKey = process.env.FINANCE_TRACKER_API_KEY || '';
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    const headers: Record<string, string> = {};
    if (apiKey) {
      headers['Authorization'] = `Bearer ${apiKey}`;
    }

    // Canonical ledger endpoint (Phase 2 ledger engine); no legacy bridge.
    const res = await fetch(`${apiUrl}/api/transactions?type=expense&limit=20`, {
      next: { revalidate: 60 },
      headers,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      // Do not expose error details to client (security)
      console.error(`[Dashboard] API error: ${res.status} ${res.statusText}`);
      return [];
    }
    const data = await res.json();
    const items = Array.isArray(data) ? data : (data.items ?? []);
    return items.map(
      (tx: { id?: number; tx_id?: number; amount?: number; description?: string; category?: string; tx_date?: string; date?: string; payment_method?: string; is_recurring?: boolean }) => ({
        id: tx.id ?? tx.tx_id,
        amount: Number(tx.amount) || 0,
        description: tx.description || '',
        category: tx.category || 'other',
        date: tx.tx_date ?? tx.date ?? new Date().toISOString(),
        payment_method: tx.payment_method ?? 'cash',
        is_recurring: Boolean(tx.is_recurring),
      }),
    );
  } catch (error) {
    console.error('[Dashboard] Error fetching expenses:', error);
    return [];
  }
}

export default async function Home() {
  const expenses = await getExpenses();

  return (
    <HomeView expenses={expenses} />
  );
}

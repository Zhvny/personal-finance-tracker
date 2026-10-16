import type { Metadata } from 'next';
import { Expense } from "@finance-tracker/types";
import { resolveApiBase } from "@/lib/api";

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
        description: tx.description || 'Pengeluaran',
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
    <div className="min-h-dvh bg-background text-foreground p-4 md:p-8 font-sans">
      <main className="max-w-4xl mx-auto bg-card text-card-foreground border border-border rounded-xl shadow-md overflow-hidden p-6 md:p-8">
        <header className="mb-8 border-b border-border pb-4">
          <h1 className="text-3xl font-bold">Personal Finance Dashboard — Track Expenses & Investments</h1>
          <p className="text-muted-foreground">AI-powered financial management & behavioral insights</p>
        </header>

        <section aria-labelledby="expenses-heading">
          <h2 id="expenses-heading" className="text-xl font-semibold mb-4">Recent Expenses</h2>
          {expenses.length === 0 ? (
            <div 
              role="status" 
              className="p-4 bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 border border-amber-200 dark:border-amber-900/50 rounded-lg"
            >
              No expenses found or API is offline.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <caption className="sr-only">List of recent expenses with date, description, category, and amount</caption>
                <thead className="bg-muted/50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Date</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Description</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Category</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">Amount</th>
                  </tr>
                </thead>
                <tbody className="bg-card divide-y divide-border">
                  {expenses.map((expense, idx) => (
                    <tr key={expense.id || idx}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">{new Date(expense.date).toLocaleDateString()}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-foreground">{expense.description}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">{expense.category}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-red-600 dark:text-red-400">
                        {new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR' }).format(expense.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="mt-12 text-center text-sm text-muted-foreground">
          Built with Next.js, FastAPI, and Prisma.
        </footer>
      </main>
    </div>
  );
}

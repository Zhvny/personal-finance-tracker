"use client";

import { useI18n } from "@/i18n/context";

export interface HomeExpense {
  id?: number;
  amount: number;
  description: string;
  category: string;
  date: string;
}

export default function HomeView({ expenses }: { expenses: HomeExpense[] }) {
  const { t, locale } = useI18n();

  return (
    <div className="min-h-dvh bg-background text-foreground p-4 md:p-8 font-sans">
      <main className="max-w-4xl mx-auto bg-card text-card-foreground border border-border rounded-xl shadow-md overflow-hidden p-6 md:p-8">
        <header className="mb-8 border-b border-border pb-4">
          <h1 className="text-3xl font-bold">{t("home.page_title")}</h1>
          <p className="text-muted-foreground">{t("home.page_subtitle")}</p>
        </header>

        <section aria-labelledby="expenses-heading">
          <h2 id="expenses-heading" className="text-xl font-semibold mb-4">
            {t("home.recent_expenses")}
          </h2>
          {expenses.length === 0 ? (
            <div
              role="status"
              className="p-4 bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 border border-amber-200 dark:border-amber-900/50 rounded-lg"
            >
              {t("home.empty_expenses")}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <caption className="sr-only">{t("home.table_caption")}</caption>
                <thead className="bg-muted/50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">{t("home.col_date")}</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">{t("home.col_description")}</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">{t("home.col_category")}</th>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">{t("home.col_amount")}</th>
                  </tr>
                </thead>
                <tbody className="bg-card divide-y divide-border">
                  {expenses.map((expense, idx) => (
                    <tr key={expense.id || idx}>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">{new Date(expense.date).toLocaleDateString(locale)}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-foreground">{expense.description || t("home.default_expense_description")}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-muted-foreground">{expense.category}</td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-bold text-red-600 dark:text-red-400">
                        {new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR" }).format(expense.amount)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <footer className="mt-12 text-center text-sm text-muted-foreground">
          {t("home.footer_built_with")}
        </footer>
      </main>
    </div>
  );
}

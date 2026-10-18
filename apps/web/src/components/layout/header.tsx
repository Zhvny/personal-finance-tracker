"use client";

import { Menu } from "lucide-react";
import { useI18n } from "@/i18n/context";

export function Header({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const { locale, setLocale } = useI18n();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/80 backdrop-blur-md px-4 lg:hidden">
      <div className="flex items-center">
        <button
          onClick={onOpenSidebar}
          aria-label="Open sidebar menu"
          className="p-2 text-muted-foreground hover:text-foreground transition-colors rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Menu size={24} />
        </button>
        <div className="ml-2 font-bold text-lg tracking-tight">FinanceTracker</div>
      </div>
      <button
        onClick={() => setLocale(locale === "en" ? "id" : "en")}
        className="px-2.5 py-1 text-xs font-bold rounded-md bg-muted text-foreground border border-border hover:bg-muted/80 transition-colors"
        title={locale === "en" ? "Ganti ke Bahasa Indonesia" : "Switch to English"}
      >
        {locale.toUpperCase()}
      </button>
    </header>
  );
}

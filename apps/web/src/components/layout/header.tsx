"use client";

import { Menu } from "lucide-react";

export function Header({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  return (
    <header className="sticky top-0 z-30 flex h-16 items-center border-b border-border bg-background/80 backdrop-blur-md px-4 lg:hidden">
      <button
        onClick={onOpenSidebar}
        aria-label="Open sidebar menu"
        className="p-2 text-muted-foreground hover:text-foreground transition-colors rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Menu size={24} />
      </button>
      <div className="ml-2 font-bold text-lg tracking-tight">FinanceTracker</div>
    </header>
  );
}

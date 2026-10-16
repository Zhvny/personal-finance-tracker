# Alpha Frontend Full Monolith Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix gateway Docker networking bug and rebuild Next.js frontend to achieve full feature parity with legacy monolith UI (12 pages + 20+ new pages), with identical UX including sidebar, mobile shell, profile switcher, theme toggle, and toast system.

**Architecture:**
1. Fix gateway to use Docker Compose service names instead of localhost for downstream service discovery
2. Build Next.js App Router frontend with monolith-identical UI/UX: sidebar navigation, mobile bottom nav, profile switcher, theme system, toast notifications
3. Migrate all 12 monolith pages from Vite/React to Next.js, then build 20+ new pages for API endpoints that had no UI
4. Implement auth flow with login page + middleware + API proxy route to hide server-side secrets

**Tech Stack:** Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, framer-motion, lucide-react, Zustand, Playwright

**Spec:** `docs/superpowers/specs/2026-09-15-alpha-frontend-full-monolith-parity.md` (to be written before this plan)

## Global Constraints

- **API keys:** Never expose `FINANCE_TRACKER_API_KEY` or `SECRET_KEY` to browser bundle; use server-side proxy route `app/api/proxy/[...path]/route.ts`
- **Env vars:** Client-side only: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`. Server-side only: `FINANCE_TRACKER_API_KEY`, `SECRET_KEY`
- **Styling:** Use existing Tailwind 4 `@theme` tokens in `globals.css`; maintain dark mode via `prefers-color-scheme`
- **Indonesian UI:** All user-facing text must be in Indonesian (except code/technical terms)
- **IDR formatting:** Use `fmtIDR()` from shared formatters; never inline `new Intl.NumberFormat`
- **Responsive:** Desktop: sidebar + main content. Mobile (≤800px): bottom nav + overlay menu. Exact breakpoints from monolith
- **Auth:** Login page at `/login`; middleware guards all `/api/*` routes except public health/read endpoints; session via HTTP-only cookie or bearer token
- **State:** Zustand stores for theme (`useThemeStore`), profile (`useProfileStore`), toast (`useToastStore`), app metadata (`useAppStore`)
- **Testing:** Playwright E2E for login, dashboard load, expense creation flow; unit tests for stores and formatters

---

## PHASE 1: Gateway Bug Fix (Docker Networking)

### Task 1.1: Fix Gateway Default Downstreams

**Files:**
- Modify: `services/gateway/main.py:31-38`

**Interfaces:**
- Consumes: None
- Produces: Fixed `DEFAULT_DOWNSTREAMS` dict with Docker Compose service names

- [ ] **Step 1: Verify current broken behavior**

Run: `docker compose up -d && docker compose logs gateway --tail=20`
Expected: warnings about `openapi.json unavailable from platform (http://localhost:8450): All connection attempts failed`

- [ ] **Step 2: Update DEFAULT_DOWNSTREAMS to use Docker service names**

```python
# BEFORE (broken in Docker):
DEFAULT_DOWNSTREAMS = {
    "platform": "http://localhost:8450",
    "ledger": "http://localhost:8451",
    "portfolio": "http://localhost:8452",
    "market": "http://localhost:8453",
    "insights": "http://localhost:8454",
    "engagement": "http://localhost:8455",
}

# AFTER (works in Docker Compose):
DEFAULT_DOWNSTREAMS = {
    "platform": "http://platform:8450",
    "ledger": "http://ledger:8451",
    "portfolio": "http://portfolio:8452",
    "market": "http://market:8453",
    "insights": "http://insights:8454",
    "engagement": "http://engagement:8455",
}
```

- [ ] **Step 3: Rebuild and verify gateway health**

Run: `docker compose build gateway && docker compose up -d gateway`
Run: `docker compose ps gateway`
Expected: `alpha-gateway ... Up (healthy)`

Run: `docker compose logs gateway --tail=5`
Expected: No more `All connection attempts failed` warnings; all 6 downstreams show `contributed N paths`

- [ ] **Step 4: Verify gateway /health endpoint**

Run: `curl http://localhost:8444/health`
Expected: `{"status":"ok","service":"alpha-gateway","downstream":{...all "up"...}}`

- [ ] **Step 5: Commit**

```bash
git add services/gateway/main.py
git commit -m "fix(gateway): use Docker Compose service names for downstreams

localhost:8450-8455 resolved to gateway itself inside container;
switch to Compose DNS names platform/ledger/portfolio/market/insights/engagement"
```

---

## PHASE 2: Frontend Infrastructure (Foundation)

### Task 2.1: Fix Security Bugs — Remove Exposed API Keys

**Files:**
- Modify: `app/overview/page.tsx` — remove `NEXT_PUBLIC_FINANCE_TRACKER_API_KEY` usage
- Modify: `app/behavioral/page.tsx` — remove `NEXT_PUBLIC_FINANCE_TRACKER_API_KEY` usage
- Modify: `app/analytics/page.tsx` — audit and fix if using exposed key
- Modify: `app/business/page.tsx` — audit and fix if using exposed key
- Modify: `components/layout/sidebar.tsx` — audit and fix if using exposed key

**Interfaces:**
- Consumes: None
- Produces: All pages use server-side proxy or `FINANCE_TRACKER_API_KEY` (server-only) for auth

- [ ] **Step 1: Write failing test for API key exposure**

Create `tests/security/test_no_exposed_keys.test.ts`:

```typescript
import { readFileSync } from "fs";

const clientFiles = [
  "app/overview/page.tsx",
  "app/behavioral/page.tsx",
  "app/analytics/page.tsx",
  "app/business/page.tsx",
  "components/layout/sidebar.tsx",
];

describe("API key security", () => {
  for (const file of clientFiles) {
    it(`should not expose ${file}`, () => {
      const content = readFileSync(file, "utf-8");
      expect(content).not.toMatch(/NEXT_PUBLIC_FINANCE_TRACKER_API_KEY/);
      expect(content).not.toMatch(/NEXT_PUBLIC_API_KEY.*Authorization/);
    });
  }
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx playwright test tests/security/test_no_exposed_keys.test.ts`
Expected: FAIL on `overview/page.tsx` and `behavioral/page.tsx`

- [ ] **Step 3: Implement API proxy route**

Create `app/api/proxy/[...path]/route.ts`:

```typescript
import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8444";
const API_KEY = process.env.FINANCE_TRACKER_API_KEY;

export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname.replace("/api/proxy", "");
  const targetUrl = `${API_URL}${path}${request.nextUrl.search}`;

  const response = await fetch(targetUrl, {
    method: request.method,
    headers: {
      "Content-Type": "application/json",
      ...(API_KEY ? { Authorization: `Bearer ${API_KEY}` } : {}),
    },
    body: request.method !== "GET" && request.method !== "HEAD" 
      ? await request.text() 
      : undefined,
  });

  const data = await response.json();
  return NextResponse.json(data, { status: response.status });
}

export const config = {
  matcher: ["/api/proxy/:path*"],
};
```

- [ ] **Step 4: Update overview/page.tsx to use proxy**

Replace inline fetch with:
```typescript
const res = await fetch("/api/proxy/health-score", {
  headers: { Authorization: `Bearer ${session?.token || ""}` },
});
```

- [ ] **Step 5: Update behavior/page.tsx similarly**

- [ ] **Step 6: Run security test again**

Run: `npx playwright test tests/security/test_no_exposed_keys.test.ts`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add app/api/proxy/[...path]/route.ts app/overview/page.tsx app/behavioral/page.tsx
git commit -m "feat(security): add API proxy route, remove exposed keys from client"
```

---

### Task 2.2: Unify API Client (lib/api.ts)

**Files:**
- Modify: `lib/api.ts` — implement `serverFetch` and `clientProxyUrl`
- Modify: All pages that import inline fetch — migrate to `lib/api.ts`

**Interfaces:**
- Consumes: Task 2.1 (proxy route)
- Produces: Unified API client used by all pages

- [ ] **Step 1: Write tests for serverFetch**

Create `tests/lib/api.test.ts`:

```typescript
import { serverFetch, clientProxyUrl } from "@/lib/api";

describe("serverFetch", () => {
  it("should add timeout and error handling", async () => {
    const result = await serverFetch("/health-score");
    expect(result).toBeDefined();
  });
});

describe("clientProxyUrl", () => {
  it("should return proxy URL for API path", () => {
    expect(clientProxyUrl("/api/transactions")).toBe("/api/proxy/transactions");
  });
});
```

- [ ] **Step 2: Implement serverFetch in lib/api.ts**

```typescript
export async function serverFetch<T>(path: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 10_000);
  
  try {
    const res = await fetch(clientProxyUrl(path), {
      headers: {
        Authorization: `Bearer ${cookies().get("session")?.value || ""}`,
      },
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timeout);
  }
}
```

- [ ] **Step 3: Implement clientProxyUrl**

```typescript
export function clientProxyUrl(path: string): string {
  return `/api/proxy${path}`;
}
```

- [ ] **Step 4: Migrate one page to use serverFetch**

Start with `app/overview/page.tsx` — replace inline fetch with `serverFetch`

- [ ] **Step 5: Run tests**

Run: `npx playwright test tests/lib/api.test.ts`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add lib/api.ts tests/lib/api.test.ts app/overview/page.tsx
git commit -m "feat(api): unify API client with serverFetch and clientProxyUrl"
```

---

### Task 2.3: Extract Shared Components

**Files:**
- Create: `components/shared/kpi-card.tsx`
- Create: `components/shared/formatters.ts`
- Modify: `app/business/page.tsx` — remove duplicated KPICard
- Modify: `app/overview/page.tsx` — use shared formatters
- Modify: `app/analytics/page.tsx` — use shared formatters

- [ ] **Step 1: Write tests for formatters**

Create `tests/shared/formatters.test.ts`:

```typescript
import { fmt, fmtIDR, fmtCompact } from "@/components/shared/formatters";

describe("formatters", () => {
  it("fmtIDR formats positive numbers", () => {
    expect(fmtIDR(1000000)).toContain("1.000.000");
  });
  it("fmtIDR formats negative numbers", () => {
    expect(fmtIDR(-500000)).toContain("-500.000");
  });
  it("fmtCompact handles millions", () => {
    expect(fmtCompact(1500000)).toContain("1,5J");
  });
});
```

- [ ] **Step 2: Implement formatters.ts**

```typescript
export function fmtIDR(value: number | null): string {
  if (value === null || value === undefined) return "Rp 0";
  const abs = Math.abs(value);
  const formatted = new Intl.NumberFormat("id-ID").format(abs);
  return value < 0 ? `-Rp ${formatted}` : `Rp ${formatted}`;
}

export function fmt(value: number | null): string {
  if (value === null || value === undefined) return "0";
  return new Intl.NumberFormat("id-ID").format(value);
}

export function fmtCompact(value: number | null): string {
  if (value === null || value === undefined) return "0";
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(abs / 1_000_000).toFixed(1)}J`;
  if (abs >= 1_000) return `${(abs / 1_000).toFixed(1)}rb`;
  return String(abs);
}
```

- [ ] **Step 3: Implement kpi-card.tsx**

Extract from `app/business/page.tsx` inline KPICard component:

```typescript
interface KpiCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon?: React.ReactNode;
  format?: "idr" | "number" | "compact";
}

export function KpiCard({ title, value, change, icon, format = "idr" }: KpiCardProps) {
  const formatted = format === "idr" ? fmtIDR(value as number) 
    : format === "compact" ? fmtCompact(value as number)
    : fmt(value as number);
  
  return (
    <div className="glass-panel rounded-xl p-5 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          {title}
        </span>
        {icon && <div className="text-muted-foreground">{icon}</div>}
      </div>
      <div className="text-2xl font-bold">{formatted}</div>
      {change !== undefined && (
        <div className={`text-xs ${change >= 0 ? "text-green-400" : "text-red-400"}`}>
          {change >= 0 ? "+" : ""}{fmtCompact(change)} dari bulan lalu
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `npx playwright test tests/shared/formatters.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add components/shared/kpi-card.tsx components/shared/formatters.ts tests/shared/formatters.test.ts
git commit -m "feat(shared): extract KpiCard and formatters to shared components"
```

---

### Task 2.4: Add Error Boundary and Not-Found Page

**Files:**
- Create: `app/error.tsx`
- Create: `app/not-found.tsx`
- Modify: `app/layout.tsx` — wrap with error boundary if needed

- [ ] **Step 1: Create error.tsx**

```typescript
"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error:", error);
  }, [error]);

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center space-y-4">
        <h2 className="text-2xl font-bold">Terjadi Kesalahan</h2>
        <p className="text-muted-foreground">{error.message}</p>
        <Button onClick={reset}>Coba Lagi</Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create not-found.tsx**

```typescript
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center space-y-4">
        <h2 className="text-4xl font-bold">404</h2>
        <p className="text-muted-foreground">Halaman tidak ditemukan</p>
        <Button asChild>
          <Link href="/">Kembali ke Dashboard</Link>
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add app/error.tsx app/not-found.tsx
git commit -m "feat(frontend): add global error boundary and 404 page"
```

---

## PHASE 3: Layout System (Monolith Parity)

### Task 3.1: Desktop Sidebar (Restore Monolith Layout)

**Files:**
- Create: `components/layout/sidebar.tsx` (replace existing)
- Create: `components/layout/sidebar-nav-item.tsx`
- Create: `components/layout/live-stats-card.tsx`

**Interfaces:**
- Consumes: `useAppStore` (metadata, net value), `useProfileStore` (active profile)
- Produces: Desktop sidebar with sections, nav items, live stats

- [ ] **Step 1: Write test for sidebar navigation**

Create `tests/layout/sidebar.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { Sidebar } from "@/components/layout/sidebar";

describe("Sidebar", () => {
  it("should render all navigation sections", () => {
    render(<Sidebar />);
    expect(screen.getByText("overview")).toBeInTheDocument();
    expect(screen.getByText("modules")).toBeInTheDocument();
    expect(screen.getByText("insights")).toBeInTheDocument();
  });

  it("should show active page with highlight", () => {
    render(<Sidebar activePage="dashboard" />);
    const dashboard = screen.getByRole("button", { name: /dashboard/i });
    expect(dashboard).toHaveClass("active");
  });
});
```

- [ ] **Step 2: Implement sidebar-nav-item.tsx**

```typescript
interface SidebarNavItemProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick: () => void;
}

export function SidebarNavItem({ icon, label, active, onClick }: SidebarNavItemProps) {
  return (
    <div
      role="button"
      tabIndex={0}
      aria-current={active ? "page" : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
      className={`
        nav-it flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer
        transition-all duration-200
        ${active 
          ? "bg-primary/10 text-primary font-semibold" 
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
        }
      `}
    >
      <span className="flex-shrink-0">{icon}</span>
      <span className="text-sm">{label}</span>
    </div>
  );
}
```

- [ ] **Step 3: Implement live-stats-card.tsx**

```typescript
interface LiveStatsCardProps {
  expenseTotal: number | null;
  incomeTotal: number | null;
  loading?: boolean;
}

export function LiveStatsCard({ expenseTotal, incomeTotal, loading }: LiveStatsCardProps) {
  return (
    <div className="mx-4 mt-auto p-4 rounded-xl bg-muted/50 space-y-3">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
        Live Stats
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">Expenses</span>
        <span className="font-semibold text-red-400">{loading ? "..." : fmtIDR(expenseTotal)}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">Income</span>
        <span className="font-semibold text-green-400">{loading ? "..." : fmtIDR(incomeTotal)}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Implement main sidebar.tsx**

```typescript
"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  IconDashboard,
  IconWallet,
  IconMenuClose,
  IconMenuOpen,
  IconRefresh,
  IconMoon,
  IconSun,
  IconSettings,
  IconAdd,
  IconUser,
  IconBusiness,
} from "lucide-react";
import { SidebarNavItem } from "./sidebar-nav-item";
import { LiveStatsCard } from "./live-stats-card";
import { useAppStore } from "@/store/useAppStore";
import { useProfileStore } from "@/store/useProfileStore";
import { useThemeStore } from "@/store/useThemeStore";
import { ProfileSwitcher } from "./profile-switcher";
import { NAV_PAGES } from "@/lib/navigation";

const SECTIONS = [
  { id: "overview", label: "overview" },
  { id: "modules", label: "modules" },
  { id: "insights", label: "insights" },
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const { meta, reloadMeta } = useAppStore();
  const { activeProfile, profiles } = useProfileStore();
  const { theme, toggleTheme } = useThemeStore();

  const currentPage = NAV_PAGES.find(p => p.path === pathname)?.id || "dashboard";

  const navigate = (id: string) => {
    const target = NAV_PAGES.find(p => p.id === id);
    if (target) router.push(target.path);
  };

  return (
    <aside className={`
      fixed inset-y-0 left-0 z-40 bg-background border-r border-border
      transition-all duration-300 ease-in-out
      ${collapsed ? "w-16" : "w-64"}
      hidden lg:block
    `}>
      {/* Logo */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <IconWallet className="text-primary" size={20} />
            <div>
              <div className="font-bold text-lg leading-none">Alpha</div>
              <div className="text-xs text-muted-foreground">By Zhvny</div>
            </div>
          </div>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1 rounded-md hover:bg-muted"
          aria-label="Toggle sidebar"
        >
          {collapsed ? <IconMenuOpen size={18} /> : <IconMenuClose size={18} />}
        </button>
      </div>

      {/* Net This Month */}
      {!collapsed && (
        <div className="p-4 border-b border-border">
          <div className="text-xs text-muted-foreground uppercase tracking-wider mb-1">
            Net This Month
          </div>
          {meta === null ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <IconRefresh className="animate-spin" size={11} />
              Loading...
            </div>
          ) : (
            <>
              <div className={`text-xl font-bold ${(meta.net ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                {fmtIDR(meta.net)}
              </div>
              <div className="text-xs text-muted-foreground">
                — {meta.month_label || "—"}
              </div>
            </>
          )}
        </div>
      )}

      {/* Navigation Sections */}
      <nav className="flex-1 overflow-y-auto p-2 space-y-4">
        {SECTIONS.map(section => (
          <div key={section.id}>
            {!collapsed && (
              <div className="px-3 mb-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {section.label}
              </div>
            )}
            <div className="space-y-1">
              {NAV_PAGES.filter(p => p.section === section.id).map(page => (
                <SidebarNavItem
                  key={page.id}
                  icon={page.icon}
                  label={!collapsed ? page.label : undefined}
                  active={currentPage === page.id}
                  onClick={() => navigate(page.id)}
                />
              ))}
            </div>
            {section.id !== "insights" && <div className="my-2 border-t border-border" />}
          </div>
        ))}
      </nav>

      {/* Bottom Actions */}
      <div className="p-2 space-y-2 border-t border-border">
        <button
          onClick={toggleTheme}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg hover:bg-muted text-muted-foreground"
          aria-label="Toggle theme"
        >
          {theme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
          {!collapsed && <span className="text-sm">{theme === "dark" ? "Light Mode" : "Dark Mode"}</span>}
        </button>
        <button
          onClick={reloadMeta}
          className="flex items-center gap-3 w-full px-3 py-2 rounded-lg hover:bg-muted text-muted-foreground"
          aria-label="Refresh"
        >
          <IconRefresh size={18} />
          {!collapsed && <span className="text-sm">Refresh</span>}
        </button>
      </div>

      {/* Live Stats */}
      {!collapsed && (
        <LiveStatsCard
          expenseTotal={meta?.expense_total ?? null}
          incomeTotal={meta?.income_total ?? null}
          loading={meta === null}
        />
      )}

      {/* Profile Switcher */}
      {!collapsed && <ProfileSwitcher />}
    </aside>
  );
}
```

- [ ] **Step 5: Create NAV_PAGES constant**

Create `lib/navigation.ts`:

```typescript
import {
  IconDashboard,
  IconWallet,
  IconTrendingUp,
  IconArrowDown,
  IconArrowUp,
  IconChartBar,
  IconBrain,
  IconDna,
  IconReceipt,
  IconBehavior,
  IconAnalytics,
  IconAward,
  IconSettings,
} from "lucide-react";

export interface NavPage {
  id: string;
  label: string;
  path: string;
  section: "overview" | "modules" | "insights";
  icon: React.ReactNode;
}

export const NAV_PAGES: NavPage[] = [
  { id: "dashboard", label: "Dashboard", path: "/", section: "overview", icon: <IconDashboard size={16} /> },
  { id: "investments", label: "Investment Tracker", path: "/investment-tracker", section: "modules", icon: <IconTrendingUp size={16} /> },
  { id: "expenses", label: "Expense Tracker", path: "/expense-tracker", section: "modules", icon: <IconArrowDown size={16} /> },
  { id: "income", label: "Income Tracker", path: "/income-tracker", section: "modules", icon: <IconArrowUp size={16} /> },
  { id: "stocks", label: "Stock Analyzer", path: "/stocks", section: "modules", icon: <IconChartBar size={16} /> },
  { id: "ml_stocks", label: "ML Predict", path: "/ml-stocks", section: "modules", icon: <IconBrain size={16} /> },
  { id: "genetic", label: "AI Portfolio Lab", path: "/genetic-lab", section: "modules", icon: <IconDna size={16} /> },
  { id: "receipt", label: "Receipt Reader", path: "/receipt-reader", section: "modules", icon: <IconReceipt size={16} /> },
  { id: "behavioral", label: "Behavioral Finance", path: "/behavioral-finance", section: "insights", icon: <IconBehavior size={16} /> },
  { id: "analytics", label: "BI/BA Dashboard", path: "/analytics", section: "insights", icon: <IconAnalytics size={16} /> },
  { id: "earn", label: "Reward", path: "/earn", section: "insights", icon: <IconAward size={16} /> },
  { id: "advanced", label: "Advanced Features", path: "/advanced", section: "insights", icon: <IconSettings size={16} /> },
];
```

- [ ] **Step 6: Run tests**

Run: `npx playwright test tests/layout/sidebar.test.tsx`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add components/layout/sidebar.tsx components/layout/sidebar-nav-item.tsx components/layout/live-stats-card.tsx lib/navigation.ts tests/layout/sidebar.test.tsx
git commit -m "feat(layout): restore desktop sidebar with sections and live stats"
```

---

### Task 3.2: Mobile Shell (Bottom Nav + Overlay Menu)

**Files:**
- Create: `components/layout/mobile-shell.tsx`
- Create: `components/layout/mobile-nav.tsx`
- Create: `components/layout/mobile-menu-overlay.tsx`

**Interfaces:**
- Consumes: `useAppStore`, `useProfileStore`, `useThemeStore`, `NAV_PAGES`
- Produces: Mobile shell with 5-tab bottom nav + "More" overflow

- [ ] **Step 1: Write test for mobile nav**

Create `tests/layout/mobile-shell.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { MobileShell } from "@/components/layout/mobile-shell";

describe("MobileShell", () => {
  it("should render bottom nav with 5 tabs", () => {
    render(<MobileShell activePage="dashboard" onNav={() {}} />);
    const tabs = screen.getAllByRole("button");
    expect(tabs.length).toBeGreaterThanOrEqual(5);
  });

  it("should show More button", () => {
    render(<MobileShell activePage="dashboard" onNav={() => {}} />);
    expect(screen.getByText("More")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement mobile-nav.tsx**

```typescript
"use client";

import { NAV_PAGES, NavPage } from "@/lib/navigation";

interface MobileNavProps {
  activePage: string;
  onNav: (id: string) => void;
}

export function MobileNav({ activePage, onNav }: MobileNavProps) {
  const topPages = NAV_PAGES.slice(0, 5);

  return (
    <nav className="fixed bottom-0 left-0 right-0 h-16 bg-background border-t border-border flex items-center px-2 pb-safe z-50">
      {topPages.map((page: NavPage, i: number) => (
        <button
          key={page.id}
          onClick={() => onNav(page.id)}
          className={`
            flex-1 flex flex-col items-center justify-center gap-1 py-2
            transition-all duration-200
            ${activePage === page.id ? "text-primary" : "text-muted-foreground"}
          `}
          style={{ animationDelay: `${i * 45}ms` }}
        >
          {page.icon}
          <span className="text-[10px] font-medium">{page.label.split(" ")[0]}</span>
        </button>
      ))}
      <MobileMenuOverlayTrigger activePage={activePage} onNav={onNav} />
    </nav>
  );
}

function MobileMenuOverlayTrigger({ activePage, onNav }: { activePage: string; onNav: (id: string) => void }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`
          flex-1 flex flex-col items-center justify-center gap-1 py-2
          ${!topPages.some(p => p.id === activePage) ? "text-primary" : "text-muted-foreground"}
        `}
      >
        <IconMore size={20} />
        <span className="text-[10px] font-medium">More</span>
      </button>
      {open && (
        <div className="fixed inset-0 z-50 bg-black/50" onClick={() => setOpen(false)}>
          <div className="absolute bottom-0 left-0 right-0 bg-background rounded-t-2xl p-4 space-y-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-lg">Menu</h3>
              <button onClick={() => setOpen(false)} className="p-2">Kembali</button>
            </div>
            <ProfileSwitcher compact />
            <div className="grid grid-cols-4 gap-4">
              {NAV_PAGES.map((page, i) => (
                <button
                  key={page.id}
                  onClick={() => { onNav(page.id); setOpen(false); }}
                  className="flex flex-col items-center gap-2 p-3 rounded-xl bg-muted/50"
                  style={{ animationDelay: `${i * 28}ms` }}
                >
                  <div className="w-10 h-10 rounded-xl bg-muted flex items-center justify-center text-primary">
                    {page.icon}
                  </div>
                  <span className="text-xs font-medium text-center">{page.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
>
}
```

- [ ] **Step 3: Implement mobile-shell.tsx**

```typescript
"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { MobileNav } from "./mobile-nav";

interface MobileShellProps {
  children: React.ReactNode;
  activePage: string;
  onNav: (id: string) => void;
  theme: "dark" | "light";
  onThemeToggle: () => void;
  onReload: () => void;
  isOffline: boolean;
}

export function MobileShell({
  children,
  activePage,
  onNav,
  theme,
  onThemeToggle,
  onReload,
  isOffline,
}: MobileShellProps) {
  return (
    <div className="mobile-app flex flex-col h-screen bg-background text-foreground overflow-hidden">
      {/* Header */}
      <header className="h-14 flex items-center justify-between px-4 bg-background/80 backdrop-blur border-b border-border flex-shrink-0">
        <div className="font-bold text-lg tracking-tight">Alpha</div>
        <div className="flex items-center gap-2">
          <button onClick={onThemeToggle} className="p-2 rounded-lg hover:bg-muted">
            {theme === "dark" ? <IconSun size={18} /> : <IconMoon size={18} />}
          </button>
          <button onClick={onReload} className="p-2 rounded-lg hover:bg-muted">
            <IconRefresh size={18} />
          </button>
        </div>
      </header>

      {/* Offline Banner */}
      {isOffline && (
        <div className="bg-red-500 text-white text-xs font-bold text-center py-2 uppercase tracking-wider">
          Server Offline
        </div>
      )}

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-4 pb-24">
        {children}
      </main>

      {/* Bottom Nav */}
      <MobileNav activePage={activePage} onNav={onNav} />
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `npx playwright test tests/layout/mobile-shell.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add components/layout/mobile-shell.tsx components/layout/mobile-nav.tsx components/layout/mobile-menu-overlay.tsx tests/layout/mobile-shell.test.tsx
git commit -m "feat(layout): add mobile shell with bottom nav and overlay menu"
```

---

### Task 3.3: Zustand Stores (Theme, Profile, Toast, App Metadata)

**Files:**
- Create: `store/useThemeStore.ts`
- Create: `store/useProfileStore.ts`
- Create: `store/useToastStore.ts`
- Create: `store/useAppStore.ts`

**Interfaces:**
- Consumes: None
- Produces: Global state stores consumed by layout and pages

- [ ] **Step 1: Write tests for stores**

Create `tests/store/theme-store.test.ts`:

```typescript
import { useThemeStore } from "@/store/useThemeStore";

describe("useThemeStore", () => {
  beforeEach(() => {
    useThemeStore.setState({ theme: "dark" });
  });

  it("should toggle theme", () => {
    const { toggleTheme } = useThemeStore.getState();
    toggleTheme();
    expect(useThemeStore.getState().theme).toBe("light");
  });
});
```

- [ ] **Step 2: Implement useThemeStore.ts**

```typescript
"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "dark" | "light";

interface ThemeStore {
  theme: Theme;
  toggleTheme: () => void;
}

export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      theme: "dark",
      toggleTheme: () => set((state) => ({ theme: state.theme === "dark" ? "light" : "dark" })),
    }),
    {
      name: "ft:theme",
      storage: typeof window !== "undefined" ? localStorage : undefined,
    }
  )
);
```

- [ ] **Step 3: Implement useProfileStore.ts**

```typescript
"use client";

import { create } from "zustand";

interface Profile {
  name: string;
  type: "personal" | "business";
}

interface ProfileStore {
  active: string;
  activeType: "personal" | "business";
  available: string[];
  types: Record<string, "personal" | "business">;
  setActive: (name: string) => void;
  setProfiles: (profiles: { active: string; active_type: string; available: string[]; types: Record<string, string> }) => void;
}

export const useProfileStore = create<ProfileStore>((set) => ({
  active: "personal",
  activeType: "personal",
  available: [],
  types: {},
  setActive: (name) => set({ active: name }),
  setProfiles: (data) => set({
    active: data.active,
    activeType: data.active_type as "personal" | "business",
    available: data.available,
    types: Object.fromEntries(
      Object.entries(data.types).map(([k, v]) => [k, v as "personal" | "business"])
    ),
  }),
}));
```

- [ ] **Step 4: Implement useToastStore.ts**

```typescript
"use client";

import { create } from "zustand";

type ToastType = "success" | "error" | "info";

interface Toast {
  message: string;
  type: ToastType;
}

interface ToastStore {
  toasts: Toast[];
  addToast: (message: string, type?: ToastType) => void;
  removeToast: (index: number) => void;
}

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  addToast: (message, type = "success") => {
    const id = Date.now();
    set((state) => ({ toasts: [...state.toasts, { id, message, type }] }));
    setTimeout(() => {
      set((state) => ({ toasts: state.toasts.filter(t => t.id !== id) }));
    }, 3000);
  },
  removeToast: (id) => set((state) => ({ toasts: state.toasts.filter(t => t.id !== id) })),
}));
```

- [ ] **Step 5: Implement useAppStore.ts**

```typescript
"use client";

import { create } from "zustand";

export interface AppMetadata {
  net: number | null;
  expense_total: number | null;
  income_total: number | null;
  month_label: string;
}

interface AppStore {
  meta: AppMetadata | null;
  loading: boolean;
  setMeta: (meta: AppMetadata) => void;
  setLoading: (loading: boolean) => void;
  reloadMeta: () => void;
}

export const useAppStore = create<AppStore>((set) => ({
  meta: null,
  loading: false,
  setMeta: (meta) => set({ meta }),
  setLoading: (loading) => set({ loading }),
  reloadMeta: async () => {
    set({ loading: true });
    try {
      const res = await fetch("/api/proxy/dashboard-metadata");
      const data = await res.json();
      set({ meta: data });
    } finally {
      set({ loading: false });
    }
  },
}));
```

- [ ] **Step 6: Run tests**

Run: `npx playwright test tests/store/theme-store.test.ts`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add store/useThemeStore.ts store/useProfileStore.ts store/useToastStore.ts store/useAppStore.ts tests/store/theme-store.test.ts
git commit -m "feat(state): add Zustand stores for theme, profile, toast, and app metadata"
```

---

### Task 3.4: Profile Switcher Component

**Files:**
- Create: `components/layout/profile-switcher.tsx`
- Create: `components/layout/profile-creator-modal.tsx`

**Interfaces:**
- Consumes: `useProfileStore`, `useAppStore`
- Produces: Profile switcher dropdown + creator modal

- [ ] **Step 1: Implement profile-switcher.tsx**

```typescript
"use client";

import { useState } from "react";
import { useProfileStore } from "@/store/useProfileStore";
import { ProfileCreatorModal } from "./profile-creator-modal";
import { IconUser, IconBusiness, IconAdd } from "lucide-react";

export function ProfileSwitcher() {
  const { active, available, types, setActive, setProfiles } = useProfileStore();
  const [showCreate, setShowCreate] = useState(false);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    fetch("/api/proxy/profile/")
      .then(res => res.json())
      .then(data => setProfiles(data))
      .catch(console.error);
  }, [setProfiles]);

  const handleSwitch = async (name: string) => {
    if (name === active) return;
    setSwitching(true);
    try {
      await fetch("/api/proxy/profile/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ profile: name }),
      });
      window.location.reload();
    } catch (e) {
      console.error("Switch failed", e);
      setSwitching(false);
    }
  };

  if (available.length === 0) return null;

  return (
    <div className="p-4 space-y-3 border-t border-border">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Active Profile
        </span>
        <button
          onClick={() => setShowCreate(true)}
          className="p-1 rounded-md hover:bg-muted text-xs"
        >
          <IconAdd size={14} />
        </button>
      </div>

      <div className="space-y-1">
        {available.map(name => {
          const type = types[name] || (name.includes("business") ? "business" : "personal");
          const isActive = active === name;
          return (
            <button
              key={name}
              onClick={() => handleSwitch(name)}
              disabled={switching}
              className={`
                w-full flex items-center justify-between px-3 py-2 rounded-lg
                transition-all duration-200
                ${isActive ? "bg-primary/10 border border-primary" : "hover:bg-muted"}
              `}
            >
              <div className="flex items-center gap-2">
                {type === "business" ? <IconBusiness size={14} /> : <IconUser size={14} />}
                <span className="text-sm font-medium">{name}</span>
              </div>
              {isActive && <div className="w-2 h-2 rounded-full bg-primary" />}
            </button>
          );
        })}
      </div>

      {showCreate && (
        <ProfileCreatorModal onClose={() => setShowCreate(false)} />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Implement profile-creator-modal.tsx**

```typescript
"use client";

import { useState } from "react";
import { useProfileStore } from "@/store/useProfileStore";
import { Button } from "@/components/ui/button";

interface ProfileCreatorModalProps {
  onClose: () => void;
}

export function ProfileCreatorModal({ onClose }: ProfileCreatorModalProps) {
  const [name, setName] = useState("");
  const [type, setType] = useState<"personal" | "business">("business");
  const [error, setError] = useState<string | null>(null);
  const { setActive } = useProfileStore();

  const handleCreate = async () => {
    if (!name.trim()) {
      setError("Nama profile tidak boleh kosong.");
      return;
    }
    try {
      const res = await fetch("/api/proxy/profile/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim().toLowerCase().replace(/[^a-z0-9_]/g, "_"), type }),
      });
      const data = await res.json();
      if (res.ok) {
        await fetch("/api/proxy/profile/switch", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ profile: name.trim() }),
        });
        window.location.reload();
      } else {
        setError(data.detail || "Gagal membuat profile.");
      }
    } catch (e) {
      setError("Gagal membuat profile.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <div className="bg-background rounded-2xl p-6 max-w-md w-full space-y-4">
        <h3 className="text-lg font-bold">Buat Profile Baru</h3>
        
        <div className="space-y-2">
          <label className="text-sm font-medium">Nama Profile</label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. pt_kreatif, client_consulting"
            className="w-full px-3 py-2 rounded-lg border border-border bg-background"
          />
          <p className="text-xs text-muted-foreground">Huruf kecil, angka, atau garis bawah (_)</p>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium">Tipe Penggunaan</label>
          <div className="space-y-2">
            <label className="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted/50">
              <input
                type="radio"
                name="profile_type"
                checked={type === "personal"}
                onChange={() => setType("personal")}
              />
              <div>
                <div className="font-medium">👤 Personal-Use</div>
                <div className="text-xs text-muted-foreground">Keuangan pribadi, rumah tangga, tabungan</div>
              </div>
            </label>
            <label className="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted/50">
              <input
                type="radio"
                name="profile_type"
                checked={type === "business"}
                onChange={() => setType("business")}
              />
              <div>
                <div className="font-medium">💼 Business-Use</div>
                <div className="text-xs text-muted-foreground">Operasional bisnis, B2B, OpEx, COGS</div>
              </div>
            </label>
          </div>
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-400/10 p-3 rounded-lg">{error}</div>
        )}

        <div className="flex gap-2">
          <Button variant="outline" onClick={onClose} className="flex-1">Batal</Button>
          <Button onClick={handleCreate} className="flex-1">Buat Profile</Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/layout/profile-switcher.tsx components/layout/profile-creator-modal.tsx
git commit -m "feat(layout): add profile switcher with creator modal"
```

---

### Task 3.5: Toast System

**Files:**
- Create: `components/shared/toast.tsx`
- Modify: `app/layout.tsx` — wrap with toast provider

- [ ] **Step 1: Implement toast.tsx**

```typescript
"use client";

import { useToastStore } from "@/store/useToastStore";
import { IconCheck, IconX, IconInfo } from "lucide-react";

export function Toast() {
  const { toasts, removeToast } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-50 space-y-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`
            flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg
            animate-in slide-in-from-bottom-4
            ${toast.type === "success" ? "bg-green-500/10 border border-green-500/20" : ""}
            ${toast.type === "error" ? "bg-red-500/10 border border-red-500/20" : ""}
            ${toast.type === "info" ? "bg-blue-500/10 border border-blue-500/20" : ""}
          `}
        >
          {toast.type === "success" && <IconCheck size={18} className="text-green-400" />}
          {toast.type === "error" && <IconX size={18} className="text-red-400" />}
          {toast.type === "info" && <IconInfo size={18} className="text-blue-400" />}
          <span className="text-sm font-medium">{toast.message}</span>
          <button onClick={() => removeToast(toast.id)} className="ml-2 text-muted-foreground">
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Wrap root layout with Toast provider**

Modify `app/layout.tsx`:

```typescript
import { Toast } from "@/components/shared/toast";

export default function RootLayout({ children }) {
  return (
    <html lang="id">
      <body>
        {children}
        <Toast />
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add components/shared/toast.tsx app/layout.tsx
git commit -m "feat(layout): add global toast notification system"
```

---

## PHASE 4: Page Migration (Tier by Tier)

### Tier 1: Critical Pages (Week 1)

#### Task 4.1: Verify and Complete Dashboard (`/`)

**Files:**
- Modify: `app/page.tsx`

**Interfaces:**
- Consumes: `serverFetch("/api/transactions?type=expense&limit=20")`
- Produces: Dashboard page with recent expenses table

- [ ] **Step 1: Verify current implementation**

Check: `app/page.tsx` already fetches expenses and renders table
Check: IDR formatting works
Check: Loading and empty states

- [ ] **Step 2: Add missing features from monolith**

Monolith dashboard has:
- Recent transactions table (last 20)
- Net this month in sidebar (already in layout)
- Quick stats cards (expense total, income total)

Add to `app/page.tsx`:
```typescript
// Add quick stats cards at top
<div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
  <KpiCard title="Expenses" value={expenseTotal} format="idr" change={expenseChange} icon={<IconArrowDown className="text-red-400" />} />
  <KpiCard title="Income" value={incomeTotal} format="idr" change={incomeChange} icon={<IconArrowUp className="text-green-400" />} />
  <KpiCard title="Net" value={net} format="idr" change={netChange} />
</div>
```

- [ ] **Step 3: Test**

Run: `npx playwright test tests/pages/dashboard.test.ts`
Expected: PASS — dashboard loads with stats and transaction table

- [ ] **Step 4: Commit**

```bash
git add app/page.tsx
git commit -m "feat(page): complete dashboard with stats cards and recent transactions"
```

---

#### Task 4.2: Investment Tracker (`/investment-tracker`)

**Files:**
- Create: `app/investment-tracker/page.tsx`

**Interfaces:**
- Consumes: `serverFetch("/api/investments")`, `serverFetch("/api/reports")`
- Produces: Investment tracker page with holdings table, performance chart, FIFO gain/loss

- [ ] **Step 1: Write failing test**

Create `tests/pages/investment-tracker.test.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Investment Tracker", () => {
  test("should load page", async ({ page }) => {
    await page.goto("/investment-tracker");
    await expect(page.locator("h1")).toContainText("Investment Tracker");
  });

  test("should display holdings table", async ({ page }) => {
    await page.goto("/investment-tracker");
    await expect(page.locator("[data-testid=holdings-table]")).toBeVisible();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx playwright test tests/pages/investment-tracker.test.ts`
Expected: FAIL — page not found

- [ ] **Step 3: Implement page**

Create `app/investment-tracker/page.tsx`:

```typescript
import { Suspense } from "react";
import { InvestmentsClient } from "./investments-client";
import { InvestmentsSkeleton } from "./investments-skeleton";

export default function InvestmentTrackerPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Investment Tracker</h1>
        <p className="text-muted-foreground">Track your portfolio performance and holdings</p>
      </div>
      <Suspense fallback={<InvestmentsSkeleton />}>
        <InvestmentsClient />
      </Suspense>
    </div>
  );
}
```

Create `app/investment-tracker/investments-client.tsx`:

```typescript
"use client";

import { use, useState, useEffect } from "react";
import { serverFetch } from "@/lib/api";
import { fmtIDR, fmtCompact } from "@/components/shared/formatters";
import { KpiCard } from "@/components/shared/kpi-card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { IconTrendingUp, IconArrowDown, IconArrowUp } from "lucide-react";

interface Investment {
  id: string;
  ticker: string;
  quantity: number;
  avg_price: number;
  current_price: number;
  gain_loss: number;
  gain_loss_pct: number;
}

export function InvestmentsClient() {
  const [investments, setInvestments] = useState<Investment[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    serverFetch<{ investments: Investment[] }>("/api/investments")
      .then(data => {
        setInvestments(data.investments);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) return <div>Loading...</div>;

  const totalValue = investments.reduce((sum, i) => sum + (i.quantity * i.current_price), 0);
  const totalGainLoss = investments.reduce((sum, i) => sum + i.gain_loss, 0);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KpiCard
          title="Total Value"
          value={totalValue}
          format="idr"
          icon={<IconTrendingUp className="text-blue-400" />}
        />
        <KpiCard
          title="Total Gain/Loss"
          value={totalGainLoss}
          format="idr"
          icon={totalGainLoss >= 0 ? <IconArrowUp className="text-green-400" /> : <IconArrowDown className="text-red-400" />}
        />
        <KpiCard
          title="Holdings"
          value={investments.length}
          format="number"
        />
      </div>

      {/* Holdings Table */}
      <div className="rounded-xl border border-border overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ticker</TableHead>
              <TableHead className="text-right">Qty</TableHead>
              <TableHead className="text-right">Avg Price</TableHead>
              <TableHead className="text-right">Current Price</TableHead>
              <TableHead className="text-right">Gain/Loss</TableHead>
              <TableHead className="text-right">Gain/Loss %</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {investments.map(inv => (
              <TableRow key={inv.id}>
                <TableCell className="font-medium">{inv.ticker}</TableCell>
                <TableCell className="text-right">{fmtCompact(inv.quantity)}</TableCell>
                <TableCell className="text-right">{fmtIDR(inv.avg_price)}</TableCell>
                <TableCell className="text-right">{fmtIDR(inv.current_price)}</TableCell>
                <TableCell className={`text-right ${inv.gain_loss >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {fmtIDR(inv.gain_loss)}
                </TableCell>
                <TableCell className={`text-right ${inv.gain_loss_pct >= 0 ? "text-green-400" : "text-red-400"}`}>
                  {fmtCompact(inv.gain_loss_pct)}%
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
```

Create `app/investment-tracker/investments-skeleton.tsx`:

```typescript
import { CardSkeleton } from "@/components/skeletons/card-skeleton";

export function InvestmentsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[1, 2, 3].map(i => (
          <CardSkeleton key={i} />
        ))}
      </div>
      <CardSkeleton className="h-96" />
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `npx playwright test tests/pages/investment-tracker.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/investment-tracker/page.tsx app/investment-tracker/investments-client.tsx app/investment-tracker/investments-skeleton.tsx tests/pages/investment-tracker.test.ts
git commit -m "feat(page): add investment tracker page"
```

---

#### Task 4.3-4.6: Remaining Tier 1 Pages

Follow same pattern as Task 4.2 for:
- `/expense-tracker` — Expense Tracker
- `/income-tracker` — Income Tracker
- `/stocks` — Stock Analyzer
- `/receipt-reader` — Receipt Reader

Each page:
1. Write failing Playwright test
2. Run to verify fail
3. Implement page component with skeleton
4. Run test to verify pass
5. Commit

---

### Tier 2: Important Pages (Week 2)

#### Task 4.7-4.12: Tier 2 Pages

Follow same pattern for:
- `/ml-stocks` — ML Predict
- `/genetic-lab` — AI Portfolio Lab
- `/behavioral-finance` — Behavioral Finance
- `/analytics` — Verify/complete BI Dashboard (already exists, verify 10 tabs)
- `/earn` — Reward (replace placeholder with real UI)
- `/advanced` — Advanced Features

---

### Tier 3: New Pages (Week 3)

#### Task 4.13-4.25: Tier 3 Pages

Follow same pattern for all 20+ new pages:
- `/budget`, `/goals`, `/forecast`, `/safe-to-spend`, `/net-worth`, `/health-score`, `/anomalies`, `/insights`, `/reports`, `/settings`, `/profile`, `/ai`, `/advisor`, `/admin`, `/market`

Each page:
1. Check API endpoint exists (verify with `curl /api/proxy/<endpoint>`)
2. Write failing Playwright test
3. Implement page
4. Test and commit

---

## PHASE 5: Auth & Polish (Week 4)

### Task 5.1: Login Page

**Files:**
- Create: `app/login/page.tsx`
- Create: `app/login/layout.tsx`

- [ ] **Step 1: Implement login page**

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LoginPage() {
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const router = useRouter();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: apiKey }),
    });
    if (res.ok) {
      router.push("/");
    } else {
      setError("Invalid API key");
    }
  };

  return (
    <div className="flex h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-md p-8 rounded-2xl border border-border">
        <h1 className="text-2xl font-bold text-center">Login</h1>
        {error && <div className="text-red-400 text-sm">{error}</div>}
        <Input
          type="password"
          placeholder="Enter your API key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
        <Button type="submit" className="w-full">Login</Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add app/login/page.tsx app/login/layout.tsx
git commit -m "feat(auth): add login page"
```

---

### Task 5.2: Auth Middleware

**Files:**
- Create: `middleware.ts`

- [ ] **Step 1: Implement middleware**

```typescript
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export function middleware(request: NextRequest) {
  const session = request.cookies.get("session")?.value;
  const isLoginPage = request.nextUrl.pathname === "/login";
  const isPublicApi = request.nextUrl.pathname.startsWith("/api/proxy/health") || 
                      request.nextUrl.pathname === "/api/proxy/profile/";

  if (isLoginPage || isPublicApi) return NextResponse.next();

  if (!session && request.nextUrl.pathname !== "/login") {
    return NextResponse.redirect(new URL("/login", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
```

- [ ] **Step 2: Commit**

```bash
git add middleware.ts
git commit -m "feat(auth): add auth middleware for route guards"
```

---

### Task 5.3: API Auth Route

**Files:**
- Create: `app/api/auth/login/route.ts`

- [ ] **Step 1: Implement login route**

```typescript
import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const { api_key } = await request.json();
  
  // Validate API key against backend
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/auth/verify`, {
    headers: { Authorization: `Bearer ${api_key}` },
  });

  if (!res.ok) {
    return NextResponse.json({ detail: "Invalid API key" }, { status: 401 });
  }

  // Create session (simplified — use proper session management in production)
  const session = Buffer.from(api_key).toString("base64");
  
  return NextResponse.json({ success: true }, {
    headers: {
      "Set-Cookie": `session=${session}; HttpOnly; Path=/; Max-Age=86400; SameSite=Strict`,
    },
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add app/api/auth/login/route.ts
git commit -m "feat(auth): add login API route with session cookie"
```

---

## EXECUTION ORDER

1. **Phase 1** — Gateway fix (Task 1.1)
2. **Phase 2.1** — Security fix + proxy route (Task 2.1)
3. **Phase 2.2** — Unified API client (Task 2.2)
4. **Phase 2.3** — Shared components (Task 2.3)
5. **Phase 2.4** — Error boundary (Task 2.4)
6. **Phase 3.1** — Desktop sidebar (Task 3.1)
7. **Phase 3.2** — Mobile shell (Task 3.2)
8. **Phase 3.3** — Zustand stores (Task 3.3)
9. **Phase 3.4** — Profile switcher (Task 3.4)
10. **Phase 3.5** — Toast system (Task 3.5)
11. **Phase 4** — Pages Tier 1 (Tasks 4.1-4.6)
12. **Phase 4** — Pages Tier 2 (Tasks 4.7-4.12)
13. **Phase 4** — Pages Tier 3 (Tasks 4.13-4.25)
14. **Phase 5** — Auth + Polish (Tasks 5.1-5.3)

**Total:** 30 tasks, estimated 4-6 days full-time

---

## TESTING CHECKLIST

After each phase:
- [ ] Gateway health: `curl http://localhost:8444/health` → all downstreams "up"
- [ ] Docker compose: all containers `Up (healthy)`
- [ ] Next.js: `npm run dev` → no build errors
- [ ] Playwright: critical flows pass (dashboard load, navigation, API calls)
- [ ] Mobile: responsive at 375px width
- [ ] Theme: dark/light toggle works, persists in localStorage
- [ ] Profile: switcher works, reloads with new profile
- [ ] Security: no `NEXT_PUBLIC_*_KEY` in client bundle

---

Plan complete and saved to `docs/superpowers/plans/2026-09-15-alpha-frontend-full-monolith-parity.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**

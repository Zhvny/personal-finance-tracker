Last Updated: 29-05-2026 (14:30)

# SEO & GUI Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a search-engine optimized GUI with responsive sidelinks, skeleton screens for performance, and a dynamic sitemap for the Finance Tracker web application.

**Architecture:** Next.js 15 App Router with Tailwind CSS v4. Uses Server Components for data fetching and Streaming (loading.tsx) for perceived performance. Structured data (JSON-LD) is injected for better sitelink recognition.

**Tech Stack:** Next.js 15, React 19, Tailwind CSS v4, Lucide React.

---

### Task 1: Project Scaffolding & Route Setup

**Files:**
- Create: `apps/web/src/app/analytics/page.tsx`
- Create: `apps/web/src/app/behavioral/page.tsx`
- Create: `apps/web/src/app/reward/page.tsx`
- Create: `apps/web/src/components/ui/card.tsx`

- [ ] **Step 1: Create Analytics page**
Create `apps/web/src/app/analytics/page.tsx` with a basic placeholder.

- [ ] **Step 2: Create Behavioral page**
Create `apps/web/src/app/behavioral/page.tsx` with a basic placeholder.

- [ ] **Step 3: Create Reward page**
Create `apps/web/src/app/reward/page.tsx` with a basic placeholder.

- [ ] **Step 4: Create shared Card component**
Create `apps/web/src/components/ui/card.tsx` for consistent UI elements.

---

### Task 2: Responsive Sidebar (Sidelink)

**Files:**
- Create: `apps/web/src/components/layout/sidebar.tsx`
- Create: `apps/web/src/components/layout/header.tsx`
- Modify: `apps/web/src/app/layout.tsx`

- [ ] **Step 1: Implement Sidebar component**
Build a responsive sidebar with `Analytics`, `Behavioral`, and `Reward` links.
Desktop: Fixed left.
Mobile: Hidden by default.

- [ ] **Step 2: Implement Mobile Header**
Add a hamburger menu to toggle the sidebar on mobile.

- [ ] **Step 3: Update Root Layout**
Wrap children in the new Sidebar/Header layout.

---

### Task 3: Performance (Skeleton Screens & Loading States)

**Files:**
- Create: `apps/web/src/components/skeletons/analytics-skeleton.tsx`
- Create: `apps/web/src/components/skeletons/card-skeleton.tsx`
- Create: `apps/web/src/app/loading.tsx`
- Create: `apps/web/src/app/analytics/loading.tsx`

- [ ] **Step 1: Create Skeleton components**
Implement `AnalyticsSkeleton` and `CardSkeleton` using Tailwind pulse animations.

- [ ] **Step 2: Implement Global Loading**
Add `apps/web/src/app/loading.tsx` to handle top-level navigation loading.

- [ ] **Step 3: Implement Page-level Loading**
Add loading states for sub-routes to enable streaming.

---

### Task 4: SEO & Sitemap Optimization

**Files:**
- Create: `apps/web/src/app/sitemap.ts`
- Create: `apps/web/src/app/robots.ts`
- Modify: `apps/web/src/app/layout.tsx` (Metadata & JSON-LD)

- [ ] **Step 1: Implement Dynamic Sitemap**
Create `apps/web/src/app/sitemap.ts` listing all routes.

- [ ] **Step 2: Configure Robots.txt**
Create `apps/web/src/app/robots.ts`.

- [ ] **Step 3: Add Metadata & JSON-LD**
Update root layout with brand metadata and `SiteNavigationElement` structured data to encourage Google Sitelinks.

---

### Task 5: Verification & Audit

- [ ] **Step 1: Run Build**
Execute `npm run build` in `apps/web` to ensure no SSR or type errors.

- [ ] **Step 2: Check Sitemap**
Verify `localhost:3000/sitemap.xml` generates correctly (in dev).

- [ ] **Step 3: SEO Validation**
Verify metadata tags and JSON-LD script are present in the HTML.

# Design Spec: Finance Tracker SEO & GUI Enhancement

**Date:** 2026-05-26  
**Status:** Draft  
**Topic:** SEO, Sitemaps, Responsive Navigation (Sidelinks), and Performance (Skeleton Screens)

## 1. Overview
Enhance the Finance Tracker web application to be search-engine optimized (SEO) and provide a modern, high-performance user interface. The focus is on three main areas: Analytics, Behavioral, and Reward, with a responsive "Sidelink" (Sidebar) and skeleton screens for a seamless experience.

## 2. Navigation (Sidelink) & Responsive Layout
### Responsive Sidebar
- **Desktop (>= 1024px)**: Fixed sidebar on the left (~280px).
- **Mobile (< 1024px)**: Hamburger menu in a top header. Sidebar slides in from the left when toggled.
- **Menu Items**:
  - `Analytics` (`/analytics`)
  - `Behavioral` (`/behavioral`)
  - `Reward` (`/reward`)
- **UI/UX**: Using Tailwind CSS v4. Active link highlighting, hover states, and clear iconography.

### Main Content Area
- Uses a flex/grid layout to ensure content expands to fill the remaining space.

## 3. Performance & Pre-shift (Skeleton Screens)
To eliminate Layout Shift (CLS) and improve perceived performance:
- **Global Loading State**: Implement `loading.tsx` for the root and each sub-route.
- **Skeleton Components**:
  - `AnalyticsSkeleton`: Placeholder boxes for charts and metrics.
  - `CardSkeleton`: Pulse-animated placeholders for Behavioral insights and Reward points.
- **Data Fetching**: Use Next.js 15+ Server Components with appropriate streaming.

## 4. SEO & Sitelinks Strategy
Goal: Achieve multiple sitelinks in Google Search results for the brand "Finance Tracker".
- **`sitemap.ts`**: Generate a dynamic `sitemap.xml` including all main routes.
- **`robots.txt`**: Standard robots configuration.
- **Metadata**:
  - Static metadata in `layout.tsx` for the brand.
  - Dynamic metadata per-page (e.g., `Analytics | Finance Tracker`).
- **JSON-LD (Structured Data)**:
  - Implement `SiteNavigationElement` in the root layout.
  - Helps Google identify the navigation structure for Sitelinks.

## 5. Technical Implementation Details
- **Next.js**: 15.x/16.x (App Router)
- **React**: 19.x
- **Styling**: Tailwind CSS v4
- **Icons**: Lucide React
- **Routes to Create**:
  - `src/app/analytics/page.tsx`
  - `src/app/behavioral/page.tsx`
  - `src/app/reward/page.tsx`
  - `src/app/loading.tsx` (Global)
  - `src/app/sitemap.ts`

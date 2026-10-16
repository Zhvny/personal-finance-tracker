# DEPRECATED: Legacy Frontend

This package (`finance-tracker-gui`) is the **legacy** Vite/React 18 frontend.

## Status: SUPERSEDED

The canonical frontend is **`apps/web/`** (Next.js 16 + React 19).

## Migration

| Feature | Legacy (`packages/web`) | Canonical (`apps/web`) |
|---|---|---|
| Framework | Vite + React 18 | Next.js 16 + React 19 |
| Routing | React Router DOM | Next.js App Router |
| Styling | Custom CSS | Tailwind CSS 4 |
| API Client | Direct fetch | Server-side + ISR |

## Decision

**Date:** 2026-08-11  
**Decision:** Freeze `packages/web`. No new features should be added here.  
**Action:** All development should target `apps/web/`.  
**Removal:** This package will be removed after the `apps/web` feature set reaches parity.

## What exists in the legacy package

- Behavioral finance visualizations (charts, heatmaps)
- OCR receipt uploads
- Investment portfolio view
- AI insight panels

These features are planned for `apps/web` in future sprints.

Last Updated: 29-05-2026 (14:30)

---
title: \"Frontend Progressive/Lazy Loading Refactor - Session 1\"
created: \"2026-05-16T14:15:00Z\"
status: \"approved\"
authors: [\"TechLead\", \"User\"]
type: \"design\"
design_depth: \"standard\"
task_complexity: \"medium\"
---

# Frontend Progressive/Lazy Loading Refactor Design

## Problem Statement
The frontend currently suffers from high 'Time to Interactive' due to a monolithic `/dashboard` API call that blocks rendering. This results in dashboard-wide re-renders during mount and ticker switches, degrading UX on lower-spec hardware (target: 8GB RAM).

## Requirements
### Functional Requirements
- **REQ-1**: Audit frontend initialization for global preload calls and blocking chains.
- **REQ-2**: Implement ticker-first rendering (shell immediately, then selected ticker).
- **REQ-3**: Isolate widget-level fetches (chart, technicals, sentiment, etc.).
- **REQ-4**: Implement individual loading states/skeletons per widget.

### Non-Functional Requirements
- **PERF-1**: Reduce First Paint Time.
- **PERF-2**: Eliminate full dashboard re-renders on ticker switch.
- **RELIABILITY**: Maintain data integrity across granular fetches.

## Approach
### Selected Approach: Decomposed State / Granular Fetches
- **Architecture**: Refactor `useDashboard` into granular, independent hooks (e.g., `useTickerBase`, `useChartData`, `useSentiment`).
- **Rendering Strategy**: Shell-First with Lazy Hydration. `App.jsx` renders immediately without waiting for API data.
- **Hydration**: Components use React 18 `Suspense` with `Skeleton` loaders to handle async data streams independently.

### Alternatives Considered
- **Unified Dashboard with Progressive Updates**: Rejected because it maintains dependency on a single backend response structure, making it harder to prioritize specific data points (like price over macro).

## Architecture
- **API Helper**: `apiFetch` in `useApi.js` remains the core transport but will handle more frequent, smaller requests.
- **Data Hook Layer**: New hooks in `useApi.js` for granular endpoints.
- **Component Layer**: Widgets in `dashboard.jsx` and `stock_analyzer.jsx` updated to use independent hooks.

## Agent Team
| Phase | Agent | Parallel | Deliverables |
|-------|-------|----------|--------------|
| 1     | coder | No       | Refactored hooks and initialization flow |
| 2     | coder | No       | Shell-first rendering implementation |
| 3     | coder | No       | Widget-level loading isolation |
| 4     | tester| No       | Performance and stability validation |

## Risk Assessment
- **Fetch Storms**: High frequency of small requests. *Mitigation*: Ensure request deduplication and stable dependency arrays in hooks.
- **State De-sync**: Widgets showing data from different tickers. *Mitigation*: Key all widget hooks by the active ticker symbol.

## Success Criteria
1. Page shell visible < 500ms.
2. Selected ticker data visible before macro/analytics data.
3. No full-page flicker when switching modules or tickers.
4. Passing tests for isolated loading states.

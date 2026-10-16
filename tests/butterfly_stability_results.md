# Butterfly Effect Map Stability Results

## Session Baseline (Phase 1)
- **Date**: 2026-05-18
- **Environment**: Local Development
- **Vite Server**: `https://localhost:5173` (ACTIVE, Verified 200 OK via Node.js)
- **API Server**: `https://0.0.0.0:8443` (ACTIVE, Verified via logs)

### Component Identification
- **Target**: Butterfly Effect Map
- **Source File**: `finance-tracker-gui/src/module/stock_analyzer.jsx`
- **Component**: `ButterflyMap`
- **Hook**: `useButterflyBenchmark` (`src/hooks/useButterflyBenchmark.js`)
- **Container**: Renders inside `StockAnalyzer` within a `ButterflyErrorBoundary`.
- **Text Anchor**: `BUTTERFLY EFFECT MAP` (verified via source grep).

### Connectivity Report
- Verified `https://localhost:5173/stocks` is reachable.
- Note: Development server uses self-signed certificates; test calls configured to ignore unauthorized certs.

### Initial Observations
- Server processes are running (Vite PID 12316, API PID 62312).
- The `ButterflyMap` component uses a memoized pattern and depends on a WebSocket connection ("butterfly") for real-time updates.
- Graph data is fetched from `/api/butterfly/risk-map/${ticker}`.

---
*End of Phase 1 Report*

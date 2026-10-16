Last Updated: 29-05-2026 (14:30)

# Design Document: Asynchronous Independent DXY Panel (Final)

**Date:** 2026-05-14
**Status:** APPROVED
**Context:** Finance Tracker / Stock Analyzer

## 1. Problem Statement
The current DXY (US Dollar Index) fetching logic is tightly coupled with the main stock analysis pipeline. If the DXY fetch is slow, it blocks the entire Quant Terminal dashboard.

## 2. Goals
- **Independence:** DXY panel must load, retry, and fail without blocking Stock Analyzer.
- **Dedicated Endpoint:** Use a lightweight endpoint for DXY updates to avoid re-running full ML/technical analysis.
- **Graceful Degradation:** Show specific status text (`Syncing`, `Unavailable`, `Awaiting`) instead of generic errors.
- **No Blocking:** Stock Analyzer returns immediately; DXY panel populates later.

## 3. Proposed Architecture

### 3.1 Backend (DXY Specialist Endpoint)
- **New Endpoint**: `GET /api/stocks/analyze/{ticker}/dxy`
    - Computes only the DCDS (DXY-Commodity Divergence Score).
    - Lightweight: No ML, no heavy technicals.
    - Returns: `{"ticker": "...", "dcds": float | status_object}`.
- **Service Layer**: Add `get_dcds_analysis(ticker)` to `StockAnalysisService`.
- **Repository**: `StockRepository` continues to handle background DXY syncing.

### 3.2 Frontend (Active DXYPanel)
- **Component**: `DXYPanel` extracted into a self-managing widget.
- **Logic**:
    - If `dcds.status === "syncing"`, start an internal interval (e.g., every 5s).
    - Call `/api/stocks/analyze/{ticker}/dxy` independently.
    - Update local state upon success.
    - Stop polling after success or max retries (3).

## 4. UI States
- `Macro data syncing`: Background DXY fetch active.
- `DXY unavailable`: Fetch failed or timed out.
- `Awaiting correlation data`: Non-macro asset or insufficient history.

## 5. Success Criteria
- Opening a ticker shows price/signal in < 1s.
- DXY panel populates independently without re-fetching the entire dashboard data.
- Dashboard remains responsive during DXY sync.

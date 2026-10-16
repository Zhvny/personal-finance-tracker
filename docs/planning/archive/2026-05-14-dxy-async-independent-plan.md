Last Updated: 29-05-2026 (14:30)

# Asynchronous Independent DXY Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple DXY loading from the main stock analysis pipeline by providing a dedicated lightweight endpoint and an active frontend widget.

**Architecture:**
1. **Backend:** Add a lightweight `/api/stocks/analyze/{ticker}/dxy` endpoint that returns only DXY divergence data.
2. **Frontend:** Refactor `DXYPanel` to manage its own loading lifecycle and poll the new endpoint if data is initially syncing.

**Tech Stack:** Python (FastAPI), React (Vite).

---

### Task 1: Backend - Add DCDS-only Analysis Method

**Files:**
- Modify: `finance-tracker-gui/backend/services/stock_analysis_service.py`

- [x] **Step 1: Implement `get_dcds_analysis` method.**
  - This method should fetch the ticker data and DXY data, then compute only DCDS.

```python
# Add to StockAnalysisService class
    async def get_dcds_analysis(self, ticker: str) -> Dict[str, Any]:
        """Lightweight DCDS calculation for async updates."""
        try:
            norm_ticker = self.fetcher.normalize(ticker)
            dxy_status = await self.repo.get_dxy_status()
            
            if not dxy_status["is_ready"]:
                if dxy_status["is_syncing"]:
                    return {"ticker": norm_ticker, "dcds": {"status": "syncing"}}
                return {"ticker": norm_ticker, "dcds": {"status": "unavailable"}}

            # Fetch ticker and DXY data
            df_task = self.repo.fetch_ticker_data(norm_ticker, period="1y")
            dxy_task = self.repo.get_dxy_data()
            df, dxy_df = await asyncio.gather(df_task, dxy_task)

            if df is None or dxy_df is None or df.empty or dxy_df.empty:
                return {"ticker": norm_ticker, "dcds": {"status": "insufficient data"}}

            # Compute DCDS only
            loop = asyncio.get_event_loop()
            df_with_dcds = await loop.run_in_executor(None, self.indicators.compute_dcds, df, dxy_df)
            
            dcds_val = df_with_dcds['dcds'].iloc[-1]
            import math
            import numpy as np
            
            if dcds_val is None or (isinstance(dcds_val, (float, np.float64)) and np.isnan(dcds_val)):
                return {"ticker": norm_ticker, "dcds": {"status": "insufficient data"}}
                
            return {
                "ticker": norm_ticker,
                "dcds": float(dcds_val) if math.isfinite(dcds_val) else None
            }
        except Exception as e:
            logger.error(f"DCDS analysis failed for {ticker}: {e}")
            return {"ticker": ticker, "dcds": {"status": "unavailable"}}
```

### Task 2: Backend - Expose DXY Endpoint

**Files:**
- Modify: `finance-tracker-gui/backend/routers/stocks.py`

- [x] **Step 1: Add the route to `routers/stocks.py`.**

```python
@router.get("/analyze/{ticker}/dxy")
async def get_dxy_analysis(ticker: str):
    """Get only DXY divergence analysis for a ticker."""
    return await _service.get_dcds_analysis(ticker.upper())
```

### Task 3: Frontend - Refactor `DXYPanel` to Active Widget

**Files:**
- Modify: `finance-tracker-gui/src/module/stock_analyzer.jsx`

- [x] **Step 1: Update `DXYPanel` to support internal polling.**
  - Add internal state and effect to fetch DXY if status is "syncing".

```javascript
const DXYPanel = ({ ticker, initialDcds }) => {
  const [dcds, setDcds] = useState(initialDcds);
  const [syncCount, setSyncCount] = useState(0);

  const status = dcds?.status;
  const isSyncing = status === "syncing";
  const isUnavailable = status === "unavailable";
  const isAwaiting = status === "insufficient data";
  const dcdsVal = typeof dcds === "object" ? null : dcds;

  useEffect(() => {
    // Reset state when ticker changes
    setDcds(initialDcds);
  }, [ticker, initialDcds]);

  useEffect(() => {
    if (status === "syncing" && syncCount < 10) {
      const timer = setTimeout(async () => {
        try {
          const res = await apiFetch(`/stocks/analyze/${ticker}/dxy`);
          if (res?.dcds && res.dcds.status !== "syncing") {
            setDcds(res.dcds);
          } else {
            setSyncCount(prev => prev + 1);
          }
        } catch (e) {
          console.error("DXY polling failed", e);
          setSyncCount(prev => prev + 1);
        }
      }, 5000); // Poll every 5s
      return () => clearTimeout(timer);
    }
  }, [status, ticker, syncCount]);

  return (
    <div style={{ background: "var(--bg3)", padding: 16, borderRadius: 16, border: "1px solid var(--bdr)", position: "relative" }}>
      <div className="lbl" style={{ fontSize: 8, marginBottom: 6 }}>DXY Divergence</div>
      <div style={{ fontSize: status ? 9 : 16, fontWeight: 900, color: status ? "var(--tx3)" : (Math.abs(dcdsVal || 0) > 1.5 ? "var(--rd)" : "var(--cy)") }}>
        {isSyncing ? (
          <div className="pulse" style={{ fontSize: 9 }}>Macro data syncing</div>
        ) : isUnavailable ? (
          "DXY unavailable"
        ) : isAwaiting ? (
          "Awaiting correlation data"
        ) : (
          fmt(dcdsVal, 2)
        )}
      </div>
      {isSyncing && (
        <div style={{ position: "absolute", bottom: 4, right: 8, fontSize: 7, opacity: 0.5 }}>BACKGROUND TASK</div>
      )}
    </div>
  );
};
```

- [x] **Step 2: Update `StockAnalyzer` main render.**
  - Update the `DXYPanel` instantiation to pass the `ticker`.
  - Remove the manual reconciliation `useEffect` in `StockAnalyzer` as it's now handled by the component.

```javascript
// Remove this from StockAnalyzer
// useEffect(() => {
//   if (data?.dcds?.status === "syncing" && !loading) {
//     const timer = setTimeout(() => {
//       analyze(data.ticker);
//     }, 8000); // Check every 8s
//     return () => clearTimeout(timer);
//   }
// }, [data, loading, analyze]);

// Update usage in render:
<DXYPanel ticker={data.ticker} initialDcds={data.dcds} />
```

### Task 4: Verification

- [x] **Step 1: Test with fresh session (No cache).**
  - Open terminal, select ticker.
  - Expect: Dashboard price/signal appears instantly. DXY shows "Macro data syncing".
  - Wait: DXY should update to a numeric value within ~10 seconds.
- [x] **Step 2: Test non-macro asset.**
  - Select an equity ticker (e.g., TSLA).
  - Expect: DXY shows "N/A for non-macro assets" (logic in `stock_analysis_service.py`).
- [x] **Step 3: Test failure scenario.**
  - (Simulate DXY API failure if possible).
  - Expect: DXY shows "DXY unavailable" after retries.

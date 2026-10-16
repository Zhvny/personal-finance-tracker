Last Updated: 29-05-2026 (14:30)

# VWAP Advanced Signals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement trend-following and mean-reversion signals in VWAPEngine.

**Architecture:** Add `get_signals` method to `VWAPEngine`. Calculate ATR for threshold. logic: retrace to VWAP (Trend) and extreme distance from VWAP (Mean Reversion).

**Tech Stack:** Python, Pandas, Numpy.

---

### Task 1: Create failing test for get_signals

**Files:**
- Modify: `tests/unit/test_vwap.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_signals_trend_bullish(session_data):
    engine = VWAPEngine()
    vwap = engine.calculate_standard(session_data)
    
    # Setup bullish trend with pullback
    # Price > VWAP (100)
    session_data.iloc[-1, session_data.columns.get_loc('Close')] = 100.3 # Pullback to 0.3%
    session_data.iloc[-1, session_data.columns.get_loc('High')] = 100.5
    session_data.iloc[-1, session_data.columns.get_loc('Low')] = 100.1
    
    signals = engine.get_signals(session_data, vwap)
    assert signals['trend_signal'] == 'BULLISH_PULLBACK'

def test_get_signals_mean_reversion_extended_up(session_data):
    engine = VWAPEngine()
    vwap = engine.calculate_standard(session_data)
    
    # Setup extended price
    # Default ATR will be low if constant. Let's force a high price.
    session_data.iloc[-1, session_data.columns.get_loc('Close')] = 120.0
    
    signals = engine.get_signals(session_data, vwap)
    assert signals['mean_reversion_signal'] == 'EXTENDED_UP'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH = "."; pytest tests/unit/test_vwap.py`
Expected: FAIL with "AttributeError: 'VWAPEngine' object has no attribute 'get_signals'"

### Task 2: Implement get_signals and helper methods

**Files:**
- Modify: `apps/cli/stock_analyzer/domain/strategies/vwap.py`

- [ ] **Step 1: Implement ATR calculation and get_signals**

```python
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range (ATR)."""
        if len(df) < 2:
            return 0.0
        
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - df['Close'].shift()).abs()
        low_close = (df['Low'] - df['Close'].shift()).abs()
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr) if not np.isnan(atr) else 0.0

    def get_signals(self, df: pd.DataFrame, vwap_series: pd.Series) -> dict:
        """
        Generate signals based on Price vs VWAP relationship.
        """
        if df.empty or vwap_series.empty:
            return {"trend_signal": "NEUTRAL", "mean_reversion_signal": "NEUTRAL"}

        last_price = df['Close'].iloc[-1]
        last_vwap = vwap_series.iloc[-1]
        
        # 1. Trend Following
        # Pullback range: within 0.5% of VWAP
        dist_pct = (last_price - last_vwap) / last_vwap
        trend_signal = "NEUTRAL"
        
        if last_price > last_vwap and 0 <= dist_pct <= 0.005:
            trend_signal = "BULLISH_PULLBACK"
        elif last_price < last_vwap and -0.005 <= dist_pct <= 0:
            trend_signal = "BEARISH_PULLBACK"
            
        # 2. Mean Reversion
        atr = self._calculate_atr(df)
        threshold = 2.5 * atr if atr > 0 else 0.05 * last_vwap # Fallback to 5% if no ATR
        
        dist_abs = abs(last_price - last_vwap)
        mr_signal = "NEUTRAL"
        
        if dist_abs > threshold:
            if last_price > last_vwap:
                mr_signal = "EXTENDED_UP"
            else:
                mr_signal = "EXTENDED_DOWN"
                
        return {
            "trend_signal": trend_signal,
            "mean_reversion_signal": mr_signal,
            "last_price": last_price,
            "last_vwap": last_vwap,
            "dist_pct": dist_pct,
            "threshold": threshold
        }
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `$env:PYTHONPATH = "."; pytest tests/unit/test_vwap.py`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add apps/cli/stock_analyzer/domain/strategies/vwap.py tests/unit/test_vwap.py
git commit -m "feat(vwap): add advanced trend-following and mean-reversion signals"
```

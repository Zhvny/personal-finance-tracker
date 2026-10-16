# System Design Report: IDX/USD Stock Analysis & Prediction System (Updated 2026-04-21)

**Document Type:** Architecture Review
**Perspective:** Senior Software Engineer / System Design Review
**Date:** April 2026
**Stack:** Python · yfinance · pandas · pandas-ta · tenacity · textual · SQLite · FRED API
**Version:** 3.1 (Reflects Remote Integration & Restricted Access)

---

## Executive Summary

This system is a **semi-automated stock analysis pipeline** built in Python that ingests OHLCV data from Yahoo Finance, computes technical indicators, applies a multi-dimensional scoring model, and delivers actionable trading signals.

**Key 2026 Updates:**
- **Remote Visibility**: Integrated into the ZhvnyTools Remote Dashboard (Port 3131).
- **Access Control**: Restricted to `run-dashboard.bat` (Mobile Dashboard) and `main.py` (Legacy CLI) within the remote context.
- **Performance**: Optimized SQLite caching for remote high-latency environments (Tailscale).

---

## 1. System Overview

The system follows a **linear modular pipeline** where each stage has one clearly defined responsibility, communicates through immutable pandas DataFrames, and can be tested in isolation.

```
┌────────────────────────────────────────────────────────────────┐
│                         Entry Points                           │
│  main.py (TUI)  ·  dashboard.py (Mobile)  ·  Remote (Web)      │
└──────────────────────────┬─────────────────────────────────────┘
                           │
                 StockAnalyzer (use_cases/analyzer.py)
                           │
         ┌─────────────────▼──────────────────┐
         │       [Stage 1] Fetch              │  DataFetcher
         │  yfinance · retry · thread · cache │  adapters/fetcher.py
         └─────────────────┬──────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │    [Stage 2] Indicators            │  IndicatorEngine
         │  EMA50/200 · OBV · RSI Diverg.     │  adapters/indicators.py
         └─────────────────┬──────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │      [Stage 3] Score               │  ScoringEngine
         │  10-point Additive Model           │  domain/scoring.py
         └─────────────────┬──────────────────┘
                           │
         ┌─────────────────▼──────────────────┐
         │   [Stage 4] Output                 │  TUI / Dashboard / Web
         └────────────────────────────────────┘
```

---

## 2. Remote Deployment & Access

Stock Analyzer is now accessible via the **ZhvnyTools Remote Dashboard**.

- **Mobile**: `stock_analyzer\run-mobile.bat` provides a responsive Plotly-based dashboard optimized for mobile viewing via Tailscale.
- **Caching**: The system uses a market-aware SQLite cache (`cache.db`) to minimize network I/O, which is critical for remote access over mobile networks.

---

## 3. Scoring Model (v3.1)

The scoring model remains a **10-point additive system**:
- **Trend (3.0 pts)**: EMA50/200 relationship.
- **Momentum (3.0 pts)**: MACD, Stoch, RSI > 50.
- **Volume/OBV (2.0 pts)**: Volume > MA20, OBV Slope > 0.
- **Divergence (2.0 pts)**: Bullish RSI Divergence detection.

**Hard Filter**: Stocks below EMA200 are automatically disqualified from Trend points to prevent "falling knife" entries.

---

*Stock Analyzer Architecture Report — v3.1*

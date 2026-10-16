Last Updated: 29-05-2026 (14:30)

# Performance Benchmark Report - Session 7 Refactor

**Date**: 2026-05-18
**System**: Finance Tracker (Backend Refactor)
**Ticker Tested**: BBCA.JK
**Environment**: Local (HTTPS :8444)

## API Endpoints Latency
Metrics captured via `scripts/benchmark_latency.py`.

| Endpoint | Latency (ms) | Response Size (KB) | Status | Note |
|----------|--------------|-------------------|--------|------|
| `ticker_base` | 6975.96 | 0.10 | 200 | Includes initial yfinance fetch/cache |
| `ticker_chart` | 215.84 | 10.48 | 200 | Historical data retrieval |
| `ticker_technicals` | 118.80 | 0.19 | 200 | Indicator calculations |
| `ticker_sentiment` | 114.74 | 0.11 | 200 | Sentiment engine analysis |
| `ticker_dxy` | 55.44 | 0.04 | 200 | Correlation check |
| `ticker_butterfly` | 57.23 | 0.11 | 200 | Risk map generation |
| `ticker_senate` | 163.82 | 1.65 | 200 | Compliance & trade signals |

## System Resource Usage (API Server)
| Metric | Baseline | During Benchmark | Post-Benchmark |
|--------|----------|------------------|----------------|
| CPU (%) | 0.0% | 0.0% | 0.0% |
| Memory (RSS MB) | 18.16 MB | - | 336.00 MB |

## Frontend KPIs
Metrics captured via Chrome DevTools Performance Trace.

| Metric | Value | Note |
|--------|-------|------|
| LCP (Largest Contentful Paint) | 740 ms | Fast (Good < 2500ms) |
| TTFB (Time to First Byte) | 633 ms | Dominates LCP due to SSL/Backend init |
| Render Delay | 108 ms | Browser rendering overhead |
| CLS (Cumulative Layout Shift) | 0.00 | No layout shifts detected |
| Ticker Switch Latency | ~200ms | Observed UI update after base fetch cache |

## Observations
- **Initial Fetch**: The `ticker_base` endpoint shows high latency (~7s) on the first request as it synchronizes with external providers (yfinance). Subsequent calls are significantly faster due to caching.
- **Memory Footprint**: Memory jumped from 18MB to 336MB. This is expected as the `MarketData` and `PostgreSQL` pools are lazily initialized upon the first request.
- **Frontend Stability**: CLS of 0.00 indicates a highly stable UI transition despite the backend processing depth.

# 🚀 Feature: Advanced Analytics & Forecasting

The **Advanced Features** module provides future-looking insights, using historical data to predict your financial trajectory.

---

## 🏗️ Technical Architecture
- **`domain/models.py`**: Defines `Goal` and `ForecastPoint` entities.
- **`application/services`**: Logic for cashflow projection and saving simulations.

---

## 🧩 Deep Dive: Predictive Engines

### 1. 30-Day Cashflow Forecast
Uses a **7-Day Simple Moving Average (SMA)** with a **90-day lookback** window.
- **Logic**: It calculates your average daily net (Income - Expense) from the last 90 days and projects it forward 30 days to estimate your month-end balance.

### 2. Goal Optimization
For each `Goal` (e.g., "Buy a Laptop"), the system calculates:
- **Months Remaining**: Based on a user-defined target date.
- **Required Monthly Saving**: The specific amount you need to save per month starting *today* to reach the goal.

### 3. Portfolio Risk (Simulation)
Uses historical volatility of asset classes (Crypto: 80%, Stocks: 22%) to run basic scenario analysis (Bear/Base/Bull) on your current net worth.

---
07-05-2026 (22:35)

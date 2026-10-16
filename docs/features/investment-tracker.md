# 📈 Feature: Investment Tracker

The **Investment Tracker** is a high-precision engine for managing financial assets including Stocks, Crypto, and Gold. It handles the entire lifecycle from acquisition to valuation and eventual exit (sale), with a core focus on **FIFO (First-In-First-Out)** logic for tax and P/L accuracy.

---

## 🏗️ Technical Architecture

The module follows a Clean Architecture pattern:
- **`core/`**: Repository interfaces and local data access logic.
- **`models/`**: Domain entities (`Investment`, `SellTransaction`, `InvestmentStatus`).
- **`services/`**: The "Brain" of the tracker.
    - `SellService`: Handles partial/full sell logic.
    - `PriceServiceFactory`: Dynamically selects the correct provider (Yahoo, CoinGecko, or Scraping).
- **`ui/`**: Rich-powered CLI views.

---

## 🧩 Deep Dive: Core Logic

### 1. The FIFO Sell Engine
To ensure accurate realized P/L, the system tracks individual "lots" of assets. When a partial sale occurs:
1. The `SellService` validates the remaining quantity.
2. It calculates the **Cost Basis** based on the original purchase price (normalized to IDR).
3. It updates the lot status: `holding` → `partial_sold` → `sold`.
4. Realized P/L is calculated as: `(Sell Price - Buy Price) * Quantity - Fees`.

### 2. Multi-Asset Price Engine
The system uses a **Factory Pattern** to fetch real-time data:
- **Stocks**: Fetched via `yfinance`.
- **Crypto**: Fetched via `CoinGecko API`.
- **Gold**: Scraped from `LogamMulia.com`.
- **FX Service**: Dynamically converts USD prices to IDR using real-time mid-market rates.

---

## 📊 Data Schema (`portfolio.db`)
- **`investments`**: Active holdings.
- **`sell_transactions`**: Audit trail of all exits.
- **`historical_prices`**: Cache for performance charting.

---

## 🚀 CLI Commands
1. **Add**: Log a new buy transaction.
2. **View**: Show active portfolio with live Unrealized P/L.
3. **Sell**: Execute a partial or full exit.
4. **Analysis**: Show historical growth and asset distribution.

---
07-05-2026 (22:35)

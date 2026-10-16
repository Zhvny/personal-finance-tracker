# Finance Tracker CLI — v10.0

Modular terminal-based personal finance suite (Python + Rich).
Mencakup investment, expense, income, receipt OCR, advanced analytics, dan behavioral finance.

---

## Table of Contents

1. [Features](#features)
2. [Project Structure](#project-structure)
3. [Architecture](#architecture)
4. [Requirements & Installation](#requirements--installation)
5. [Quick Start](#quick-start)
6. [Module Documentation](#module-documentation)
7. [Data Storage](#data-storage)
8. [GUI Integration](#gui-integration)

---

## Features

| Module | Highlights |
|---|---|
| **Investment Tracker** | Yahoo Finance (stocks), CoinGecko (crypto), LogamMulia (gold); sell FIFO dengan P/L; realized P/L history; status: `holding → partial_sold → sold` |
| **Expense Tracker** | Category breakdown, budget-vs-actual, monthly summary, recurring expenses |
| **Income Tracker** | Income type breakdown, PPh 21 tax estimate, monthly summary |
| **Receipt Reader** | Ensemble OCR (Tesseract + EasyOCR + PaddleOCR), auto-kategorisasi, export ke expense/income DB |
| **Advanced Features** | Goal-based saving, cashflow forecast 30-hari, budget planner per kategori |
| **Behavioral Finance** | FBS score, impulse spending analysis, lifestyle inflation, fragility score, net worth snapshot |

---

## Project Structure

```
apps/cli/
├── main.py                              ← Root launcher + live dashboard
├── README_CLI.md
│
├── expense_tracker/
│   ├── main.py
│   ├── core/
│   │   ├── models.py                    ← Expense, ExpenseCategory, PaymentMethod
│   │   ├── repository.py                ← SQLiteExpenseRepository
│   │   ├── calculator.py                ← ExpenseCalculator
│   │   └── interfaces.py
│   ├── services/
│   │   ├── budget_service.py
│   │   └── recurring_service.py
│   ├── ui/cli_view.py
│   └── data/expense.db                  ← Consolidated Data Source
```
├── income_tracker/
│   ├── main.py
│   ├── core/
│   │   ├── models.py                    ← Income, IncomeType
│   │   ├── repository.py
│   │   ├── calculator.py
│   │   └── interfaces.py
│   ├── services/
│   │   ├── categorization_service.py
│   │   └── tax_service.py               ← PPh 21 progressive calculator
│   ├── ui/cli_view.py
│   └── data/income.db
│
├── investment_tracker/
│   ├── main.py
│   ├── core/
│   │   ├── models.py                    ← Investment, AssetType, Status
│   │   ├── repository.py
│   │   ├── calculator.py
│   │   └── interfaces.py
│   ├── services/
│   │   ├── price_service.py             ← PriceServiceFactory
│   │   ├── stock_service.py             ← Yahoo Finance
│   │   ├── crypto_service.py            ← CoinGecko
│   │   ├── gold_service.py              ← LogamMulia scraper
│   │   ├── fx_service.py                ← USD/IDR rate
│   │   ├── sell_service.py              ← FIFO sell logic
│   │   └── historical_service.py
│   ├── ui/cli_view.py
│   └── data/portfolio.db               ← investments, sell_transactions, historical_prices
│
├── receipt_reader/
│   ├── main.py
│   ├── core/
│   │   ├── ocr_engine.py
│   │   ├── ocr_ensemble.py              ← Multi-engine voting ensemble
│   │   ├── parser.py                    ← Text → structured ReceiptData (~1200 LOC)
│   │   ├── validator.py
│   │   ├── categorizer.py
│   │   ├── keywords.py
│   │   └── engines/
│   │       ├── tesseract_engine.py
│   │       ├── easyocr_engine.py
│   │       └── paddle_engine.py
│   ├── core/exporters/
│   │   ├── expense_exporter.py
│   │   ├── income_exporter.py
│   │   └── json_exporter.py
│   └── ui/cli_view.py
│
├── advanced_features/
│   ├── main.py
│   ├── domain/models.py                 ← Goal, CashflowForecast
│   ├── application/use_cases.py         ← GoalUseCases, ForecastUseCases, BudgetUseCases
│   ├── interface/cli.py
│   └── data/goals.db                    ← Dibaca juga oleh GUI (shared)
│
└── behavioral_finance/
    ├── __main__.py
    ├── domain/models.py                 ← FBSResult, FragilityResult, ImpulseResult
    ├── application/use_cases.py         ← compute_fbs, compute_fragility, compute_impulse_score
    └── interface/cli.py
```

---

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────┐
│  interface  │────▶│ application │────▶│    domain    │
│  (cli.py)   │     │ (use_cases) │     │  (models)    │
└─────────────┘     └─────────────┘     └──────────────┘
                            │
                     ┌──────┴──────┐
                     │    core     │
                     │ (repository)│
                     └──────┬──────┘
                            │
                       SQLite .db
```

**Design Patterns:**
- **Repository Pattern** — semua DB access lewat `core/repository.py`
- **Strategy Pattern** — OCR engines dan price services pluggable via factory
- **Factory Pattern** — `PriceServiceFactory.get_service(asset_type)` pilih service berdasarkan tipe aset
- **Clean Architecture** — UI → Application → Domain → Data (dependency inward only)

**Import convention:** Semua import antar-module menggunakan fully-qualified path (contoh: `from expense_tracker.core.models import Expense`) agar benar apapun working directory saat dijalankan.

---

## Requirements & Installation

```bash
# Core
pip install rich

# Investment prices
pip install yfinance requests

# Receipt OCR (pilih salah satu atau semua)
pip install pytesseract pillow          # Tesseract (perlu binary Tesseract di PATH)
pip install easyocr                     # EasyOCR (auto-download model ~1GB)
pip install paddlepaddle paddleocr      # PaddleOCR

# GUI API bridge
pip install fastapi uvicorn python-multipart

# Behavioral Finance
pip install numpy
```

---

## Quick Start

### Cara cepat — `setup.bat` (Windows)

Dari root monorepo (`finance-tracker/`), double-click atau jalankan:

```
setup.bat
```

Script otomatis install semua dependencies, generate `.env` + TLS cert (sekali saja), lalu tampilkan menu:

```
  1. Command Line Interface
  2. Graphical User Interface
  3. Exit
```

Pilih **1** untuk langsung masuk CLI.

### Manual

```bash
# Jalankan root dashboard (menu utama)
cd apps/cli
python main.py
```
# Langsung ke module tertentu
python -m expense_tracker.main
python -m income_tracker.main
python -m investment_tracker.main
python -m receipt_reader.main
python -m advanced_features.main
python -m behavioral_finance
```

---

## Module Documentation

### Investment Tracker

**Status lifecycle:**
```
holding → partial_sold (sisa > 0 setelah jual sebagian) → sold (remaining_quantity = 0)
```

**Sell logic:**
- FIFO — lot terlama dijual duluan
- Harga sell bisa dalam USD atau IDR
- Realized P/L disimpan di `sell_transactions` dan tidak hilang saat prune/clean

**Penting:**
- Baris `status = 'sold'` tidak muncul di portfolio aktif (GUI maupun CLI)
- Prune CLI / Clean DB GUI: hapus baris sold, P/L history tetap ada

### Expense Tracker

- Kategori: `food, transport, housing, entertainment, health, shopping, education, other`
- Payment method: `cash, transfer, credit_card, debit_card, e-wallet, other`
- Budget per kategori per bulan di-set via GUI (Advanced → Budget Planner) → `budget.db`

### Income Tracker

- Tipe: `salary, freelance, side_hustle, investment, other`
- PPh 21 progressive bracket (PTKP K/0 = Rp58.5 juta):

| PKP | Tarif |
|---|---|
| s/d Rp60 juta | 5% |
| Rp60–250 juta | 15% |
| Rp250–500 juta | 25% |
| Rp500 juta–5 miliar | 30% |
| >Rp5 miliar | 35% |

### Receipt Reader

**OCR Engines** (ensemble — majority voting untuk akurasi terbaik):
1. **Tesseract** — cepat, perlu binary Tesseract di PATH
2. **EasyOCR** — akurat untuk teks campuran Indonesia/Inggris, model auto-download
3. **PaddleOCR** — alternatif untuk dokumen terstruktur

Tiga engine berjalan concurrent via `ThreadPoolExecutor`. Hasil tiap field (merchant, total, date) dipilih berdasarkan suara mayoritas (≥2 engine sepakat) atau engine dengan confidence tertinggi.

**Export:** → `expense.db` atau `income.db`

### Advanced Features

**Goal-based Saving:**
- Set target amount dan deadline
- Track progress dengan deposit
- `advanced_features/data/goals.db` dibaca juga oleh GUI (shared, path absolut)

**Cashflow Forecast:**
- Proyeksi 30 hari berdasarkan 7-day SMA dari 90 hari data historis
- Warning otomatis jika proyeksi saldo negatif

### Behavioral Finance

**FBS (Financial Behavior Score):** composite 0–100

| Komponen | Bobot | Keterangan |
|---|---|---|
| Saving Rate | 30% | (Income – Expense) / Income |
| Budget Adherence | 25% | Kepatuhan terhadap limit budget |
| Impulse Control | 20% | Kebalikan dari impulse index |
| Consistency | 15% | Stabilitas pengeluaran antar bulan |
| Emergency Buffer | 10% | EF / (monthly_expense × 3) |

**Fragility Score:** 0–100 (higher = lebih stabil)
- Emergency Fund (30%), Income Diversification (20%), High-Risk Assets (20%), Debt Ratio (20%), Save Stability (10%)

---

## Data Storage

| File | Path (dari `apps/cli/`) | Tabel |
|---|---|---|
| `expense.db` | `expense_tracker/data/expense.db` | `expenses` |
| `income.db` | `income_tracker/data/income.db` | `incomes` |
| `portfolio.db` | `investment_tracker/data/portfolio.db` | `investments`, `sell_transactions`, `historical_prices` |
| `goals.db` | `advanced_features/data/goals.db` | `goals` — **dipakai bersama GUI** |

GUI-only databases (di `finance-tracker-gui/data/`):

| File | Tabel |
|---|---|
| `goals.db` | `cash_split`, `manual_balances`, `transfer_log`, `reward_state` |
| `budget.db` | `budgets` |
| `merchant_map.db` | `merchant_map` |
| `networth_history.db` | `networth_snapshots` |
| `audit_log.db` | `audit_log` |

> **Jangan hapus file .db — semua data transaksi ada di sana.**

---

## GUI Integration

GUI (`finance-tracker-gui/`) terhubung ke CLI via FastAPI bridge (`api_server.py`) dengan HTTPS + Bearer token auth.

**Yang GUI baca dari CLI databases:**
- `expense.db` → semua expense transactions
- `income.db` → semua income transactions
- `portfolio.db` → investments + harga historis + sell transactions
- `goals.db` (CLI path) → goals data (shared, satu DB)

**Yang GUI maintain sendiri:**
- `budget.db` → budget limits
- `cash_split`, `manual_balances` → balance system (dalam `goals.db` GUI-side)
- `merchant_map.db` → learned merchant → category mappings
- `networth_history.db` → snapshots harian dari scheduler
- `audit_log.db` → security log

**Bank Savings auto-sync:**
```python
bank_savings = max(0, SUM(incomes.amount) - SUM(expenses.amount))
```
Dihitung ulang setiap `GET /api/balances` — tidak perlu set manual.

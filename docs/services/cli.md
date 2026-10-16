# **Service Documentation: Finance Tracker CLI**

**Service Name:** `finance-tracker-cli`  
**Location:** `apps/cli`  
**Entry Points:** `main.py` (Standard), `tui.py` (Textual)

---

### **1. Purpose**
The `finance-tracker-cli` (located in `apps/cli`) serves as the high-velocity, engineer-centric interface for the Finance Tracker ecosystem. It provides a keyboard-driven environment for rapid data entry, portfolio monitoring, and administrative tasks without the overhead of a web browser. It is designed to share the same persistence layer as the GUI, ensuring real-time consistency across all interfaces.

---

### **2. Core Features**
*   **Unified Dashboard:** Displays a high-level summary of the current month's Income, Expenses, Net Savings, and Portfolio P/L upon launch.
*   **Modular Sub-trackers:**
    *   **Investment:** Portfolio management with live market price fetching.
    *   **Expense:** Categorized spending logs with budget threshold monitoring.
    *   **Income:** Earnings tracker with categorization.
    *   **Receipt Reader:** OCR-powered automation for digitizing physical receipts.
    *   **Stock Intelligence:** Direct access to technical analysis and ML predictions.
*   **Multi-Interface Support:**
    *   **Standard CLI:** A lightweight `rich`-powered interactive menu.
    *   **TUI (Textual):** A full-terminal application with "Desktop" and "Mobile-layout" modes.

---

### **3. CLI Interface**

#### **Command Structure (`main.py`)**
The standard interface uses a numbered menu system:
*   `1`: **INVEST** — Launch Investment Tracker.
*   `2`: **EXPENSE** — Launch Expense Tracker.
*   `3`: **INCOME** — Launch Income Tracker.
*   `4`: **SCAN** — Launch Receipt OCR module.
*   `5`: **STOCKS** — Open Technical Analyzer.
*   `6`: **ML_STX** — Run Machine Learning Prediction Engine.
*   `0`: **EXIT** — Terminate session.

#### **TUI Commands (`tui.py`)**
A modern terminal UI built with the Textual framework:
*   **Launch:** `python tui.py` (Desktop mode) or `python tui.py --mobile` (Vertical layout).
*   **Key Bindings:**
    *   `q`: Quit application.
    *   `r`: Refresh dashboard data.
    *   `Enter`: Select and launch the highlighted module.

---

### **4. Internal Architecture**

The CLI follows a **Modular Orchestrator** pattern:

*   **Orchestrator (`main.py`):** Dynamically loads sub-modules using `importlib`. It manages `sys.path` injection and module cleanup to prevent namespace collisions between independent trackers.
*   **Domain-Driven Sub-modules:** Each tracker (e.g., `expense_tracker`) is architected with clear separation:
    *   `core/`: Contains pure business logic and models.
    *   `data/`: Domain-specific SQLite databases.
    *   `services/`: External integrations (e.g., Budget calculation).
    *   `ui/cli_view.py`: Responsibility for rendering tables and capturing user input.
*   **Shared Constants:** Integrates with root-level scripts (`stock_analyzer`, `stock_machine_learning`) via relative path resolution.

---

### **5. Module Deep-Dive**

This section provides a technical breakdown of the individual modules within the `finance-tracker-cli` service.

#### **A. Investment Tracker (`/investment_tracker`)**
*   **Responsibility:** Manages the lifecycle of financial assets (Stocks, Crypto, Gold). It handles acquisition, valuation via live price feeds, and realized P/L calculation upon sale.
*   **Key Components:**
    *   `PortfolioApp` (Main Orchestrator): Handles routing for add/view/sell/analyze actions.
    *   `ProfitCalculator`: Computes unrealized gains using weighted average cost.
    *   `PriceServiceFactory`: Injects the correct service (`yfinance`, `CoinGecko`, or `LogamMulia`) based on asset type.
    *   `SellService`: Manages partial and full exits, updating `remaining_quantity` and calculating tax/fees.
*   **Interactions:** Hits financial APIs for live prices and writes to `portfolio.db`.

#### **B. Expense Tracker (`/expense_tracker`)**
*   **Responsibility:** Precision tracking of outflows. It provides categorized logging and monitors budget compliance.
*   **Key Components:**
    *   `SQLiteExpenseRepository`: Handles persistence for the `expenses` table in `expense.db`.
    *   `BudgetService`: Compares current spending against user-defined monthly limits.
    *   `ExpenseCLIView`: Renders ASCII tables of transaction history.
*   **Interactions:** Consumed by the **Behavioral Finance** module to analyze spending habits.

#### **C. Income Tracker (`/income_tracker`)**
*   **Responsibility:** Manages inflows and tax estimation.
*   **Key Components:**
    *   `IncomeCalculator`: Aggregates annual earnings and provides a progressive tax bracket estimate.
    *   `SQLiteIncomeRepository`: Manages the `incomes` table in `income.db`.
*   **Interactions:** Feeds data to the **Dashboard** for Net Cash Flow calculation.

#### **D. Receipt Reader (`/receipt_reader`)**
*   **Responsibility:** Automates transaction entry via Optical Character Recognition (OCR).
*   **Key Components:**
    *   `OCREnsemble`: A voting-based engine that runs Tesseract, EasyOCR, and PaddleOCR simultaneously to pick the most accurate text.
    *   `ReceiptParser`: Regex-based heuristics for parsing specific receipt formats (BCA, QRIS, Indomaret, etc.).
    *   `UniversalCategorizer`: Uses keyword matching and merchant memory to auto-assign categories.
*   **Interactions:** Exports parsed `ReceiptData` directly into `expense_tracker` or `income_tracker` repositories.

#### **E. Behavioral Finance (`/behavioral_finance`)**
*   **Responsibility:** Analyzes the psychological patterns of the user's finances.
*   **Key Components:**
    *   `AnalyseFBSUseCase`: Calculates the **Financial Behaviour Score** (0-100) based on saving rate, consistency, and impulse control.
    *   `compute_fragility`: Measures stability by comparing emergency funds against burn rate.
    *   `ListImpulseTransactionsUseCase`: Identifies "high-risk" spending (e.g., late-night, weekend, or non-essential categories).
*   **Interactions:** Performs cross-database joins between `expense.db` and `income.db`.

#### **F. Advanced Features (`/advanced_features`)**
*   **Responsibility:** Strategic planning and forecasting.
*   **Key Components:**
    *   `GoalUseCases`: Tracks progress towards specific savings targets (e.g., "Emergency Fund," "Vacation").
    *   `CashflowForecastUseCase`: Uses a 7-day Simple Moving Average (SMA) to project the next 30 days of liquidity.
    *   `BudgetPlannerUseCase`: Interactive tool for setting and reviewing category-specific spending limits.
*   **Interactions:** Reads historical patterns to generate predictive forecasts.

---

### **6. Data Flow**

1.  **Dashboard Fetch:** On boot, `main.py` performs aggregate read-only queries across `expense.db`, `income.db`, and `portfolio.db`.
2.  **Module Execution:** When a user selects a module, the orchestrator suspends itself and passes control to the sub-module's `main()` function.
3.  **Persistence:** Sub-modules write directly to their respective SQLite databases.
4.  **Handoff:** Upon exiting a sub-module, the main dashboard re-queries the databases to reflect the updated state.

---

### **7. Dependencies**

The CLI relies on a curated set of libraries for UI and data processing:
*   **`rich`**: For monochrome-themed tables, rules, and styled text.
*   **`textual`**: Powers the advanced TUI components and layout engine.
*   **`yfinance`**: Fetches real-time asset prices for the Investment module.
*   **`pytesseract` / `Pillow`**: Core engine for Receipt OCR.
*   **`numpy`**: Supports computational logic in behavioral finance analysis.
*   **`sqlite3`**: Built-in Python library for all persistence needs.

---
**Service Documentation End.**

---
07-05-2026 (22:35)

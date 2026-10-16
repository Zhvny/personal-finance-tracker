# 🏗️ Finance Tracker: MASTER ARCHITECTURE BLUEPRINT (v10.0)

This document is the authoritative technical source of truth for the Finance Tracker ecosystem, detailing the system design, domain logic, data persistence layer, and infrastructure specifications.

---

## 🏛️ 1. Architectural Philosophy
The Finance Tracker ecosystem is built on **Clean Architecture** principles, prioritizing **Local-First Data Sovereignty** and **Modular Decomposition**.

- **Single Source of Truth (SSOT)**: `apps/cli/` is the authoritative container for all core business logic, domain models, and primary persistence.
- **Distributed Persistence**: Each domain module maintains specialized databases to ensure isolation and performance.
- **Interface Segregation**: CLI (TUI) and GUI (Web/Mobile) operate as independent interfaces consuming shared services via the **Universal API Bridge**.
- **Persistence Agnostic**: Supports both PostgreSQL (Primary for Cloud-Sync) and SQLite (Local-First Edge) via the **Repository Pattern**.

---

## 🚀 2. System Tiers & Service Roles

### 🖥️ 2.1 Core Engine (CLI)
- **Framework**: Python 3.12+ / Textual TUI (Rich).
- **Responsibility**: High-velocity data entry, primary record management, and automated background tasks.
- **Modules**: Expense Tracker, Income Tracker, Investment Tracker, and Behavioral Finance (FBS).

### 🌐 2.2 Visual Dashboard (GUI & API Gateway)
- **Tech Stack**: React 18 + Vite (Frontend), FastAPI (Backend).
- **Responsibility**: Visual analytics, real-time market monitoring, AI-driven insights, and gamified rewards.
- **API Gateway**: The central orchestrator and data gatekeeper on Port 8444 (HTTPS).
- **Consolidated Modular Frontend**: Page-level components are strictly consolidated in `finance-tracker-gui/src/pages/` for high cohesion, using standardized relative imports to shared services in `../finance/`.

### 🎯 2.3 Stock Intelligence & ML Suite
- **Role**: The analytical "brain" of the system.
- **Analyzer**: Scrapes and processes technical data (Support/Resistance, RSI).
- **Indicator Engine**: Employs a "Flatten-before-Process" strategy to normalize complex `yfinance` MultiIndex DataFrames into a uniform single-index format, ensuring robust quant metric calculation (DCDS, MRZG).
- **ML Engine**: Runs inference on "Sniper" models (XGBRegressor) to predict price movement confidence.
- **Genetic Optimizer**: Automatically evolves "Sniper" models monthly. Runs 50 iterations of hyperparameter tuning per ticker, saving the most accurate (lowest MAE) models to `models/prod/` and logging all results to `genetic_audit.db` for performance verification.

---

## 🏛️ 3. Design Philosophy & Mitigations
The system is designed to resolve critical "Pain Points" identified in legacy iterations.

### 3.1 Security & Data Isolation
- **Multi-Profile Isolation**: Each profile maintains its own physical directory and database set. Cross-profile data leakage is prevented via strict directory mapping.
- **Goal System Separation**: `goals.db` and the reward economy are profile-specific. To prevent leakage in shared database scenarios, **Row-Level Security (Profile-IDs)** is enforced at the repository layer.
- **Audit Trails**: Every transaction change is recorded in `audit_log.db` with status tracking to prevent "Lot Washing" in FIFO logic.

### 3.2 AI & Resource Efficiency
- **Lazy Loading**: The Local LLM engine (Ollama) is initialized only on-demand and auto-offloaded after 10 minutes of inactivity to preserve system resources.
- **Contextual Learning**: The OCR "Brain" (`merchant_map.db`) is profile-aware. Merchants are categorized differently based on the active domain (Personal vs. Business).

### 3.3 Accuracy & Verification
- **Uncertainty Flags**: OCR results that lack a majority consensus from the ensemble (Tesseract, EasyOCR, PaddleOCR) are flagged for mandatory manual verification.
- **Confidence Scoring**: Heuristics are replaced with confidence-based models. 100% accuracy claims are rejected in favor of "High-Confidence Suggestions."

---

## 🧱 4. Domain Logic & Core Engines

### 📈 4.1 Investment Tracker (FIFO Engine)
- **Asset Support**: Stocks (yfinance), Crypto (CoinGecko), and Gold (LogamMulia Scraping).
- **FIFO Logic**: Automatic P/L calculation using First-In-First-Out; tracks status lifecycle: `holding` → `partial_sold` → `sold`.
- **Dynamic FX Factory**: Real-time USD/IDR conversion using a tiered resolution strategy. `PostgresFXRepository` resolves `fx_rates` dynamically from the active profile schema (Personal/Business) or falls back to the global `investment.fx_rates` table to ensure data accuracy even in empty environments.

### 💳 4.2 Expense & Income Engines
- **Budgeting**: 8-category tracking with 80% threshold visual alerts.
- **Tax Engine (PPh 21)**: Automated Indonesian progressive tax brackets (5% - 35%) and PTKP logic.
- **Recurrence Detector**: Background analysis identifying subscription patterns using interval confidence scoring.

### 📷 4.3 Receipt Reader (OCR Ensemble)
- **Multi-Engine Voting**: Parallel execution of Tesseract, EasyOCR, and PaddleOCR.
- **Consensus Logic**: Field values (Total, Merchant, Date) are chosen based on majority consensus (≥2 engines).
- **Merchant Map**: Fuzzy-matching learning brain (`merchant_map.db`) for automated category assignment.

### 🏛️ 4.4 Agent Senate (Ensemble Voting)
- **Orchestrator Layer**: A regime-aware controller (`SenateService`) that aggregates votes using dynamic weighting.
- **Agent Layer**: 7 specialized personas providing independent opinions:
    - **Macro**: Correlation analysis with DXY, Gold, SPY via `ButterflyService`.
    - **Momentum**: RSI and MA-based breakout tracking.
    - **Value**: 200-day mean reversion analysis.
    - **Mean Reversion**: Bollinger Band distribution tracking.
    - **Sentiment**: LLM-based news analysis (Gemini 1.5 Flash).
    - **Risk**: ATR-based volatility cap.
    - **Quant**: Integration with XGBoost `PredictionService`.
- **Evaluation Engine**: Asynchronous background job that processes T+24h outcomes and refreshes agent performance metrics in the `audit` schema.

---

## 🔌 5. System Integration & Data Flow

### 5.1 Integration Map
- **CLI Core**: Writes to distributed databases in `apps/cli/`.
- **GUI Backend**: Reads CLI databases and writes to its own GUI-specific databases.
- **ML Engine**: Operates on `cache.db` and `market.db` for signals.
- **API Bridge**: The central orchestrator for all data requests.

### 5.2 Port & Communication Map
- **Port 8443**: FastAPI Bridge (HTTPS).
- **Port 3131**: Stock Analyzer Mobile Dashboard.
- **Tailscale**: Required for secure remote access via mobile.

---

## 🧠 6. Advanced Intelligence & Analytics
- **Behavioral Scoring (FBS)**: Analyzes spending patterns to generate impulse and fragility scores.
- **Lust System**: Gamified reward economy linked to financial discipline and savings milestones.
- **Ensemble ML**: Majority-voting system for OCR and Stock signal validation to ensure maximum accuracy.

---

## ☁️ 7. Cloud-Native Infrastructure & Dockerization
The ecosystem is containerized for production-grade reliability and high availability.

### 7.1 Multi-Stage Alpine Build
To ensure a minimum footprint and high security, the system uses a 3-stage Docker build:
1. **Frontend Builder (Node:18-Alpine)**: Compiles the React/Vite UI into static assets.
2. **Backend Builder (Python:3.12-Alpine)**: Installs build-time dependencies (`gcc`, `postgresql-dev`) and compiles Python packages into a portable layer.
3. **Runtime (Python:3.12-Alpine)**: A clean, minimal Alpine image containing only the essential runtime libraries (`libpq`, `tesseract-ocr`) and the pre-built assets from stages 1 and 2.
- **Image Size**: ~180MB (Well below the 300MB strict limit).

### 7.2 Unified Serving Architecture
Unlike traditional deployments that require an Nginx sidecar, the Finance Tracker utilizes **Unified Serving**:
- **Gateway**: FastAPI serves as the single entry point.
- **Static Assets**: The backend surgically mounts the compiled React `dist/` folder.
- **SPA Routing**: A catch-all route ensures that the React router handles all UI-related navigation, while API calls are routed to the logic layer.
- **Benefit**: Reduced architectural complexity, lower memory overhead, and simplified K8s manifests.

---
*Last Updated: 22-05-2026 (14:30)*

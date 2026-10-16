# **Finance Tracker Ecosystem: Service Documentation**

This document provides a detailed technical breakdown of the core services within the Finance Tracker ecosystem: the **GUI & API Bridge**, the **Stock Analyzer**, and the **Stock Machine Learning (Honest Sniper) System**.

---

## **1. Service: Finance Tracker GUI (API & Visual Hub)**

### **1.1. Purpose**
The Finance Tracker GUI serves as the central orchestration layer and visual dashboard for the entire ecosystem. It bridges the gap between the specialized Python-based trackers (CLI) and the end-user via a high-performance React web application and a FastAPI-based backend.

### **1.2. Core Features**
*   **Unified Dashboard:** Aggregates data from multiple SQLite databases (Expenses, Income, Investments) into a single financial overview.
*   **AI Insights:** Integrates with local LLMs (via Ollama) to provide behavioral analysis and financial recommendations.
*   **Gamified Rewards:** Implements the "Lust System," a state-driven engine that unlocks rewards based on financial discipline.
*   **Security & Audit:** Robust API Key validation and a mandatory Audit Log for all mutating operations.
*   **Module-Based Navigation:** Specialized interfaces for Expense Tracking, Investment Management, and Stock Analysis.

### **1.3. Internal Architecture**
The backend follows a **Router-per-Domain** architecture:
*   `api_server.py`: The application factory and central configuration point.
*   `backend/routers/`: Individual modules for `expenses`, `investments`, `behavioral`, etc.
*   `backend/security/`: Logic for JWT/API Key verification and audit middleware.
*   `src/`: React frontend organized by domain (`finance`, `behavioral`, `module`).

### **1.4. Data Flow**
1.  **Frontend Request:** The React GUI makes an authenticated request to the FastAPI server.
2.  **Authentication:** Security middleware verifies the API Key and logs the intent in `audit_log.db`.
3.  **Domain Processing:** The request is routed to the appropriate domain router (e.g., `investments.py`).
4.  **Database Bridge:** The backend interacts with the CLI's SQLite databases (`portfolio.db`, `expense.db`) using shared dependency helpers in `deps.py`.
5.  **Response:** The aggregated and normalized data is returned as JSON to the frontend.

### **1.5. UI/UX Design Principles**
*   **Aesthetic:** "Dark Stealth" theme using `DM Sans` for UI and `Space Mono` for financial precision.
*   **User Flow:** Splash Screen (`IntroScreen.jsx`) → Dashboard → Deep-dive Module.
*   **Layout Logic:** Flex-based responsive containers with a 30-principle UX audit compliance (e.g., "Immediate Feedback," "Minimal Cognitive Load").
*   **Responsiveness:** Mobile-first strategy with adaptive grids (e.g., 4-col desktop summary becoming 2x2 on mobile).

---

## **2. Service: Stock Analyzer (Algorithmic Technical Scan)**

### **1.1. Purpose**
The Stock Analyzer is an algorithmic technical analysis engine designed to identify high-probability trading setups and generate comprehensive risk-managed strategies.

### **2.2. Core Features**
*   **Composite Scoring:** Calculates a technical score (0-10) based on Trend, Momentum, Volatility, and Liquidity.
*   **Macro Regime Mapping:** Integrates FRED data (LPI, YCMO) to adjust scoring based on market conditions.
*   **CSS (Core Stock Score):** A weighted proprietary metric that combines technical strength with macro filters.
*   **Risk Management:** Automatic calculation of Kelly Criterion, Expectancy, and Position Sizing.
*   **Visualizer:** Generates Support/Resistance visual structures for strategy planning.

### **2.3. Internal Architecture (Adapter Pattern)**
*   **Adapters:** `fetcher.py` (yfinance), `fred_fetcher.py` (FRED), `indicators.py` (Pandas-based technicals).
*   **Domain:** `scoring.py` (logic for composite scores), `risk.py` (mathematical risk models).
*   **Use Cases:** `analyzer.py` (orchestrates the end-to-end analysis of a ticker).
*   **Interfaces:** `tui.py` (Terminal interface) and `web_app.py` (Streamlit-based dashboard).

### **2.4. Data Flow**
1.  **Ingestion:** `DataFetcher` pulls historical price data from yfinance.
2.  **Macro Pulse:** `FREDFetcher` retrieves global economic vectors (Yield Curve, Inflation, Liquidity).
3.  **Indicators:** `IndicatorEngine` computes EMA, RSI, ATR, and Volatility Regimes.
4.  **Scoring:** `ScoringEngine` applies weights from `config.yaml` to generate the final composite score and trade signals.
5.  **Strategy:** `RiskManager` defines the entry, stop-loss, and take-profit targets.

---

## **3. Service: Stock Machine Learning (Honest Sniper System)**

### **3.1. Purpose**
The Stock Machine Learning service is a specialized predictive system focused on **Precision over Frequency**. It employs the "Honest Sniper" methodology to filter for only the highest-confidence market signals.

### **3.2. Model Architecture & Pipeline**
*   **Model Type:** XGBoost Classifier.
*   **Labeling:** "Triple Barrier Method" — Labels are determined by hitting a profit target (+2 ATR) or stop loss (-1 ATR) within a 5-day horizon.
*   **Purged Validation:** Uses "Purged Walk-Forward Cross-Validation" to ensure zero data leakage between training and testing folds.
*   **Liar Detector:** A diagnostic tool that trains the model on shuffled labels; if the model still claims high accuracy, it is flagged for overfitting.

### **3.3. Feature Engineering**
*   **Stationary Features:** Close-to-Close returns, RSI, and ADX.
*   **Normalization:** Distance from MA (Z-score) and ATR-normalized volatility spikes.
*   **Market Context:** ALPHA (Relative return vs SPY) and Correlation metrics.

### **3.4. Selective Sniper Engine**
Instead of predicting every day, the system only issues a signal if three conditions are met:
1.  **Probability:** Prediction probability > 0.85 (Long) or < 0.15 (Short).
2.  **Institutional Pulse:** Volume Spike > 1.5 (Proxy for big money movement).
3.  **Structural Confirmation:** ADX > 25 (Ensures a strong trend is present).

### **3.5. Evaluation Metrics**
*   **Global Accuracy:** Overall model performance on out-of-sample data.
*   **Selective Precision (Target: 80%):** The accuracy of signals that pass the Sniper filters.
*   **Kelly Fraction:** Suggested bet size based on the model's historical win rate and payoff ratio.

---
**Documentation End.**

---
07-05-2026 (22:35)

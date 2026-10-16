# 📦 Finance Tracker: MASTER PRODUCT MANUAL (v10.0)

This document is the high-fidelity comprehensive guide to the features, services, and user-centric capabilities of the Finance Tracker ecosystem.

---

## 🏗️ 1. Ecosystem Overview
The Finance Tracker ecosystem is a modular, high-performance financial command center designed for **Local-First Data Sovereignty**, precision asset management, and AI-driven behavioral coaching.

### 🌟 Design Philosophy
Our architecture is built to eliminate the common "frictions" of personal finance:
- **Zero Input Fatigue**: Automated data entry via OCR and fuzzy-matching categorization.
- **Strict Privacy**: Local-first data storage with no cloud-mandatory leakage.
- **Insight-Driven**: Not just recording data, but providing "Why" via behavioral scores and AI advice.
- **Institutional Precision**: Professional-grade FIFO engines and ML-based stock forecasting.

---

## 🚀 2. Core Services & Roles

### 🖥️ 2.1 Finance Tracker CLI
*Source: `docs/services/cli.md`*
High-velocity, engineer-centric interface for rapid data entry and system management.
- **Unified Dashboard**: Real-time summary of expenses, income, and portfolio status.
- **Modular Trackers**: Specialized sub-trackers for Income, Expenses, and Investments.
- **Power Features**: Bulk OCR imports, manual database vacuuming, and direct configuration editing.

### 🌐 2.2 Finance Tracker GUI & API
*Source: `docs/services/finance-tracker-gui.md`*
The interactive visual hub of the ecosystem, providing high-fidelity analytics and gamified rewards.
- **Visual Analytics**: Real-time charts, heatmaps, and gauges for financial health.
- **Modular Pages**: Page components are logically consolidated into a unified `pages/` container for high-performance lazy loading and routing.
- **Design Language**: "Dark Stealth" aesthetics with high-fidelity portfolio visuals and smooth Framer Motion animations.
- **Gamified Progress**: Visualizes the "Lust System" and behavioral scores.

### 🎯 2.3 Stock Intelligence & ML Suite
*Source: `docs/services/stock-analyzer.md` & `stock_ml.md`*
Algorithmic technical scan engine for institutional-grade market analysis.
- **Indicator Normalization**: Employs robust MultiIndex handling to ensure reliable DCDS and MRZG analytics even with complex market data.
- **Quant Ladder V4**: Symmetrical vertical price track mirroring professional trading terminals.
- **MLEngine (Price Sniper)**: XGBRegressor-powered predictive engine.
- **Validation**: Strict "Anti-Pucuk" filters to prevent buying at overextended price peaks.

### 🏛️ 2.4 Agent Senate (Quantitative Intelligence)
*Source: `docs/services/senate.md`*
A multi-agent quantitative and qualitative decision system.
- **Ensemble Voting**: Aggregates opinions from 7 specialized agents (Momentum, Value, Macro, Sentiment, etc.).
- **Regime Awareness**: Automatically detects market conditions (Bull/Bear/Sideways) to dynamically weight agent influence.
- **Continuous Evaluation**: Background engine audits prediction accuracy every 24 hours to evolve agent weights.

---

## 🧩 3. Key Product Features

### 🏢 3.1 Multi-Profile Switcher (Business vs. Personal)
Enables strict physical isolation between financial entities within a single installation.
- **Personal Profile**: Optimized for individual budgeting, behavioral scoring (FBS), and the Lust reward system.
- **Business Profile**: Optimized for P&L Reporting, Quarterly Tax Generation, and Invoicing.

### 📸 3.2 Receipt Reader (OCR Ensemble)
- **High Accuracy**: Ensemble approach achieving 98%+ accuracy.
- **Learning Brain**: Automatically maps merchants to categories based on historical data.

### 💖 3.3 Behavioral Finance & Gamification
- **FBS Scoring**: Tracks impulsive spending and financial fragility.
- **Lust System**: Earn points for discipline and unlock "rewards" in the visual catalogue.

---

## 🛠️ 4. Interservice Interaction
1.  **Client-Server**: GUI communicates with the API Gateway using JSON over HTTPS (Port 8443).
2.  **Shared Persistence**: CLI and API share the same database layer, ensuring real-time synchronization between terminal and browser.
3.  **Local Intelligence**: ML models and OCR engines run locally to ensure data privacy.

---
*Last Updated: 19-07-2026 (22:01)*

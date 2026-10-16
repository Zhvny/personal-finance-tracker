# 💸 Feature: Expense Tracker

The **Expense Tracker** is the primary transaction ledger for the ecosystem, providing high-speed logging and budget monitoring.

---

## 🏗️ Technical Architecture
- **`services/budget_service.py`**: Monitors spending against category limits.
- **`services/recurring_service.py`**: (Planned) Engine for automated monthly bills.

---

## 🧩 Deep Dive: Budget Compliance
The system tracks 8 core categories. When a transaction is logged:
1. **Validation**: Checks against the `expense.db` to see the current month's cumulative spending for that category.
2. **Alerting**: If spending exceeds **80%** of the category budget, a "Warning" state is triggered in the UI.
3. **Behavioral Sync**: Budget adherence data is pushed to the **Behavioral Finance** module to calculate the monthly FBS.

---

## 📊 Data Mapping
- **Categories**: `food, transport, housing, entertainment, health, shopping, education, other`.
- **Payment Methods**: `cash, transfer, credit_card, debit_card, e-wallet, other`.

---
07-05-2026 (22:35)

# 🧠 Feature: Behavioral Finance (FBS)

The **Behavioral Finance** module analyzes the "Why" behind your spending. It moves beyond raw numbers to calculate a **Financial Behavior Score (0-100)** based on psychological finance theories.

---

## 🏗️ Technical Architecture

This module is the most "Theory-Heavy" part of the ecosystem:
- **`Prospect Theory`**: Implements **Loss Aversion** (losses feel ~1.8x heavier than gains).
- **`Mental Accounting`**: Weighting discretionary categories (e.g., Shopping) as higher risk than utilities.
- **`Present Bias`**: Penalizing impulsive weekend/evening spending patterns.

---

## 🧩 The Scoring Algorithm (FBS)

The **Financial Behavior Score** is a composite metric weighted as follows:

| Metric | Weight | Description |
| :--- | :--- | :--- |
| **Saving Rate** | 30% | `(Income - Expense) / Income`. |
| **Budget Adherence** | 25% | Percentage of categories that stayed under limit. |
| **Impulse Control** | 20% | Detection of "spike" transactions and weekend spending. |
| **Consistency** | 15% | Standard deviation of monthly spending variance. |
| **Emergency Buffer** | 10% | Liquidity status (Months of expenses covered). |

### Grading Scale:
- **85 - 100**: **Grade A** (Elite)
- **70 - 84**: **Grade B** (Healthy)
- **55 - 69**: **Grade C** (Fair)
- **< 40**: **Grade F** (Critical)

---

## 📊 Analytics Provided
- **Impulse Index**: Visualizes how much "lifestyle inflation" or impulsive spending is occurring.
- **Fragility Score**: Measures how quickly your finances would collapse in a crisis (based on income diversity and liquid cash).

---
07-05-2026 (22:35)

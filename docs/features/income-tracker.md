# 💰 Feature: Income Tracker (Tax Edition)

The **Income Tracker** manages all inflows (Salary, Freelance, Side Hustles) and provides a **Progressive Tax Estimation** engine tailored for the Indonesian market.

---

## 🏗️ Technical Architecture
- **`core/calculator.py`**: The logic provider for annualizing income and tax brackets.
- **`core/repository.py`**: SQLite adapter for `income.db`.

---

## 🧩 Deep Dive: PPh 21 Tax Logic

The system automatically calculates estimated annual taxes using the **Progressive Bracket System (Indonesia)**:

### 1. PTKP (Penghasilan Tidak Kena Pajak)
Defaults to **K/0 (Rp 58.500.000)**. Income below this threshold is not taxed.

### 2. Tax Brackets (Progressive)
| Taxable Income | Rate |
| :--- | :--- |
| First Rp 60.000.000 | 5% |
| Rp 60.000.000 - Rp 250.000.000 | 15% |
| Rp 250.000.000 - Rp 500.000.000 | 25% |
| Rp 500.000.000 - Rp 5.000.000.000 | 30% |
| Above Rp 5.000.000.000 | 35% |

---

## 📊 Features
- **Annualization**: Projects your current monthly income to estimate the year-end tax liability.
- **Categorization**: Segregates Active (Salary) vs. Passive (Investment) income.
- **Net Calculation**: Automatically subtracts estimated tax to show your "True" Take Home Pay.

---
07-05-2026 (22:35)

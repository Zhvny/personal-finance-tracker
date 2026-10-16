# 🛠️ Maintenance & Disaster Recovery Guide (Operations Hub)

This document is the operational command center for system maintenance, architectural audits, and disaster recovery protocols within the Finance Tracker ecosystem.

---

## 📅 System Overview
- **Project**: Finance Tracker
- **Primary Environment**: Windows / Python 3.12 / PostgreSQL (Primary) / SQLite (Edge Fallback)
- **Latest Audit Status**: ✅ **CLEAN (v11.2.0)**
- **Integrity Level**: Production-Ready / High-Fidelity

---

## 📑 Table of Contents
1. [Data Inventory (Where is my data?)](#-data-inventory-where-is-my-data)
2. [Backup Strategy](#-backup-strategy)
3. [Optimization & Health Checks](#-optimization--health-checks)
4. [Disaster Recovery Scenarios](#-disaster-recovery-scenarios)
5. [Machine Migration](#-machine-migration)
6. [System Debugging Audit Summary](#-system-debugging-audit-summary)
7. [Specialized Documentation Links](#-specialized-documentation-links)

---

## 📂 Data Inventory (Where is my data?)

The system utilizes a dual-persistence strategy. Primary data resides in **PostgreSQL** for multi-agent concurrency, while **SQLite** remains for local-first edge scenarios.

### 1. PostgreSQL Schemas (Primary)
| Schema | Primary Purpose | Table Examples |
| :--- | :--- | :--- |
| `personal` | Personal profile transactions. | `expenses`, `incomes`, `investments`, `fx_rates` |
| `business` | Business profile transactions. | `expenses`, `incomes`, `investments`, `fx_rates` |
| `investment`| Global investment fallbacks. | `fx_rates` (Global default) |
| `market` | Global market data cache. | `ohlcv_cache`, `latest_prices` |
| `audit` | Prediction and outcome logs. | `senate_votes`, `evaluation_logs` |
| `system` | Operational metadata. | `audit_log`, `usage_stats` |

### 2. SQLite Databases (Edge/Legacy)
The following SQLite databases are synchronized from Postgres for offline access.

| Database | Primary Purpose | Primary Location |
| :--- | :--- | :--- |
| `expense.db` | All categorized spending transactions. | `apps/cli/profiles/{active}/data/` |
| `income.db` | Earnings and tax estimation records. | `apps/cli/profiles/{active}/data/` |
| `portfolio.db` | Stocks, Crypto, Gold, and Sell history. | `apps/cli/profiles/{active}/data/` |
| `goals.db` | Gamification (Lust Points) and milestones. | `apps/cli/profiles/{active}/data/` |
| `merchant_map.db`| OCR learning data (Merchant ↔ Category). | `apps/cli/profiles/{active}/data/` |
| `audit_log.db` | Security logs and API request history. | `finance-tracker-gui/data/` |

---

## 💾 Backup Strategy

### **1. Manual Backup (The "Golden Rule")**
Before performing any major updates or refactoring, copy the entire project directory or at least the `apps/cli/profiles` folder to an external drive.
```bash
# Example for Windows PowerShell
Copy-Item -Path ".\apps\cli\profiles" -Destination "D:\Backups\FinanceTracker\backup-$(Get-Date -Format 'yyyyMMdd')" -Recurse
```

### **2. Automated Rotation**
It is recommended to use a tool like **Google Drive for Desktop** or **OneDrive** to sync the project folder in real-time for off-site redundancy.

---

## 🧹 Optimization & Health Checks

### **1. Vacuuming (Database Compaction)**
If you notice the GUI slowing down or the file sizes becoming unusually large, run the `VACUUM` command to defragment the databases:
```python
# Quick snippet to run via Python CLI
import sqlite3
import os

profile = "Personal" # or "Business"
db_path = f"./apps/cli/profiles/{profile}/data/"
for db in ['expense.db', 'portfolio.db', 'income.db']:
    conn = sqlite3.connect(os.path.join(db_path, db))
    conn.execute("VACUUM")
    conn.close()
```

### **2. Log Rotation**
The `audit_log.db` can grow rapidly. It is safe to clear logs older than 90 days:
```sql
DELETE FROM request_logs WHERE ts < date('now', '-90 days');
```

---

## 🚑 Disaster Recovery Scenarios

- **Database Locked**: Ensure all `python.exe` or `node.exe` processes related to the project are closed via Task Manager.
- **Corruption**: Use the SQLite `.recover` command. If failure persists, restore from the latest backup archive.
- **Dependency Issues**: Re-run `./setup.bat` and verify the Python environment.

---

## 🔄 Machine Migration

1. Install Python 3.12+ on the target machine.
2. Transfer the full project directory.
3. Run `./setup.bat` to initialize the environment and dependencies.
4. Verify that the `apps/cli/profiles/` directory contains your data.
5. Launch `./run-gui.bat` or `./run-cli.bat` and verify balances.

---

## 🔍 System Debugging Audit Summary

- **Concurrency**: Validated WAL (Write-Ahead Logging) mode in SQLite for multi-process stability.
- **Performance**: Added SQL indexes on `date` and `category` columns to resolve high-volume latency.
- **Security**: Verified SSL/TLS enforcement on port 8443 and parameterized all dynamic SQL queries.
- **ML Sync Fix**: Re-aligned `CSV_ML_PATH` to fix "No Data" issues in the GUI.

---

## 📂 Specialized Documentation Links

For more detailed technical records, refer to the following files:

- **[Change Log](./change-log.md)**: Comprehensive history of all releases and historical audits.
- **[Debug Reports](./debug-report.md)**: Technical post-mortems and infrastructure audit details.
- **[Task Archive](./task-archive.md)**: Completion logs for developer tickets and technical fixes.

---
*Last Updated: 07-05-2026 (23:45)*

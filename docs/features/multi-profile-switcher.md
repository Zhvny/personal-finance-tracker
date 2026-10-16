# 🏢 Technical Specification: Multi-Profile Switcher

The **Multi-Profile Switcher** enables the application to support multiple isolated data environments (Tenants) within a single installation. This allows for strict separation between **Personal Finances** and **Business Operations**.

---

## 🏗️ Core Concept: "Isolated Data Tiers"

Instead of a single global `data/` folder, the system will treat each profile as a self-contained directory.

### **Folder Structure**
```text
data/
├── profiles.json           <-- Master Registry
├── personal_default/       <-- Profile UUID/Name
│   ├── expense.db
│   ├── income.db
│   └── portfolio.db
└── business_unit_abc/      <-- Business A
    ├── expense.db
    ├── income.db
    └── portfolio.db
```

---

## 🧩 Technical Components

### **1. Profile Registry (`profiles.json`)**
A JSON configuration file at the root of the `data/` directory to manage metadata.
```json
{
  "active_profile": "personal_default",
  "profiles": [
    {
      "id": "personal_default",
      "name": "Personal Finance",
      "type": "PERSONAL",
      "created_at": "2026-01-01"
    },
    {
      "id": "business_unit_abc",
      "name": "Creative Studio",
      "type": "BUSINESS",
      "currency": "IDR",
      "tax_mode": "UMKM_FINAL"
    }
  ]
}
```

### **2. Profile Manager (The Orchestrator)**
A new module `apps/cli/core/profile_manager.py` responsible for:
- Reading/Writing the `profiles.json`.
- Validating folder existence.
- Creating new profile skeletons (copying empty `.db` templates).

### **3. Dependency Injection Pattern**
Repositories must be refactored to stop using hardcoded paths. They should accept a `base_path` or `profile_id`.

**Old Way (Hardcoded):**
```python
db_path = "./data/expense.db"
```

**New Way (Injected):**
```python
class SQLiteExpenseRepository:
    def __init__(self, profile_data_path: str):
        self.db_path = os.path.join(profile_data_path, "expense.db")
```

---

## 🔄 Logic Flow

### **Initialization (Bootup)**
1. **Load Config**: `main.py` calls `ProfileManager.load()`.
2. **User Selection**:
   - If `active_profile` exists, use it.
   - Or, show a TUI/CLI menu: *"Select Profile: [1] Personal [2] Creative Studio [3] Create New"*.
3. **Set Environment**: The selected `profile_path` is passed as a "Global Context" to all sub-modules (Investment, Expense, etc.).

### **Profile-Specific Logic (Business vs. Personal)**
- **Personal Profile**: Enables **FBS Scoring** and **Lust System**.
- **Business Profile**: Enables **P&L Reporting**, **Invoicing**, and **UMKM Tax Mode**.

---

## 🚀 Implementation Steps

### **Phase 1: Foundation (Current Sprint)**
- [ ] Create `profiles.json` and `ProfileManager` class.
- [ ] Refactor `main.py` (CLI) and `FastAPI` (GUI) to handle profile selection at boot.
- [ ] Update all Repository constructors to accept dynamic paths.

### **Phase 2: Management UI**
- [ ] Add "Create New Profile" menu in CLI.
- [ ] Add "Switch Profile" hotkey (`Ctrl+S`) in TUI/GUI.

### **Phase 3: Business Modules**
- [ ] Implement `tax_mode` logic in `IncomeCalculator` based on profile type.
- [ ] Add "Balance Sheet" view for Business profiles.

---

## ⚠️ Safety & Migration
- **Auto-Migration**: Upon first launch of the new version, the existing `data/*.db` files should be automatically moved to a new `data/personal_default/` folder to prevent data loss.
- **Backup Isolation**: The `backup.py` script must be updated to backup profiles individually or as a complete bundle.

---
07-05-2026 (22:35)

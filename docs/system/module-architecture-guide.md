# 🏛️ Module Architecture Style Guide

> **Status**: CANONICAL — This document is the authoritative standard for all `apps/cli/` module architecture going forward.
> All new modules MUST follow Pattern A. Existing modules are tracked for migration below.

---

## 🔍 Problem: Three Patterns in One Repo

A code quality audit (19-07-2026) identified three divergent directory structures within `apps/cli/`. While all three loosely follow Clean Architecture, the different layer naming creates unnecessary cognitive overhead for developers and AI assistants.

| Module | Current Pattern | Layers Used |
|---|---|---|
| `expense_tracker`, `income_tracker`, `investment_tracker`, `receipt_reader` | Pattern A — `core/services/ui` | `core/`, `services/`, `ui/` |
| `advanced_features`, `behavioral_finance` | Pattern B — `domain/application/interface` | `domain/`, `application/`, `interface/` |
| `stock_analyzer`, `stock_ml` | Pattern C — `domain/infrastructure/use_cases` | `domain/`, `infrastructure/`, `use_cases/` |

---

## ✅ Pattern A — The Designated Standard

**All new modules MUST use Pattern A.** It is already used by the majority of modules and aligns with the existing `packages/core/` package.

```
apps/cli/<module_name>/
├── core/               # Domain: pure business logic, models, interfaces
│   ├── interfaces.py   # Abstract contracts (IRepository, IService, etc.)
│   ├── models.py       # Domain models (if not in packages/core/domain/)
│   └── ...
├── services/           # Application: use cases, orchestrators, domain services
│   └── <feature>_service.py
├── ui/                 # Interface: CLI views, TUI components, Rich rendering
│   └── cli_view.py
└── main.py             # Entry point / controller; wires dependencies together
```

### Mapping to Clean Architecture
| Pattern A Folder | Clean Architecture Layer | Responsibility |
|---|---|---|
| `core/` | **Domain** | Business rules, entities, interfaces — zero external deps |
| `services/` | **Application** | Use cases, orchestrators — depends only on `core/` interfaces |
| `ui/` | **Interface/Presentation** | Rendering, input — depends on `services/`, never on `core/` DB |
| `main.py` | **Composition Root** | Wires all layers; the only place that knows all concrete types |

---

## 📋 Layer Rules (Enforced)

1. **Domain (`core/`) is import-free**: No imports from `services/`, `ui/`, or any infrastructure. Only stdlib and `packages/core/domain/`.
2. **Services depend on interfaces, not implementations**: Use the abstract contracts in `core/interfaces.py` — never import the SQLite/Postgres repository directly.
3. **UI layer never touches DB**: `ui/cli_view.py` calls service methods only. It does not call `_db()`, `sqlite3`, or `DatabaseManager`.
4. **`main.py` is the composition root**: This is the only file allowed to instantiate concrete implementations (e.g., `SQLiteExpenseRepository`) and inject them into services.
5. **No `print()` in `services/` or `core/`**: Use `packages.core.infrastructure.logging.get_logger()`. `ui/` may use Rich/print for terminal rendering.

---

## 🗺️ Migration Tracker

| Module | Current Pattern | Target | Status |
|---|---|---|---|
| `expense_tracker` | A | A | ✅ Compliant |
| `income_tracker` | A | A | ✅ Compliant |
| `investment_tracker` | A | A | ✅ Compliant |
| `receipt_reader` | A | A | ✅ Compliant |
| `advanced_features` | B | A | 🟡 Pending migration |
| `behavioral_finance` | B | A | 🟡 Pending migration |
| `stock_analyzer` | C | A | 🟡 Pending migration |
| `stock_ml` | C | C (standalone runner) | ⚪ Exempt — not a CLI module |

> **Migration strategy for Pattern B → A**: Rename `domain/` → `core/`, `application/` → `services/`, `interface/` → `ui/`. No logic changes needed; it is a pure rename. Update imports in `main.py` of the module.

---

## 📁 Reference Implementation

See `apps/cli/expense_tracker/` as the canonical reference implementation of Pattern A.

Key files to study:
- `core/interfaces.py` — abstract contracts
- `services/` — use case orchestration
- `ui/cli_view.py` — pure rendering
- `main.py` — composition root

---

*Last Updated: 19-07-2026 (22:06)*

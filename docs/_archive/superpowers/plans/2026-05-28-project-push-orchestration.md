Last Updated: 29-05-2026 (14:30)

# Deployment Orchestration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Securely prepare and push the finance-tracker repository to origin/main with proper ignore rules and staged commits.

**Architecture:** Systematic staging of untracked files following a strict dependency and logical grouping order to ensure a clean commit history.

**Tech Stack:** Git, Shell.

---

### Task 1: Security & Cleanup - .gitignore Update

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Update .gitignore with project-specific sensitive files**
Update `.gitignore` to include `data/`, `logs/`, `debug/`, `tests/logs/`, `tests/ocr_iamge_input_test/`, `active_profile.txt`, and other transient files.

```text
# ... (existing content) ...

# Finance Tracker Specific
data/
logs/
debug/
apps/cli/profiles/
apps/cli/advanced_features/data/*.db
apps/cli/behavioral_finance/data/*.db
apps/cli/expense_tracker/data/*.db
apps/cli/investment_tracker/data/*.db
apps/cli/investment_tracker/data/cache/
packages/api/data/
packages/api/cache.db
packages/api/certs/
results_honest/
market_sync_backoff.json
active_profile.txt
.setup_done
.ai/
conductor/
```

- [X] **Step 2: Commit .gitignore changes**
```bash
git add .gitignore
git commit -m "chore: update gitignore with project-specific rules"
```

### Task 2-52: Staged Commits (51 Stages)

*Note: Since the user requested exactly 52 stages (Task 1 + 51 others), we will decompose the untracked files into logical batches.*

- [X] **Task 2: Commit Root Configuration (package.json, pnpm-workspace.yaml, turbo.json)**
```bash
git add package.json pnpm-workspace.yaml pnpm-lock.yaml turbo.json package-lock.json profiles.json
git commit -m "chore: add root configuration and workspace files"
```

- [X] **Task 3: Commit Root Documentation (DESIGN.md, GEMINI.md, README.md)**
```bash
git add DESIGN.md GEMINI.md README.md
git commit -m "docs: add root design and standards documentation"
```

- [X] **Task 4: Commit Infrastructure (Dockerfile, k8s-deployment.yaml, k8s-ingress.yaml)**
```bash
git add Dockerfile k8s-deployment.yaml k8s-ingress.yaml
git commit -m "infra: add docker and k8s configuration"
```

- [X] **Task 5: Commit Entry Scripts (run-cli.bat, run-gui.bat, setup.bat)**
```bash
git add run-cli.bat run-gui.bat setup.bat
git commit -m "chore: add bootstrap and execution scripts"
```

- [X] **Task 6: Commit Core Package - Initial Structure**
```bash
git add packages/core/__init__.py packages/core/README.md
git commit -m "feat(core): initialize core package"
```

- [X] **Task 7: Commit Core Package - Domain Models**
```bash
git add packages/core/domain/models/
git commit -m "feat(core): add domain models for finance entities"
```

- [X] **Task 8: Commit Core Package - Repository Interfaces**
```bash
git add packages/core/domain/repositories/
git commit -m "feat(core): add repository interfaces"
```

- [X] **Task 9: Commit Core Package - Infrastructure (Cache & Config)**
```bash
git add packages/core/infrastructure/cache/ packages/core/infrastructure/config.py
git commit -m "feat(core): add infrastructure cache and config"
```

- [X] **Task 10: Commit Core Package - Persistence (Postgres Manager)**
```bash
git add packages/core/infrastructure/persistence/postgres_manager.py
git commit -m "feat(core): add postgres database manager"
```

- [X] **Task 11: Commit Core Package - Expense Tracker Infrastructure**
```bash
git add packages/core/infrastructure/expense_tracker/
git commit -m "feat(core): add expense tracker infrastructure implementation"
```

- [X] **Task 12: Commit Core Package - Income Tracker Infrastructure**
```bash
git add packages/core/infrastructure/income_tracker/
git commit -m "feat(core): add income tracker infrastructure implementation"
```

- [X] **Task 13: Commit Core Package - Investment Tracker Infrastructure**
```bash
git add packages/core/infrastructure/investment_tracker/
git commit -m "feat(core): add investment tracker infrastructure implementation"
```

- [X] **Task 14: Commit Core Package - External Services (YFinance, FX)**
```bash
git add packages/core/infrastructure/external/
git commit -m "feat(core): add external service adapters for market data"
```

- [X] **Task 15: Commit Core Package - Application Services (Expense & Income)**
```bash
git add packages/core/application/expense_service.py packages/core/application/income_service.py
git commit -m "feat(core): add expense and income application services"
```

- [X] **Task 16: Commit Core Package - Application Services (Investment & Market)**
```bash
git add packages/core/application/investment_service.py packages/core/application/market_data_service.py
git commit -m "feat(core): add investment and market data application services"
```

- [X] **Task 17: Commit Core Package - Receipt Reader Logic**
```bash
git add packages/core/infrastructure/receipt_reader/
git commit -m "feat(core): add receipt reader infrastructure and ocr ensemble"
```

- [ ] **Task 18: Commit Core Package - Utilities**
```bash
git add packages/core/utils/
git commit -m "feat(core): add project utilities and guards"
```

- [ ] **Task 19: Commit API Package - Initial Structure**
```bash
git add packages/api/README.md packages/api/package.json packages/api/requirements.txt
git commit -m "feat(api): initialize api package"
```

- [ ] **Task 20: Commit API Package - Server Entry**
```bash
git add packages/api/api_server.py
git commit -m "feat(api): add fastapi server entry point"
```

- [ ] **Task 21: Commit API Package - AI Strategy**
```bash
git add packages/api/backend/ai/
git commit -m "feat(api): add ai rule engine and provider strategies"
```

- [ ] **Task 22: Commit API Package - Infrastructure Layer**
```bash
git add packages/api/backend/infrastructure/
git commit -m "feat(api): add database and repository infrastructure"
```

- [X] **Task 23: Commit API Package - Routers (Accounts & Auth)**
```bash
git add packages/api/backend/routers/accounts.py packages/api/backend/routers/profiles.py
git commit -m "feat(api): add account and profile routers"
```

- [X] **Task 24: Commit API Package - Routers (Finance Flows)**
```bash
git add packages/api/backend/routers/expenses.py packages/api/backend/routers/income.py packages/api/backend/routers/investments.py
git commit -m "feat(api): add routers for core financial flows"
```

- [X] **Task 25: Commit API Package - Routers (Analytics & AI)**
```bash
git add packages/api/backend/routers/analytics.py packages/api/backend/routers/ai.py packages/api/backend/routers/behavioral.py
git commit -m "feat(api): add analytics and ai-driven routers"
```

- [ ] **Task 26: Commit API Package - Services**
```bash
git add packages/api/backend/services/
git commit -m "feat(api): add backend service layer"
```

- [X] **Task 27: Commit Web Package - Initial Scaffold**
```bash
git add packages/web/package.json packages/web/vite.config.js packages/web/index.html
git commit -m "feat(web): initialize react frontend with vite"
```

- [X] **Task 28: Commit Web Package - Assets & Icons**
```bash
git add packages/web/public/
git commit -m "feat(web): add public assets and branding icons"
```

- [X] **Task 29: Commit Web Package - Styles & Themes**
```bash
git add packages/web/src/styles/
git commit -m "feat(web): add css modules and theme tokens"
```

- [X] **Task 30: Commit Web Package - Core Components**
```bash
git add packages/web/src/components.jsx packages/web/src/App.jsx packages/web/src/main.jsx
git commit -m "feat(web): add shared components and app shell"
```

- [X] **Task 31: Commit Web Package - Finance Components**
```bash
git add packages/web/src/finance/
git commit -m "feat(web): add finance-specific charts and panels"
```

- [X] **Task 32: Commit Web Package - Behavioral Finance Views**
```bash
git add packages/web/src/behavioral/
git commit -m "feat(web): add behavioral finance dashboard components"
```

- [X] **Task 33: Commit Web Package - Reward System (LustShop)**
```bash
git add packages/web/src/rewards/
git commit -m "feat(web): add reward system frontend logic"
```

- [X] **Task 34: Commit Web Package - Pages (Core Financial)**
```bash
git add packages/web/src/pages/dashboard.jsx packages/web/src/pages/expense_tracker.jsx packages/web/src/pages/income_tracker.jsx packages/web/src/pages/investment_tracker.jsx
git commit -m "feat(web): add core financial tracker pages"
```

- [X] **Task 35: Commit Web Package - Pages (Advanced)**
```bash
git add packages/web/src/pages/advanced.jsx packages/web/src/pages/stock_analyzer.jsx packages/web/src/pages/stock_ml.jsx
git commit -m "feat(web): add advanced analytics and ml pages"
```

- [X] **Task 36: Commit CLI App - Entry Point**
```bash
git add apps/cli/main.py apps/cli/scheduler.py
git commit -m "feat(cli): add main entry and automation scheduler"
```

- [X] **Task 37: Commit CLI App - Expense Tracker Module**
```bash
git add apps/cli/expense_tracker/
git commit -m "feat(cli): add expense tracker cli module"
```

- [X] **Task 38: Commit CLI App - Income Tracker Module**
```bash
git add apps/cli/income_tracker/
git commit -m "feat(cli): add income tracker cli module"
```

- [X] **Task 39: Commit CLI App - Investment Tracker Module**
```bash
git add apps/cli/investment_tracker/
git commit -m "feat(cli): add investment tracker cli module"
```

- [X] **Task 40: Commit CLI App - Behavioral Finance Module**
```bash
git add apps/cli/behavioral_finance/
git commit -m "feat(cli): add behavioral finance cli module"
```

- [X] **Task 41: Commit CLI App - Advanced Features Module**
```bash
git add apps/cli/advanced_features/
git commit -m "feat(cli): add advanced features cli module"
```

- [X] **Task 42: Commit CLI App - Receipt Reader Module**
```bash
git add apps/cli/receipt_reader/
git commit -m "feat(cli): add receipt reader cli module"
```

- [X] **Task 43: Commit CLI App - Stock ML Scripts**
```bash
git add apps/cli/stock-ml/
git commit -m "feat(cli): add stock ml research scripts"
```

- [X] **Task 44: Commit System Scripts - Audit & DB**
```bash
git add scripts/audit_database_schemas.py scripts/check_all_dbs.py scripts/inspect_db_schemas.py
git commit -m "chore: add database audit and schema inspection scripts"
```

- [X] **Task 45: Commit System Scripts - Performance & Benchmarks**
```bash
git add scripts/benchmark_latency.py scripts/stress_test_optimizer.py
git commit -m "chore: add performance benchmarking and stress tests"
```

- [X] **Task 46: Commit System Scripts - Migration & Setup**
```bash
git add scripts/setup_postgres.py tools/migrate_to_postgres.py
git commit -m "chore: add postgres setup and migration tools"
```

- [X] **Task 47: Commit Tests - Unit Tests**
```bash
git add tests/unit/
git commit -m "test: add unit tests for domain logic"
```

- [X] **Task 48: Commit Tests - Integration Tests**
```bash
git add tests/integration/
git commit -m "test: add integration tests for financial workflows"
```

- [X] **Task 49: Commit Tests - Automation (QA)**
```bash
git add tests/automation/
git commit -m "test: add automated qa probes and drivers"
```

- [X] **Task 50: Commit Documentation - Authority Hubs**
```bash
git add docs/system/ docs/planning/ docs/maintenance/
git commit -m "docs: add authoritative system and maintenance documentation"
```

- [X] **Task 51: Commit Documentation - Features & Guides**
```bash
git add docs/features/ docs/services/
git commit -m "docs: add feature-specific documentation"
```

- [X] **Task 52: Final Push to Origin**
```bash
git push origin main
```

---

Plan complete and saved to `docs/superpowers/plans/2026-05-28-project-push-orchestration.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?

Last Updated: 29-05-2026 (14:30)

# 🎫 Development Tickets Archive

Historical record of developer tasks and task-specific specifications.

---

## 🛡️ [DEV_A] Enterprise Security & Core Engine
**Assignee:** Developer A
**Priority:** High
**Status:** ✅ COMPLETED & VERIFIED

### 🛠️ Assigned Tasks

#### Task A.1: Auth Integration (TOTP)
- **Objective**: Implement secure user enrollment and 2FA authentication.
- **Action**:
    - Created `AuthManager.enroll_user` to generate and store TOTP secrets in `system.users`.
    - Added `gm auth register` command to display ASCII QR codes for Google Authenticator.
    - Implemented `gm auth login` to enforce 6-digit token verification.
- **Verification**: ✅ `gm auth register` successfully generates QR codes. ✅ `gm auth login` correctly validates TOTP tokens and passwords.

#### Task A.2: Database Connection Leak Fix
- **Objective**: Prevent PostgreSQL "Idle" connection build-up.
- **Action**:
    - Refactored `Database` class in `database.py` to use the `with self.get_cursor() as cursor:` context manager for ALL data-fetching methods.
    - Eliminated all instances of returning unclosed connections.
    - Implemented `gm maintenance debug-conn` to monitor active sessions.
- **Verification**: ✅ `debug-conn` confirms 0 "Idle" connections remain after command execution. Total connections remain at 1 (current query).

---

## 🛠️ [DEV_A] Legacy Stabilization
**Status:** ✅ COMPLETED

### Tasks
- **Task A.1 Core Service Refactoring**: Implement ABC for repository interfaces. Successfully decoupled domain logic from PostgreSQL.
- **Task A.2 TUI Style Standardization**: Standardized light blue accent and monochrome styling across CLI modules.

---

## 🛡️ [DEV_B] Data Integrity & UI Stability
**Status:** ✅ COMPLETED & VERIFIED

### Tasks
- **Task B.1 Fix Silent Failures in Macro Logic**: Replaced `except: pass` with structured logging in `fred_fetcher.py`. Implemented `stale_data` flag.
- **Task B.2 Resolve React Race Condition**: Refactored `ButterflyMap` component with `ignore` flag pattern in `useEffect` to prevent "Ghost Data".
- **Task B.3 Secure SQL Parameter Binding**: Refactored `cleanup()` in `cache.py` to use secure PostgreSQL parameter binding.

---

## 📍 [TICKET_DEV_C] Profile Logic & Data Isolation
**Status:** ✅ COMPLETED

### Implementation Details
- **Profile Switcher**: Logic in `config.py` to detect `active_profile`.
- **Directory Mapping**: Database/folder mapping to `apps/cli/profiles/personal/` vs `.../business/`.
- **Feature Gating**: Flag/toggle to disable Reward/ML features in "Business" profile.
- **Report Engine (Business)**: Service for quarterly Excel/PDF reports.

### Acceptance Criteria
1. Physical isolation of financial data.
2. Reward menu hidden in "Business" profile.
3. Dashboard Stock updates automatically (5 min).
4. Starred tickers appear at top of Dashboard table.

---

## 🎨 [AGENT8] UI/UX Refinement
**Assignee:** Gemini CLI
**Priority:** Medium
**Status:** ✅ COMPLETED

### 🛠️ Assigned Tasks

#### Task 1: Remove Aggressive Warning Banner
- **Objective**: Strip infrastructure details and developer-oriented warnings from the GUI.
- **Action**:
    - Removed `InfoTooltip` and collapsible status sections in `ReceiptReader.jsx` that exposed API keys.
    - Refactored `NoProviderState` in `AIInsightPanel.jsx` to remove environment variable instructions and terminal commands.
    - Eliminated redundant info banners regarding offline/rule-based fallbacks.
- **Verification**: ✅ Confirmed no sensitive API key names are exposed. ✅ Empty states are polished and consumer-grade.

#### Task 2: Replace With Passive Status Indicator
- **Objective**: Replace intrusive/interactive AI status UI with a subtle, non-intrusive component.
- **Action**:
    - Created `AIPassiveStatus.jsx` with muted styling and context-aware labeling (e.g., "Using Local AI").
    - Integrated the new component into `BehavioralDashboard.jsx` and `receipt_reader.jsx`.
    - Removed interactive `setProvider` logic from the passive indicator.
    - Deleted the deprecated `AIStatusBadge.jsx`.
- **Verification**: ✅ Visual audit confirms muted styling. ✅ Logic correctly identifies Local vs Cloud AI. ✅ Layout remains stable in both dashboards.

#### Task 5: Visual Consistency Audit
- **Objective**: Ensure new UI elements align with project theme, spacing, and mobile standards.
- **Action**:
    - Refactored `AIPassiveStatus` to use theme variables (`var(--ind-d)`, `var(--bdr)`, `var(--gr)`) instead of hardcoded values.
    - Standardized typography and spacing to match existing circular pill badges.
    - Verified mobile responsiveness and light/dark mode compatibility.
- **Verification**: ✅ Confirmed theme variables correctly apply contrast in both modes. ✅ Verified 24px standardized height for alignment. ✅ Confirmed responsive wrapping in headers.

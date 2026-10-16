Last Updated: 29-05-2026 (14:30)

# DESIGN - GUI Stability Audit (Prioritized)

## 🎯 Objective
Stabilize the Finance Tracker GUI by fixing critical runtime errors, enforcing strict data separation between profiles, auditing the database schema, and restoring broken analytics pipelines.

## 🏗️ Architecture & Logic Changes

### 1. React Lifecycle & Stability (Priority 1)
- **Problem**: `ReferenceError: setLoading is not defined` in `StockAnalyzerContent`.
- **Solution**: Replace `setLoading(false)` with `setBaseLoading(false)` in the `loadBaseData` `finally` block of `src/module/stock_analyzer.jsx`.
- **Impact**: Prevents dashboard crashes on load.

### 2. Multi-Profile Data Isolation (Priority 1)
- **Problem**: `DashboardService` hardcodes `schema = "personal"`.
- **Solution**: 
    - Implement a `ProfileManager` utility in the backend to read `data/active_profile.txt`.
    - Update `DashboardService`, `ExpenseService`, and others to accept a `schema` parameter or resolve it dynamically.
    - Ensure `api_server.py` routes detect the active profile for every request.
- **Impact**: Ensures Business data doesn't leak into Personal views and vice-versa.

### 3. Database Schema Audit (Priority 2)
- **Objective**: Verify that both `personal` and `business` schemas in Postgres are perfectly aligned with the `financials` and `investment` definitions.
- **Action**: Create a verification script that compares table structures, constraints, and indexes across both schemas.
- **Remediation**: Apply missing migrations to bring both schemas to parity.

### 4. Analytics Restoration (DCDS/MRZG) (Priority 3)
- **Problem**: DCDS displays "syncing" indefinitely; MRZG displays "NONE".
- **Solution**:
    - **DCDS**: Improve background sync reliability in `StockRepository.py`. Ensure DXY data is persisted or cached effectively.
    - **MRZG**: Update `mrzg_signal` in `domain/scoring.py` to handle edge cases where macro data might be partially unavailable but technical indicators are valid.
    - **UI**: Hide "NONE" or "N/A" indicators in `StockAnalyzer.jsx` to reduce visual noise.

### 5. Asset Integration (Priority 4)
- **Action**: Move `images/New/*.jpeg` to `finance-tracker-gui/public/assets/investments/`.
- **UI**: Update the dashboard or investment detail components to use these new high-quality images.

## 🧪 Verification Plan

### Automated Tests
- **Unit**: Verify `ProfileManager` correctly reads the active profile.
- **Integration**: Test `/api/dashboard` with different active profiles to confirm data isolation.
- **Schema**: Run the new audit script to confirm parity.

### Manual Verification
- Launch GUI and confirm no `ReferenceError` in console.
- Switch profiles via CLI and verify GUI updates correctly.
- Inspect Stock Analyzer to confirm DCDS/MRZG values are populated.

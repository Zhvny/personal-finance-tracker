Last Updated: 29-05-2026 (14:30)

# IMPLEMENTATION PLAN - GUI Stability Audit

## 🛠️ Phase 1: Critical Fixes (Priority 1)
### 1.1 Fix `setLoading` ReferenceError
- [ ] Modify `finance-tracker-gui/src/module/stock_analyzer.jsx`:
    - Update `loadBaseData`'s `finally` block to use `setBaseLoading(false)` instead of `setLoading(false)`.

### 1.2 Implement Dynamic Profile/Schema Resolution
- [ ] Update `backend/routers/deps.py`:
    - Add a helper to read `data/active_profile.txt`.
- [ ] Refactor `backend/services/dashboard_service.py`:
    - Remove hardcoded `schema = "personal"`.
    - Use resolved profile name as the schema.
- [ ] Update `api_server.py`:
    - Ensure `dashboard_service` and others receive the correct schema context.

## 🔍 Phase 2: Database Schema Audit (Priority 2)
### 2.1 Create Audit Script
- [ ] Develop `scripts/audit_database_schemas.py`:
    - Compare `personal` vs `business` schemas in Postgres.
    - Check for missing tables or column mismatches.
### 2.2 Execute Remediation
- [ ] Run the audit script.
- [ ] Apply any identified fixes to align schemas.

## 📈 Phase 3: Analytics Restoration (Priority 3)
### 3.1 Stabilize DCDS Background Sync
- [ ] Update `backend/repositories/stock_repository.py`:
    - Increase timeout or add retry logic for DXY (`DX-Y.NYB`) fetch.
    - Ensure sync doesn't block main analysis loop.
### 3.2 Refine MRZG Logic
- [ ] Update `apps/stock_analyzer/domain/scoring.py`:
    - Adjust `mrzg_signal` to provide better fallback status.
### 3.3 UI Cleanup
- [ ] Update `finance-tracker-gui/src/module/stock_analyzer.jsx`:
    - Add conditional rendering to hide "NONE" for MRZG.

## 🖼️ Phase 4: Asset Integration (Priority 4)
### 4.1 Migrate Images
- [ ] Move `images/New/*.jpeg` to `finance-tracker-gui/public/assets/investments/`.
### 4.2 Link to UI
- [ ] Update relevant React components to use the new assets.

## ✅ Phase 5: Final Validation
- [ ] Verify GUI stability (no console errors).
- [ ] Verify Profile switching isolation.
- [ ] Verify Analytics population.

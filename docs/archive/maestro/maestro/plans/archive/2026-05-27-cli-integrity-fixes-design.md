# CLI Integrity Fixes Design

## 1. Validation Errors
- **Goal**: Allow today's date for transactions.
- **Approach**: Change `datetime` comparison to `.date()` comparison.
- **Impact**: Fixes "Transaction date cannot be in the future" for entries made on the current day.

## 2. Main Menu Overhaul
- **Goal**: Correct ordering and profile-based filtering.
- **Approach**: 
    - Move 'Whale' to index 9, after 'Profile' (8).
    - If `profile == "business"`, exclude Whale, Stocks, ML, and Behavioral features.
    - Consolidate dispatch logic to match filtered items.

## 3. Path Neutralization for ML_Stocks
- **Goal**: Fix "file not found" errors when launching ML_Stocks.
- **Approach**: Use absolute paths derived from `ROOT` (apps/cli) instead of potentially fragile `MONOREPO_ROOT` jumps. Update all occurrences of `apps/stock-ml` to `apps/cli/stock-ml`.

## 4. Receipt Reader Enhancements
- **Goal**: Implement Gemini-first scan and fix Bulk mode.
- **Approach**:
    - Modify `OCREnsemble.run` to allow optional short-circuiting if the first engine (Gemini) succeeds.
    - Investigate and fix `_run_bulk` loop in `receipt_reader/main.py`.

## 5. UI/UX Polishing
- **Goal**: Ensure Income/Expense/Invest sub-modules launch reliably.
- **Approach**: Audit `run_module` for module isolation issues. Verify `DatabaseManager` initialization.

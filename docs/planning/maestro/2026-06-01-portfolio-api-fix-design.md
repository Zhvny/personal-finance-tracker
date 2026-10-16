---
title: "Portfolio FX Integrity & API Fix"
created: "2026-06-01T17:50:00Z"
status: "approved"
authors: ["TechLead", "User"]
type: "design"
design_depth: "quick"
task_complexity: "medium"
---

# Portfolio FX Integrity & API Fix Design Document

## Problem Statement
The Portfolio system is suffering from two critical issues:
1. **API Crash**: A `ModuleNotFoundError` for `PostgresFXRepository` due to inconsistent import paths in the monorepo structure.
2. **Valuation Inaccuracy**: Gold and stale-priced assets show incorrect P/L. Gold price (GC=F) is not correctly converted to grams and IDR, and the system fails to persist historical snapshots reliably.

## Approach
### Selected Approach
**Standardized Monorepo Imports & Enhanced Valuation Logic**
- Standardize all imports to use absolute `packages.*` paths.
- Refactor `InvestmentService` to handle Gold conversion (Ounce to Gram) and integrate live FX (USD to IDR) for all commodities.
- Implement a robust persistence layer for historical price snapshots to prevent "0% gain" fallbacks.

## Risk Assessment
| Risk | Severity | Likelihood | Mitigation |
|------|----------|------------|------------|
| Financial Logic Error | HIGH | MEDIUM | Unit tests with mocked historical data. |
| DB Migration Conflict | MEDIUM | LOW | Validate schema against Pydantic models before write. |
| Broken Imports | MEDIUM | MEDIUM | CI-style verification of server entry point. |

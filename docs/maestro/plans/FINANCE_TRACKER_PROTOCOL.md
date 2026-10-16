Last Updated: 29-05-2026 (14:30)

# FINANCE TRACKER STRUCTURED ENGINEERING PROTOCOL

This protocol defines the mandatory 7-step engineering lifecycle for the Finance Tracker project.

## 1. The 7-Step Execution Lifecycle
For every task and sub-task, agents MUST follow this sequence:
1.  **Analyze**: Understand requirements, "Source of Truth" (`apps/cli/`), and `DESIGN.md`.
2.  **Plan**: Draft implementation and testing strategy (Regression/TDD).
3.  **Execute**: Implement code changes (MUST include a Binance-style UI change in BOTH TUI and GUI).
    - TUI: Update `apps/cli/` using `BinanceTUI` components.
    - GUI: Update `finance-tracker-gui/src/` components matching Binance tokens.
4.  **Validate**: Run `pytest`, verify TUI visually, and ensure GUI build (`npm run build`) passes.
5.  **Document**: Update the 4 Authoritative Hubs (Architecture, P. Manual, Master Plan, Change Log).
6.  **Verify Documentation**: Ensure implementation claims match code symbols.
7.  **Next**: Transition only after all verification gates are passed.

## 2. Mandatory Documentation Hubs
-   **Implementation Notes**: `docs/system/implementation-notes.md` (What/Why/How).
-   **Architecture Blueprint**: `docs/system/architecture.md` (High-level design & Contracts).
-   **Master Plan**: `docs/planning/master-plan.md` (Backlog & Roadmap).
-   **Change Log**: `docs/maintenance/change-log.md` (Release history with timestamps).

## 3. Task-Specific Mandates
- **Async**: Lifecycle diagrams, failure handling logic, loading states.
- **Frontend/TUI**: Binance tokens (#FCD535/#0B0E11), responsive layout notes.
- **Backend**: API contracts, DB schema impact, row-level security checks.
- **Testing**: Reproduction steps, regression coverage report.

## 4. Completion Summary Format
Every task completion MUST generate:
## Completed Work
[List of changes]

## Validation
[Test results and UI verification logs]

## Documentation Updated
[List of hubs and sections updated]

## Remaining Risks
[Potential debt or edge cases]

## Next Recommended Task
[Next step in the implementation plan]

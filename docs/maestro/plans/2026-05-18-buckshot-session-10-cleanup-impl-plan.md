Last Updated: 29-05-2026 (14:30)

---
title: "Session 10 - Final Cleanup Pass Implementation Plan"
design_ref: "conductor/2026-05-18-buckshot-session-10-cleanup-design.md"
created: "2026-05-18T10:30:00Z"
status: "approved"
total_phases: 3
estimated_files: 5
task_complexity: "medium"
---

# Session 10 - Final Cleanup Pass Implementation Plan

## Plan Overview

- **Total phases**: 3
- **Agents involved**: coder, tester
- **Estimated effort**: Low to Medium. The codebase is clean, so this is mostly naming alignment and safety verification.

## Dependency Graph

```
Phase 1: Terminology Alignment (shared)
    |
Phase 2: Renderer & Timer Audit (client/server)
    |
Phase 3: Final Verification & Performance Baseline
```

## Execution Strategy

| Stage | Phases | Execution | Agent Count | Notes |
|-------|--------|-----------|-------------|-------|
| 1     | Phase 1 | Sequential | 1 | Shared constants |
| 2     | Phase 2 | Sequential | 1 | Client/Server cleanup |
| 3     | Phase 3 | Sequential | 1 | Testing & Metrics |

## Phase 1: Terminology Alignment

### Objective
Rename `MaxWebSocketClients` to `MaxTCPClients` and align any legacy "WebSocket" terminology in the source code to reflect the actual TCP implementation.

### Agent: coder
### Parallel: No

### Files to Modify

- `shared/constants.go` — Rename `MaxWebSocketClients` constant.
- `server/server.go` — Update usage of the renamed constant.
- `shared/protocol.go` — (If applicable) Update comments/docs referring to WebSockets.

### Implementation Details

- Surgical rename of the constant to ensure no breaking changes in protocol logic.
- Update any internal comments that mislabel the connection type.

### Validation

- `go build ./...` to ensure all references are updated.

### Dependencies

- Blocked by: None
- Blocks: Phase 2

---

## Phase 2: Renderer & Timer Audit

### Objective
Audit `client/plain_renderer.go` for excessive `fmt` calls and verify that `time.AfterFunc` in `server/game.go` is safely stopped in all exit paths.

### Agent: coder
### Parallel: No

### Files to Modify

- `client/plain_renderer.go` — Review and optionally silence non-critical game loop prints.
- `server/game.go` — Verify `time.AfterFunc` cleanup handlers.

### Implementation Details

- Implement a "quiet mode" or ensure `plain_renderer` only outputs meaningful state changes.
- Add/Verify `Timer.Stop()` calls for all timers in `server/game.go` exit paths (e.g., player disconnect, game end).

### Validation

- Run server and client in plain mode and observe output frequency.

### Dependencies

- Blocked by: Phase 1
- Blocks: Phase 3

---

## Phase 3: Final Verification & Performance Baseline

### Objective
Run final stress tests and record RAM/CPU usage to ensure Session 10 maintained performance standards.

### Agent: tester
### Parallel: No

### Implementation Details

- Execute a 10-minute automated "reconnect spam" and "gameplay loop" test.
- Capture final process metrics using `top` or equivalent.

### Validation

- RAM usage remains within the baseline established in previous sessions.
- 0 Crashes/BSOD during stress test.

### Dependencies

- Blocked by: Phase 2
- Blocks: None

---

## File Inventory

| # | File | Phase | Purpose |
|---|------|-------|---------|
| 1 | `shared/constants.go` | 1 | Rename misnamed constant. |
| 2 | `server/server.go` | 1 | Update constant usage. |
| 3 | `client/plain_renderer.go` | 2 | Reduce log spam. |
| 4 | `server/game.go` | 2 | Audit timer safety. |

## Risk Classification

| Phase | Risk | Rationale |
|-------|------|-----------|
| 1     | LOW | Simple rename of internal constant. |
| 2     | MEDIUM | Modifying timer logic could cause deadlocks or missed events if not careful. |
| 3     | LOW | Verification only. |

## Execution Profile

```
Execution Profile:
- Total phases: 3
- Parallelizable phases: 0
- Sequential-only phases: 3
- Estimated parallel wall time: N/A
- Estimated sequential wall time: 20-30 minutes

Note: Native subagents currently run without user approval gates.
All tool calls are auto-approved without user confirmation.
```

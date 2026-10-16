# F821 — undefined-name follow-up (audit A-007)

## Status

Audit A-007 flagged that `ruff.toml:13` (previous line) explicitly exempted
`F821 x15 undefined-name in routers/cli — FOLLOW UP, possible real bugs`.
The audit recommended re-enabling F821 and filing bugs for each hit.

## Why not globally enabled yet

The 15 undefined-name sites in `routers/cli` (paths relative to `apps/cli/`
or `services/*/routers/cli`) reference names that the static analyzer cannot
resolve. They are likely:

- `__all__` re-exports picked up by a different import path
- `TYPE_CHECKING` imports
- A real bug (the audit's "possible real bugs" caveat)

Without running `ruff check` on the project (network/install constraints),
I cannot produce the exact file:line list. Operators should run:

```bash
ruff check apps/services cli 2>&1 | grep F821
```

…and triage each hit. Each **real** bug must be fixed in a separate
commit. False positives can be re-excluded via `lint.per-file-ignores`
in `ruff.toml`.

## Plan

1. Remove `"F821"` from the top-level `ignore` in `ruff.toml`.
2. Add a narrow per-file-ignore for any F821 hits that are confirmed
   false positives after triage.
3. File one issue per real bug.

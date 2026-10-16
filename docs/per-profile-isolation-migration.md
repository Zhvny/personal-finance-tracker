# Per-Profile Data Isolation — Migration Notes

## Problem
Financial data (income/expense/investments) was shared across all profiles.
Root cause: Prisma models used `previewFeatures=["multiSchema"]` + `@@schema("alpha_*")`,
which fully-qualifies every table (e.g. `alpha_ledger.incomes`), so the per-profile
`search_path` set in `packages/database/index.py` was ignored. All profiles wrote to
the shared `alpha_*` schemas.

Meanwhile a complete per-profile schema system already exists:
`migrations/015_per_profile_schema.sql` + `per_profile_ddl.build_all_ddl_for_profile()`
provision 23 tables in each profile schema (`personal`, `business`, ...). They were
fully created but unused for money data.

## Decision (owner)
- (b) Existing data in `alpha_*` stays put (orphaned); only NEW data is isolated per profile.
- Prisma regeneration goes through a proper CI image rebuild (not in-container).
- Staged rollout.

## Stage 1 — Prisma schema change (DONE in source; needs CI regen)
Edited `packages/database/schema.prisma`:
- Removed `previewFeatures = ["multiSchema"]` from the generator.
- Removed `schemas = [...]` from the datasource.
- Removed all `@@schema("alpha_*")` lines from every model.

Result: Prisma emits UNQUALIFIED table names. At runtime, `packages/database/index.py`
patches `DATABASE_URL` with `schema={profile}` + `options=-c search_path={profile},public`,
so reads/writes resolve to the ACTIVE PROFILE's schema (`personal.incomes`, etc.).

Verified: `python -m prisma validate --schema packages/database/schema.prisma` → valid.

### CI steps required
1. Rebuild the service images (Dockerfile already runs `python3 -m prisma generate`).
   The regenerated client will emit unqualified table names.
2. Ensure each deployed profile schema is provisioned (already true for `personal`/`business`;
   custom profiles are provisioned by `ProfileService.add_profile` →
   `SchemaInitializer.provision_profile_schema`).
3. No `prisma migrate` needed — per-profile tables already exist via `per_profile_ddl`.

### Post-rebuild verification
- Create income under `personal`, switch to `business`, confirm it is NOT visible, and vice versa.
- Confirm `{profile}.incomes` row counts change per active profile.

## Stage 2 — Align reads (after Stage 1 is live)
Most reads already honor the active profile:
- `DatabaseManager.get_connection` sets `search_path` to the active profile first.
- `analytics.py` migrated to `DatabaseManager` (profile-scoped).
Remaining: audit any remaining `DatabaseManager.query(..., schema="alpha_*")` explicit
overrides and legacy SQLite readers; ensure none pin to a shared schema.

## Existing orphaned data (optional, later)
`alpha_ledger.incomes` (3), `alpha_ledger.expenses` (1), `alpha_portfolio.investments` (7)
remain in the shared schemas. If you later want them under a profile, copy rows into
`personal.*` (or the intended profile) — a manual, owner-approved data move.

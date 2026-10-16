# Alpha Database Schema Authority

## Canonical Source of Truth

The **`migrations/`** directory is the single authoritative source for the Alpha database schema.

- Each migration is a numbered, ordered SQL file.
- `packages/api/backend/infrastructure/schemas.py` (`SchemaInitializer`) enforces runtime DDL at startup for the current stage-1 shared-DB topology.
- Do not hand-edit `alpha_db_schema.sql` or `packages/database/schema.prisma` for production DDL.

## Deprecated Files

| File | Status | Reason |
|------|--------|--------|
| `alpha_db_schema.sql` | **Deprecated** | Historical reference only. Missing latest migrations. |
| `packages/database/schema.prisma` | **Deprecated** | Drifts from actual SQL. Do not generate migrations from it. |

## Adding Schema Changes

1. Add a new numbered file in `migrations/` (e.g. `011_add_xxx.sql`).
2. Update `SchemaInitializer` if new DDL is required at startup.
3. Do not modify `alpha_db_schema.sql` or `schema.prisma` to reflect the change.

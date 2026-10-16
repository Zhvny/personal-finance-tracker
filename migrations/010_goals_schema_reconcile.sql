-- 010_goals_schema_reconcile.sql
-- Reconciles deployed per-profile `goals` tables (legacy naming: title/deadline)
-- with the canonical Phase 8 schema (name/target_date).
--
-- Context: migration 005 is a TEMPLATE; deployed profiles may still have the
-- legacy goals table shape (title TEXT NOT NULL, deadline DATE, no name /
-- target_date). goals_service writes name/target_date — without this
-- migration the canonical write fails with UndefinedColumn / NotNullViolation.
--
-- Additive only: keeps legacy columns intact so legacy readers keep working;
-- goals_service reads name OR title, target_date OR deadline (aliases).
-- Applies to every profile schema that exposes a `goals` table.

DO $$
DECLARE
    prof TEXT;
    has_title BOOLEAN;
    has_name BOOLEAN;
    has_deadline BOOLEAN;
    has_target_date BOOLEAN;
BEGIN
    FOR prof IN
        SELECT DISTINCT table_schema
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE'
          AND table_name = 'goals'
          AND table_schema NOT IN ('information_schema', 'pg_catalog')
        ORDER BY 1
    LOOP
        EXECUTE format('SET search_path TO %I', prof);

        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = prof AND table_name = 'goals' AND column_name = 'title'
        ) INTO has_title;
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = prof AND table_name = 'goals' AND column_name = 'name'
        ) INTO has_name;
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = prof AND table_name = 'goals' AND column_name = 'deadline'
        ) INTO has_deadline;
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = prof AND table_name = 'goals' AND column_name = 'target_date'
        ) INTO has_target_date;

        IF NOT has_name THEN
            EXECUTE format('ALTER TABLE %I.goals ADD COLUMN name TEXT', prof);
        END IF;
        IF NOT has_target_date THEN
            EXECUTE format('ALTER TABLE %I.goals ADD COLUMN target_date DATE', prof);
        END IF;
        IF has_title THEN
            -- Legacy title was NOT NULL; canonical writes use `name` and leave
            -- title unset. Relax the constraint so both writers can coexist.
            EXECUTE format('ALTER TABLE %I.goals ALTER COLUMN title DROP NOT NULL', prof);
        END IF;

        RAISE NOTICE 'goals schema reconciled for schema %', prof;
    END LOOP;
END $$;
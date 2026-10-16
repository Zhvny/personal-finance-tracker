-- 021_rename_lust_to_reward_points.sql
--
-- Rename the legacy `lust_points` user_stats key to `reward_points`.
--
-- Context: there is NO `lust_points` COLUMN anywhere in this repo (verified:
-- repo-wide grep finds only one genuine `lust_points` occurrence, the seed
-- *row value* in 015_per_profile_schema.sql:291; `user_stats` is a
-- key-value table `(key TEXT PK, value TEXT, ...)`). An
-- `ALTER TABLE ... RENAME COLUMN lust_points TO reward_points` would fail on
-- deploy because the column does not exist, so this migration renames the
-- seed *key row* instead — that is the actual T2 divergence: 015 seeds
-- `lust_points` while fresh installs via per_profile_ddl.py seed
-- `reward_points`.
--
-- Covers the 015 default profiles (`personal`, `business`) plus
-- `alpha_platform.user_stats` when present (016 moved the legacy
-- `public.user_stats` there; `public` itself no longer holds the table).
-- Custom profiles provisioned later already seed `reward_points` via
-- per_profile_ddl.py, so they need no migration.
--
-- Idempotent: every statement is conditional on the rows existing, and the
-- both-keys merge folds the old numeric value into the new key before
-- deleting the old row, so re-running (or running on already-migrated data)
-- is a no-op. Existing migration files are NOT edited.

DO $$
DECLARE
    schema_name TEXT;
    schema_names TEXT[] := ARRAY['personal', 'business', 'alpha_platform'];
BEGIN
    FOREACH schema_name IN ARRAY schema_names
    LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = schema_name AND table_name = 'user_stats'
        ) THEN
            -- Both keys present (e.g. partial manual backfill): fold the old
            -- numeric value into the new key, then drop the old row.
            EXECUTE format(
                'UPDATE %I.user_stats new SET value = ('
                '  COALESCE(NULLIF(new.value, '''')::NUMERIC, 0) + '
                '  COALESCE(NULLIF(old.value, '''')::NUMERIC, 0))::TEXT '
                'FROM %I.user_stats old '
                'WHERE new.key = ''reward_points'' AND old.key = ''lust_points''',
                schema_name, schema_name
            );
            EXECUTE format(
                'DELETE FROM %I.user_stats old WHERE old.key = ''lust_points'' '
                'AND EXISTS (SELECT 1 FROM %I.user_stats new '
                'WHERE new.key = ''reward_points'')',
                schema_name, schema_name
            );
            -- Plain rename (common case): only fires when `reward_points`
            -- is still absent, otherwise a no-op.
            EXECUTE format(
                'UPDATE %I.user_stats SET key = ''reward_points'' '
                'WHERE key = ''lust_points'' '
                'AND NOT EXISTS (SELECT 1 FROM %I.user_stats '
                'WHERE key = ''reward_points'')',
                schema_name, schema_name
            );
        END IF;
    END LOOP;
END $$;

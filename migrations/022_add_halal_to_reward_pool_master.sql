-- 022_add_halal_to_reward_pool_master.sql
--
-- Add `halal` boolean column to `reward_pool_master` (default TRUE).
-- Backfill known non-halal items to FALSE.
--
-- Idempotent: safe to run multiple times.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'reward_pool_master'
    ) THEN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = 'reward_pool_master' AND column_name = 'halal'
        ) THEN
            ALTER TABLE reward_pool_master ADD COLUMN halal BOOLEAN NOT NULL DEFAULT TRUE;
        END IF;

        UPDATE reward_pool_master
        SET halal = FALSE
        WHERE name_en IN (
            'Tonkotsu Ramen Bowl',
            'Ramen and Gyoza Set',
            'Personal Charcuterie Box'
        );
    END IF;
END $$;

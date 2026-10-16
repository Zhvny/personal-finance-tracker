
import logging
import os
import sys

# Setup paths to include project core
# This script is in scripts/migrations/, so project root is 2 levels up
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "packages"))

from core.infrastructure.config import Config
from core.infrastructure.persistence.postgres_manager import DatabaseManager

# Ensure Config is initialized to load .env if necessary
Config.initialize()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate():
    """Create system.optimization_tasks table."""
    sql = """
    -- Ensure the system schema exists
    CREATE SCHEMA IF NOT EXISTS system;

    -- Create the optimization_tasks table
    CREATE TABLE IF NOT EXISTS system.optimization_tasks (
        task_id UUID PRIMARY KEY,
        profile_id TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'timeout')),
        progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
        input_params JSONB,
        result JSONB,
        error TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Index for faster lookup by profile and status
    CREATE INDEX IF NOT EXISTS idx_opt_tasks_profile ON system.optimization_tasks(profile_id);
    CREATE INDEX IF NOT EXISTS idx_opt_tasks_status ON system.optimization_tasks(status);
    
    -- Trigger for updated_at
    CREATE OR REPLACE FUNCTION system.update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ language 'plpgsql';

    -- Drop existing trigger if it exists to avoid errors on multiple runs
    DROP TRIGGER IF EXISTS update_opt_tasks_updated_at ON system.optimization_tasks;
    
    CREATE TRIGGER update_opt_tasks_updated_at
        BEFORE UPDATE ON system.optimization_tasks
        FOR EACH ROW
        EXECUTE FUNCTION system.update_updated_at_column();
    """

    logger.info("Starting migration: Create system.optimization_tasks")
    try:
        # We don't use DatabaseManager.transaction because it tries to set search_path
        # which might fail if we are creating the schema in the same transaction.
        # But here we are creating table in 'system' schema which already exists based on my check.
        DatabaseManager.execute(sql)
        logger.info("Migration successful.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise

def rollback():
    """Rollback system.optimization_tasks table."""
    sql = "DROP TABLE IF EXISTS system.optimization_tasks;"
    logger.info("Starting rollback: Drop system.optimization_tasks")
    try:
        DatabaseManager.execute(sql)
        logger.info("Rollback successful.")
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        rollback()
    else:
        migrate()

import logging

import psycopg2
from psycopg2.extras import RealDictCursor

DSN = "postgresql://postgres:postgres@localhost:5432/finance_tracker"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("schema_audit")

def get_tables(schema):
    conn = psycopg2.connect(DSN)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s 
            ORDER BY table_name
        """, (schema,))
        tables = [row['table_name'] for row in cur.fetchall()]
    conn.close()
    return tables

def get_columns(schema, table):
    conn = psycopg2.connect(DSN)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        columns = {row['column_name']: (row['data_type'], row['is_nullable']) for row in cur.fetchall()}
    conn.close()
    return columns

def audit():
    schemas = ["personal", "business"]
    base_schemas = ["financials", "investment", "system"]

    logger.info("Starting Schema Audit...")

    # Check tables in personal vs business
    p_tables = get_tables("personal")
    b_tables = get_tables("business")

    all_tables = sorted(list(set(p_tables) | set(b_tables)))

    mismatches = 0

    for table in all_tables:
        if table not in p_tables:
            logger.warning(f"Table '{table}' missing in schema 'personal'")
            mismatches += 1
            continue
        if table not in b_tables:
            logger.warning(f"Table '{table}' missing in schema 'business'")
            mismatches += 1
            continue

        # Compare columns
        p_cols = get_columns("personal", table)
        b_cols = get_columns("business", table)

        if p_cols != b_cols:
            logger.error(f"Column mismatch in table '{table}':")
            all_cols = set(p_cols.keys()) | set(b_cols.keys())
            for col in sorted(list(all_cols)):
                p_val = p_cols.get(col)
                b_val = b_cols.get(col)
                if p_val != b_val:
                    logger.error(f"  - Column '{col}': personal={p_val}, business={b_val}")
            mismatches += 1

    if mismatches == 0:
        logger.info("SUCCESS: 'personal' and 'business' schemas are in perfect sync.")
    else:
        logger.error(f"FAILURE: Found {mismatches} schema mismatches.")

if __name__ == "__main__":
    audit()

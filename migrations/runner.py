#!/usr/bin/env python3
import hashlib
import os
import sys
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("Error: psycopg2 is not installed.")
    sys.exit(1)

MIGRATIONS_DIR = Path(__file__).parent

def get_db_connection():
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "finance_tracker")
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=db,
        user=user,
        password=password
    )

def bootstrap_schema_migrations(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                description TEXT,
                checksum VARCHAR(64)
            );
            ALTER TABLE public.schema_migrations ADD COLUMN IF NOT EXISTS description TEXT;
            ALTER TABLE public.schema_migrations ADD COLUMN IF NOT EXISTS checksum VARCHAR(64);
        """)
    conn.commit()

def get_applied_migrations(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT version, checksum, applied_at FROM public.schema_migrations ORDER BY version")
        return {row[0]: {"checksum": row[1], "applied_at": row[2]} for row in cur.fetchall()}

def get_migration_files():
    files = []
    for f in MIGRATIONS_DIR.glob("*.sql"):
        if f.name == "005_profile_schema_template.sql":
            continue
        files.append(f)
    return sorted(files, key=lambda x: x.name)

def compute_checksum(filepath):
    content = filepath.read_text(encoding="utf-8")
    return hashlib.md5(content.encode()).hexdigest()

def cmd_status():
    try:
        conn = get_db_connection()
        bootstrap_schema_migrations(conn)
        applied = get_applied_migrations(conn)
        files = get_migration_files()

        print("Migration Status:")
        print(f"{'Version':<35} | {'Status':<10} | {'Applied At'}")
        print("-" * 75)

        for f in files:
            version = f.name
            if version in applied:
                status = "APPLIED"
                applied_at = str(applied[version]["applied_at"]).split(".")[0]
            else:
                status = "PENDING"
                applied_at = "-"
            print(f"{version:<35} | {status:<10} | {applied_at}")

    except Exception as e:
        print(f"Error checking status: {e}")
        sys.exit(1)

def cmd_apply():
    try:
        conn = get_db_connection()
        conn.autocommit = False
        bootstrap_schema_migrations(conn)
        applied = get_applied_migrations(conn)
        files = get_migration_files()

        for f in files:
            version = f.name
            if version in applied:
                continue

            print(f"Applying {version}...")
            content = f.read_text(encoding="utf-8")
            checksum = hashlib.md5(content.encode()).hexdigest()

            try:
                with conn.cursor() as cur:
                    cur.execute(content)
                    cur.execute(
                        "INSERT INTO public.schema_migrations (version, description, checksum) VALUES (%s, %s, %s)",
                        (version, "Applied via runner", checksum)
                    )
                conn.commit()
                print(f"SUCCESS: {version}")
            except Exception as e:
                conn.rollback()
                print(f"FAILED: {version}")
                print(f"Error: {e}")
                sys.exit(1)

    except Exception as e:
        print(f"Connection error: {e}")
        sys.exit(1)

def cmd_verify():
    try:
        conn = get_db_connection()
        bootstrap_schema_migrations(conn)
        applied = get_applied_migrations(conn)
        files = get_migration_files()

        mismatches = 0
        print("Verifying applied migrations...")
        for f in files:
            version = f.name
            if version in applied:
                current_checksum = compute_checksum(f)
                stored_checksum = applied[version]["checksum"]

                if current_checksum != stored_checksum:
                    print(f"MISMATCH: {version}")
                    print(f"  Stored:  {stored_checksum}")
                    print(f"  Current: {current_checksum}")
                    mismatches += 1
                else:
                    print(f"OK: {version}")

        if mismatches > 0:
            print(f"\nVerification FAILED. {mismatches} mismatch(es) found.")
            sys.exit(1)
        else:
            print("\nVerification SUCCESS. All applied migrations match.")

    except Exception as e:
        print(f"Error verifying: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python runner.py [status|apply|verify]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "status":
        cmd_status()
    elif cmd == "apply":
        cmd_apply()
    elif cmd == "verify":
        cmd_verify()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

import os
import sqlite3

dbs = [
    r'../data/audit/genetic_audit.db',
    r'../data/audit/ml_audit.db'
]

for db_path in dbs:
    print(f"\n--- Checking DB: {db_path} ---")
    if not os.path.exists(db_path):
        print("  Not found.")
        continue
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    for table in tables:
        tname = table[0]
        print(f"  Table: {tname}")
        cursor.execute(f"PRAGMA table_info({tname})")
        cols = cursor.fetchall()
        for col in cols:
            print(f"    Column: {col[1]} ({col[2]})")
    conn.close()

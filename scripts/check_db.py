import os
import sqlite3

db_path = r'../data/audit/genetic_audit.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
for table in tables:
    tname = table[0]
    print(f"Table: {tname}")
    cursor.execute(f"PRAGMA table_info({tname})")
    cols = cursor.fetchall()
    for col in cols:
        print(f"  Column: {col[1]} ({col[2]})")
conn.close()

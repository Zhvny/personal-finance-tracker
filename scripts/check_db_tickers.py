import sqlite3

db_path = r'../data/audit/genetic_audit.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT DISTINCT ticker FROM evolution_logs")
print("Tickers in evolution_logs:", cursor.fetchall())
conn.close()

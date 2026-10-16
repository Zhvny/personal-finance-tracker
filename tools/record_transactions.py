import sqlite3

INV_DB = "apps/cli/investment_tracker/data/portfolio.db"

def query_jnj():
    conn = sqlite3.connect(INV_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM investments WHERE ticker='JNJ' AND status != 'sold'").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def sell_jnj(inv_id, qty, price, fee, date_str):
    conn = sqlite3.connect(INV_DB)
    # 1. Update investment
    row = conn.execute("SELECT * FROM investments WHERE id=?", (inv_id,)).fetchone()
    if not row:
        print(f"Investment {inv_id} not found")
        return

    current_qty = row[8] if row[8] is not None else row[3] # remaining_quantity or quantity
    new_qty = current_qty - qty
    status = 'sold' if new_qty <= 0.00000001 else 'partial'

    conn.execute("UPDATE investments SET remaining_quantity=?, status=? WHERE id=?", (new_qty, status, inv_id))

    # 2. Record sell transaction
    # We need FX_RATE for realized_pl_idr
    FX_RATE = 16500.0
    buy_price = row[4]
    buy_currency = row[5]
    buy_idr = buy_price if buy_currency == 'IDR' else buy_price * FX_RATE
    sell_idr = price * FX_RATE

    realized_pl_idr = (sell_idr - buy_idr) * qty - (fee * FX_RATE)
    realized_pl_pct = (realized_pl_idr / (buy_idr * qty)) * 100 if buy_idr * qty else 0

    conn.execute("""INSERT INTO sell_transactions 
        (investment_id, sell_date, quantity, sell_price, sell_currency, fees, realized_pl_idr, realized_pl_pct)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (inv_id, date_str, qty, price, 'USD', fee, realized_pl_idr, realized_pl_pct))

    conn.commit()
    conn.close()
    print(f"Sold {qty} JNJ at {price}")

def buy_nvda(qty, price, fee, date_str):
    conn = sqlite3.connect(INV_DB)
    conn.execute("""INSERT INTO investments 
        (asset_type, ticker, quantity, buy_price, buy_currency, buy_date, status, remaining_quantity)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        ('stock', 'NVDA', qty, price, 'USD', date_str, 'holding', qty))
    conn.commit()
    conn.close()
    print(f"Bought {qty} NVDA at {price}")

if __name__ == "__main__":
    jnj_holdings = query_jnj()
    print("Current JNJ holdings:", jnj_holdings)
    if jnj_holdings:
        # User said: sell JNJ 0.354678135 at 226.51 fee 0.33
        # Use the first JNJ holding found
        sell_jnj(jnj_holdings[0]['id'], 0.354678135, 226.51, 0.33, '2026-04-22T20:43:00')

    # User said: buy NVDA 0.407245465 at 200.346 fee 0.32
    buy_nvda(0.407245465, 200.346, 0.32, '2026-04-22T20:44:00')

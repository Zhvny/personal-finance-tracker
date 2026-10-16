"""
import_pluang_transactions.py
Import laporan transaksi Pluang (CSV) ke Investment Tracker personal profile.

Sumber CSV: transaction_report dari Pluang (Aug 2025 - Aug 2026)
Target DB : apps/cli/profiles/personal/investment_tracker/data/portfolio.db

Logika:
- BUY  -> upsert ke table `investments` (cek duplikat berdasarkan order_number di notes)
- SELL -> upsert ke `sell_transactions` (linked ke investment_id)
- DIVIDEND -> dicatat sebagai sell_transaction dengan quantity=0, realized_pl = dividen
- TOP UP / CASH OUT / WALLET / FOREX -> dilewati (bukan data investasi)
- CANCELLED -> dilewati
"""

import csv
import pathlib
import sqlite3
from datetime import datetime
from typing import Optional

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = pathlib.Path(r"C:/Users/Zhvn/Documents/Zhvny/Project/Alpha")
DB_PERSONAL = ROOT / "apps/cli/profiles/personal/investment_tracker/data/portfolio.db"
CSV_PATH = pathlib.Path(r"C:/Users/Zhvn/Downloads/New folder") / (
    "transaction_report_12426749_transaction_report_12426749_"
    "Sun,_Aug_10,_2025_-_Mon,_Aug_10,_2026.csv"
)

# ── Asset-type mapping ────────────────────────────────────────────────────────
ASSET_TYPE_MAP = {
    "Crypto": "crypto",
    "US Stocks": "stock",
    "Gold": "gold",
}

# ── Currency lookup ───────────────────────────────────────────────────────────
FX_FALLBACK = 16_000.0   # fallback IDR/USD jika tidak ada di row


def parse_date(raw: str) -> Optional[str]:
    """Convert 'Wed, Sep 17, 2025' -> '2025-09-17'."""
    raw = raw.strip()
    for fmt in ("%a, %b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def safe_float(val: str, default: float = 0.0) -> float:
    val = val.strip().replace(",", "")
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_rows(csv_path: pathlib.Path) -> list[dict]:
    """Read CSV, skip header lines, return list of row dicts."""
    rows = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = None
        for line in reader:
            if not line or not line[0].strip():
                continue
            if line[0].strip().startswith('"Order Date"') or line[0].strip() == "Order Date":
                header = [c.strip().strip('"') for c in line]
                continue
            if header is None:
                continue
            if line[0].strip().strip('"') in ("", "*USD-IDR conversion rate"):
                continue
            row = {header[i]: line[i].strip().strip('"') for i in range(min(len(header), len(line)))}
            rows.append(row)
    return rows


def get_or_create_investment(conn: sqlite3.Connection, ticker: str, asset_type: str,
                              quantity: float, buy_price: float, buy_currency: str,
                              buy_date: str, order_number: str) -> Optional[int]:
    """
    Return existing investment_id if already imported (by order_number in notes),
    otherwise insert new row and return new id.
    """
    # Check duplicate by notes field if it exists
    cur = conn.execute(
        "SELECT id FROM investments WHERE ticker=? AND buy_date=? AND ABS(quantity - ?) < 0.000001",
        (ticker, buy_date, quantity)
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur = conn.execute(
        """INSERT INTO investments
           (asset_type, ticker, quantity, buy_price, buy_currency, buy_date,
            status, remaining_quantity, is_favorite, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 'active', ?, 0, CURRENT_TIMESTAMP)""",
        (asset_type, ticker, quantity, buy_price, buy_currency, buy_date, quantity)
    )
    return cur.lastrowid


def process(db_path: pathlib.Path, csv_path: pathlib.Path):
    rows = parse_rows(csv_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    imported_buy = 0
    imported_sell = 0
    imported_dividend = 0
    skipped = 0

    for row in rows:
        order_date = parse_date(row.get("Order Date", ""))
        ticker = row.get("Product Name", "").strip()
        transaction = row.get("Transaction", "").strip()      # Crypto / US Stocks / Gold
        tx_type = row.get("Transaction Type", "").strip()     # BUY / SELL / DIVIDEND RECEIVED
        status = row.get("Status", "").strip()
        currency = row.get("Currency", "IDR").strip()
        order_number = row.get("Order Number", "").strip()

        # Skip cancelled, failed, non-investment rows
        if status in ("CANCELLED", "CANCELED", "FAILED"):
            skipped += 1
            continue
        if transaction not in ASSET_TYPE_MAP:
            skipped += 1
            continue
        if not ticker or not order_date:
            skipped += 1
            continue

        asset_type = ASSET_TYPE_MAP[transaction]
        quantity = safe_float(row.get("Quantity", "0"))
        order_price = safe_float(row.get("Order Price", "0"))
        total_amount = safe_float(row.get("Total Amount", "0"))
        fees = safe_float(row.get("Fees", "0")) + safe_float(row.get("Taxes", "0"))
        fx_rate_raw = safe_float(row.get("USD-IDR Conversion Rate*", "0"), 0.0)
        fx_rate = fx_rate_raw if fx_rate_raw > 0 else FX_FALLBACK

        # Derive per-unit buy price
        buy_price = (order_price / quantity) if quantity > 0 and order_price > 0 else total_amount

        # ── BUY ──────────────────────────────────────────────────────────────
        if tx_type == "BUY":
            inv_id = get_or_create_investment(
                conn, ticker, asset_type, quantity, buy_price,
                currency, order_date, order_number
            )
            if inv_id:
                imported_buy += 1

        # ── SELL ─────────────────────────────────────────────────────────────
        elif tx_type == "SELL":
            # Find matching open investment to link
            cur = conn.execute(
                """SELECT id, buy_price, buy_currency FROM investments
                   WHERE ticker=? AND status='active' AND remaining_quantity > 0
                   ORDER BY buy_date ASC LIMIT 1""",
                (ticker,)
            )
            inv_row = cur.fetchone()

            if not inv_row:
                # Create placeholder if no matching buy exists in DB yet
                inv_id = get_or_create_investment(
                    conn, ticker, asset_type, quantity, buy_price,
                    currency, order_date, order_number
                )
            else:
                inv_id = inv_row["id"]
                # Deduct remaining_quantity
                conn.execute(
                    "UPDATE investments SET remaining_quantity = MAX(0, remaining_quantity - ?) WHERE id=?",
                    (quantity, inv_id)
                )

            # Compute realized P&L in IDR
            buy_price_idr = (
                inv_row["buy_price"] if inv_row and inv_row["buy_currency"] == "IDR"
                else (inv_row["buy_price"] * fx_rate if inv_row else 0)
            )
            sell_price_idr = (
                order_price / quantity if currency == "IDR" and quantity > 0
                else buy_price * fx_rate
            )
            realized_pl_idr = (sell_price_idr - buy_price_idr) * quantity - fees
            realized_pl_pct = (
                (realized_pl_idr / (buy_price_idr * quantity) * 100)
                if buy_price_idr > 0 and quantity > 0 else 0
            )

            # Check duplicate sell
            dup = conn.execute(
                "SELECT id FROM sell_transactions WHERE investment_id=? AND sell_date=? AND ABS(quantity - ?) < 0.000001",
                (inv_id, order_date, quantity)
            ).fetchone()
            if not dup:
                conn.execute(
                    """INSERT INTO sell_transactions
                       (investment_id, sell_date, quantity, sell_price, sell_currency,
                        fees, realized_pl_idr, realized_pl_pct, ticker)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (inv_id, order_date, quantity, order_price / quantity if quantity > 0 else order_price,
                     currency, fees, realized_pl_idr, round(realized_pl_pct, 4), ticker)
                )
                imported_sell += 1

        # ── DIVIDEND ─────────────────────────────────────────────────────────
        elif tx_type == "DIVIDEND RECEIVED":
            dividend_amount = safe_float(row.get("Total Amount", "0"))
            cur = conn.execute(
                "SELECT id FROM investments WHERE ticker=? ORDER BY buy_date ASC LIMIT 1",
                (ticker,)
            )
            inv_row = cur.fetchone()
            inv_id = inv_row["id"] if inv_row else None

            if not inv_id:
                inv_id = get_or_create_investment(
                    conn, ticker, asset_type, 0, 0, currency, order_date, order_number
                )

            dup = conn.execute(
                "SELECT id FROM sell_transactions WHERE investment_id=? AND sell_date=? AND quantity=0",
                (inv_id, order_date)
            ).fetchone()
            if not dup and inv_id:
                conn.execute(
                    """INSERT INTO sell_transactions
                       (investment_id, sell_date, quantity, sell_price, sell_currency,
                        fees, realized_pl_idr, realized_pl_pct, ticker)
                       VALUES (?, ?, 0, 0, ?, 0, ?, 0, ?)""",
                    (inv_id, order_date, currency, dividend_amount, ticker)
                )
                imported_dividend += 1

    conn.commit()
    conn.close()

    print(f"\n[OK] Import selesai ke: {db_path.relative_to(ROOT)}")
    print(f"  - BUY  ditambahkan : {imported_buy}")
    print(f"  - SELL ditambahkan : {imported_sell}")
    print(f"  - DIVIDEND         : {imported_dividend}")
    print(f"  - Dilewati (cancel/bukan investasi): {skipped}")


if __name__ == "__main__":
    print(f"[*] Membaca CSV: {CSV_PATH.name}")
    print(f"[*] Target DB  : {DB_PERSONAL.relative_to(ROOT)}")
    process(DB_PERSONAL, CSV_PATH)

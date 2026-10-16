import sqlite3
from pathlib import Path
from typing import List


class StockRepository:
    """SQLite implementation of the Stock Repository for user preferences."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent.parent / "cache.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS favorites (
                    ticker TEXT PRIMARY KEY,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def add_favorite(self, ticker: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT OR IGNORE INTO favorites (ticker) VALUES (?)", (ticker.upper(),))
                return True
        except Exception:
            return False

    def remove_favorite(self, ticker: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM favorites WHERE ticker = ?", (ticker.upper(),))
                return True
        except Exception:
            return False

    def is_favorite(self, ticker: str) -> bool:
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute("SELECT 1 FROM favorites WHERE ticker = ?", (ticker.upper(),)).fetchone()
                return row is not None
        except Exception:
            return False

    def get_favorites(self) -> List[str]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("SELECT ticker FROM favorites ORDER BY added_at DESC").fetchall()
                return [row[0] for row in rows]
        except Exception:
            return []

    def toggle_favorite(self, ticker: str) -> bool:
        if self.is_favorite(ticker):
            return self.remove_favorite(ticker)
        else:
            return self.add_favorite(ticker)

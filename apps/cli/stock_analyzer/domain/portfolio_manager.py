import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

# Use the unified DatabaseManager
try:
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
except ImportError:
    # Minimal fallback if packages not in path
    import psycopg2
    from psycopg2.extras import RealDictCursor

    def _pg_password() -> str:
        pw = os.environ.get("POSTGRES_PASSWORD")
        if pw:
            return pw
        if os.environ.get("DEV_MODE") == "1":
            logger.warning("POSTGRES_PASSWORD unset, using dev default")
            return "postgres"
        logger.warning("POSTGRES_PASSWORD unset, using localhost dev default")
        return "postgres"

    class DatabaseManager:
        @staticmethod
        def query(sql, params=()):
            conn = psycopg2.connect(
                dbname="finance_tracker", user="postgres", password=_pg_password(), host="localhost", port="5432"
            )
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    return [dict(row) for row in cur.fetchall()]

logger = logging.getLogger(__name__)

class PortfolioManager:
    """
    Manages portfolio positions. Can fetch from finance-tracker's PostgreSQL DB
    and overlay SL/TP from local JSON.
    """

    def __init__(self, file_path: str = "portfolio.json"):
        # Local JSON for SL/TP overrides (stored in the stock_analyzer directory)
        _BASE = Path(__file__).resolve().parent.parent
        self.json_path = str(_BASE / ("portfolio_fix.json" if os.path.exists(_BASE / "portfolio_fix.json") else file_path))

        if not os.path.exists(self.json_path):
            self._atomic_write_json([])

    def _atomic_write_json(self, data: list) -> None:
        dir_  = os.path.dirname(os.path.abspath(self.json_path))
        fd, tmp_path = tempfile.mkstemp(dir=dir_, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            os.replace(tmp_path, self.json_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                logger.exception(f"Failed to unlink temp file {tmp_path}")
            raise

    def load_positions(self) -> list:
        """Merge PostgreSQL positions with local SL/TP overrides."""
        overrides = {}
        try:
            if os.path.exists(self.json_path):
                with open(self.json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        for p in data:
                            if isinstance(p, dict) and "ticker" in p:
                                overrides[p['ticker'].upper()] = p
        except Exception as e:
            logger.error(f"Error loading overrides: {e}")

        db_positions = []
        try:
            # Query from PostgreSQL financials.investments or investment.investments schema
            # Based on postgres_manager search_path, it should find it.
            sql = "SELECT ticker, buy_price, buy_date, remaining_quantity FROM investments WHERE status != 'sold'"
            rows = DatabaseManager.query(sql)

            for row in rows:
                ticker = row['ticker'].upper()
                ov = overrides.get(ticker, {})
                db_positions.append({
                    "ticker": ticker,
                    "entry": float(row['buy_price']),
                    "date": str(row['buy_date']),
                    "sl": ov.get("sl", 0.0),
                    "tp": ov.get("tp", 0.0),
                    "source": "db"
                })
        except Exception as e:
            logger.error(f"PostgreSQL portfolio load error: {e}")

        db_tickers = {p['ticker'] for p in db_positions}
        for t, p in overrides.items():
            if t not in db_tickers:
                db_positions.append({
                    "ticker": t,
                    "entry": p.get("entry", 0.0),
                    "date": p.get("date", ""),
                    "sl": p.get("sl", 0.0),
                    "tp": p.get("tp", 0.0),
                    "source": "json"
                })

        return db_positions

    def add_position(self, ticker: str, entry_price: float,
                     entry_date: str, sl: float, tp: float) -> None:
        """Update local SL/TP overrides for a ticker."""
        positions = []
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    positions = json.load(f)
            except Exception:
                logger.exception(f"Error loading positions in add_position from {self.json_path}")

        for pos in positions:
            if pos["ticker"].upper() == ticker.upper():
                pos.update({"entry": entry_price, "date": entry_date, "sl": sl, "tp": tp})
                break
        else:
            positions.append({
                "ticker":    ticker.upper(),
                "entry":     float(entry_price),
                "date":      entry_date,
                "sl":        float(sl),
                "tp":        float(tp),
                "added_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
        self._atomic_write_json(positions)

    def remove_position(self, ticker: str) -> None:
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    positions = json.load(f)
                positions = [p for p in positions if p["ticker"].upper() != ticker.upper()]
                self._atomic_write_json(positions)
            except Exception:
                logger.exception(f"Error removing position {ticker}")

    def update_sl_tp(self, ticker: str, sl: float, tp: float) -> bool:
        """Updates local SL/TP overrides only."""
        positions = []
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    positions = json.load(f)
            except Exception:
                logger.exception(f"Error loading positions in update_sl_tp from {self.json_path}")

        found = False
        for pos in positions:
            if pos["ticker"].upper() == ticker.upper():
                pos["sl"] = float(sl)
                pos["tp"] = float(tp)
                found = True
                break

        if not found:
            # If not in JSON, maybe it's in DB. Add it to JSON as override.
            # But we need entry price. Let's just store SL/TP.
            positions.append({
                "ticker": ticker.upper(),
                "sl": float(sl),
                "tp": float(tp)
            })

        self._atomic_write_json(positions)
        return True

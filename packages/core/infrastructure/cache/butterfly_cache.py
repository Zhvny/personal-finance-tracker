import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class ButterflyCache:
    """
    SQLite-based persistent cache for ButterflyResponse objects.
    Key format: butterfly:<ticker>:<params>
    Default TTL: 1 hour (3600 seconds)
    """

    def __init__(self, db_path: str = "data/cache/butterfly.db", ttl: int = 3600):
        # Ensure path is absolute if relative to project root
        self.db_path = Path(db_path)
        if not self.db_path.is_absolute():
            # Assume we are running from project root
            self.db_path = Path.cwd() / self.db_path

        self.ttl = ttl
        self._init_db()

    def _init_db(self):
        """Initializes the cache table if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS butterfly_cache (
                        cache_key TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        timestamp REAL NOT NULL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON butterfly_cache(timestamp)")
        except sqlite3.Error as e:
            # Silently fail for now or log error
            logger.error(f"ButterflyCache Initialization Error: {e}")

    def get(self, ticker: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Retrieves a cached ButterflyResponse if valid and not expired."""
        cache_key = self._generate_key(ticker, params)
        now = time.time()

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "SELECT data, timestamp FROM butterfly_cache WHERE cache_key = ?",
                    (cache_key,)
                )
                row = cursor.fetchone()

                if row:
                    data_str, timestamp = row
                    if now - timestamp < self.ttl:
                        return json.loads(data_str)
                    else:
                        # Expired
                        self.delete(ticker, params)
        except sqlite3.Error:
            pass
        return None

    def set(self, ticker: str, data: Dict[str, Any], params: Optional[Dict[str, Any]] = None):
        """Stores a ButterflyResponse in the cache."""
        cache_key = self._generate_key(ticker, params)
        data_str = json.dumps(data)
        now = time.time()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO butterfly_cache (cache_key, data, timestamp) VALUES (?, ?, ?)",
                    (cache_key, data_str, now)
                )
        except sqlite3.Error:
            pass

    def delete(self, ticker: str, params: Optional[Dict[str, Any]] = None):
        """Removes an entry from the cache."""
        cache_key = self._generate_key(ticker, params)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM butterfly_cache WHERE cache_key = ?", (cache_key,))
        except sqlite3.Error:
            pass

    def _generate_key(self, ticker: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generates a unique cache key."""
        param_str = json.dumps(params, sort_keys=True) if params else "default"
        return f"butterfly:{ticker}:{param_str}"

    def clear_expired(self):
        """Cleans up all expired cache entries."""
        cutoff = time.time() - self.ttl
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM butterfly_cache WHERE timestamp < ?", (cutoff,))
        except sqlite3.Error:
            pass

    def clear_all(self):
        """Removes all entries from the cache."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM butterfly_cache")
        except sqlite3.Error:
            pass

import functools
import logging
import os
import pickle
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

try:
    import redis
except ImportError:
    redis = None

# US Federal holidays (month, day)
_US_HOLIDAYS = {
    (1, 1), (1, 20), (2, 17), (4, 18), (5, 26),
    (6, 19), (7, 4), (9, 1), (11, 27), (12, 25),
}

# IDX holidays (month, day)
_IDX_HOLIDAYS = {
    (1, 1), (1, 27), (1, 28), (1, 29),
    (3, 28), (3, 29), (3, 30), (3, 31),
    (4, 18),
    (5, 1), (5, 12), (5, 29),
    (6, 1), (6, 2), (6, 6), (6, 7),
    (8, 17),
    (10, 2),
    (12, 25), (12, 26),
}

_TTL_INTRADAY = 300
_TTL_DAILY    = 3600 * 4
_TTL_CLOSED   = 3600 * 14
_TTL_WEEKEND  = 3600 * 12
_TTL_HOLIDAY  = 3600 * 36

# Granular TTL Constants
TTL_OHLCV = 300        # 5 min
TTL_TECHNICALS = 60    # 1 min
TTL_SENTIMENT = 600    # 10 min
TTL_FUNDAMENTALS = 3600 # 1 hour

def _ticker_suffix(ticker: str) -> str:
    if "." in ticker: return "." + ticker.split(".")[-1]
    if ticker.endswith("=F"): return "=F"
    if "-USD" in ticker: return "-USD"
    if "-X" in ticker: return "-X"
    if ticker.startswith("^"): return "^"
    return ""

def _is_idx(ticker: str) -> bool: return _ticker_suffix(ticker) == ".JK"
def _is_crypto(ticker: str) -> bool: return "-USD" in ticker or "-X" in ticker
def _is_us_holiday(d: date) -> bool: return (d.month, d.day) in _US_HOLIDAYS
def _is_idx_holiday(d: date) -> bool: return (d.month, d.day) in _IDX_HOLIDAYS

def _smart_ttl(ticker: str, fetched_at: float = None) -> int:
    try:
        import pytz
        ny_tz = pytz.timezone('America/New_York')
        now_ny = datetime.now(ny_tz)
        d_ny, wd_ny, hour_ny, minute_ny = now_ny.date(), now_ny.weekday(), now_ny.hour, now_ny.minute
    except (ImportError, Exception):
        now_ny = datetime.now()
        d_ny, wd_ny, hour_ny, minute_ny = now_ny.date(), now_ny.weekday(), now_ny.hour, now_ny.minute

    if wd_ny >= 5: return _TTL_WEEKEND
    if _is_crypto(ticker): return _TTL_DAILY

    is_market_open = 9 <= hour_ny < 16 and not (hour_ny == 9 and minute_ny < 30)

    if _is_idx(ticker):
        now_local = datetime.now()
        if _is_idx_holiday(now_local.date()): return _TTL_HOLIDAY
        if 9 <= now_local.hour < 16: return _TTL_INTRADAY
        return _TTL_CLOSED

    if _is_us_holiday(d_ny): return _TTL_HOLIDAY
    if is_market_open: return _TTL_INTRADAY
    return _TTL_CLOSED

class RedisCache:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisCache, cls).__new__(cls)
            redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
            try:
                if redis:
                    cls._instance.client = redis.from_url(redis_url)
                    cls._instance.enabled = True
                else:
                    cls._instance.enabled = False
            except Exception as e:
                logging.error(f"[Cache] Redis initialization failed: {e}")
                cls._instance.enabled = False
        return cls._instance

    def get(self, key):
        if not self.enabled: return None
        try:
            data = self.client.get(key)
            return pickle.loads(data) if data else None
        except Exception as e:
            logging.error(f"[Cache] Redis GET error for {key}: {e}")
            return None

    def set(self, key, value, ttl):
        if not self.enabled: return
        try:
            self.client.setex(key, ttl, pickle.dumps(value))
        except Exception as e:
            logging.error(f"[Cache] Redis SET error for {key}: {e}")

def ticker_cache(ttl: int, cache_type: str):
    """
    Decorator for caching results by ticker.
    Expects 'ticker' as keyword argument or in args.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 1. Resolve Ticker
            ticker = kwargs.get('ticker')
            if not ticker:
                # Search in args (skip 'self' if it's an instance method)
                # We assume if args[0] has func.__name__ as an attribute, it's likely an instance method.
                # However, for robustness, we just search for uppercase strings.
                search_args = args
                for arg in search_args:
                    if isinstance(arg, str) and 1 <= len(arg) <= 12 and arg.isupper():
                        ticker = arg
                        break

            if not ticker:
                return func(*args, **kwargs)

            ticker = ticker.upper()
            period = kwargs.get('period', 'default')
            key = f"cache:{ticker}:{cache_type}:{period}"

            cache = RedisCache()
            cached_val = cache.get(key)
            if cached_val is not None:
                logging.debug(f"[Cache] Hit for {key}")
                return cached_val

            result = func(*args, **kwargs)
            cache.set(key, result, ttl)
            return result
        return wrapper
    return decorator

class DataCache:
    """PostgreSQL-backed OHLCV cache with SQLite fallback and market-aware TTL expiration."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parent.parent / "cache.db")
        self.db_path = db_path
        self._init_db()

        # Initialize Postgres repository
        try:
            from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository
            self.pg_repo = PostgresOHLCVRepository()
        except ImportError:
            self.pg_repo = None

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS ohlcv_cache (
                        ticker TEXT,
                        period TEXT,
                        fetched_at REAL,
                        data BLOB,
                        PRIMARY KEY (ticker, period)
                    )
                """)
        except Exception as e:
            logging.error(f"[Cache] SQLite init error: {e}")

    def get(self, ticker: str, period: str, allow_stale: bool = False) -> "pd.DataFrame | None":
        # 1. Try Postgres First (Source of Truth for background updates)
        if self.pg_repo:
            try:
                res = self.pg_repo.get(ticker, period)
                if res is not None:
                    data, fetched_at_dt = res
                    # Convert datetime to timestamp
                    fetched_at = fetched_at_dt.timestamp()
                    ttl = _smart_ttl(ticker, fetched_at)
                    age = time.time() - fetched_at

                    if age < ttl or allow_stale:
                        return data
                    else:
                        logging.info(f"[Cache] Postgres data for {ticker} is stale ({age/3600:.1f}h old)")
            except Exception as e:
                logging.error(f"[Cache] Postgres read error for {ticker}: {e}")

        # 2. Fallback to SQLite
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT data, fetched_at FROM ohlcv_cache WHERE ticker=? AND period=?",
                    (ticker, period)
                ).fetchone()

                if row:
                    data, fetched_at = row
                    ttl = _smart_ttl(ticker, fetched_at)
                    age = time.time() - fetched_at

                    if age < ttl or allow_stale:
                        return pickle.loads(data)
        except Exception as e:
            logging.error(f"[Cache] SQLite read error for {ticker}: {e}")
        return None

    def set(self, ticker: str, period: str, df: "pd.DataFrame"):
        # 1. Save to Postgres
        if self.pg_repo:
            try:
                self.pg_repo.save(ticker, period, df)
            except Exception as e:
                logging.error(f"[Cache] Postgres write error for {ticker}: {e}")

        # 2. Save to SQLite (Legacy fallback)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO ohlcv_cache (ticker, period, fetched_at, data)
                    VALUES (?, ?, ?, ?)
                """, (ticker, period, time.time(), pickle.dumps(df)))
        except Exception as e:
            logging.error(f"[Cache] SQLite write error for {ticker}: {e}")

    def invalidate(self, ticker: str, period: str = None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                if period:
                    conn.execute("DELETE FROM ohlcv_cache WHERE ticker=? AND period=?", (ticker, period))
                else:
                    conn.execute("DELETE FROM ohlcv_cache WHERE ticker=?", (ticker,))
        except Exception as e:
            logging.error(f"[Cache] Invalidate error: {e}")

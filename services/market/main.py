"""alpha-market :8453 — stocks, ML inference, genetic optimizer, senate,
butterfly risk map, market scheduler."""

import asyncio

from services.runtime.bootstrap import create_service_app, run_service

ROUTERS = [
    "stocks",
    "ml_stocks",
    "genetic",
    "butterfly",
    "senate",
    "scheduler",
    "scheduler_status",
]

DEFAULT_PORT = 8453


def register_inline(app, logger):
    # Moved verbatim from legacy apps/api/main.py (/api/genetic/universe/audit)
    from fastapi import Depends
    from fastapi.responses import JSONResponse

    from packages.api.backend.security.core import require_scope
    from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager

    @app.get("/api/genetic/universe/audit", tags=["Genetic Analytics"], dependencies=[Depends(require_scope("read"))])
    async def get_genetic_universe_audit():
        try:
            import pandas as pd

            from apps.cli.genetic_optimizer import PortfolioOptimizer
            from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository

            repo = PostgresOHLCVRepository()
            tickers = await asyncio.to_thread(DatabaseManager.query, "SELECT DISTINCT ticker FROM market.ohlcv_cache")
            ticker_list = [r["ticker"] for r in tickers]

            if not ticker_list:
                return {"total": 0, "eligible": 0, "excluded": [], "message": "No data in market cache"}

            import io as _io

            def _load_all_closes():
                """Satu roundtrip utk semua blob OHLCV '1y', ekstrak kolom Close saja."""
                rows = DatabaseManager.query("SELECT ticker, data FROM market.ohlcv_cache WHERE period = '1y'")
                closes = {}
                for r in rows:
                    raw = r["data"]
                    if isinstance(raw, memoryview):
                        raw = raw.tobytes()
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8")
                    try:
                        df = pd.read_json(_io.StringIO(raw), orient="split")
                    except Exception:
                        continue
                    if df is None or df.empty or len(df) < 30:
                        continue
                    df.columns = [str(c).capitalize() for c in df.columns]
                    if "Close" in df.columns:
                        closes[r["ticker"]] = df["Close"]
                return closes

            returns_map = await asyncio.to_thread(_load_all_closes)

            if not returns_map:
                return {
                    "total": len(ticker_list),
                    "eligible": 0,
                    "excluded": [{"ticker": t, "reason": "No valid historical data"} for t in ticker_list],
                }

            all_available_tickers = list(returns_map.keys())
            price_df = pd.DataFrame(returns_map).ffill().dropna()

            aligned_tickers = list(price_df.columns)
            _dropped_during_alignment = set(all_available_tickers) - set(aligned_tickers)

            if price_df.empty:
                return {
                    "total": len(ticker_list),
                    "eligible": 0,
                    "excluded": [{"ticker": t, "reason": "No overlapping historical data"} for t in ticker_list],
                }

            returns_df = price_df.pct_change().dropna()
            optimizer = PortfolioOptimizer()
            audit_result = optimizer.get_universe_audit(returns_df)
            audit_result["total"] = len(ticker_list)

            pre_excluded = set(ticker_list) - set(all_available_tickers)
            for t in pre_excluded:
                audit_result["excluded"].append(
                    {"ticker": t, "reason": "Insufficient data history (< 30 days) or missing Close column"}
                )

            return audit_result

        except Exception as e:
            logger.error(f"Universe audit error: {str(e)}", exc_info=True)
            return JSONResponse(
                status_code=503,
                content={"error": "Universe audit failed", "total": 0, "eligible": 0, "excluded": []},
            )


app = create_service_app(
    service_name="alpha-market",
    default_port=DEFAULT_PORT,
    routers=ROUTERS,
    register_inline=register_inline,
    scheduler_enabled=True,
    butterfly_cleanup=True,
)

if __name__ == "__main__":
    run_service(app, "alpha-market")

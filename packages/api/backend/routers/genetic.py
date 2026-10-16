import asyncio
import json
import logging
import sqlite3
import sys
import uuid
from pathlib import Path
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

# Resolve paths
_HERE = Path(__file__).resolve().parent
_BACKEND = _HERE.parent
_API_PACKAGE = _BACKEND.parent
_PACKAGES = _API_PACKAGE.parent
_ROOT = _PACKAGES.parent
_APPS = _ROOT / "apps"
_CLI = _APPS / "cli"


# Ensure apps and root are in path for imports
for p in [str(_APPS), str(_ROOT)]:
    if p not in sys.path:
        sys.path.append(p)

from apps.cli.genetic_optimizer import PortfolioOptimizer
from apps.cli.stock_analyzer.domain.config import AppConfig
from packages.api.backend.repositories.stock_repository import StockRepository
from packages.core.application.shared.profile_service import ProfileService
from packages.core.infrastructure.config import Config
from packages.core.infrastructure.persistence.postgres_manager import DatabaseManager
from packages.core.infrastructure.persistence.postgres_ohlcv_repository import PostgresOHLCVRepository

# Path to the genetic_audit.db
AUDIT_DB = _ROOT / "data" / "audit" / "genetic_audit.db"
PROD_MODELS_DIR = _ROOT / "models" / "prod"

logger = logging.getLogger("api.genetic_optimizer")

from packages.api.backend.security.core import require_scope

router = APIRouter(prefix="/api/genetic", tags=["genetic"], dependencies=[Depends(require_scope("read"))])

# Initialize Components
_config_path = _APPS / "cli" / "stock_analyzer" / "config.yaml"
_config = AppConfig.load(str(_config_path))
_repo = StockRepository(_config)
_optimizer = PortfolioOptimizer()
_profile_service = ProfileService(Config.BASE_DIR)


class EvolutionLog(BaseModel):
    id: int
    ticker: str
    category: str
    iteration: int
    params: dict
    mae: float
    is_winner: bool
    timestamp: str


class OptimizedModelMeta(BaseModel):
    ticker: str
    category: str
    best_mae: float
    params: dict
    optimized_at: str


@router.get("/logs/{ticker}")
async def get_evolution_logs(ticker: str):
    """Fetch evolution history for a specific ticker."""
    if not AUDIT_DB.exists():
        return []

    try:
        conn = sqlite3.connect(str(AUDIT_DB))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM evolution_logs WHERE ticker = ? ORDER BY iteration ASC", (ticker.upper(),)
        ).fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append(
                {
                    "id": r["id"],
                    "ticker": r["ticker"],
                    "category": r["category"],
                    "iteration": r["iteration"],
                    "params": json.loads(r["params"]),
                    "mae": r["mae"],
                    "is_winner": bool(r["is_winner"]),
                    "timestamp": r["timestamp"],
                }
            )
        return results
    except Exception as e:
        logger.error(f"Error fetching genetic logs for {ticker}: {e}")
        return []


@router.get("/models")
async def list_optimized_models():
    """List all models currently optimized by the Genetic Engine."""
    if not PROD_MODELS_DIR.exists():
        return []

    models = []
    try:
        for meta_file in PROD_MODELS_DIR.glob("*_meta.json"):
            with open(meta_file, "r") as f:
                models.append(json.load(f))
        return models
    except Exception as e:
        logger.error(f"Error listing optimized models: {e}")
        return []


@router.get("/status")
async def get_engine_status():
    """Get overall status of the Genetic Optimization engine."""
    status = {"db_exists": AUDIT_DB.exists(), "total_optimized": 0, "last_run": None, "audit_path": str(AUDIT_DB)}

    if AUDIT_DB.exists():
        try:
            conn = sqlite3.connect(str(AUDIT_DB))
            row = conn.execute("SELECT MAX(timestamp) as last_run FROM evolution_logs").fetchone()
            count = conn.execute("SELECT COUNT(DISTINCT ticker) FROM evolution_logs").fetchone()
            status["last_run"] = row[0] if row else None
            status["total_optimized"] = count[0] if count else 0
            conn.close()
        except Exception as e:
            logger.error(f"Error checking engine status: {e}")

    return status


class OptimizationRequest(BaseModel):
    tickers: Optional[List[str]] = None
    min_assets: int = Field(default=1, ge=1, le=50)
    max_assets: int = Field(default=10, ge=1, le=100)
    num_generations: int = Field(default=50, ge=10, le=500)
    risk_mode: str = "sharpe"
    diversification_mode: str = "standard"


class OptimizationResponse(BaseModel):
    task_id: str
    status: str
    message: str


async def execute_optimization_task(task_id: str, tickers: List[str], request: OptimizationRequest):
    """Background task to run optimization logic."""
    logger.info(f"[Optimization][DEBUG] execute_optimization_task started for task: {task_id}")
    logger.info(f"[Optimization][DEBUG] Tickers: {tickers}, Request: {request.model_dump()}")

    # Update status to processing
    try:
        DatabaseManager.execute(
            "UPDATE system.optimization_tasks SET status = %s WHERE task_id = %s",
            ("processing", task_id),
            schema="system",
        )
        logger.info(f"[Optimization][DEBUG] Task {task_id} status updated to processing")
    except Exception as e:
        logger.error(f"[Optimization][DEBUG] Failed to update status to processing for task {task_id}: {e}")

    def progress_callback(progress: float):
        """Callback to update progress in PostgreSQL."""
        try:
            DatabaseManager.execute(
                "UPDATE system.optimization_tasks SET progress = %s WHERE task_id = %s",
                (int(progress * 100), task_id),
                schema="system",
            )
        except Exception as e:
            logger.error(f"[Optimization] Failed to update progress for task {task_id}: {e}")

    try:
        # 1. Fetch OHLCV data from Postgres (SSOT)
        logger.info(f"[Optimization] Task {task_id}: Fetching OHLCV data from Postgres for {len(tickers)} tickers...")
        ohlcv_repo = PostgresOHLCVRepository()
        dfs = {}
        last_error = None
        for ticker in tickers:
            try:
                data = ohlcv_repo.get(ticker, "2y")
                if data:
                    df, _ = data
                    if df is not None and not df.empty:
                        dfs[ticker] = df["Close"]
                        logger.info(f"[Optimization][DEBUG] Task {task_id}: Fetched {len(df)} rows for {ticker}")
                    else:
                        logger.warning(f"[Optimization][DEBUG] Task {task_id}: DF is empty for {ticker}")
                else:
                    logger.warning(f"[Optimization][DEBUG] Task {task_id}: No data returned for {ticker}")
            except Exception as inner_e:
                logger.warning(f"[Optimization] Task {task_id}: Failed to fetch data for {ticker}: {inner_e}")
                last_error = str(inner_e)

        if not dfs:
            error_msg = (
                f"No data found in Postgres for requested tickers. Details: {last_error}"
                if last_error
                else "No data found in Postgres for requested tickers."
            )
            logger.error(f"[Optimization] Task {task_id} failed: {error_msg}")
            DatabaseManager.execute(
                "UPDATE system.optimization_tasks SET status = %s, error = %s WHERE task_id = %s",
                ("failed", error_msg, task_id),
                schema="system",
            )
            return

        # 2. Transform to Returns
        price_df = pd.DataFrame(dfs).ffill().dropna()
        returns_df = price_df.pct_change().dropna()

        logger.info(f"[Optimization][DEBUG] Task {task_id}: Returns DF shape: {returns_df.shape}")

        if returns_df.empty or returns_df.shape[1] < 1:
            error_msg = "Insufficient overlapping data for returns calculation."
            logger.error(f"[Optimization] Task {task_id} failed: {error_msg}")
            DatabaseManager.execute(
                "UPDATE system.optimization_tasks SET status = %s, error = %s WHERE task_id = %s",
                ("failed", error_msg, task_id),
                schema="system",
            )
            return

        # 3. Run GA Optimization with timeout
        logger.info(f"[Optimization] Task {task_id}: Running GA Optimization...")
        try:
            result = await asyncio.wait_for(
                _optimizer.optimize_async(
                    returns_df,
                    target=request.risk_mode,
                    max_assets=request.max_assets,
                    progress_callback=progress_callback,
                    task_id=task_id,
                ),
                timeout=300.0,
            )
            logger.info(
                f"[Optimization][DEBUG] Task {task_id}: GA Optimization finished. Result keys: {list(result.keys()) if result else 'None'}"
            )
        except asyncio.TimeoutError:
            logger.error(f"[Optimization] Task {task_id} timed out after 300s.")
            DatabaseManager.execute(
                "UPDATE system.optimization_tasks SET status = %s, error = %s WHERE task_id = %s",
                ("timeout", "Optimization timed out after 300s", task_id),
                schema="system",
            )
            return

        if not result or not result.get("weights"):
            error_msg = "Optimizer returned no result or empty weights."
            logger.error(f"[Optimization] Task {task_id} failed: {error_msg}")
            DatabaseManager.execute(
                "UPDATE system.optimization_tasks SET status = %s, error = %s WHERE task_id = %s",
                ("failed", error_msg, task_id),
                schema="system",
            )
            return

        # 4. Finalize
        DatabaseManager.execute(
            "UPDATE system.optimization_tasks SET status = %s, result = %s, progress = 100 WHERE task_id = %s",
            ("completed", json.dumps(result), task_id),
            schema="system",
        )
        logger.info(f"[Optimization] Task {task_id} completed successfully.")

    except Exception as e:
        logger.exception(f"[Optimization] Task {task_id} encountered unexpected error: {e}")
        try:
            DatabaseManager.execute(
                "UPDATE system.optimization_tasks SET status = %s, error = %s WHERE task_id = %s",
                ("failed", str(e), task_id),
                schema="system",
            )
        except Exception:
            logger.exception("Failed to persist failed status for genetic task %s", task_id)
            raise


@router.get("/portfolio/status/{task_id}")
async def get_optimization_status(task_id: str):
    """Check the status of a background optimization task from PostgreSQL."""
    try:
        rows = DatabaseManager.query(
            "SELECT * FROM system.optimization_tasks WHERE task_id = %s", (task_id,), schema="system"
        )
        if not rows:
            raise HTTPException(status_code=404, detail="Task not found.")

        task = rows[0]
        # Result and input_params might be JSON strings or dicts depending on driver/schema
        if isinstance(task.get("input_params"), str):
            task["input_params"] = json.loads(task["input_params"])
        if isinstance(task.get("result"), str):
            task["result"] = json.loads(task["result"])

        return task
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching status for task {task_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")


@router.post(
    "/portfolio/optimize",
    response_model=OptimizationResponse,
    status_code=202,
    dependencies=[Depends(require_scope("write"))],
)
async def run_portfolio_optimization(request: OptimizationRequest, background_tasks: BackgroundTasks):
    """Trigger a new portfolio optimization run via async BackgroundTasks."""
    logger.info(f"[Optimization][DEBUG] run_portfolio_optimization invoked with request: {request.model_dump()}")
    try:
        # 1. Resolve Tickers
        tickers = request.tickers
        if not tickers:
            try:
                tickers = await _repo.get_favorites()
                logger.info(f"[Optimization][DEBUG] Resolved favorites: {tickers}")
            except Exception as e:
                logger.exception(f"[Optimization] Failed to resolve favorites: {e}")
                raise HTTPException(
                    status_code=500,
                    detail="Failed to resolve favorites from repository. Please specify tickers explicitly.",
                )

        if not tickers:
            # Emergency Fallback
            tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
            logger.warning(
                f"[Optimization] No tickers found and no favorites available. Using emergency fallback: {tickers}"
            )

        logger.info(f"[Optimization] Request received for tickers: {tickers}")

        # 2. Create Task ID and Persist to DB
        task_id = str(uuid.uuid4())
        profile_id = _profile_service.get_active_profile()
        logger.info(f"[Optimization][DEBUG] Task ID: {task_id}, Profile ID: {profile_id}")

        try:
            DatabaseManager.execute(
                "INSERT INTO system.optimization_tasks (task_id, profile_id, status, progress, input_params) VALUES (%s, %s, %s, %s, %s)",
                (task_id, profile_id, "pending", 0, json.dumps(request.model_dump())),
                schema="system",
            )
            logger.info(f"[Optimization][DEBUG] Task {task_id} persisted to database.")
        except Exception as e:
            logger.exception(f"[Optimization] Failed to persist task {task_id} to database: {e}")
            raise HTTPException(status_code=500, detail="Database failure while creating optimization task.")

        # 3. Schedule Background Task
        try:
            background_tasks.add_task(execute_optimization_task, task_id, tickers, request)
            logger.info(f"[Optimization] Task {task_id} scheduled successfully.")
        except Exception as e:
            logger.exception(f"[Optimization] Failed to schedule background task: {e}")
            # Update status in DB as failed if we couldn't even schedule it
            DatabaseManager.execute(
                "UPDATE system.optimization_tasks SET status = %s, error = %s WHERE task_id = %s",
                ("failed", f"Failed to schedule: {str(e)}", task_id),
                schema="system",
            )
            raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

        return {"task_id": task_id, "status": "accepted", "message": "Optimization started in background."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Critical error in run_portfolio_optimization: {e}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")


@router.get("/portfolio/stats")
async def get_portfolio_stats():
    """Fetch the latest optimized portfolio statistics."""
    path = PROD_MODELS_DIR / "active_portfolio.json"
    if not path.exists():
        # Check if active_portfolio.json is in another location or try to find any meta
        raise HTTPException(status_code=404, detail="No active portfolio found.")

    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading portfolio stats: {e}")
        raise HTTPException(status_code=500, detail="Error reading portfolio data.")

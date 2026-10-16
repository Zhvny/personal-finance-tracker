import logging
import time
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends

logger = logging.getLogger("api.ml_stocks")

# ── Cache Layer ───────────────────────────────────────────────────────────
_ML_CACHE = {
    "df": None,
    "last_load": 0,
    "ttl": 3600 # 1 hour
}

def _get_ml_summary_df(active_path: Path):
    now = time.time()
    if _ML_CACHE["df"] is not None and (now - _ML_CACHE["last_load"]) < _ML_CACHE["ttl"]:
        return _ML_CACHE["df"]

    try:
        df = pd.read_csv(active_path)
        _ML_CACHE["df"] = df
        _ML_CACHE["last_load"] = now
        logger.info(f"ML Summary loaded and cached from {active_path}")
        return df
    except Exception as e:
        logger.error(f"Error reading ML Summary: {e}")
        return None

# Robust Path Detection
_HERE = Path(__file__).resolve()
_ROUTERS = _HERE.parent
_BACKEND = _ROUTERS.parent
_API = _BACKEND.parent
_PACKAGES = _API.parent
_ROOT = _PACKAGES.parent

# Primary path in data/results_honest
SUMMARY_PATH = _ROOT / "data" / "results_honest" / "honest_summary.csv"
# Fallback path in apps/cli/stock_ml (new standard)
FALLBACK_PATH = _ROOT / "apps" / "cli" / "stock_ml" / "results_honest" / "honest_summary.csv"

from packages.api.backend.security.core import require_scope

router = APIRouter(prefix="/api/ml-stocks", tags=["ml-stocks"], dependencies=[Depends(require_scope("read"))])

@router.get("/summary")
async def get_summary():
    # Detect which file exists
    active_path = SUMMARY_PATH if SUMMARY_PATH.exists() else (FALLBACK_PATH if FALLBACK_PATH.exists() else None)

    if not active_path:
        logger.warning(f"ML Summary file not found. Checked: {SUMMARY_PATH}, {FALLBACK_PATH}")
        return []

    try:
        # Optimization: use cached loader
        df = _get_ml_summary_df(active_path)
        if df is None: return []

        df = df.where(pd.notnull(df), None) # Handle NaNs for JSON compatibility

        results = []
        for _, d in df.iterrows():
            results.append({
                "ticker": str(d['ticker']),
                "category": str(d.get('category', 'US')),
                "global_acc": d.get('global_acc'),
                "precision": d.get('precision'),
                "signal": str(d.get('signal', 'NEUTRAL')),
                "prob": d.get('prob'),
                "trend": d.get('trend'),
                "risk": d.get('risk'),
                "last_close": d.get('last_close'),
                "timestamp": str(d.get('timestamp', '')),
                "n_signals": int(d['n_signals']) if d.get('n_signals') is not None else 0
            })

        return results
    except Exception as e:
        logger.error(f"Error processing ML Summary: {str(e)}", exc_info=True)
        return []

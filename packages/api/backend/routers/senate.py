import logging
import sys
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

# Resolve paths
_HERE = Path(__file__).resolve().parent
_GUI = _HERE.parent.parent
_PROJECT_ROOT = _GUI.parent
_APPS = _PROJECT_ROOT / "apps"
_CLI = _APPS / "cli"

if str(_APPS) not in sys.path: sys.path.insert(0, str(_APPS))
if str(_CLI) not in sys.path: sys.path.insert(0, str(_CLI))
_INVESTMENT_TRACKER = _CLI / "investment_tracker"
if str(_INVESTMENT_TRACKER) not in sys.path: sys.path.insert(0, str(_INVESTMENT_TRACKER))

# Now we can import from the CLI logic
try:
    from cli.investment_tracker.services.senate_service import SenateService
except ImportError:
    # Fallback for different path structures
    from apps.cli.investment_tracker.services.senate_service import SenateService

from packages.api.backend.security.core import require_scope

from .deps import market_service

router = APIRouter(prefix="/api/stocks/senate", tags=["senate"], dependencies=[Depends(require_scope("read"))])
logger = logging.getLogger("api.router.senate")

@router.get("/{ticker}")
async def get_senate_decision(ticker: str, asset_type: str = "stock"):
    """Get the agent senate decision for a ticker."""
    try:
        # Load data
        df = await market_service.get_ohlcv(ticker.upper())
        if df is None or df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")

        # Instantiate SenateService with category
        category = "crypto" if "crypto" in asset_type.lower() else "stock"
        senate = SenateService(category)

        # The service call might be blocking (parallel threads inside), but get_senate_decision is synchronous
        # We should run it in an executor to be safe
        import asyncio
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, senate.get_senate_decision, ticker.upper(), df)

        return {
            "ticker": ticker.upper(),
            "consensus": result.consensus.value,
            "confidence": float(result.confidence),
            "opinions": [
                {
                    "agent": op.agent_name,
                    "vote": op.vote.value,
                    "confidence": float(op.confidence),
                    "rationale": op.rationale
                } for op in result.opinions
            ],
            "market_regime": result.market_regime,
            "timestamp": result.timestamp.isoformat()
        }
    except Exception:
        logger.exception(f"Error in Senate Agent for {ticker}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

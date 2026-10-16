import logging
import sys
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException

# Resolve paths
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent.parent.parent
_STOCK_ANALYZER = _PROJECT_ROOT / "apps" / "cli" / "stock_analyzer"

# Ensure apps/cli is in sys.path to find stock_analyzer package
if str(_STOCK_ANALYZER.parent) not in sys.path:
    sys.path.insert(0, str(_STOCK_ANALYZER.parent))
# Also ensure project root is in sys.path for packages.* imports
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from stock_analyzer.domain.config import AppConfig

from packages.api.backend.repositories.stock_repository import StockRepository
from packages.api.backend.security.core import require_scope
from packages.core.application.stock_analysis_service import StockAnalysisService

from .deps import whale_service

# Structured Logging
logger = logging.getLogger("api.router.stocks")

router = APIRouter(prefix="/api/stocks", tags=["stocks"], dependencies=[Depends(require_scope("read"))])

# Dependency Injection / Components Init
_config = AppConfig.load(str(_STOCK_ANALYZER / "config.yaml"))
_repo = StockRepository(_config)
_service = StockAnalysisService(_repo, _config)

@router.get("/macro")
async def get_macro_context():
    """Get macro regime and liquidity metrics."""
    return await _repo.get_macro_context()

@router.get("/whale/{ticker}")
async def get_whale_signals(ticker: str, asset_type: str = "stock"):
    """Get whale / smart money signals for a ticker."""
    try:
        return await whale_service.get_whale_signals(ticker.upper(), asset_type)
    except Exception:
        logger.exception(f"Error fetching whale signals for {ticker}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

@router.get("/analyze/{ticker}")
async def analyze_ticker(ticker: str):
    """Analyze a single ticker with full technical and ML metrics."""
    try:
        # Service already uses run_in_executor internally
        res = await _service.analyze_ticker(ticker.upper())
        if not res:
            raise HTTPException(status_code=404, detail=f"Analysis failed for {ticker}")
        return res
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Router error analyzing {ticker}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

@router.get("/analyze/{ticker}/base")
async def get_ticker_base(ticker: str):
    """Get basic price and signal data for a ticker."""
    res = await _service.analyze_ticker(ticker.upper())
    if not res:
        raise HTTPException(status_code=404, detail=f"Base data unavailable for {ticker}")
    return {
        "ticker": res["ticker"],
        "price": res["price"],
        "change": res["change"],
        "signal": res["signal"],
        "score": res["score"]
    }

@router.get("/analyze/{ticker}/chart")
async def get_ticker_chart(ticker: str, period: str = "1y"):
    """Get historical price data for charting."""
    return await _service.get_history(ticker.upper(), period)

@router.get("/analyze/{ticker}/sentiment")
async def get_ticker_sentiment(ticker: str):
    """Get sentiment and macro correlation metrics."""
    res = await _service.analyze_ticker(ticker.upper())
    if not res:
        raise HTTPException(status_code=404, detail=f"Sentiment data unavailable for {ticker}")
    return {
        "ticker": res["ticker"],
        "csi": res["csi"],
        "dcds": res["dcds"],
        "mrzg": res["mrzg"]
    }

@router.get("/analyze/{ticker}/technicals")
async def get_ticker_technicals(ticker: str):
    """Get technical indicators and ML forecast metrics."""
    res = await _service.analyze_ticker(ticker.upper())
    if not res:
        raise HTTPException(status_code=404, detail=f"Technical data unavailable for {ticker}")
    return {
        "ticker": res["ticker"],
        "support": res["support"],
        "resistance": res["resistance"],
        "stop_loss": res["stop_loss"],
        "take_profit": res["take_profit"],
        "ml_signal": res["ml_signal"],
        "ml_prob": res["ml_prob"],
        "forecast_1w": res["forecast_1w"],
        "forecast_1m": res["forecast_1m"]
    }

@router.get("/analyze/{ticker}/dxy")
async def get_dxy_analysis(ticker: str):
    """Get only DXY divergence analysis for a ticker."""
    return await _service.get_dcds_analysis(ticker.upper())

@router.post("/analyze/batch")
async def analyze_batch(tickers: List[str]):
    """Analyze a list of tickers in parallel."""
    return await _service.analyze_batch(tickers)

@router.get("/favorites")
async def get_favorites():
    """Get all favorite tickers."""
    return await _repo.get_favorites()

@router.post("/favorites/{ticker}", dependencies=[Depends(require_scope("write"))])
async def add_favorite(ticker: str):
    """Add a ticker to favorites."""
    success = await _repo.add_favorite(ticker)
    if not success:
        logger.error(f"Failed to add {ticker} to favorites")
        raise HTTPException(status_code=500, detail=f"Failed to add {ticker} to favorites")
    return {"status": "success", "ticker": ticker}

@router.delete("/favorites/{ticker}", dependencies=[Depends(require_scope("write"))])
async def remove_favorite(ticker: str):
    """Remove a ticker from favorites."""
    success = await _repo.remove_favorite(ticker)
    if not success:
        logger.error(f"Failed to remove {ticker} from favorites")
        raise HTTPException(status_code=500, detail=f"Failed to remove {ticker} from favorites")
    return {"status": "success", "ticker": ticker}

@router.get("/watchlist")
async def get_watchlist():
    """Get the defined stock watchlist from list.txt."""
    list_path = _STOCK_ANALYZER / "list.txt"
    if not list_path.exists():
        return {}
    try:
        categories = {}
        current_cat = "OTHERS"
        with open(list_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.endswith(":"):
                    current_cat = line[:-1].strip().upper()
                    if current_cat not in categories:
                        categories[current_cat] = []
                else:
                    ticker = line.strip().upper()
                    if current_cat not in categories:
                        categories[current_cat] = []
                    if ticker not in categories[current_cat]:
                        if current_cat == "IDX STOCKS" and not ticker.endswith(".JK"):
                            ticker += ".JK"
                        categories[current_cat].append(ticker)
        return categories
    except Exception:
        logger.exception("Watchlist error")
        return {}

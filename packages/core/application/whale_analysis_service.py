import logging
from typing import Any, Dict

from packages.core.application.investment_tracker.whale_service import WhaleVolumeProfiler

logger = logging.getLogger("core.application.whale_service")

class WhaleAnalysisService:
    """
    Service to detect 'Whale' / Smart Money activity using volume profile analysis.
    Wraps the existing WhaleVolumeProfiler from the CLI modules.
    """
    def __init__(self):
        self.profiler = WhaleVolumeProfiler()

    async def get_whale_signals(self, ticker: str, asset_type: str = "stock") -> Dict[str, Any]:
        """
        Analyzes volume spikes and price absorption for a given ticker.
        """
        try:
            # WhaleVolumeProfiler currently uses blocking yfinance calls,
            # so we run it in a thread if needed, but for now we'll call it directly
            # and let the router handle the async transition if necessary.
            result = self.profiler.analyze_ticker(ticker, asset_type)
            return result
        except Exception as e:
            logger.error(f"Error in WhaleAnalysisService for {ticker}: {e}")
            return {"error": str(e), "ticker": ticker, "is_whale_activity": False}

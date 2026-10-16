import logging

from fastapi import APIRouter, Depends, HTTPException

from packages.api.backend.security.core import require_scope
from packages.core.application.butterfly_schemas import ButterflyResponse

from .deps import butterfly_service

router = APIRouter(prefix="/api/butterfly", tags=["butterfly"], dependencies=[Depends(require_scope("read"))])
logger = logging.getLogger(__name__)

@router.get("/risk-map/{ticker}", response_model=ButterflyResponse)
async def get_risk_map(ticker: str):
    """Get the butterfly effect risk map (correlations) for a ticker."""
    try:
        return await butterfly_service.get_risk_map(ticker.upper())
    except Exception:
        logger.exception(f"Error fetching butterfly risk map for {ticker}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

@router.get("/benchmark/{scale}", response_model=ButterflyResponse)
async def benchmark_risk_map(scale: int):
    """
    Get a mock risk map for benchmarking UI performance.
    Scale represents the number of nodes (e.g., 10, 100, 500).
    """
    try:
        # Default density 0.1 ensures a reasonable number of edges
        return await butterfly_service.generate_mock_risk_map(scale, edge_density=0.1)
    except Exception:
        logger.exception(f"Error generating benchmark risk map for scale {scale}")
        raise HTTPException(status_code=500, detail="Internal server error. Check server logs for details.")

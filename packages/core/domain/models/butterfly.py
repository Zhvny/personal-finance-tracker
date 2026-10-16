
from pydantic import BaseModel


class ButterflyStabilityMetrics(BaseModel):
    """
    Dummy model to satisfy imports until full implementation.
    """
    stability_score: float = 0.0
    volatility_index: float = 0.0
    node_count: int = 0

class CorrelationNode(BaseModel):
    id: str # Ticker symbol
    ticker: str
    correlation: float
    description: str
    impact_level: str # Low, Medium, High

class Edge(BaseModel):
    source: str
    target: str
    correlation: float

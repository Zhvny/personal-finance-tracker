from typing import List, Optional

from pydantic import BaseModel, Field


class ButterflyNode(BaseModel):
    id: str = Field(..., description="Unique identifier for the node (usually ticker symbol)")
    ticker: str = Field(..., description="Ticker symbol (alias for id)")
    label: str = Field(..., description="Display label for the node")
    correlation: float = Field(..., description="Correlation coefficient with the target asset")
    description: Optional[str] = Field(None, description="Description of the asset or macro indicator")
    impact: Optional[str] = Field(None, description="Impact level (alias for impact_level)")
    impact_level: Optional[str] = Field(None, description="Impact level: Target, Low, Medium, or High")

class ButterflyEdge(BaseModel):
    source: str = Field(..., description="ID of the source node")
    target: str = Field(..., description="ID of the target node")
    weight: float = Field(..., description="Correlation value between the two nodes")

class ButterflyResponse(BaseModel):
    nodes: List[ButterflyNode]
    edges: List[ButterflyEdge]
    status: str = Field("success", description="Response status (success, insufficient_data)")
    message: Optional[str] = Field(None, description="Detailed message for fallback states")
    metadata: Optional[dict] = Field(default_factory=dict)

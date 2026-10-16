from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel


class Operator(str, Enum):
    CONTAINS = "contains"
    EQUALS = "equals"
    STARTS_WITH = "starts_with"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"

class Criterion(BaseModel):
    field: str
    operator: Operator
    value: Any

class RuleAction(BaseModel):
    set_category: Optional[str] = None
    add_tags: List[str] = []
    set_metadata: dict = {}

class Rule(BaseModel):
    id: str
    name: str
    priority: int = 0
    criteria: List[Criterion]
    action: RuleAction
    enabled: bool = True

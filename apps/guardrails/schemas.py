from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

@dataclass
class GuardrailResult:
    status: str  # "PASS" or "BLOCK"
    reasons: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StructuredRequest:
    task_type: str  # "food_image" or "food_edit"
    user_goal: str
    dish_name: Optional[str] = None
    ingredients: Optional[str] = None
    cuisine: Optional[str] = None

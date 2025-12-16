from dataclasses import dataclass, field
from typing import List, Dict, Any

@dataclass
class GuardrailResult:
    status: str  # "PASS" or "BLOCK"
    reasons: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

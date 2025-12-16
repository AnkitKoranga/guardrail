import hashlib
from django.core.cache import cache
from .schemas import GuardrailResult

def compute_hash(prompt: str, image_hash: str = None) -> str:
    """Compute a unique hash for the request."""
    data = f"{prompt}|{image_hash or ''}"
    return hashlib.sha256(data.encode()).hexdigest()

def get_cached_decision(request_hash: str) -> GuardrailResult:
    """Retrieve cached decision if available."""
    data = cache.get(f"guardrail:{request_hash}")
    if data:
        return GuardrailResult(**data)
    return None

def cache_decision(request_hash: str, result: GuardrailResult, timeout: int = 3600):
    """Cache the decision result."""
    # Convert dataclass to dict for caching
    data = {
        "status": result.status,
        "reasons": result.reasons,
        "scores": result.scores,
        "metadata": result.metadata
    }
    cache.set(f"guardrail:{request_hash}", data, timeout)

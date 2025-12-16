import re
from .schemas import GuardrailResult

INJECTION_PATTERNS = [
    r"ignore previous",
    r"system prompt",
    r"developer message",
    r"bypass safety",
    r"jailbreak",
    r"DAN mode",
    r"do anything now",
]

def check_injection(text: str) -> GuardrailResult:
    """Check for prompt injection attempts."""
    text_lower = text.lower()
    
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return GuardrailResult(
                status="BLOCK",
                reasons=[f"Potential prompt injection detected: {pattern}"]
            )
            
    # Heuristic: Check for high entropy or base64-like blobs (simplified)
    # If a word is very long and has mixed case/numbers, it might be suspicious
    words = text.split()
    for word in words:
        if len(word) > 40 and not word.startswith("http"):
             return GuardrailResult(
                status="BLOCK",
                reasons=["Suspicious long string detected"]
            )

    return GuardrailResult(status="PASS")

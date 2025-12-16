from .schemas import GuardrailResult

DENYLIST_TERMS = [
    "nude", "naked", "sex", "porn", "xxx",
    "kill", "murder", "suicide", "hurt", "blood", "gore",
    "hate", "racist", "nazi",
    "scam", "fraud", "credit card", "ssn",
    "child", "minor", "kid",
]

def check_policy(text: str) -> GuardrailResult:
    """Check against policy denylist."""
    text_lower = text.lower()
    
    found_terms = []
    for term in DENYLIST_TERMS:
        if term in text_lower:
            found_terms.append(term)
            
    if found_terms:
        return GuardrailResult(
            status="BLOCK",
            reasons=[f"Policy violation: {', '.join(found_terms)}"]
        )
        
    return GuardrailResult(status="PASS")

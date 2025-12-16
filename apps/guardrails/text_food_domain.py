from sentence_transformers import SentenceTransformer, util
from .schemas import GuardrailResult
import logging
import re

logger = logging.getLogger(__name__)

# Lazy load model
_model = None

# Specific food items and food-related context keywords (strict matching)
FOOD_ITEMS = [
    # Common dishes
    "pizza", "burger", "pasta", "sandwich", "salad", "soup", "sushi", "taco", "burrito",
    "curry", "stir fry", "noodles", "ramen", "dumpling", "spring roll", "sushi roll",
    # Meals
    "breakfast", "lunch", "dinner", "brunch", "snack", "appetizer", "dessert",
    # Food categories
    "cake", "bread", "cookie", "pie", "pastry", "muffin", "donut", "croissant",
    "steak", "chicken", "beef", "pork", "lamb", "fish", "seafood", "shrimp", "crab", "lobster",
    "rice", "quinoa", "pasta", "noodle", "potato", "fries", "mashed potato",
    "vegetable", "fruit", "apple", "banana", "orange", "strawberry", "grape",
    "tomato", "lettuce", "onion", "garlic", "pepper", "carrot", "broccoli", "spinach",
    # Beverages
    "coffee", "tea", "juice", "smoothie", "milkshake", "soda", "wine", "beer",
    # Cooking terms
    "recipe", "cooking", "baking", "grilling", "roasting", "frying", "steaming", "boiling",
    # Food context
    "restaurant", "cafe", "bakery", "menu", "chef", "cuisine", "dish", "meal", "food"
]

# Patterns that indicate non-food content (fast block)
# These patterns check for person/celebrity names without food context
NON_FOOD_PATTERNS = [
    r'\b(generate|create|make).*image.*of\s+(a\s+)?(person|people|man|woman|boy|girl|child|baby|portrait)\b',
    r'\b(generate|create|make).*image.*of\s+(a\s+)?(celebrity|actor|actress|model|singer|artist)\b',
]

ALLOWLIST_INTENTS = [
    "write a recipe for pizza",
    "ingredients list for pasta",
    "cooking steps for burger",
    "plating photo of food",
    "food photography",
    "restaurant menu item",
    "recipe for chicken",
    "how to cook pasta",
    "dinner idea",
    "create a food image",
    "generate food photo",
    "recipe for pasta",
    "cooking instructions",
    "food preparation",
    "dish presentation",
    "meal planning"
]

def get_model():
    global _model
    if _model is None:
        # Use a small model for CPU efficiency
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model

def check_food_domain(text: str, threshold: float = 0.55) -> GuardrailResult:
    """
    Strict food domain check - only allows prompts explicitly about food items/context.
    Uses fast keyword matching first, then strict embedding check.
    """
    text_lower = text.lower().strip()
    
    # Stage 0: Quick non-food pattern check (fastest)
    # Check for "generate/create/make image of X" patterns
    image_of_pattern = r'\b(generate|create|make|show|display).*image.*of\s+(.+?)(?:\s|$)'
    match = re.search(image_of_pattern, text_lower)
    if match:
        # Extract what comes after "image of"
        subject = match.group(2).strip()
        # Check if subject is a food item
        is_food_item = any(item in subject for item in FOOD_ITEMS)
        # Check if subject looks like a person name (common name patterns)
        looks_like_person = bool(re.search(r'\b(emma|watson|hitler|person|people|man|woman|celebrity|actor)\b', subject))
        
        if looks_like_person and not is_food_item:
            logger.info(f"Non-food pattern detected: image of {subject}")
            return GuardrailResult(
                status="BLOCK",
                reasons=["Prompt does not contain food-related items or context"],
                scores={"domain_score": 0.0, "method": "pattern_block"}
            )
    
    # Also check other non-food patterns
    for pattern in NON_FOOD_PATTERNS:
        if re.search(pattern, text_lower):
            # Check if it also mentions food - if not, block immediately
            has_food_item = any(item in text_lower for item in FOOD_ITEMS)
            if not has_food_item:
                logger.info(f"Non-food pattern detected: {pattern}")
                return GuardrailResult(
                    status="BLOCK",
                    reasons=["Prompt does not contain food-related items or context"],
                    scores={"domain_score": 0.0, "method": "pattern_block"}
                )
    
    # Stage A: Fast keyword check - must contain actual food items/context
    keyword_matches = [item for item in FOOD_ITEMS if item in text_lower]
    if keyword_matches:
        # Strong food item match - fast path, approve immediately
        logger.info(f"Fast path: Food items found: {keyword_matches[:3]}")
        return GuardrailResult(
            status="PASS",
            scores={"domain_score": 0.95, "method": "keyword_match", "matched_keywords": keyword_matches[:5]}
        )

    # Stage B: Strict embedding check (only if no keywords found)
    # Higher threshold - only allow if strongly food-related
    try:
        model = get_model()
        text_emb = model.encode(text, convert_to_tensor=True)
        intent_embs = model.encode(ALLOWLIST_INTENTS, convert_to_tensor=True)
        
        # Compute cosine similarities
        cosine_scores = util.cos_sim(text_emb, intent_embs)
        max_score = float(cosine_scores.max())
        
        # Strict threshold - block if score is below 0.55
        if max_score < threshold:
            logger.info(f"Embedding check failed: score {max_score:.2f} < threshold {threshold}")
            return GuardrailResult(
                status="BLOCK",
                reasons=[f"Prompt not related to food items or context (score: {max_score:.2f})"],
                scores={"domain_score": max_score, "method": "embedding"}
            )
            
        logger.info(f"Embedding check passed: score {max_score:.2f}")
        return GuardrailResult(
            status="PASS",
            scores={"domain_score": max_score, "method": "embedding"}
        )
    except Exception as e:
        logger.error(f"Domain check failed: {str(e)}")
        # If embedding check fails and no keywords matched, block to be safe
        return GuardrailResult(
            status="BLOCK",
            reasons=[f"Domain check failed: {str(e)}"]
        )

import torch
import open_clip
from PIL import Image
from .schemas import GuardrailResult
import logging

logger = logging.getLogger(__name__)

_model = None
_preprocess = None
_tokenizer = None
# Cache for pre-computed text features (speeds up inference significantly)
_text_features_cache = {}

POS_LABELS = ["a photo of food", "a meal", "a dish", "ingredients", "cooking"]
# Enhanced negative labels: NSFW, violence, and non-food content
# CLIP now handles NSFW detection, eliminating need for separate NudeNet check
NEG_LABELS = [
    # NSFW content
    "a nude person", "nudity", "naked person", "explicit nudity",
    "porn", "pornography", "sexual content", "adult content",
    # Violence and weapons
    "weapon", "gun", "knife", "violence", "gore", "blood", "death",
    # Non-food content
    "a face portrait", "portrait", "person", "people",
    "document", "text", "paper", "child", "minor"
]

# Food type classification labels - ordered by common food categories
FOOD_TYPE_LABELS = [
    # Pizza varieties
    "pizza", "pepperoni pizza", "margherita pizza", "cheese pizza",
    # Cakes and desserts
    "cake", "chocolate cake", "birthday cake", "cheesecake", "cupcake",
    "pastry", "pie", "brownie", "cookie", "donut", "ice cream",
    # Burgers and sandwiches
    "burger", "hamburger", "cheeseburger", "sandwich", "hot dog", "sub sandwich",
    # Pasta and Italian
    "pasta", "spaghetti", "lasagna", "ravioli", "noodles",
    # Asian cuisine
    "sushi", "ramen", "fried rice", "dumplings", "spring rolls", "curry",
    # Salads and vegetables
    "salad", "caesar salad", "fruit salad", "vegetable dish",
    # Meat dishes
    "steak", "fried chicken", "grilled chicken", "roasted meat", "bbq",
    # Seafood
    "fish", "shrimp", "lobster", "seafood",
    # Breakfast items
    "pancakes", "waffles", "eggs", "bacon", "breakfast",
    # Beverages
    "coffee", "smoothie", "juice", "tea",
    # Snacks
    "fries", "chips", "popcorn", "nachos",
    # Breads
    "bread", "toast", "croissant", "bagel",
    # Soups
    "soup", "stew", "chili",
    # Other common foods
    "tacos", "burritos", "quesadilla", "wrap",
    "rice", "fried food", "appetizer", "main course", "dessert"
]

def get_clip_model():
    global _model, _preprocess, _tokenizer
    if _model is None:
        # Use a small model for CPU
        _model, _, _preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
        _tokenizer = open_clip.get_tokenizer('ViT-B-32')
        # Set model to eval mode for faster inference
        _model.eval()
    return _model, _preprocess, _tokenizer


def _get_cached_text_features(labels: list, cache_key: str):
    """Get cached text features or compute and cache them."""
    global _text_features_cache
    if cache_key not in _text_features_cache:
        model, _, tokenizer = get_clip_model()
        text = tokenizer(labels)
        with torch.no_grad():
            text_features = model.encode_text(text)
            text_features /= text_features.norm(dim=-1, keepdim=True)
        _text_features_cache[cache_key] = text_features
    return _text_features_cache[cache_key]


def identify_food_type(pil_image: Image.Image) -> dict:
    """
    Identify the type of food in the image using CLIP.
    Returns dict with 'food_type', 'confidence', and 'top_matches'.
    This is called AFTER the image passes food validation for efficiency.
    """
    try:
        model, preprocess, _ = get_clip_model()
        
        image = preprocess(pil_image).unsqueeze(0)
        
        # Get cached food type text features (pre-computed for speed)
        food_labels_for_clip = [f"a photo of {food}" for food in FOOD_TYPE_LABELS]
        text_features = _get_cached_text_features(food_labels_for_clip, "food_types")
        
        with torch.no_grad():
            image_features = model.encode_image(image)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            
            # Compute similarities
            similarities = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            
        probs = similarities[0].tolist()
        
        # Get top 3 matches for detailed results
        top_indices = sorted(range(len(probs)), key=lambda i: probs[i], reverse=True)[:3]
        top_matches = [
            {"food_type": FOOD_TYPE_LABELS[i], "confidence": round(probs[i] * 100, 2)}
            for i in top_indices
        ]
        
        # Best match
        best_idx = top_indices[0]
        best_food = FOOD_TYPE_LABELS[best_idx]
        best_confidence = probs[best_idx]
        
        logger.info(f"Food identified as: {best_food} (confidence: {best_confidence:.2%})")
        
        return {
            "food_type": best_food,
            "confidence": round(best_confidence * 100, 2),
            "top_matches": top_matches
        }
        
    except Exception as e:
        logger.error(f"Food type identification failed: {e}")
        return {
            "food_type": "unknown",
            "confidence": 0,
            "top_matches": [],
            "error": str(e)
        }


def check_food_clip(pil_image: Image.Image, margin: float = 0.1, identify_type: bool = True) -> GuardrailResult:
    """
    Check if image is food-related using CLIP.
    Also detects NSFW content via negative labels, eliminating need for separate NSFW detector.
    If identify_type is True, also identifies the specific food type.
    """
    try:
        model, preprocess, _ = get_clip_model()
        
        image = preprocess(pil_image).unsqueeze(0)
        
        # Get cached text features for validation (pre-computed for speed)
        all_labels = POS_LABELS + NEG_LABELS
        text_features = _get_cached_text_features(all_labels, "validation")
        
        with torch.no_grad():
            image_features = model.encode_image(image)
            image_features /= image_features.norm(dim=-1, keepdim=True)
            
            text_probs = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            
        probs = text_probs[0].tolist()
        pos_probs = probs[:len(POS_LABELS)]
        neg_probs = probs[len(POS_LABELS):]
        
        max_pos = max(pos_probs)
        max_neg = max(neg_probs)
        
        # Check if top label is positive AND margin is sufficient
        # This also blocks NSFW content since negative labels include NSFW terms
        if max_pos < max_neg + margin:
            # Determine reason based on which negative label scored highest
            neg_label_idx = neg_probs.index(max_neg)
            neg_label = NEG_LABELS[neg_label_idx]
            
            # Check if it's NSFW-related
            nsfw_terms = ["nude", "naked", "porn", "sexual", "adult"]
            is_nsfw = any(term in neg_label.lower() for term in nsfw_terms)
            
            reason = f"NSFW content detected: {neg_label}" if is_nsfw else f"Image not clearly food (pos: {max_pos:.2f}, neg: {max_neg:.2f})"
            return GuardrailResult(
                status="BLOCK",
                reasons=[reason],
                scores={"food_score": max_pos, "non_food_score": max_neg, "top_negative_label": neg_label}
            )
        
        # Image passed validation - now identify the food type if requested
        scores = {"food_score": max_pos, "non_food_score": max_neg}
        metadata = {}
        
        if identify_type:
            food_info = identify_food_type(pil_image)
            scores["identified_food"] = food_info["food_type"]
            scores["food_type_confidence"] = food_info["confidence"]
            metadata["food_identification"] = food_info
            
        return GuardrailResult(
            status="PASS",
            scores=scores,
            metadata=metadata
        )

    except Exception as e:
        return GuardrailResult(status="BLOCK", reasons=[f"CLIP check failed: {str(e)}"])

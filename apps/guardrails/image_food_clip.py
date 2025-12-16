import torch
import open_clip
from PIL import Image
from .schemas import GuardrailResult

_model = None
_preprocess = None
_tokenizer = None

POS_LABELS = ["a photo of food", "a meal", "a dish", "ingredients", "cooking"]
NEG_LABELS = ["a nude person", "porn", "weapon", "gore", "a face portrait", "document", "child"]

def get_clip_model():
    global _model, _preprocess, _tokenizer
    if _model is None:
        # Use a small model for CPU
        _model, _, _preprocess = open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k')
        _tokenizer = open_clip.get_tokenizer('ViT-B-32')
    return _model, _preprocess, _tokenizer

def check_food_clip(pil_image: Image.Image, margin: float = 0.1) -> GuardrailResult:
    """Check if image is food-related using CLIP."""
    try:
        model, preprocess, tokenizer = get_clip_model()
        
        image = preprocess(pil_image).unsqueeze(0)
        text = tokenizer(POS_LABELS + NEG_LABELS)
        
        with torch.no_grad(), torch.cuda.amp.autocast() if torch.cuda.is_available() else torch.no_grad():
            image_features = model.encode_image(image)
            text_features = model.encode_text(text)
            
            image_features /= image_features.norm(dim=-1, keepdim=True)
            text_features /= text_features.norm(dim=-1, keepdim=True)
            
            text_probs = (100.0 * image_features @ text_features.T).softmax(dim=-1)
            
        probs = text_probs[0].tolist()
        pos_probs = probs[:len(POS_LABELS)]
        neg_probs = probs[len(POS_LABELS):]
        
        max_pos = max(pos_probs)
        max_neg = max(neg_probs)
        
        # Check if top label is positive AND margin is sufficient
        if max_pos < max_neg + margin:
             return GuardrailResult(
                status="BLOCK",
                reasons=[f"Image not clearly food (pos: {max_pos:.2f}, neg: {max_neg:.2f})"],
                scores={"food_score": max_pos, "non_food_score": max_neg}
            )
            
        return GuardrailResult(
            status="PASS",
            scores={"food_score": max_pos, "non_food_score": max_neg}
        )

    except Exception as e:
        return GuardrailResult(status="BLOCK", reasons=[f"CLIP check failed: {str(e)}"])

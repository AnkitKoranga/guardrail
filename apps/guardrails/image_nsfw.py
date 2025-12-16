from nudenet import NudeDetector
from .schemas import GuardrailResult
import tempfile
import os

_detector = None

def get_detector():
    global _detector
    if _detector is None:
        _detector = NudeDetector()
    return _detector

def check_nsfw(image_path: str, threshold: float = 0.5) -> GuardrailResult:
    """Check for NSFW content using NudeNet Detector."""
    try:
        detector = get_detector()
        detections = detector.detect(image_path)
        # detections is list of {'class': '...', 'score': 0.9, 'box': [...]}
        
        unsafe_labels = [
            "FEMALE_GENITALIA_EXPOSED", "MALE_GENITALIA_EXPOSED", 
            "BUTTOCKS_EXPOSED", "FEMALE_BREAST_EXPOSED", 
            "MALE_BREAST_EXPOSED", "ANUS_EXPOSED"
        ]
        
        max_unsafe_score = 0.0
        found_classes = []
        
        for d in detections:
            if d['class'] in unsafe_labels:
                score = d['score']
                if score > max_unsafe_score:
                    max_unsafe_score = score
                if score > threshold:
                    found_classes.append(f"{d['class']} ({score:.2f})")
        
        if max_unsafe_score > threshold:
            return GuardrailResult(
                status="BLOCK", 
                reasons=[f"NSFW content detected: {', '.join(found_classes)}"],
                scores={"nsfw_score": max_unsafe_score}
            )
            
        return GuardrailResult(status="PASS", scores={"nsfw_score": max_unsafe_score})
        
    except Exception as e:
        return GuardrailResult(status="BLOCK", reasons=[f"NSFW check failed: {str(e)}"])

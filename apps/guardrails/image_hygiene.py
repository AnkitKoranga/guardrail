from PIL import Image
import io
from .schemas import GuardrailResult
from django.conf import settings

def check_hygiene(image_bytes: bytes) -> GuardrailResult:
    """Check image hygiene (size, format, EXIF)."""
    
    if len(image_bytes) > settings.GUARDRAILS_MAX_IMAGE_BYTES:
        return GuardrailResult(status="BLOCK", reasons=["Image too large"])
        
    try:
        img = Image.open(io.BytesIO(image_bytes))
        
        # Check dimensions
        w, h = img.size
        if w * h > settings.GUARDRAILS_MAX_PIXELS:
             return GuardrailResult(status="BLOCK", reasons=["Image dimensions too large"])
             
        # Strip EXIF (by creating new image)
        data = list(img.getdata())
        image_without_exif = Image.new(img.mode, img.size)
        image_without_exif.putdata(data)
        
        # Convert to RGB if needed
        if image_without_exif.mode != 'RGB':
            image_without_exif = image_without_exif.convert('RGB')
            
        return GuardrailResult(status="PASS", metadata={"pil_image": image_without_exif})
        
    except Exception as e:
        return GuardrailResult(status="BLOCK", reasons=[f"Invalid image: {str(e)}"])

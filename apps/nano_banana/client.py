import google.generativeai as genai
from django.conf import settings
from .prompt_template import SYSTEM_PROMPT
import base64
import logging

logger = logging.getLogger(__name__)

def generate_content(prompt: str, pil_image=None):
    """
    Call Gemini 2.5 Flash (Nano Banana).
    Only called AFTER guardrails pass.
    Returns dict with 'text' and optionally 'image' (base64 encoded).
    """
    if not settings.GEMINI_API_KEY:
        return {"text": "Error: GEMINI_API_KEY not configured.", "image": None}

    genai.configure(api_key=settings.GEMINI_API_KEY)
    
    # Use gemini-2.5-flash model
    model_name = 'gemini-2.5-flash'
    model = genai.GenerativeModel(model_name)
    
    full_prompt = [SYSTEM_PROMPT, prompt]
    if pil_image:
        full_prompt.append(pil_image)
        
    try:
        response = model.generate_content(full_prompt)
        
        # Check response for text and images
        result_text = ""
        result_image = None
        
        # Process all parts of the response
        if hasattr(response, 'parts'):
            for part in response.parts:
                if hasattr(part, 'text') and part.text:
                    result_text += part.text + "\n"
                elif hasattr(part, 'inline_data') and part.inline_data:
                    # Image data found in inline_data
                    image_data = part.inline_data.data
                    # Convert to base64 for storage/transmission
                    result_image = base64.b64encode(image_data).decode('utf-8')
                    logger.info("Found image in response.inline_data")
                elif hasattr(part, 'image') and part.image:
                    # Alternative image format
                    if hasattr(part.image, 'data'):
                        image_data = part.image.data
                        result_image = base64.b64encode(image_data).decode('utf-8')
                        logger.info("Found image in response.image.data")
        
        # If no text but we have response, try getting text directly
        if not result_text and hasattr(response, 'text'):
            result_text = response.text or ""
        
        # Log what we found
        if result_image:
            logger.info("Gemini generated an image - image data length: %d", len(result_image) if result_image else 0)
        else:
            logger.info("Gemini response contains text only (no image found)")
            # Debug: log response structure
            logger.debug("Response type: %s, has parts: %s", type(response), hasattr(response, 'parts'))
            if hasattr(response, 'parts'):
                logger.debug("Number of parts: %d", len(response.parts))
                for i, part in enumerate(response.parts):
                    logger.debug("Part %d attributes: %s", i, dir(part))
        
        return {
            "text": result_text.strip() if result_text else ("Generated successfully." if result_image else "No response generated."),
            "image": result_image
        }
    except Exception as e:
        return {"text": f"Gemini Error: {str(e)}", "image": None}

import logging
import tempfile
import os
from typing import Optional, Tuple
from django.conf import settings
from .schemas import GuardrailResult, StructuredRequest
from . import (
    text_injection,
    text_policy,
    text_food_domain,
    image_hygiene,
    image_nsfw,
    image_food_clip,
    cache
)

logger = logging.getLogger(__name__)

# Pattern to detect use case 1: image analysis with specific prompt
IMAGE_ANALYSIS_PROMPT_PATTERNS = [
    "generate image with this image attached in center of the background",
    "generate image with this image attached in center",
    "generate image with this image in center",
    "create image with this image in center",
]

class GuardrailEngine:
    def _is_image_analysis_use_case(self, prompt: str, image_bytes: Optional[bytes]) -> bool:
        """
        Detect if this is use case 1: Image analysis with specific prompt.
        Returns True if image is provided and prompt matches the pattern.
        """
        if not image_bytes:
            return False
        
        prompt_lower = prompt.lower().strip()
        return any(pattern.lower() in prompt_lower for pattern in IMAGE_ANALYSIS_PROMPT_PATTERNS)
    
    def process_image_analysis(self, prompt: str, image_bytes: bytes, request_hash: str) -> GuardrailResult:
        """
        Use Case 1: Analyze the uploaded image for food context.
        Prompt is expected to be "generate image with this image attached in center of the background".
        Focus: Check if image is food-related, then approve/block.
        """
        logger.info("Processing Use Case 1: Image Analysis")
        
        pil_image = None
        image_scores = {}
        
        # 1. Image Hygiene Check
        res = image_hygiene.check_hygiene(image_bytes)
        if res.status == "BLOCK":
            return self._block(res.reasons, request_hash)
        
        pil_image = res.metadata.get("pil_image")
        
        # 2. Save to temp file for NudeNet
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            pil_image.save(tmp, format="JPEG")
            tmp_path = tmp.name
            
        try:
            # 3. NSFW Check
            res = image_nsfw.check_nsfw(tmp_path)
            if res.status == "BLOCK":
                return self._block(res.reasons, request_hash, res.scores)
            image_scores.update(res.scores)
            
            # 4. Food CLIP Check - This is the main check for business context
            res = image_food_clip.check_food_clip(pil_image)
            if res.status == "BLOCK":
                return self._block(res.reasons, request_hash, res.scores)
            image_scores.update(res.scores)
            
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # PASS - Image is food-related
        final_result = GuardrailResult(
            status="PASS",
            scores=image_scores,
            metadata={"pil_image": pil_image, "use_case": "image_analysis"}
        )
        
        # Cache the success
        cache_decision = GuardrailResult(
            status="PASS",
            scores=final_result.scores
        )
        cache.cache_decision(request_hash, cache_decision)
        
        return final_result
    
    def process_prompt_analysis(self, prompt: str, image_bytes: Optional[bytes], request_hash: str) -> GuardrailResult:
        """
        Use Case 2: Analyze user prompt for generating images.
        Focus: Check prompt for restrictions and food domain context.
        Note: No image processing for this use case - prompt-only analysis.
        """
        logger.info("Processing Use Case 2: Prompt Analysis")
        
        # 1. Hard Caps (Text)
        if len(prompt) > settings.GUARDRAILS_MAX_PROMPT_CHARS:
            return self._block("Prompt too long", request_hash)

        # 2. Text Injection
        res = text_injection.check_injection(prompt)
        if res.status == "BLOCK":
            return self._block(res.reasons, request_hash)

        # 3. Text Policy
        res = text_policy.check_policy(prompt)
        if res.status == "BLOCK":
            return self._block(res.reasons, request_hash)

        # 4. Food Domain (Text) - Main check for business context
        res = text_food_domain.check_food_domain(prompt)
        if res.status == "BLOCK":
            return self._block(res.reasons, request_hash, res.scores)
        
        domain_scores = res.scores

        # PASS - No image processing for prompt analysis use case
        final_result = GuardrailResult(
            status="PASS",
            scores=domain_scores,
            metadata={"use_case": "prompt_analysis"}
        )
        
        # Cache the success
        cache_decision = GuardrailResult(
            status="PASS",
            scores=final_result.scores
        )
        cache.cache_decision(request_hash, cache_decision)
        
        return final_result
    
    def process_request(self, prompt: str, image_bytes: Optional[bytes] = None) -> GuardrailResult:
        """
        Main entry point for the guardrail pipeline.
        Routes to appropriate use case:
        - Use Case 1: Image analysis (when image provided with specific prompt)
        - Use Case 2: Prompt analysis (analyze user prompts for restrictions)
        Returns a GuardrailResult with status="PASS" or "BLOCK".
        """
        
        # 0. Compute Hash & Check Cache
        image_hash = None
        if image_bytes:
            import hashlib
            image_hash = hashlib.sha256(image_bytes).hexdigest()
            
        request_hash = cache.compute_hash(prompt, image_hash)
        cached_result = cache.get_cached_decision(request_hash)
        if cached_result:
            logger.info(f"Cache hit for {request_hash}")
            return cached_result

        # Route to appropriate use case
        if self._is_image_analysis_use_case(prompt, image_bytes):
            return self.process_image_analysis(prompt, image_bytes, request_hash)
        else:
            return self.process_prompt_analysis(prompt, image_bytes, request_hash)

    def _block(self, reasons, request_hash, scores=None):
        if isinstance(reasons, str):
            reasons = [reasons]
        result = GuardrailResult(status="BLOCK", reasons=reasons, scores=scores or {})
        cache.cache_decision(request_hash, result)
        return result

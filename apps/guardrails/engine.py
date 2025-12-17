import logging
from typing import Optional
from django.conf import settings
from .schemas import GuardrailResult
from . import (
    text_injection,
    text_policy,
    text_food_domain,
    image_hygiene,
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
        Focus: Check if image is food-related, identify food type, then approve/block.
        CLIP check handles both food detection and NSFW detection via negative labels.
        Returns identified food type (pizza, cake, etc.) in scores and metadata.
        """
        logger.info("Processing Use Case 1: Image Analysis with Food Identification")
        
        pil_image = None
        image_scores = {}
        
        # 1. Image Hygiene Check
        res = image_hygiene.check_hygiene(image_bytes)
        if res.status == "BLOCK":
            return self._block(res.reasons, request_hash)
        
        pil_image = res.metadata.get("pil_image")
        
        # 2. Food CLIP Check - Handles food detection, NSFW detection, AND food type identification
        # identify_type=True ensures we get what kind of food it is (pizza, cake, etc.)
        res = image_food_clip.check_food_clip(pil_image, identify_type=True)
        if res.status == "BLOCK":
            return self._block(res.reasons, request_hash, res.scores)
        
        image_scores.update(res.scores)
        
        # Get food identification metadata
        food_identification = res.metadata.get("food_identification", {})
        
        logger.info(f"Food identified: {food_identification.get('food_type', 'unknown')} "
                   f"(confidence: {food_identification.get('confidence', 0):.1f}%)")

        # PASS - Image is food-related with identification
        final_result = GuardrailResult(
            status="PASS",
            scores=image_scores,
            metadata={
                "pil_image": pil_image, 
                "use_case": "image_analysis",
                "food_identification": food_identification
            }
        )
        
        # Cache the success (without pil_image for serialization)
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
        If image is provided (optional), it must ALSO pass food validation.
        Both prompt AND image (if present) must be approved for PASS.
        """
        logger.info(f"Processing Use Case 2: Prompt Analysis (image provided: {image_bytes is not None})")
        
        combined_scores = {}
        pil_image = None
        food_identification = None
        
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
        
        combined_scores.update(res.scores)
        
        # 5. OPTIONAL: If image is provided, validate it too
        # Both prompt AND image must pass for approval
        if image_bytes:
            logger.info("Use Case 2: Validating optional image attachment")
            
            # 5a. Image Hygiene Check
            res = image_hygiene.check_hygiene(image_bytes)
            if res.status == "BLOCK":
                return self._block(["Image validation failed: " + r for r in res.reasons], request_hash)
            
            pil_image = res.metadata.get("pil_image")
            
            # 5b. Food CLIP Check with food type identification
            res = image_food_clip.check_food_clip(pil_image, identify_type=True)
            if res.status == "BLOCK":
                return self._block(["Image validation failed: " + r for r in res.reasons], request_hash, res.scores)
            
            # Add image scores with prefix to distinguish from prompt scores
            combined_scores["image_food_score"] = res.scores.get("food_score", 0)
            combined_scores["image_non_food_score"] = res.scores.get("non_food_score", 0)
            combined_scores["image_identified_food"] = res.scores.get("identified_food", "unknown")
            combined_scores["image_food_type_confidence"] = res.scores.get("food_type_confidence", 0)
            
            food_identification = res.metadata.get("food_identification", {})
            
            logger.info(f"Image passed validation - Food: {food_identification.get('food_type', 'unknown')}")

        # PASS - Both prompt and image (if provided) passed validation
        metadata = {"use_case": "prompt_analysis"}
        if pil_image:
            metadata["pil_image"] = pil_image
            metadata["has_image"] = True
            metadata["food_identification"] = food_identification
        else:
            metadata["has_image"] = False
        
        final_result = GuardrailResult(
            status="PASS",
            scores=combined_scores,
            metadata=metadata
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
          - Validates image is food-related
          - Identifies what TYPE of food (pizza, cake, etc.)
        - Use Case 2: Prompt analysis (analyze user prompts for restrictions)
          - Validates prompt is food-related
          - If optional image provided, BOTH must pass validation
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

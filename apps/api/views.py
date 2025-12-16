from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import GenerationRequest
from .serializers import GenerationRequestSerializer
from apps.guardrails.engine import GuardrailEngine
from apps.nano_banana.client import generate_content
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_request_task(request_id, prompt, image_bytes_list=None):
    """
    Async task to process the request.
    image_bytes_list is a list of integers (bytes) because Celery JSON serialization.
    """
    try:
        req = GenerationRequest.objects.get(id=request_id)
        req.status = 'PROCESSING'
        req.save()
        
        image_bytes = bytes(image_bytes_list) if image_bytes_list else None
        
        engine = GuardrailEngine()
        result = engine.process_request(prompt, image_bytes)
        
        req.status = result.status
        req.reasons = result.reasons
        req.scores = result.scores
        req.save()
        
        if result.status == 'PASS':
            # Call Gemini
            # If image passed, we need to re-open it or pass bytes. 
            # The engine returns PIL image in metadata if passed.
            pil_image = result.metadata.get('pil_image')
            use_case = result.metadata.get('use_case', 'prompt_analysis')
            
            # For use case 1 (image analysis), use the standard prompt for nano_banana
            # For use case 2 (prompt analysis), use the user's prompt
            prompt_for_gemini = prompt
            if use_case == 'image_analysis':
                # Use the standard prompt for image generation
                prompt_for_gemini = "generate image with this image attached in center of the background"
                logger.info("Use Case 1: Using standard prompt for image generation")
            else:
                logger.info("Use Case 2: Using user prompt for generation")
            
            gemini_response = generate_content(prompt_for_gemini, pil_image)
            # Handle both old string format and new dict format
            if isinstance(gemini_response, dict):
                req.result_text = gemini_response.get('text', '')
                req.result_image = gemini_response.get('image')
            else:
                # Backward compatibility with old string format
                req.result_text = gemini_response
            req.save()
            
    except Exception as e:
        logger.error(f"Task failed: {e}")
        req = GenerationRequest.objects.get(id=request_id)
        req.status = 'ERROR'
        req.reasons = [str(e)]
        req.save()

class GenerateView(APIView):
    def post(self, request):
        prompt = request.data.get('prompt')
        image_file = request.FILES.get('image')
        
        if not prompt:
            return Response({"error": "Prompt is required"}, status=status.HTTP_400_BAD_REQUEST)
            
        # Create DB entry
        req = GenerationRequest.objects.create(prompt=prompt)
        
        # Read image bytes if present
        image_bytes = None
        if image_file:
            image_bytes = image_file.read()
            # Basic size check before queuing
            if len(image_bytes) > 5 * 1024 * 1024:
                 req.status = 'BLOCK'
                 req.reasons = ["Image too large (pre-check)"]
                 req.save()
                 return Response(GenerationRequestSerializer(req).data)

        # Convert bytes to list for JSON serialization if needed, or handle better
        # For simplicity in this demo, passing small images via Celery args is okay-ish, 
        # but for prod, save to disk/S3 and pass path.
        # Given "single VPS" requirement, let's save to tmp and pass path? 
        # Or just pass bytes if < 5MB. 5MB is small enough for Redis/Celery usually.
        
        image_bytes_list = list(image_bytes) if image_bytes else None
        
        # Queue task - use apply() in eager mode to execute synchronously without broker
        from django.conf import settings
        if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
            # In eager mode, use apply() to execute synchronously and avoid broker connection
            process_request_task.apply(args=[req.id, prompt, image_bytes_list])
        else:
            # Normal async execution
            process_request_task.delay(req.id, prompt, image_bytes_list)
        
        return Response(GenerationRequestSerializer(req).data)

class StatusView(APIView):
    def get(self, request, request_id):
        req = get_object_or_404(GenerationRequest, id=request_id)
        return Response(GenerationRequestSerializer(req).data)

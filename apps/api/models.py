from django.db import models
import uuid

class GenerationRequest(models.Model):
    STATUS_CHOICES = [
        ('QUEUED', 'Queued'),
        ('PROCESSING', 'Processing'),
        ('PASS', 'Pass'),
        ('BLOCK', 'Block'),
        ('ERROR', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    prompt = models.TextField()
    image_hash = models.CharField(max_length=64, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='QUEUED')
    reasons = models.JSONField(default=list, blank=True)
    scores = models.JSONField(default=dict, blank=True)
    
    result_text = models.TextField(null=True, blank=True)
    result_image = models.TextField(null=True, blank=True)  # Base64 encoded image
    
    def __str__(self):
        return f"{self.id} - {self.status}"

from rest_framework import serializers
from .models import GenerationRequest

class GenerationRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationRequest
        fields = ['id', 'status', 'reasons', 'scores', 'result_text', 'result_image', 'created_at']

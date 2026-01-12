from rest_framework import serializers
from django.contrib.auth import authenticate
from account.models import UserAPIKey


class GenerateApiKeySerializer(serializers.Serializer):
    key_name = serializers.CharField()
    
    def validate_key_name(self, value):
        # Note: user will be available in the view, but we can't access it here in the serializer
        # The view should handle user-specific validation
        return value


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAPIKey
        fields = ['id', 'name', 'created', 'revoked', 'key_type', 'plain_api_key']
        read_only_fields = fields


class ApiKeyActionSerializer(serializers.Serializer):
    key_id = serializers.CharField()

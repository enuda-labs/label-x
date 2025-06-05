from rest_framework import serializers
from django.contrib.auth import authenticate
from account.models import UserAPIKey


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAPIKey
        fields = ['id', 'name', 'created', 'revoked', 'key_type', 'plain_api_key']
        read_only_fields = fields


class ApiKeyActionSerializer(serializers.Serializer):
    key_id = serializers.CharField()

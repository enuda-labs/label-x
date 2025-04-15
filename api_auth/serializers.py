from rest_framework import serializers
from django.contrib.auth import authenticate
from account.models import UserAPIKey


class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserAPIKey
        fields = ['id', 'name', 'created', 'revoked']
        read_only_fields = fields


class ApiKeyActionSerializer(serializers.Serializer):
    """Serializer for user login"""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    key_id = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])
        print(user)
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("User is not active")
        return {
            "user": user,
            "key_id": data['key_id']
        }

import uuid
from rest_framework.permissions import BasePermission
from django.utils import timezone
from django.conf import settings
import datetime
import jwt
from cryptography.fernet import Fernet
import base64
import json
from .models import ApiKeyTypeChoices, UserAPIKey
from rest_framework_api_key.permissions import BaseHasAPIKey

class IsSuperAdmin(BasePermission):
    """Allow access to only users mark as admin"""

    def has_permission(self, request, view):
        return (
            request.user and request.user.is_authenticated and request.user.is_superuser
        )


class IsAdminUser(BasePermission):
    """Allow access to only users mark as admin"""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_admin


class IsReviewer(BasePermission):
    """
    Allows access only to users marked as reviewers.
    """

    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and request.user.is_reviewer
        )

class HasUserAPIKey(BaseHasAPIKey):
    model = UserAPIKey
    def has_permission(self, request, view):
        has_api_key_permission = super().has_permission(request, view)
        if not has_api_key_permission:
            return False
        
        key = self.get_key(request)
        if not key:
            return False

        api_key = self.model.objects.get_from_key(key)
        request.user = api_key.user
        request.is_test_key = api_key.key_type == ApiKeyTypeChoices.DEVELOPMENT
        return True

def generate_stateless_api_key(user, expiry_days=30):
    """Generates a stateless api key with embedded user information"""
    key_id = str(uuid.uuid4())

    expiry_date = timezone.now() + datetime.timedelta(days=expiry_days)

    payload = {
        "pid": str(user.pid),
        "username": user.username,
        "key_id": key_id,
        "exp": expiry_date.timestamp(),
    }

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return {"key": token, "expires_at": expiry_date}


def create_api_key_for_uer(user, name="Default", key_type="production"):
    api_key, key = UserAPIKey.objects.create_key(name=name, user=user, key_type=key_type)
    api_key.plain_api_key = key
    api_key.save(update_fields=["plain_api_key"])
    return api_key, key
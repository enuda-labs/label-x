from httpx import delete
from rest_framework import generics
from account.serializers import LoginSerializer
from rest_framework.response import Response
from account.models import UserAPIKey
from account.utils import create_api_key_for_uer, HasUserAPIKey
from rest_framework import status
import logging
from datetime import datetime

from api_auth.serializers import APIKeySerializer, ApiKeyActionSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny

from common.responses import ErrorResponse, SuccessResponse
from drf_spectacular.utils import extend_schema

logger = logging.getLogger('api_auth.apis')

class ViewApiKeyView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            api_keys = UserAPIKey.objects.filter(user=user)
            api_key_serializer = APIKeySerializer(api_keys, many=True)
            logger.info(f"User '{user.username}' viewed their API keys at {datetime.now()}")
            return SuccessResponse(data=api_key_serializer.data)

        logger.warning(f"Failed API key view attempt with invalid credentials at {datetime.now()}")
        return ErrorResponse(message="Invalid login credentials")


class DeleteApiKey(generics.DestroyAPIView):
    serializer_class = ApiKeyActionSerializer
    permission_classes = [AllowAny]
    def destroy(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data.get('user')
            key_id = serializer.validated_data.get('key_id')
            
            try:
                api_key = UserAPIKey.objects.get(id=key_id, user=user)
                api_key.revoked = True
                api_key.save()
                logger.info(f"User '{user.username}' revoked API key {key_id} at {datetime.now()}")
                return SuccessResponse(message="API key revoked successfully")
            except UserAPIKey.DoesNotExist:
                logger.warning(f"User '{user.username}' attempted to revoke non-existent API key {key_id} at {datetime.now()}")
                return ErrorResponse(message="API key not found")
        
        logger.warning(f"Failed API key revocation attempt with invalid credentials at {datetime.now()}")
        return ErrorResponse(message="Invalid credentials")


class RollApiKey(generics.GenericAPIView):
    """
    Revoke the api key with the provided key_id and create a new one 
    
    ---
    """

    serializer_class = ApiKeyActionSerializer
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data.get('user')
            key_id = serializer.validated_data.get('key_id')

            try:
                api_key = UserAPIKey.objects.get(id=key_id, user=user)
                if api_key.revoked:
                    logger.warning(f"User '{user.username}' attempted to roll revoked API key {key_id} at {datetime.now()}")
                    return ErrorResponse(message="You can only roll active API keys")
                api_key.revoked = True
                api_key.save()
                new_api_key, key = create_api_key_for_uer(user, user.username)
                logger.info(f"User '{user.username}' rolled API key {key_id} to new key {new_api_key.id} at {datetime.now()}")
                return SuccessResponse(
                    data={
                        "id": api_key.id,
                        "name": api_key.name,
                        "api_key": key,
                        "created": api_key.created,
                        "message": "Please keep your api key safe, you will not be able to retrieve it again",
                    },
                    status=status.HTTP_201_CREATED,
                )
            except UserAPIKey.DoesNotExist:
                logger.warning(f"User '{user.username}' attempted to roll non-existent API key {key_id} at {datetime.now()}")
                return ErrorResponse(message="Api key not found")


class GenerateApiKeyView(generics.GenericAPIView):
    permission_classes = []
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="Generate a new api key for the currently logged in user"
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            if UserAPIKey.objects.filter(user=user, revoked=False).exists():
                logger.warning(f"User '{user.username}' attempted to generate new API key while having active keys at {datetime.now()}")
                return ErrorResponse(message="You already have an active api key")
            api_key, key = create_api_key_for_uer(user, user.username)
            logger.info(f"User '{user.username}' generated new API key {api_key.id} at {datetime.now()}")

            return SuccessResponse(
                data={
                    "id": api_key.id,
                    "name": api_key.name,
                    "api_key": key,
                    "created": api_key.created,
                    "message": "Please keep your api key safe, you will not be able to retrieve it again",
                },
                status=status.HTTP_201_CREATED,
            )

        logger.warning(f"Failed API key generation attempt with invalid credentials at {datetime.now()}")
        return ErrorResponse(
            message="Invalid credentials", status=status.HTTP_401_UNAUTHORIZED
        )

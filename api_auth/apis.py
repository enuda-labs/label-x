from httpx import delete
from rest_framework import generics
from account.serializers import LoginSerializer
from rest_framework.response import Response
from account.models import UserAPIKey
from account.utils import create_api_key_for_uer, HasUserAPIKey
from rest_framework import status

from api_auth.serializers import APIKeySerializer, ApiKeyActionSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny

from common.responses import ErrorResponse, SuccessResponse



class ViewApiKeyView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            api_keys = UserAPIKey.objects.filter(user=user)
            api_key_serializer = APIKeySerializer(api_keys, many=True)
            return SuccessResponse(data=api_key_serializer.data)

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
                return SuccessResponse(message="API key revoked successfully")
            except UserAPIKey.DoesNotExist:
                return ErrorResponse(message="API key not found")
        
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
                    return ErrorResponse(message="You can only roll active API keys")
                api_key.revoked = True
                api_key.save()
                api_key, key = create_api_key_for_uer(user, user.username)
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
                return ErrorResponse(message="Api key not found")


class GenerateApiKeyView(generics.GenericAPIView):
    """
    Generate an api key

    ---
    """

    permission_classes = []
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            if UserAPIKey.objects.filter(user=user, revoked=False).exists():
                return ErrorResponse(message="You already have an active api key")
            api_key, key = create_api_key_for_uer(user, user.username)

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

        return ErrorResponse(
            message="Invalid credentials", status=status.HTTP_401_UNAUTHORIZED
        )

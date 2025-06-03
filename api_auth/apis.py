from httpx import delete
from rest_framework import generics
from account.serializers import LoginSerializer
from rest_framework.response import Response
from account.models import ApiKeyTypeChoices, UserAPIKey
from account.utils import create_api_key_for_uer, HasUserAPIKey
from rest_framework import status
import logging
from datetime import datetime

from api_auth.serializers import APIKeySerializer, ApiKeyActionSerializer
from rest_framework.permissions import IsAuthenticated, AllowAny

from common.responses import ErrorResponse, SuccessResponse
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework.views import APIView

logger = logging.getLogger('api_auth.apis')

class ViewApiKeyView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        user = request.user
        api_keys = UserAPIKey.objects.filter(user=user)
        api_key_serializer = APIKeySerializer(api_keys, many=True)
        logger.info(f"User '{user.username}' viewed their API keys at {datetime.now()}")
        return SuccessResponse(data=api_key_serializer.data)


class DeleteApiKey(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    def destroy(self, request, *args, **kwargs):
        user = request.user
        key_id = kwargs.get('key_id')
        
        try:
            api_key = UserAPIKey.objects.get(id=key_id, user=user)
            api_key.revoked = True
            api_key.save()
            logger.info(f"User '{user.username}' revoked API key {key_id} at {datetime.now()}")
            return SuccessResponse(message="API key revoked successfully")
        except UserAPIKey.DoesNotExist:
            logger.warning(f"User '{user.username}' attempted to revoke non-existent API key {key_id} at {datetime.now()}")
            return ErrorResponse(message="API key not found")
        


class RollApiKey(generics.GenericAPIView):
    """
    Revoke the api key with the provided key_id and create a new one 
    
    ---
    """

    serializer_class = ApiKeyActionSerializer
    permission_classes = [IsAuthenticated]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            key_id = serializer.validated_data.get('key_id')

            try:
                api_key = UserAPIKey.objects.get(id=key_id, user=user)
                if api_key.revoked:
                    logger.warning(f"User '{user.username}' attempted to roll revoked API key {key_id} at {datetime.now()}")
                    return ErrorResponse(message="You can only roll active API keys")
                api_key.revoked = True
                api_key.save()
                new_api_key, key = create_api_key_for_uer(user, user.username, api_key.key_type)
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
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Generate a new api key for the user",
        description="This endpoint generates either a production or development api key for the user after they have provided their username and password",
        parameters=[
            OpenApiParameter(
                name="key_type",
                location=OpenApiParameter.PATH,
                required=True,
                enum=ApiKeyTypeChoices.values,
                description="The type of api key to be generated (either production or test)"
            )
        ]
    )
    def post(self, request, key_type, *args, **kwargs):
        if key_type not in ApiKeyTypeChoices.values:
            return ErrorResponse(message="Invalid key type")
        
        
        user = request.user
        if UserAPIKey.objects.filter(user=user, revoked=False, key_type=key_type).exists():
            logger.warning(f"User '{user.username}' attempted to generate new {key_type} API key while having active keys at {datetime.now()}")
            return ErrorResponse(message=f"You already have an active {key_type} api key")
        api_key, key = create_api_key_for_uer(user, user.username, key_type)
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



import token
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from urllib.parse import parse_qs
from rest_framework_simplejwt.tokens import UntypedToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from account.models import CustomUser, UserAPIKey


@database_sync_to_async
def get_user(user_id):
    try:
        return CustomUser.objects.get(id=user_id)
    except CustomUser.DoesNotExist:
        return AnonymousUser()

@database_sync_to_async
def get_user_from_key(key):
    try:
        user_api_key = UserAPIKey.objects.get_from_key(key)
        if user_api_key.has_expired or user_api_key.revoked:
            return None
        return user_api_key.user
    except Exception:
        return None


class JWTAuthMiddleWare(BaseMiddleware):
    """
    JWT Authentication Middleware for WebSocket connections.

    This middleware authenticates WebSocket connections using JWT tokens passed as URL query parameters.
    It extracts the token, validates it, and sets the authenticated user on the connection scope.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope[
            "query_string"
        ].decode()  # decode() converts a byte string to a regular string
        query_params = parse_qs(
            query_string
        )  # passing query string from a url into a dictionary
        token = query_params.get("token", [None])[0]

        if token:
            try:
                user_id = UntypedToken(token=token)[
                    "user_id"
                ]  # decodinig the jwt token to get the userid
                scope["user"] = await get_user(user_id)

            except (InvalidToken, TokenError) as e:
                scope["user"] = AnonymousUser()
        else:
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)


class ApiKeyMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope["query_string"].decode()
        query_params = parse_qs(query_string)
        api_key = query_params.get("api_key", [None])[0]
        
        if api_key:
            user = await get_user_from_key(api_key)
            if user:
                scope["user"] = user
            else:
                scope["user"] = AnonymousUser()
        else:
            scope['user'] = AnonymousUser()
        return await super().__call__(scope, receive, send)
    

class HybridAuthentication(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope['query_string'].decode()
        query_params = parse_qs(query_string)


        api_key = query_params.get('token', [None])[0]
        if api_key:
            user = await get_user_from_key(api_key)
            if user:
                scope["user"] = user
            else:
                scope["user"] = AnonymousUser()
                
                    
        token = query_params.get('token', [None])[0]
        if token:
            try:
                user_id = UntypedToken(token=token)[
                    "user_id"
                ]
                scope["user"] = await get_user(user_id)

            except (InvalidToken, TokenError) as e:
                scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)            
        
        
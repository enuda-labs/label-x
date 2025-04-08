
from django.db import IntegrityError
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import CustomUser
from .serializers import UserSerializer, LoginSerializer, RegisterSerializer, TokenRefreshResponseSerializer, TokenRefreshSerializer,RegisterReviewerSerializer

class LoginView(APIView):
    """User login view to generate JWT token"""
    permission_classes = [AllowAny]
    
    @extend_schema(
        summary="User Login",
        description="Authenticate user and return access & refresh tokens.",
        request=LoginSerializer,  # This tells Swagger the expected request format
        responses={
            200: UserSerializer,  # Document the response structure
            401: {"status":"error", "error": "Invalid credentials....."},
        }
    )

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)

            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user_data": UserSerializer(user).data
            })
            
        return Response({
                'status': 'error',
                'error': "Invalid Credentials"
            }, status=status.HTTP_401_UNAUTHORIZED)
        


class RegisterView(APIView):
    """User registration endpoint"""
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new user",
        description="Creates a new user account with username, email, and password.",
        request=RegisterSerializer,
        responses={201: RegisterSerializer}
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'status': 'success',
                'user_data': RegisterSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        
        # Custom error messages for validation errors
        
        error_message = ""
        if 'username' in serializer.errors:
            error_message = "Username already exists"
        elif 'email' in serializer.errors:
            error_message = "Email already exists"
        elif 'password' in serializer.errors:
            error_message = serializer.errors['password'][0]
        else:
            error_message = "Invalid data provided"

        return Response({
            'status': 'error',
            'error': error_message
        }, status=status.HTTP_400_BAD_REQUEST)
        

class RegisterReviewerView(APIView):
    """API view for creating a new reviewer user"""
    permission_classes = [AllowAny]  # Make this accessible to everyone

    @extend_schema(
        summary="Register a new reviewer",
        description="This endpoint allows you to register a new user who will be marked as a reviewer.",
        request=RegisterReviewerSerializer,  # Specify the request schema
        responses={201: RegisterReviewerSerializer, 400: "Invalid data provided"}
    )
    def post(self, request):
        # Use the RegisterReviewerSerializer to create a new reviewer
        serializer = RegisterReviewerSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.save()  # Save the user as a reviewer
            return Response({
                'status': 'success',
                'user_data': RegisterReviewerSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        
        # If the serializer is not valid, return the error
        return Response({
            'status': 'error',
            'error': "Invalid data provided",
            'details': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom refresh token endpoint with drf-spectacular documentation.
    """

    @extend_schema(
        summary="Refresh JWT access token",
        description="Exchanges a refresh token for a new access token.",
        request=TokenRefreshSerializer,
        responses={
            200: OpenApiResponse(
                response=TokenRefreshResponseSerializer,
                description="A new access token is returned.",
            ),
            400: OpenApiResponse(description="Invalid or expired refresh token."),
        },
        examples=[
            OpenApiExample(
                "Valid Request",
                value={"refresh": "your_refresh_token_here"},
                request_only=True,
            ),
            OpenApiExample(
                "Successful Response",
                value={"access": "new_access_token_here", "refresh": "new_refresh_token_here"},
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            return Response({
                "status": "success",
                "access": response.data["access"],
                "refresh": response.data.get("refresh", ""),
            }, status=status.HTTP_200_OK)
        
        except AuthenticationFailed as e:  # Catch invalid token error
            return Response(
                {
                    "status": "error",
                    "error": "Your session has expired. Please log in again."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )



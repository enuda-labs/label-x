
from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser
from .serializers import UserSerializer, LoginSerializer, RegisterSerializer

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



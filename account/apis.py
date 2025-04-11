
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView


from .serializers import UserSerializer, LoginSerializer, RegisterSerializer, TokenRefreshResponseSerializer, TokenRefreshSerializer,MakeReviewerSerializer, ProjectCreateSerializer
from .utils import IsAdminUser
from .models import Project

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
        

class MakeUserReviewerView(APIView):
    """ view to upgrade a user to reviewer """
    permission_classes = [IsAdminUser]
    
    @extend_schema(
    request=MakeReviewerSerializer,
    responses={200: None}
    )

    def post(self, request):
        """
        Admin-only: Promote a user to reviewer and assign them to a reviewer group.
        Expects POST data: {"user_id": 5, "group_id": 1}
        """
        serializer = MakeReviewerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user_id']
        group = serializer.validated_data['group_id']

        user.is_reviewer = True
        user.save()
        group.reviewers.add(user)
        group.save()
        

        return Response({
            "status": "success",
            "detail": f"User '{user.username}' is now a reviewer in group '{group.name}'."
        }, status=status.HTTP_200_OK)

class CreateProjectView(generics.CreateAPIView):
    queryset = Project.objects.all()
    serializer_class = ProjectCreateSerializer
    permission_classes = [IsAdminUser]
    

class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom refresh token endpoint with drf-spectacular documentation.
    """

    @extend_schema(
        summary="Refresh JWT access token",
        description="Exchanges a refresh token for a new access token.",
        request=TokenRefreshSerializer,
         responses={
            200:TokenRefreshResponseSerializer,  # Document the response structure
            401: {"status":"error", "detail": "Invalid credentials....."},
        }
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
                    "detail": "Your session has expired. Please log in again."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )


from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .utils import IsAdminUser, IsSuperAdmin
from .serializers import (
    LoginSerializer,
    MakeAdminSerializer,
    MakeReviewerSerializer,
    ProjectCreateSerializer,
    ProjectListResponseSerializer,
    RegisterSerializer,
    RevokeReviewerSerializer,
    SimpleUserSerializer,
    SuccessDetailResponseSerializer,
    TokenRefreshResponseSerializer,
    TokenRefreshSerializer,
    UserDetailResponseSerializer,
    UserDetailSerializer,
    UserListResponseSerializer,
    UserProjectSerializer,
    UserSerializer,
)
from .utils import (
    HasUserAPIKey,
    IsAdminUser,
    IsSuperAdmin,
)
from .models import CustomUser, Project


class LoginView(APIView):
    """User login view to generate JWT token"""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="User Login",
        description="Authenticate user and return access & refresh tokens.",
        request=LoginSerializer,  # This tells Swagger the expected request format
        responses={
            200: UserSerializer,  # Document the response structure
            401: {"status": "error", "error": "Invalid credentials....."},
        },
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user_data": UserSerializer(user).data,
                }
            )

        return Response(
            {"status": "error", "error": "Invalid Credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


class RegisterView(APIView):
    """User registration endpoint"""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="Register a new user",
        description="Creates a new user account with username, email, and password.",
        request=RegisterSerializer,
        responses={201: RegisterSerializer},
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"status": "success", "user_data": RegisterSerializer(user).data},
                status=status.HTTP_201_CREATED,
            )

        # Custom error messages for validation errors

        error_message = ""
        if "username" in serializer.errors:
            error_message = "Username already exists"
        elif "email" in serializer.errors:
            error_message = "Email already exists"
        elif "password" in serializer.errors:
            error_message = serializer.errors["password"][0]
        else:
            error_message = "Invalid data provided"

        return Response(
            {"status": "error", "error": error_message},
            status=status.HTTP_400_BAD_REQUEST,
        )


class MakeUserAdminView(APIView):
    """view to upgrade a user to reviewer"""

    permission_classes = [IsSuperAdmin]
    
    @extend_schema(
        summary="Promote user to admin",
        description="SuperAdmin-only: Promote a user to admin by enabling `is_admin` and `is_staff` flags.",
        request=MakeAdminSerializer,
         responses={
            200: OpenApiResponse(
                response=SuccessDetailResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Admin Promotion',
                        value={
                            "status": "success",
                            "detail": "User 'alice' is now an admin."
                        },
                        response_only=True
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                "Promote Admin Example",
                value={"user_id": 5},
                request_only=True
            )
        ]
    )


    @extend_schema(request=MakeAdminSerializer, responses={200: None})
    def post(self, request):
        """
        Admin-only: Promote a user to reviewer and assign them to a reviewer group.
        Expects POST data: {"user_id": 5, "group_id": 1}
        """
        serializer = MakeAdminSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user_id"]

        user.is_admin = True
        user.is_staff = True
        user.save()

        return Response(
            {"status": "success", "detail": f"User '{user.username}' is now an admin."},
            status=status.HTTP_200_OK,
        )




class MakeUserReviewerView(APIView):
    """view to upgrade a user to reviewer"""

    permission_classes = [IsAdminUser]
    
    @extend_schema(
        summary="Promote user to reviewer",
        description="Admin-only: Promote a user to reviewer and assign them to a project.",
        request=MakeReviewerSerializer,
        responses={
            200: OpenApiResponse(
                response=SuccessDetailResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Reviewer Promotion',
                        value={
                            "status": "success",
                            "detail": "User 'john_doe' is now a reviewer in project 'Alpha Project'."
                        },
                        response_only=True
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                "Promotion Example",
                value={"user_id": 5, "group_id": 2},
                request_only=True
            )
        ]
    )


    @extend_schema(request=MakeReviewerSerializer, responses={200: None})
    def post(self, request):
        """
        Admin-only: Promote a user to reviewer and assign them to a reviewer group.
        Expects POST data: {"user_id": 5, "group_id": 1}
        """
        serializer = MakeReviewerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user_id"]
        project = serializer.validated_data["group_id"]

        user.is_reviewer = True
        user.project = project
        user.save()
        

        return Response({
            "status": "success",
            "detail": f"User '{user.username}' is now a reviewer in project '{project.name}'."
        }, status=status.HTTP_200_OK)
        
        

class RemoveUserReviewerView(APIView):
    """View to revoke reviewer status from a user"""
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Remove reviewer role from user",
        description="Admin-only: Revoke a user's reviewer status and remove project assignment.",
        request=RevokeReviewerSerializer,
         responses={
            200: OpenApiResponse(
                response=SuccessDetailResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Reviewer Revoked',
                        value={
                            "status": "success",
                            "detail": "User 'Dama' is no longer a reviewer."
                        },
                        response_only=True
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                "Revoke Reviewer Example",
                value={"user_id": 5},
                request_only=True
            )
        ]
    )
    def post(self, request):
        serializer = RevokeReviewerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user_id']
        user.is_reviewer = False
        user.project = None
        user.save()

        return Response({
            "status": "success",
            "detail": f"User '{user.username}' is no longer a reviewer."
        }, status=status.HTTP_200_OK)


        return Response(
            {
                "status": "success",
                "detail": f"User '{user.username}' is now a reviewer in project '{project.name}'.",
            },
            status=status.HTTP_200_OK,
        )



class ListUserProjectView(generics.ListAPIView):
    permission_classes =[IsAuthenticated | HasUserAPIKey]
    serializer_class = UserProjectSerializer
    
    def get_queryset(self):
        return Project.objects.filter(created_by=self.request.user)

class CreateUserProject(generics.CreateAPIView):
    """
    Create a project for the currently logged in user 
    
    ---
    """
    queryset = Project.objects.all()
    permission_classes =[IsAuthenticated | HasUserAPIKey]
    serializer_class = UserProjectSerializer
    
    


class CreateProjectView(generics.CreateAPIView):
    """Endpoint to allow allow admin create project. this is for testing purpose only as 
        project will subsequently be created by the organization"""
    queryset = Project.objects.all()
    serializer_class = ProjectCreateSerializer
    permission_classes = [IsAdminUser]
    
    @extend_schema(
        summary="Create a new project",
        description="Allows an admin user to create a new project by providing a name.(only for testing now)",
        request=ProjectCreateSerializer,
        responses={
            201: OpenApiResponse(
                response=ProjectCreateSerializer,
                examples=[
                    OpenApiExample(
                        'Project Created',
                        value={"id": 3, "name": "Gamma"},
                        response_only=True
                    )
                ]
            )
        },
        examples=[
            OpenApiExample(
                'Create Project Example',
                value={"name": "New Project X"},
                request_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    
    
    
class ProjectListView(APIView):
    """
    Endpoint to list all tasks submitted by the user
    """
    permission_classes = [IsAdminUser]
    
    @extend_schema(
        summary="List all projects",
        description="Returns a list of all projects in the system. Admin access required.",
        responses={
            200: OpenApiResponse(
                response=ProjectListResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Project List',
                        value={
                            "status": "success",
                            "projects": [
                                {"id": 1, "name": "Alpha"},
                                {"id": 2, "name": "Beta"}
                            ]
                        },
                        response_only=True
                    )
                ]
            )
        }
    )

    def get(self, request, *args, **kwargs):
        projects = Project.objects.all()
        serializer = ProjectCreateSerializer(projects, many=True)
        return Response({
            "status": "success",
            "projects": serializer.data,
        }, status=status.HTTP_200_OK)
        
        


class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom refresh token endpoint with drf-spectacular documentation.
    """

    @extend_schema(
        summary="Refresh JWT access token",
        description="Exchanges a refresh token for a new access token.",
        request=TokenRefreshSerializer,
        responses={
            200: TokenRefreshResponseSerializer,  # Document the response structure
            401: {"status": "error", "detail": "Invalid credentials....."},
        },
    )
    def post(self, request, *args, **kwargs):
        try:
            response = super().post(request, *args, **kwargs)
            return Response(
                {
                    "status": "success",
                    "access": response.data["access"],
                    "refresh": response.data.get("refresh", ""),
                },
                status=status.HTTP_200_OK,
            )

        except AuthenticationFailed as e:  # Catch invalid token error
            return Response(
                {
                    "status": "error",
                    "detail": "Your session has expired. Please log in again.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )



class ProjectListView(APIView):
    """
    Endpoint to list all tasks submitted by the user
    """

    permission_classes = [IsAdminUser]

    def get(self, request, *args, **kwargs):
        projects = Project.objects.all()
        serializer = ProjectCreateSerializer(projects, many=True)
        return Response(
            {
                "status": "success",
                "projects": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class UserDetailView(APIView):
    """
    Endpoint to get the authenticated user's detail
    """
    
    @extend_schema(
        summary="Get current authenticated user's details",
        description="Returns the details of the currently authenticated user.",
        responses={
            200: OpenApiResponse(
                response=UserDetailResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Authenticated User Detail',
                        value={
                            "status": "success",
                            "user": {
                                "id": 1,
                                "username": "alice",
                                "email": "alice@example.com",
                                "is_reviewer": True,
                                "is_admin": False,
                                "is_staff": False,
                                "is_superuser": False,
                                "date_joined": "2024-01-01T12:00:00Z",
                                "last_activity": "2024-04-15T10:00:00Z"
                            }
                        },
                        response_only=True
                    )
                ]
            )
        }
    )

    def get(self, request):
        user = request.user
        serializer = UserDetailSerializer(user)
        return Response(
            {"status": "success", "user": serializer.data}, status=status.HTTP_200_OK
        )


class UsersNotInProjectView(APIView):
    permission_classes = [IsAdminUser]
    
    @extend_schema(
        summary="Get users not in a project",
        description="Returns a list of users who are not assigned to any project.",
        parameters=[
            OpenApiParameter(
                name="project_id",
                location=OpenApiParameter.PATH,
                required=True,
                description="ID of the project (not used in logic but required in URL).",
                type=int,
            )
        ],
        responses={
            200: OpenApiResponse(
                response=UserListResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Users Not In Project',
                        value={
                            "status": "success",
                            "users": [
                                {"id": 3, 
                                 'email':"example@mail.com", 
                                 "username": "charlie"}
                            ]
                        },
                        response_only=True
                    )
                ]
            )
        }
    )

    def get(self, request, project_id=None):
        users = CustomUser.objects.filter(project__isnull=True)
        serializer = SimpleUserSerializer(users, many=True)
        return Response({
            "status": "success",
            "users": serializer.data
        }, status=status.HTTP_200_OK)
        
        

class UsersInProjectView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        summary="Get users in a project",
        description="Returns a list of users who are assigned to the specified project.",
        parameters=[
            OpenApiParameter(
                name="project_id",
                location=OpenApiParameter.PATH,
                required=True,
                description="ID of the project to filter users by.",
                type=int,
            ),
        ],
        responses={
            200: OpenApiResponse(
                response=UserListResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Users In Project',
                        value={
                            "status": "success",
                            "users": [
                                {"id": 1,
                                 'email':"example@mail.com", 
                                 "username": "alice"},
                                {"id": 2, 
                                 'email':"example@mail.com", 
                                 "username": "bob"}
                            ]
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def get(self, request, project_id=None):
        if project_id is None:
            return Response({
                "status": "error",
                "message": "Project ID is required"
            }, status=status.HTTP_400_BAD_REQUEST)

        users = CustomUser.objects.filter(project__id=project_id)
        serializer = SimpleUserSerializer(users, many=True)
        return Response({
            "status": "success",
            "users": serializer.data
        }, status=status.HTTP_200_OK)
        return Response(
            {"status": "success", "users": serializer.data}, status=status.HTTP_200_OK
        )

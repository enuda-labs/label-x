import logging
from datetime import datetime
from tokenize import TokenError
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, OpenApiExample, OpenApiResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from common.responses import ErrorResponse, SuccessResponse, format_first_error, get_first_error
from common.utils import get_duration
from subscription.models import UserDataPoints
from subscription.serializers import UserDataPointsSerializer
from task.choices import TaskClusterStatusChoices
from task.models import Task, TaskCluster
from task.serializers import ListReviewersWithClustersSerializer, ProjectUpdateSerializer, TaskSerializer

from .utils import IsAdminUser, IsSuperAdmin, NotReviewer, assign_default_plan
from .serializers import (
    AdminProjectDetailSerializer,
    Disable2faSerializer,
    LoginSerializer,
    LogoutSerializer,
    MakeAdminSerializer,
    MakeReviewerSerializer,
    OtpVerificationSerializer,
    ProjectCreateSerializer,
    ProjectDetailSerializer,
    ProjectListResponseSerializer,
    ProjectSerializer,
    RegisterSerializer,
    RevokeReviewerSerializer,
    SetUserActiveStatusSerializer,
    SimpleUserSerializer,
    SuccessDetailResponseSerializer,
    TokenRefreshResponseSerializer,
    TokenRefreshSerializer,
    UserDetailResponseSerializer,
    UserDetailSerializer,
    UserListResponseSerializer,
    UserProjectSerializer,
    UserSerializer,
    ChangePasswordSerializer,
    UpdateNameSerializer,
)
from .utils import (
    HasUserAPIKey,
    IsAdminUser,
    IsSuperAdmin,
)
from .models import CustomUser, OTPVerification, Project
from django.contrib.auth import logout
# Set up logger
logger = logging.getLogger('account.apis')
from .choices import ProjectStatusChoices
from datetime import datetime
from django.db.models.functions import TruncDate
from django.db.models import Sum, Count, Q, Avg 
from drf_spectacular.openapi import OpenApiTypes


class SetUserActiveStatusView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class= SetUserActiveStatusSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user_id = serializer.validated_data['user_id']
        
        try:
            user= CustomUser.objects.get(id=user_id)
        except CustomUser.DoesNotExist:
            return ErrorResponse(message="User not found", status=status.HTTP_404_NOT_FOUND)
        
        user.is_active = serializer.validated_data['is_active']
        user.save()
        return SuccessResponse(message="User active status updated", data=SimpleUserSerializer(user).data)



class DeactivateUserView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    @extend_schema(
        summary="Deactivate a user",
        description="Deactivate a user, this will prevent the user from logging in to the platform",
        responses={
            200: SuccessResponse,
            404: ErrorResponse
        }
    )
    def post(self, request, *args, **kwargs):
        try:
            user = CustomUser.objects.get(id=kwargs.get('user_id'))
            user.is_active = False
            user.save()
            return SuccessResponse(message="User deactivated")       
        except CustomUser.DoesNotExist:
            return ErrorResponse(message="User not found", status=status.HTTP_404_NOT_FOUND)


class GetReviewersListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = ListReviewersWithClustersSerializer
    def get_queryset(self):
        return CustomUser.objects.prefetch_related("assigned_clusters").filter(is_reviewer=True)
    
    @extend_schema(
        summary="Get a list of reviewers on the platform and task clusters they are assigned to"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class GetProjectChart(generics.GenericAPIView):
    @extend_schema(
        summary='Get Project Chart Data',
        description='''
        Get analytics data for a project over a specified time period.
        
        **Time Period Calculation:**
        The API looks back from today by the specified time_period in the given time_unit.
        
        **Examples:**
        - `time_unit=day, time_period=7` → Data from 7 days ago to today
        - `time_unit=week, time_period=2` → Data from 2 weeks ago to today  
        - `time_unit=month, time_period=3` → Data from 3 months ago to today
        - `time_unit=year, time_period=1` → Data from 1 year ago to today
        ''',
        parameters=[
            OpenApiParameter(
                name='project_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the project to get chart data for',
                required=True
            ),
            OpenApiParameter(
                name='time_unit',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Time unit for the period (day, week, month, year, hour, seconds)',
                required=True,
                enum=['day', 'week', 'month', 'year', 'hour', 'seconds']
            ),
            OpenApiParameter(
                name='time_period',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Number of time units to look back from today',
                required=True
            ),
        ],
        responses={
            200: {
                'description': 'Project chart data retrieved successfully',
                'example': {
                    'message': 'Project charts',
                    'data': {
                        'daily_progress': [
                            {
                                'date': '2025-07-15',
                                'task_count': 10,
                                'total_data_points': 250,
                                'human_reviewed_count': 6
                            }
                        ],
                        'pie_chart_data': {
                            'completed': 45,
                            'pending': 12,
                            'in_progress': 8
                        },
                        'accuracy_trend': [
                            {
                                'date': '2025-07-15',
                                'average_ai_confidence': 87.5
                            }
                        ]
                    }
                }
            },
            404: {
                'description': 'Project not found',
                'example': {
                    'message': 'Project not found'
                }
            }
        },
        tags=['Projects']
    )
    def get(self, request, *args, **kwargs):
        time_unit = kwargs.get('time_unit')
        time_period = kwargs.get('time_period')
        project_id = kwargs.get('project_id')
        
        try:
            project = Project.objects.get(id=int(project_id))
        except Project.DoesNotExist:
            return ErrorResponse(message='Project not found', status=status.HTTP_404_NOT_FOUND)
        
        duration = get_duration(time_unit, time_period)
        
        queryset = Task.objects.filter(created_at__date__gte=duration.date(), created_at__date__lte=datetime.today().date(), cluster__project=project)
        
        clusters = TaskCluster.objects.filter(project=project, created_at__date__gte=duration.date(), created_at__date__lte=datetime.today().date())
        
        
        daily_stats = queryset.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            task_count=Count('id'),
            total_data_points=Sum('used_data_points'),
            human_reviewed_count = Count('id', filter=Q(human_reviewed=True))
        ).order_by('date')
        
        # cluster_daily_stats = clusters.annotate(date=TruncDate('created_at')).values('date').annotate(
        #     task_count=Count('id'),
        #     total_data_points=Sum('tasks__used_data_points'),
        # ).order_by('date')
        
        
        # pie_chart_data= queryset.aggregate(
        #     completed = Count('id', filter=Q(final_label__isnull=False)),
        #     pending = Count('id', filter=Q(processing_status='PENDING')),
        #     in_progress = Count('id', filter=Q(processing_status='PROCESSING')),
        # )
        
        cluster_pie_chart_data = clusters.aggregate(
            completed = Count('id', filter=Q(status=TaskClusterStatusChoices.COMPLETED)),
            pending = Count('id', filter=Q(status=TaskClusterStatusChoices.PENDING)),
            in_progress = Count('id', filter=Q(status=TaskClusterStatusChoices.IN_REVIEW)),
        )
        
        accuracy_trend = queryset.annotate(date=TruncDate('created_at')).values('date').annotate(
            average_ai_confidence = Avg('ai_confidence') * 100
        )

        return SuccessResponse(message="Project charts", data={
            'daily_progress': daily_stats,
            "pie_chart_data": cluster_pie_chart_data,
            'accuracy_trend': accuracy_trend
        }) 
        
        


class GetUserDataPointsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    serializer_class = UserDataPointsSerializer
    
    @extend_schema(
        summary="Get the used and remaining data points for the currently logged in user"
    )
    def get(self, request):
        user_data_points, created = UserDataPoints.objects.get_or_create(user=request.user)
        return SuccessResponse(data=self.get_serializer(user_data_points).data)
    

class AdminProjectDetailView(generics.RetrieveAPIView):
    serializer_class = AdminProjectDetailSerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'id'
    def get_queryset(self):
        return Project.objects.all()
    
    @extend_schema(
        summary="Get the details of a project tailored for admins",
        description="Get the details of a project for an admin",
        responses={
            200: AdminProjectDetailSerializer,
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class ProjectDetailView(generics.RetrieveAPIView):
    serializer_class = ProjectDetailSerializer
    lookup_field = 'id'
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    
    def get_queryset(self):
        if self.request.user.is_admin or self.request.user.is_staff:
            return Project.objects.all()
        else:
            return Project.objects.filter(created_by=self.request.user)


@extend_schema_view(
    patch=extend_schema(
        summary="Update a project",
        description=(
            "Partially update a project’s **name**, **description**, or **status**.\n\n"
            "#### Permission rules\n"
            "- **Admins/staff** can edit any project.\n"
            "- **Regular users** can only edit projects they created.\n\n"
            "#### Allowed `status` values:\n"
            f"- `{ProjectStatusChoices.PENDING}` — {ProjectStatusChoices.PENDING.label}\n"
            f"- `{ProjectStatusChoices.IN_PROGRESS}` — {ProjectStatusChoices.IN_PROGRESS.label}\n"
            f"- `{ProjectStatusChoices.COMPLETED}` — {ProjectStatusChoices.COMPLETED.label}"
        ),
        request=ProjectUpdateSerializer,
        responses={
            200: ProjectUpdateSerializer,
            403: None,
            404: None,
        },
        parameters=[
            OpenApiParameter(
                name="id",
                description="Primary key of the project to update",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            )
        ],
        tags=["Projects"],
    )
)
class EditProjectView(generics.UpdateAPIView):
    serializer_class = ProjectUpdateSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    lookup_field = 'id'
    def get_queryset(self):
        if self.request.user.is_admin or self.request.user.is_staff:
            return Project.objects.all()
        else:
            return Project.objects.filter(created_by=self.request.user)
    

    def patch(self, request, *args, **kwargs):
        project = self.get_object()
        
        
        response = super().patch(request, *args, **kwargs)
        if response.status_code == 200:
            updated_fields= list(request.data.keys())
            project.create_log(
                message=f"Project details updated by {request.user.username}. Fields changed: {', '.join(updated_fields)}"
            )
        return response


class LogoutView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = LogoutSerializer
    
    @extend_schema(
        summary="Logout a user by blacklisting the refresh token"
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors))
        
        refresh_token = serializer.validated_data.get('refresh_token')
        
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            logout(request)
            return SuccessResponse(message="Logout successful")
        except TokenError as e:
            return ErrorResponse(message="Invalid token")
        except Exception as e:
            return ErrorResponse(message="An error occurred during logout", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        


class Disable2FAView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = Disable2faSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors))
        
        user = request.user
        
        try:
            otp_verification = OTPVerification.objects.get(user=user)
            password = serializer.validated_data.get('password')
            
            if not user.check_password(password):
                return ErrorResponse(message="Invalid password")
            
            
            otp_verification.is_verified = False
            otp_verification.save()
            
            return SuccessResponse(message="2FA disabled successfully")
        except OTPVerification.DoesNotExist:
            return ErrorResponse(message="2FA not setup yet.", status=status.HTTP_400_BAD_REQUEST)


class Setup2faView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="Get all the details required to setup 2fa for a user"
    )
    def get(self, request):
        otp_verification, created = OTPVerification.objects.get_or_create(user=request.user)
        
        #regenerate the qr code if otp was not newly created
        if not created:
            otp_verification.generate_qr_code()
            otp_verification.save()
        
        return SuccessResponse(data={
            "qr_code_url": otp_verification.qr_code,
            "secret_key": otp_verification.secret_key,
            "is_verified": otp_verification.is_verified
        })
        # return SuccessResponse(data={
        #     "qr_code_url": request.build_absolute_uri(otp_verification.qr_code.url),
        #     "secret_key": otp_verification.secret_key,
        #     "is_verified": otp_verification.is_verified
        # })
    
    
    @extend_schema(
        request=OtpVerificationSerializer,
        summary="Verify the otp code from an authenticator app"
    )
    def post(self, request):
        try:
            otp_verification = OTPVerification.objects.get(user=request.user)
        except OTPVerification.DoesNotExist:
            return ErrorResponse(
                message="2FA not setup yet",
                status= status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OtpVerificationSerializer(otp_verification, data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=format_first_error(serializer.errors, with_key=False))
        
        otp_verification.is_verified = True
        otp_verification.save()
        
        return SuccessResponse(
            message="2fa Verified successfully",
        )

class LoginView(APIView):
    """User login view to generate JWT token"""

    permission_classes = [AllowAny]

    @extend_schema(
        summary="User Login",
        description="Authenticate user and return access & refresh tokens along with user roles and permissions.",
        request=LoginSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description="Successful login response with tokens and user data",
                examples=[
                    OpenApiExample(
                        "Login Success",
                        value={
                            "status": "success",
                            "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "access": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                            "user_data": {
                                "id": 1,
                                "username": "john_doe",
                                "email": "john@example.com",
                                "is_reviewer": True,
                                "is_admin": False,
                                "roles": ["reviewer"],
                                "permissions": [
                                    "can_review_tasks",
                                    "can_create_tasks",
                                    "can_view_assigned_tasks"
                                ]
                            }
                        },
                        response_only=True
                    )
                ]
            ),
            401: OpenApiResponse(
                response=None,
                description="Invalid credentials",
                examples=[
                    OpenApiExample(
                        "Login Failed",
                        value={
                            "status": "error",
                            "error": "Invalid credentials"
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            
            #check if 2fa is enabled 
            try:
                otp_verification = OTPVerification.objects.get(user=user, is_verified=True)
                otp_code = request.data.get('otp_code')
                
                if not otp_code:
                    #2FA is enabled but the user has not provided their otp code during login
                    return ErrorResponse(
                        message="2fa verification required",
                        data={
                            "requires_2fa": True
                        },
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                
                if not otp_verification.verify_otp(otp_code):
                    #The 2FA otp provided by the user during login is not valid
                    logger.warning(f"Failed login attempt for username '{request.data.get('username')}' at {datetime.now()}, Invalid 2fa otp code")
                    return ErrorResponse(message="Invalid 2FA code", status=status.HTTP_401_UNAUTHORIZED)
                
            except OTPVerification.DoesNotExist:
                #this means 2FA is not enabled, so we continue with normal login
                pass
                
        
            
            refresh = RefreshToken.for_user(user)
            logger.info(f"User '{user.username}' logged in successfully at {datetime.now()}")
            
            return Response(
                {
                    "status": "success",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user_data": UserSerializer(user).data,
                }
            )

        logger.warning(f"Failed login attempt for username '{request.data.get('username')}' at {datetime.now()}")
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
            user, role = serializer.save()
            if role == "organization":
                assign_default_plan(user)
                logger.info(f"Organization '{user.username}' has been assign the default free plan {datetime.now()}")
            logger.info(f"New user '{user.username}' registered successfully at {datetime.now()}")
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

        logger.warning(f"Failed registration attempt for username '{request.data.get('username')}' at {datetime.now()}. Error: {error_message}")
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
        admin_user = request.user

        user.is_admin = True
        user.is_staff = True
        user.save()

        logger.info(f"User '{admin_user.username}' promoted '{user.username}' to admin at {datetime.now()}")
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
        admin_user = request.user

        user.is_reviewer = True
        user.project = project
        user.save()

        logger.info(f"Admin '{admin_user.username}' promoted '{user.username}' to reviewer in project '{project.name}' at {datetime.now()}")
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
        admin_user = request.user
        project_name = user.project.name if user.project else "No Project"

        user.is_reviewer = False
        user.project = None
        user.save()

        logger.info(f"Admin '{admin_user.username}' removed reviewer status from '{user.username}' (previously in project '{project_name}') at {datetime.now()}")
        return Response({
            "status": "success",
            "detail": f"User '{user.username}' is no longer a reviewer."
        }, status=status.HTTP_200_OK)



class ListUserProjectView(generics.ListAPIView):
    permission_classes =[IsAuthenticated | HasUserAPIKey]
    serializer_class = UserProjectSerializer
    
    
    def get_queryset(self):
        return Project.objects.filter(created_by=self.request.user)
    
    @extend_schema(
        summary="Get the list of projects owned by the currently logged in user"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class CreateUserProject(generics.CreateAPIView):
    queryset = Project.objects.all()
    permission_classes =[IsAuthenticated | HasUserAPIKey, NotReviewer]
    serializer_class = UserProjectSerializer
    
    @extend_schema(
        summary="Create a project for the currently logged in user "
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)
    


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
                value={"name": "New Project X", "description": "For a new project"},
                request_only=True
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 201:
            project_name = request.data.get('name')
            logger.info(f"Admin '{request.user.username}' created new project '{project_name}' at {datetime.now()}")
        return response
    
    
    
class ListProjectsView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="List projects based on user role",
        description="""
        Returns a list of projects based on the user's role:
        - Admin/Staff: Can see all projects
        - Reviewer: Can only see projects they are assigned to
        - Organization: Can only see their own projects
        
        Each project includes task completion statistics:
        - total_tasks: Total number of tasks in the project
        - completed_tasks: Number of completed tasks
        - pending_review: Number of tasks pending review
        - in_progress: Number of tasks currently being processed
        """,
        responses={
            200: OpenApiResponse(
                response=ProjectSerializer,
                examples=[
                    OpenApiExample(
                        'Admin Response',
                        value={
                            "status": "success",
                            "projects": [
                                {
                                    "id": 1,
                                    "name": "Project 1",
                                    "description": "Test project 1",
                                    "created_by": {
                                        "id": 1,
                                        "username": "org",
                                        "email": "org@example.com"
                                    },
                                    "members": [
                                        {
                                            "id": 2,
                                            "username": "reviewer",
                                            "email": "reviewer@example.com"
                                        }
                                    ],
                                    "created_at": "2024-03-13T12:00:00Z",
                                    "updated_at": "2024-03-13T12:00:00Z",
                                    "task_stats": {
                                        "total_tasks": 100,
                                        "completed_tasks": 75,
                                        "pending_review": 15,
                                        "in_progress": 10
                                    }
                                }
                            ]
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def get(self, request):
        user = request.user
        
        if user.is_staff or user.is_superuser:
            # Admin can see all projects
            projects = Project.objects.all()
        elif user.is_reviewer:
            # Reviewer can only see projects they are assigned to
            projects = Project.objects.filter(members=user)
        else:
            # Organization can only see their own projects
            projects = Project.objects.filter(created_by=user)
        
        # Get task statistics for each project
        project_data = []
        for project in projects:
            project_dict = ProjectSerializer(project).data
            
            # Get task statistics
            total_tasks = project.created_tasks.count()
            completed_tasks = project.created_tasks.filter(processing_status="COMPLETED").count()
            pending_review = project.created_tasks.filter(processing_status="REVIEW_NEEDED").count()
            in_progress = project.created_tasks.filter(processing_status="PROCESSING").count()
            
            completion_percentage = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # Add task statistics to project data
            project_dict['task_stats'] = {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'pending_review': pending_review,
                'in_progress': in_progress,
                "completion_percentage": round(completion_percentage)
            }
            
            project_data.append(project_dict)
        
        return Response({
            'status': 'success',
            'projects': project_data
        })

        


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
            logger.info(f"Token refresh successful at {datetime.now()}")
            return Response(
                {
                    "status": "success",
                    "access": response.data["access"],
                    "refresh": response.data.get("refresh", ""),
                },
                status=status.HTTP_200_OK,
            )

        except AuthenticationFailed as e:  # Catch invalid token error
            logger.warning(f"Failed token refresh attempt at {datetime.now()}")
            return Response(
                {
                    "status": "error",
                    "detail": "Your session has expired. Please log in again.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
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
        description="""
        Returns a list of users who are not assigned to any project or not in a specific project.
        - If project_id query parameter is provided: Returns users not in that specific project
        - If no project_id is provided: Returns users not assigned to any project
        """,
        parameters=[
            OpenApiParameter(
                name="project_id",
                location=OpenApiParameter.QUERY,
                required=False,
                description="ID of the project to exclude users from. If not provided, returns users not in any project.",
                type=int,
            )
        ],
        responses={
            200: OpenApiResponse(
                response=UserListResponseSerializer,
                examples=[
                    OpenApiExample(
                        'Users Not In Specific Project',
                        value={
                            "status": "success",
                            "users": [
                                {
                                    "id": 3,
                                    "email": "user3@example.com",
                                    "username": "user3"
                                },
                                {
                                    "id": 4,
                                    "email": "user4@example.com",
                                    "username": "user4"
                                }
                            ]
                        },
                        response_only=True
                    ),
                    OpenApiExample(
                        'Users Not In Any Project',
                        value={
                            "status": "success",
                            "users": [
                                {
                                    "id": 5,
                                    "email": "user5@example.com",
                                    "username": "user5"
                                },
                                {
                                    "id": 6,
                                    "email": "user6@example.com",
                                    "username": "user6"
                                }
                            ]
                        },
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid project ID",
                examples=[
                    OpenApiExample(
                        'Invalid Project ID',
                        value={
                            "status": "error",
                            "error": "Invalid project ID"
                        },
                        response_only=True
                    )
                ]
            )
        }
    )
    def get(self, request):
        project_id = request.query_params.get('project_id')
        
        try:
            if project_id is not None:
                # Get users not in the specific project
                project = Project.objects.get(id=project_id)
                users = CustomUser.objects.exclude(project=project)
            else:
                # Get users not in any project
                users = CustomUser.objects.filter(project__isnull=True)
            
            serializer = SimpleUserSerializer(users, many=True)
            return Response({
                "status": "success",
                "users": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Project.DoesNotExist:
            return Response({
                "status": "error",
                "error": "Invalid project ID"
            }, status=status.HTTP_400_BAD_REQUEST)


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


class ChangePasswordView(APIView):
    """
    Endpoint to change user password
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Change user password",
        description="Change the password of the currently authenticated user. Requires current password and new password confirmation.",
        request=ChangePasswordSerializer,
        responses={
            200: OpenApiResponse(
                description="Password changed successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={"status": "success", "message": "Password changed successfully"},
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid input",
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={"status": "error", "error": "Current password is incorrect"},
                        response_only=True
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = request.user
            
            # Check if current password is correct
            if not user.check_password(serializer.validated_data['current_password']):
                return Response(
                    {"status": "error", "error": "Current password is incorrect"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            return Response(
                {"status": "success", "message": "Password changed successfully"},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )


class UpdateNameView(APIView):
    """
    Endpoint to update user's username
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="Update username",
        description="Update the username of the currently authenticated user.",
        request=UpdateNameSerializer,
        responses={
            200: OpenApiResponse(
                description="Username updated successfully",
                examples=[
                    OpenApiExample(
                        'Success Response',
                        value={"status": "success", "message": "Username updated successfully"},
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(
                description="Invalid input",
                examples=[
                    OpenApiExample(
                        'Error Response',
                        value={"status": "error", "error": "This username is already taken"},
                        response_only=True
                    )
                ]
            )
        }
    )
    def post(self, request):
        serializer = UpdateNameSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.username = serializer.validated_data['username']
            user.save()
            
            return Response(
                {"status": "success", "message": "Username updated successfully"},
                status=status.HTTP_200_OK
            )
        
        return Response(
            {"status": "error", "error": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

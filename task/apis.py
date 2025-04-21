from django.shortcuts  import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import logging
from rest_framework.views import APIView

from account.models import Project
from common.responses import ErrorResponse, SuccessResponse
from task.utils import dispatch_task_message, push_realtime_update
from .models import Task, UserReviewChatHistory
from .serializers import AssignedTaskSerializer, FullTaskSerializer, TaskIdSerializer, TaskSerializer, TaskStatusSerializer, TaskReviewSerializer, AssignTaskSerializer
from .tasks import process_task, provide_feedback_to_ai_model
from rest_framework_api_key.permissions import HasAPIKey

# import custom permissions
from account.utils import HasUserAPIKey, IsReviewer



logger = logging.getLogger(__name__)


class TaskListView(generics.ListAPIView):
    """
    Get a list of tasks the currently logged in user can work on
    
    ---
    """
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    queryset = Task.objects.all()
    
    def get_queryset(self):
        my_projects= Project.objects.filter(reviewers=self.request.user)
        tasks_list= Task.objects.filter(group__in=my_projects, assigned_to=None, processing_status="REVIEW_NEEDED")
        return tasks_list
    

class TaskCreateView(generics.CreateAPIView):
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated | HasUserAPIKey]
    
    def get_queryset(self):
        return Task.objects.select_related('group').all()
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            try:
                # Set the user to the current authenticated user
                task = serializer.save(user=request.user)
                logger.info(f"Submitting task {task.id} to Celery queue")
                
                # Queue the task for processing using Celery
                celery_task = process_task.delay(task.id)
                
                logger.info(f"Task {task.id} submitted to Celery. Celery task ID: {celery_task.id}")

                # Get fresh task data with related fields
                task = Task.objects.select_related('group').get(id=task.id)
                
                return Response({
                    'status': 'success',
                    'data': {
                        'message': 'Task submitted successfully',
                        'task_id': task.id,
                        'serial_no': task.serial_no,
                        'celery_task_id': celery_task.id,
                        'processing_status': task.processing_status,
                        # 'submitted_by': task.user.username
                    }
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Task creation failed: {str(e)}", exc_info=True)
                return Response({
                    'status': 'error',
                    'error': str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.error(f"Task creation failed: {serializer.errors}")
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
class TasksNeedingReviewView(APIView):
    """
    View all tasks that need review (Admins or Reviewers)
    """
    permission_classes = [IsAuthenticated]
    @extend_schema(
        summary="View all tasks that need review",
        description="Admins and Reviewers can view tasks that are awaiting review. "
                    "This includes filtering by the user's associated project and tasks with the "
                    "'REVIEW_NEEDED' processing status.",
        request=None,  # No request body
        responses={
            200: TaskSerializer(many=True),
            403: OpenApiExample(
                "Unauthorized",
                value={"detail": "Not authorized."},
                response_only=True
            ),
        },
        examples=[
            OpenApiExample(
                "Tasks Needing Review Example",
                value=[
                    {
                        "id": 1,
                        "serial_no": "T12345",
                        "task_type": "text_classification",
                        "data": {"text": "This is an example task data."},
                        "ai_output": {
                            "label": "positive",
                            "confidence": 0.95
                        },
                        "predicted_label": "positive",
                        "human_reviewed": False,
                        "final_label": None,
                        "processing_status": "REVIEW_NEEDED",
                        "assigned_to": None,
                        "created_at": "2025-04-15T07:58:59Z",
                        "updated_at": "2025-04-15T08:00:00Z",
                        "priority": "NORMAL",
                        "group": 1  # Reference to a project/group ID
                    }
                ],
                response_only=True
            ),
        ]
    )
    
    def get(self, request):
        if not (request.user.is_admin or request.user.is_reviewer):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)
        
        tasks = Task.objects.filter(processing_status='REVIEW_NEEDED', group=request.user.project, assigned_to=None,)
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)


class AssignTaskToSelfView(APIView):
    """
    Allow a reviewer to assign a REVIEW_NEEDED task to themselves.
    Expects POST payload: { "task_id": 123 }
    """
    permission_classes = [IsReviewer]
    serializer_class= AssignTaskSerializer
    
    @extend_schema(
        summary="Assign a task to self",
        description="Allows a reviewer to claim a task for review if it is in REVIEW_NEEDED state and unassigned.",
        request=AssignTaskSerializer,
        responses={
            200: OpenApiResponse(
                response=None,
                description="Task successfully assigned",
                examples=[
                    OpenApiExample(
                        "Successful Assignment",
                        value={
                            "status": "success",
                            "message": "Task T12345 assigned to you."
                        },
                        response_only=True
                    )
                ]
            ),
            400: OpenApiResponse(
                response=None,
                description="Invalid task or already assigned",
                examples=[
                    OpenApiExample(
                        "Task Already Assigned",
                        value={
                            "status": "error",
                            "detail": "Task is already assigned."
                        },
                        response_only=True
                    ),
                    OpenApiExample(
                        "Invalid Status",
                        value={
                            "status": "error",
                            "detail": "Task is not available for review."
                        },
                        response_only=True
                    ),
                ]
            )
        },
        examples=[
            OpenApiExample(
                "Assign Task Request",
                value={"task_id": 123},
                request_only=True
            )
        ]
    )

    def post(self, request):
        serializer = AssignTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_id = serializer.validated_data['task_id']
        task = get_object_or_404(Task, id=task_id)

        if task.processing_status != 'REVIEW_NEEDED':
            return Response(
                {   "status": "error",
                    "detail": "Task is not available for review."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if task.assigned_to:
            return Response(
                {
                    "status": "error",
                    "detail": "Task is already assigned."},
                status=status.HTTP_400_BAD_REQUEST
            )

        task.assigned_to = request.user
        task.processing_status = 'ASSIGNED_REVIEWER'
        task.review_status = "PENDING_REVIEW"
        task.save()
        push_realtime_update(task, action='task_status_changed')

        return Response(
            {   "status": "success",
                "message": f"Task {task.serial_no} assigned to you."},
            status=status.HTTP_200_OK
        )

class MyPendingReviewTasks(APIView):
    permission_classes = [IsReviewer]
    
    @extend_schema(
        summary="List My Pending Review Tasks",
        description="Returns all tasks assigned to the authenticated reviewer that are in `PENDING_REVIEW` status.",
        responses={
            200: OpenApiResponse(
                response=TaskSerializer(many=True),
                description="List of pending review tasks assigned to the user",
                examples=[
                    OpenApiExample(
                        "Successful Response",
                        value=[
                            {
                                "id": 12,
                                "serial_no": "T12345",
                                "task_type": "classification",
                                "data": {"text": "Example input text"},
                                "ai_output": {"prediction": "label_1"},
                                "predicted_label": "label_1",
                                "human_reviewed": False,
                                "final_label": None,
                                "processing_status": "ASSIGNED_REVIEWER",
                                "assigned_to": 7,
                                "created_at": "2024-04-01T10:00:00Z",
                                "updated_at": "2024-04-02T10:00:00Z",
                                "priority": "NORMAL",
                                "group": 3
                            }
                        ],
                        response_only=True
                    )
                ]
            )
        }
    )

    def get(self, request):
        tasks = Task.objects.select_related('assigned_to', 'group').filter(
            assigned_to=request.user,
            review_status='PENDING_REVIEW')
       
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

class CompleteTaskReviewView(generics.GenericAPIView):
    """
    After using the websocket to review a task, use this endpoint to save the final decision
    
    ---
    """
    serializer_class = TaskIdSerializer
    permission_classes =[IsAuthenticated]
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(data=serializer.errors, message="Error validating request")
        
        task_id = serializer.validated_data.get('task_id')
        
        try:
            task = Task.objects.get(id=task_id)
            last_human_review = UserReviewChatHistory.objects.filter(task=task).order_by('-created_at').first()
            
            if not last_human_review:
                return ErrorResponse(message="This task has not been reviewed by a human")
            
            task.processing_status = 'COMPLETED'
            task.review_status = 'PENDING_APPROVAL'
            task.human_reviewed = True
            task.final_label = last_human_review.ai_output.get('corrected_classification')
            task.save()
            return SuccessResponse(message="Task review complete", data=TaskSerializer(task).data)
        except Task.DoesNotExist:
            return ErrorResponse(message="Task not found")

class TaskReviewView(generics.GenericAPIView):
    """View for submission of review by a reviewer"""
    serializer_class = TaskReviewSerializer
    permission_classes = [IsAuthenticated, IsReviewer]
    @extend_schema(
        summary="Submit task review",
        description="Submit a review for an existing task with AI output data.",
        request=TaskReviewSerializer,
        responses={
            200: TaskReviewSerializer,
            400: None,
            404: None,
            500: None
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'status': 'error',
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)  
            
        # Get task_id from request data
        task_id = serializer.validated_data.get('task_id')            
        try:
            # Fetch the existing task
            task = Task.objects.select_related('user', 'assigned_to').get(id=task_id)

            # Extract ai_output for processing
            ai_output = task.ai_output
    
            if task.review_status != 'PENDING_REVIEW':
                return Response({
                    'status': "error",
                    'error': "Task does not require review at this moment"
                }, status=status.HTTP_403_FORBIDDEN)

            
            if task.assigned_to != request.user and request.user.is_admin != True :
                
                return Response({
                    'status': "error",
                    'error': "You have not been assigned to review this task"
                }, status=status.HTTP_401_UNAUTHORIZED)
            
                        
            if not ai_output or not ai_output.get('human_review'):
                return Response({
                    'status': 'error',
                    'error': "AI output for this task does not match predefined structure"
                }, status=status.HTTP_417_EXPECTATION_FAILED)
            
            ai_output['human_review']['correction'] = serializer.validated_data.get('correction')
            ai_output['human_review']['justification'] = serializer.validated_data.get('justification')
            ai_output['confidence'] = serializer.validated_data.get('confidence')
            
            print('the final ai ap', ai_output)
            
            # Log and queue task to Celery with both task id and ai_output
            logger.info(f"Submitting task {task.id} to Celery queue")
            
            celery_task = provide_feedback_to_ai_model.delay(task.id, ai_output)
            logger.info(f"Task {task.id} submitted to Celery. Celery task ID: {celery_task.id}")
            
            return Response({
                'status': 'success',
                'data': {
                    'message': 'Task queued for review',
                    'task_id': task.id,
                    'serial_no': task.serial_no,
                    'celery_task_id': celery_task.id,
                    'processing_status': task.processing_status,
                }
            }, status=status.HTTP_200_OK)
            
        except Task.DoesNotExist:
            return Response({
                'status': 'error',
                'error': f"Task with ID {task_id} not found."
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Failed to queue task: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
class TaskStatusView(APIView):
    """
    Endpoint to check the status of a task by ID or serial number
    """
    def get(self, request, identifier):
        logger.info(f"Checking status for task identifier: {identifier}")
        
        try:
            # Use select_related for user data
            tasks_qs = Task.objects.select_related('user', 'assigned_to')
            
            # Try to find task by serial_no first, then by id
            if identifier.isdigit():
                task = tasks_qs.get(id=identifier, user=request.user)
            else:
                task = tasks_qs.get(serial_no=identifier, user=request.user)
            
            logger.info(f"Found task {task.id} with status: {task.processing_status}")
            
            return Response({
                'status': 'success',
                'data': {
                    'task_id': task.id,
                    'serial_no': task.serial_no,
                    'task_type': task.task_type,
                    'processing_status': task.processing_status,
                    'human_reviewed': task.human_reviewed,
                    "ai_output": task.ai_output,
                    'submitted_by': task.user.username if task.user else None,
                    'assigned_to': task.assigned_to.username if task.assigned_to else None,
                    'created_at': task.created_at,
                    'updated_at': task.updated_at
                }
            })
            
        except Task.DoesNotExist:
            logger.error(f"Task not found for identifier: {identifier}")
            return Response({
                'status': 'error',
                'error': 'Task not found'
            }, status=status.HTTP_404_NOT_FOUND)

class UserTaskListView(generics.ListAPIView):
    """
    Endpoint to list all tasks submitted by the user
    """
    serializer_class = FullTaskSerializer
    
    def get_queryset(self):
        logger.info(f"Fetching tasks for user: {self.request.user.id}")
        return (Task.objects
                .select_related('user', 'assigned_to')
                .filter(user=self.request.user)
                .order_by('-created_at'))
        
        
class AssignedTaskListView(generics.ListAPIView):
    """
    Endpoint to list all tasks assigned to the authenticated user
    """
    serializer_class = AssignedTaskSerializer
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
    summary="List tasks assigned to the authenticated user",
    description="Retrieve a list of all tasks currently assigned to the authenticated user, ordered by creation date (descending).",
    responses={
        200: OpenApiResponse(
            response=TaskSerializer(many=True),
            description="List of tasks assigned to the user",
            examples=[
                OpenApiExample(
                    "Successful Response Example",
                    value=[
                        {
                            "id": 42,
                            "serial_no": "T98765",
                            "task_type": "classification",
                            "data": {"text": "Sample text input"},
                            "ai_output": {"prediction": "positive"},
                            "predicted_label": "positive",
                            "human_reviewed": False,
                            "final_label": None,
                            "processing_status": "ASSIGNED_REVIEWER",
                            "review_status": "PENDING_REVIEW",
                            "assigned_to": 10,
                            "created_at": "2024-03-20T12:00:00Z",
                            "updated_at": "2024-03-21T12:00:00Z",
                            "priority": "NORMAL",
                            "group": 2
                        }
                    ],
                    response_only=True
                )
            ]
        )
    }
)
    def get_queryset(self):
        logger.info(f"Fetching assigned tasks for user: {self.request.user.id}")
        return (Task.objects
                .select_related('assigned_to')
                .filter(assigned_to=self.request.user)
                .order_by('-created_at'))

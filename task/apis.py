from django.shortcuts  import get_object_or_404
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiExample
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
import logging
from rest_framework.views import APIView
from .models import Task
from .serializers import FullTaskSerializer, TaskSerializer, TaskStatusSerializer, TaskReviewSerializer, AssignTaskSerializer
from .tasks import process_task, provide_feedback_to_ai_model

# import custom permissions
from account.utils import IsReviewer



logger = logging.getLogger(__name__)

class TaskCreateView(generics.CreateAPIView):
    serializer_class = TaskSerializer
    
    def get_queryset(self):
        return Task.objects.select_related('user').all()
    
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
                task = Task.objects.select_related('user').get(id=task.id)
                
                return Response({
                    'status': 'success',
                    'data': {
                        'message': 'Task submitted successfully',
                        'task_id': task.id,
                        'serial_no': task.serial_no,
                        'celery_task_id': celery_task.id,
                        'status': task.status,
                        'submitted_by': task.user.username
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

    def get(self, request):
        if not (request.user.is_admin or request.user.is_reviewer):
            return Response({"detail": "Not authorized."}, status=status.HTTP_403_FORBIDDEN)

        tasks = Task.objects.filter(processing_status='REVIEW_NEEDED')
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)


class AssignTaskToSelfView(APIView):
    """
    Allow a reviewer to assign a REVIEW_NEEDED task to themselves.
    Expects POST payload: { "task_id": 123 }
    """
    permission_classes = [IsReviewer]

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

        return Response(
            {   "status": "success",
                "message": f"Task {task.serial_no} assigned to you."},
            status=status.HTTP_200_OK
        )

class MyPendingReviewTasks(APIView):
    permission_classes = [IsReviewer]

    def get(self, request):
        tasks = Task.objects.select_related('assigned_to', 'group').filter(
            assigned_to=request.user,
            review_status='PENDING_REVIEW')
       
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)


class TaskReviewView(APIView):
    """View for submission of review by a reviewer"""
    
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
        # Get task_id from request data
        task_id = request.data.get('task_id')
        
        if not task_id:
            return Response({
                'status': 'error',
                'error': 'Task ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Fetch the existing task
            task = Task.objects.select_related('user', 'assigned_to').get(id=task_id)
            
            # Validate incoming data against serializer with existing task instance
            serializer = TaskReviewSerializer(task, data=request.data, partial=True)
            
            if not serializer.is_valid():
                return Response({
                    'status': 'error',
                    'errors': serializer.errors
                }, status=status.HTTP_400_BAD_REQUEST)
                
            # Extract ai_output for processing
            ai_output = serializer.validated_data.get('ai_output')
            
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
                    'status': task.status,
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
            
            logger.info(f"Found task {task.id} with status: {task.status}")
            
            return Response({
                'status': 'success',
                'data': {
                    'task_id': task.id,
                    'serial_no': task.serial_no,
                    'task_type': task.task_type,
                    'status': task.status,
                    'human_reviewed': task.human_reviewed,
                    "ai_output": task.ai_output,
                    'submitted_by': task.user.username,
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
    serializer_class = TaskSerializer
    
    def get_queryset(self):
        logger.info(f"Fetching assigned tasks for user: {self.request.user.id}")
        return (Task.objects
                .select_related('user', 'assigned_to')
                .filter(assigned_to=self.request.user)
                .order_by('-created_at'))

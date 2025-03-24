from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
import logging
from rest_framework.views import APIView

from .models import Task
from .serializers import TaskSerializer, TaskStatusSerializer
from .tasks import process_task

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
    serializer_class = TaskStatusSerializer
    
    def get_queryset(self):
        logger.info(f"Fetching tasks for user: {self.request.user.id}")
        return (Task.objects
                .select_related('user', 'assigned_to')
                .filter(user=self.request.user)
                .order_by('-created_at'))

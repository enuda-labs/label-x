from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
import logging

from .models import Task
from .serializers import TaskSerializer
from .tasks import process_task

logger = logging.getLogger(__name__)

class TaskCreateView(generics.CreateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Set the user to the current authenticated user
            task = serializer.save(user=request.user)
            logger.info(f"Submitting task {task.id} to Celery queue")
            
            # Queue the task for processing using Celery
            celery_task = process_task.delay(task.id)
            
            logger.info(f"Task {task.id} submitted to Celery. Celery task ID: {celery_task.id}")

            return Response({
                'message': 'Task submitted successfully', 
                'task_id': task.id,
                'celery_task_id': celery_task.id
            }, status=status.HTTP_201_CREATED)

        logger.error(f"Task creation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

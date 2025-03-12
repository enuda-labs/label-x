from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status

from .models import Task
from .serializers import TaskSerializer
from .tasks import process_task

class TaskCreateView(generics.CreateAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Set the user to the current authenticated user
            task = serializer.save(user=request.user)

            # Queue the task for processing using Celery
            process_task.delay(task.id) 

            # headers = self.get_success_headers(serializer.data)
            return Response(
                {'message': 'Task submitted successfully', 'task_id': task.id},
                status=status.HTTP_201_CREATED,
                # headers=headers
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

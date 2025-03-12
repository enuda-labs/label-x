from rest_framework import serializers
from .models import Task

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ['id', 'task_type', 'content', 'priority', 
                  'confidence_threshold', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']
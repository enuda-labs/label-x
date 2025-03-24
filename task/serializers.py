from rest_framework import serializers
from .models import Task

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'serial_no', 'task_type', 'data', 
            'predicted_label', 'human_reviewed', 'final_label',
            'status', 'assigned_to', 'created_at', 'updated_at',
            'priority'
        ]
        read_only_fields = [
            'id', 'serial_no', 'predicted_label', 
            'human_reviewed', 'final_label', 'status',
            'assigned_to', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'priority': {'default': 'NORMAL'}
        }

class TaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'serial_no', 'task_type', 'status',
            'human_reviewed', 'created_at', 'updated_at'
        ]
        read_only_fields = fields
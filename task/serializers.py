from rest_framework import serializers
from .models import Task

class HumanReviewSerializer(serializers.Serializer):
    correction = serializers.CharField(allow_null=True, required=False)
    justification = serializers.CharField(allow_null=True, required=False)

class AIOutputSerializer(serializers.Serializer):
    text = serializers.CharField()
    classification = serializers.CharField()
    confidence = serializers.FloatField()
    requires_human_review = serializers.BooleanField()
    human_review = HumanReviewSerializer()


class FullTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'

class TaskSerializer(serializers.ModelSerializer):
    ai_output = AIOutputSerializer()
    class Meta:
        model = Task
        fields = [
            'id', 'serial_no', 'task_type', 'data', 'ai_output' ,
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
        
        

class TaskReviewSerializer(serializers.ModelSerializer):
    task_id = serializers.IntegerField()
    ai_output = AIOutputSerializer()

    class Meta:
        model = Task
        exclude = ['assigned_to', 'user']

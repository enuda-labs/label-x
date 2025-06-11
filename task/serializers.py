from rest_framework import serializers
from django.core.exceptions import ValidationError

from account.serializers import UserSerializer
from .models import Task, TaskClassificationChoices



class HumanReviewSerializer(serializers.Serializer):
    correction = serializers.CharField(allow_null=True, required=False)
    justification = serializers.CharField(allow_null=True, required=False)

class AIOutputSerializer(serializers.Serializer):
    text = serializers.CharField()
    classification = serializers.CharField()
    confidence = serializers.FloatField()
    requires_human_review = serializers.BooleanField()
    human_review = HumanReviewSerializer()

class TextContentSerializer(serializers.Serializer):
    content = serializers.CharField()
    language = serializers.CharField(required=False)
    metadata = serializers.DictField(required=False)

class ImageContentSerializer(serializers.Serializer):
    image_url = serializers.URLField()
    metadata = serializers.DictField(required=False)

class AudioContentSerializer(serializers.Serializer):
    audio_url = serializers.URLField()
    duration = serializers.CharField(required=False)
    metadata = serializers.DictField(required=False)

class VideoContentSerializer(serializers.Serializer):
    video_url = serializers.URLField()
    duration = serializers.CharField(required=False)
    resolution = serializers.CharField(required=False)
    metadata = serializers.DictField(required=False)

class MultimodalContentSerializer(serializers.Serializer):
    text_content = serializers.CharField(required=False)
    image_url = serializers.URLField(required=False)
    audio_url = serializers.URLField(required=False)
    video_url = serializers.URLField(required=False)
    metadata = serializers.DictField(required=False)

    def validate(self, data):
        # Ensure at least one content type is provided
        if not any([
            data.get('text_content'),
            data.get('image_url'),
            data.get('audio_url'),
            data.get('video_url')
        ]):
            raise ValidationError("At least one content type must be provided")
        return data

class FullTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'

class TaskSerializer(serializers.ModelSerializer):
    ai_output = AIOutputSerializer(read_only=True)
    
    class Meta:
        model = Task
        fields = [
            'id', 'serial_no', 'task_type', 'data', 'ai_output',
            'predicted_label', 'human_reviewed', 'final_label',
            'processing_status', "review_status", 'assigned_to', 'created_at', 'updated_at',
            'priority', 'group'
        ]
        read_only_fields = [
            'id', 'serial_no', 'predicted_label', "ai_output",
            'human_reviewed', 'final_label', 'processing_status', "review_status",
            'assigned_to', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'priority': {'default': 'NORMAL'}
        }

    def validate(self, data):
        task_type = data.get('task_type')
        content_data = data.get('data', {})

        # Validate content based on task type
        if task_type == 'TEXT':
            serializer = TextContentSerializer(data=content_data)
        elif task_type == 'IMAGE':
            serializer = ImageContentSerializer(data=content_data)
        elif task_type == 'AUDIO':
            serializer = AudioContentSerializer(data=content_data)
        elif task_type == 'VIDEO':
            serializer = VideoContentSerializer(data=content_data)
        elif task_type == 'MULTIMODAL':
            serializer = MultimodalContentSerializer(data=content_data)
        else:
            raise ValidationError(f"Invalid task type: {task_type}")

        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        return data

class AssignedTaskSerializer(serializers.ModelSerializer):
    ai_output = AIOutputSerializer(read_only=True) 
    assigned_to = UserSerializer()
    class Meta:
        model = Task
        fields = [
            'id', 'serial_no', 'task_type', 'data', 'ai_output' ,
            'predicted_label', 'human_reviewed', 'final_label',
            'processing_status', "review_status", 'assigned_to', 'created_at', 'updated_at',
            'priority', 'group' 
        ]
        read_only_fields = [
            'id', 'serial_no', 'predicted_label', "ai_output",
            'human_reviewed', 'final_label', 'processing_status',"review_status",
            'assigned_to', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'priority': {'default': 'NORMAL'}
        }

class TaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            'id', 'serial_no', 'task_type', 'processing_status', "review_status",
            'human_reviewed', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class TaskIdSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    

class TaskReviewSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    correction = serializers.ChoiceField(choices=TaskClassificationChoices.choices)
    justification = serializers.CharField()
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)
    
    
    # ai_output = AIOutputSerializer()

    # class Meta:
    #     model = Task
    #     exclude = ['assigned_to', 'group']


class AssignTaskSerializer(serializers.Serializer):
    task_id = serializers.IntegerField(help_text="ID of the task to assign to the current reviewer")
    
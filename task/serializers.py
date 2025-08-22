import attr
from rest_framework import serializers

from account.models import Project
from account.serializers import SimpleUserSerializer, UserSerializer
from subscription.models import UserDataPoints
from task.choices import AnnotationMethodChoices, TaskInputTypeChoices, TaskTypeChoices
from task.utils import calculate_required_data_points
from .models import MultiChoiceOption, Task, TaskClassificationChoices, TaskCluster

class AcceptClusterIdSerializer(serializers.Serializer):
    cluster = serializers.IntegerField()

    def validate_cluster(self, value):
        try:
            cluster = TaskCluster.objects.get(id=value)
            return cluster
        except TaskCluster.DoesNotExist:
            raise serializers.ValidationError("Cluster not found")
class ProjectUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ["name", "description", "status"]
        model = Project


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
        fields = "__all__"

class FileItemSerializer(serializers.Serializer):
    file_url = serializers.URLField()
    file_name = serializers.CharField()
    file_size_bytes = serializers.FloatField()
    file_type = serializers.CharField()
    

class TaskCreateSerializer(serializers.Serializer):
    file = FileItemSerializer(required=False)
    data = serializers.CharField(required=False)


class MultiChoiceOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MultiChoiceOption
        fields = ['option_text']


class TaskClusterCreateSerializer(serializers.ModelSerializer):
    tasks = TaskCreateSerializer(many=True)
    labelling_choices = MultiChoiceOptionSerializer(many=True, required=False)

    class Meta:
        model = TaskCluster
        fields = "__all__"
        read_only_fields = ["assigned_reviewers", 'created_by']

    def validate(self, attrs):
        attrs = super().validate(attrs)
        task_type = attrs.get('task_type')

        if attrs.get('annotation_method') == AnnotationMethodChoices.AI_AUTOMATED and task_type != TaskTypeChoices.TEXT:
            raise serializers.ValidationError("AI annotation is currently only supported for text-based tasks.")

        tasks_data = attrs.get("tasks", [])
        if len(tasks_data) == 0:
            raise serializers.ValidationError("Cannot create an empty cluster")
        
        labelling_choices = attrs.get('labelling_choices', [])
        print(labelling_choices)
        if attrs.get('input_type') == TaskInputTypeChoices.MULTIPLE_CHOICE and len(labelling_choices) ==0:
            raise serializers.ValidationError(f"Must specify at least one labelling choice for a Multiple choice labelling input type")

        total_required_dp = 0
        # loop through the tasks data that were created and ensure accuracy
        for data in tasks_data:
            file = data.get('file', None)
            text_data = data.get('data', None)
            
            if task_type == TaskTypeChoices.TEXT and not text_data:
                raise serializers.ValidationError("Must provide a text data for task of type TEXT")
            
            if task_type != TaskTypeChoices.TEXT and not file:
                raise serializers.ValidationError(f"Must provide file data for task of type {task_type}")
            
            # ensure file type is supported
            # TODO: IF THE TASK TYPE IS IMAGE, ENSURE USERS CAN ONLY UPLOAD IMAGES, E.T.C
            accepted_file_types = ['csv', 'jpg', 'jpeg', 'png']
            if file and file.get('file_type') not in accepted_file_types:
                raise serializers.ValidationError(f"Unsupported file type for file `{file.get('file_name')}`")
            
            required_data_points = calculate_required_data_points(task_type, text_data=data.get('data'), file_size_bytes=file.get('file_size_bytes'))
            total_required_dp += required_data_points
        

        
        attrs['required_data_points'] = total_required_dp
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('tasks')
        validated_data.pop('required_data_points')
        validated_data.pop("labelling_choices")
        return super().create(validated_data)



class TaskClusterListSerializer(serializers.ModelSerializer):
    """
    Use this serializer to serialize a list of task clusters
    """
    class Meta:
        fields ="__all__"
        model = TaskCluster

class TaskSerializer(serializers.ModelSerializer):
    ai_output = AIOutputSerializer(read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "serial_no",
            "task_type",
            "data",
            "ai_output",
            "predicted_label",
            "human_reviewed",
            "final_label",
            "processing_status",
            "review_status",
            "assigned_to",
            "created_at",
            "updated_at",
            "priority",
            "group",
            "used_data_points",
        ]
        read_only_fields = [
            "id",
            "serial_no",
            "predicted_label",
            "ai_output",
            "human_reviewed",
            "final_label",
            "processing_status",
            "review_status",
            "assigned_to",
            "created_at",
            "updated_at",
            "used_data_points",
        ]
        extra_kwargs = {"priority": {"default": "NORMAL"}}


class TaskClusterDetailSerializer(serializers.ModelSerializer):
    """
    Use this serializer when you need to get the full details of a task cluster
    
    Warning: to avoid n+1 queries, do not use for task list
    """
    tasks = TaskSerializer(many=True, read_only=True)
    assigned_reviewers = SimpleUserSerializer(many=True)
    class Meta:
        fields ="__all__"
        model = TaskCluster

class AssignedTaskSerializer(serializers.ModelSerializer):
    ai_output = AIOutputSerializer(read_only=True)
    assigned_to = UserSerializer()

    class Meta:
        model = Task
        fields = [
            "id",
            "serial_no",
            "task_type",
            "data",
            "ai_output",
            "predicted_label",
            "human_reviewed",
            "final_label",
            "processing_status",
            "review_status",
            "assigned_to",
            "created_at",
            "updated_at",
            "priority",
            "group",
        ]
        read_only_fields = [
            "id",
            "serial_no",
            "predicted_label",
            "ai_output",
            "human_reviewed",
            "final_label",
            "processing_status",
            "review_status",
            "assigned_to",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {"priority": {"default": "NORMAL"}}


class TaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "serial_no",
            "task_type",
            "processing_status",
            "review_status",
            "human_reviewed",
            "created_at",
            "updated_at",
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
    task_id = serializers.IntegerField(
        help_text="ID of the task to assign to the current reviewer"
    )

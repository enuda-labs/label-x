import attr
from rest_framework import serializers

from account.models import Project
from account.serializers import SimpleUserSerializer, UserSerializer
from subscription.models import UserDataPoints
from task.choices import AnnotationMethodChoices, TaskInputTypeChoices, TaskTypeChoices
from task.utils import calculate_required_data_points
from .models import MultiChoiceOption, Task, TaskClassificationChoices, TaskCluster

class AcceptClusterIdSerializer(serializers.Serializer):
    """
    Serializer for accepting a cluster ID from request data.
    
    Used when operations require a valid cluster identifier.
    """
    cluster = serializers.IntegerField()

    def validate_cluster(self, value):
        """
        Validate that the provided cluster ID exists in the database.
        
        Args:
            value: The cluster ID to validate
            
        Returns:
            TaskCluster: The validated cluster instance
            
        Raises:
            ValidationError: If cluster with given ID doesn't exist
        """
        try:
            cluster = TaskCluster.objects.get(id=value)
            return cluster
        except TaskCluster.DoesNotExist:
            raise serializers.ValidationError("Cluster not found")

class ProjectUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating project information.
    
    Allows modification of project name, description, and status.
    """
    class Meta:
        fields = ["name", "description", "status"]
        model = Project

class HumanReviewSerializer(serializers.Serializer):
    """
    Serializer for human review feedback on AI predictions.
    
    Captures corrections and justifications provided by human reviewers.
    """
    correction = serializers.CharField(allow_null=True, required=False)
    justification = serializers.CharField(allow_null=True, required=False)

class AIOutputSerializer(serializers.Serializer):
    """
    Serializer for AI model output data.
    
    Represents the complete output from AI processing including predictions,
    confidence scores, and human review requirements.
    """
    text = serializers.CharField()
    classification = serializers.CharField()
    confidence = serializers.FloatField()
    requires_human_review = serializers.BooleanField()
    human_review = HumanReviewSerializer()

class FullTaskSerializer(serializers.ModelSerializer):
    """
    Complete task serializer with all fields. Provides comprehensive task data including all model fields.
    To be Use with caution to avoid performance issues in list views.
    """
    class Meta:
        model = Task
        fields = "__all__"

class FileItemSerializer(serializers.Serializer):
    """
    Serializer for file metadata in tasks.
    
    Handles file-related information including URL, name, size, and type.
    """
    file_url = serializers.URLField()
    file_name = serializers.CharField()
    file_size_bytes = serializers.FloatField()
    file_type = serializers.CharField()

class TaskCreateSerializer(serializers.Serializer):
    """
    Serializer for creating individual tasks.
    
    Supports both text-based and file-based task creation.
    """
    file = FileItemSerializer(required=False)
    data = serializers.CharField(required=False)

class MultiChoiceOptionSerializer(serializers.ModelSerializer):
    """
    Serializer for predefined label choices in multiple-choice tasks.
    
    Used when clusters require standardized labeling options.
    """
    class Meta:
        model = MultiChoiceOption
        fields = ['option_text']

class TaskClusterCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating task clusters with multiple tasks.
    
    Handles cluster creation, task validation, and data point calculation.
    Supports both manual and AI-automated annotation methods.
    """
    tasks = TaskCreateSerializer(many=True)
    labelling_choices = MultiChoiceOptionSerializer(many=True, required=False)

    class Meta:
        model = TaskCluster
        fields = "__all__"
        read_only_fields = ["assigned_reviewers", 'created_by']

    def validate(self, attrs):
        """
        Validate cluster creation data including tasks and labeling choices.
        
        Performs comprehensive validation:
        - Ensures non-empty task list
        - Validates task data based on type
        - Checks file type compatibility
        - Calculates required data points
        - Validates multiple-choice options when required
        
        Args:
            attrs: Validated attributes from the serializer
            
        Returns:
            dict: Validated attributes with calculated data points
            
        Raises:
            ValidationError: For various validation failures
        """
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
        """
        Create a new task cluster with the validated data.
        
        Removes task and labeling choice data before cluster creation
        as these are handled separately in the view.
        
        Args:
            validated_data: Validated cluster data
            
        Returns:
            TaskCluster: The created cluster instance
        """
        validated_data.pop('tasks')
        validated_data.pop('required_data_points')
        validated_data.pop("labelling_choices")
        return super().create(validated_data)

class TaskClusterListSerializer(serializers.ModelSerializer):
    """
    Serializer for listing task clusters.
    
    Provides essential cluster information for list views.
    Optimized for performance in list operations.
    """
    class Meta:
        fields ="__all__"
        model = TaskCluster

class TaskSerializer(serializers.ModelSerializer):
    """
    Standard task serializer for general task operations.
    
    Includes core task fields and AI output data.
    Used for task listing and basic task information.
    """
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
    Detailed serializer for task cluster information.
    
    Includes full cluster data with related tasks and reviewers.
    Warning: Avoid using in list views to prevent N+1 query issues.
    """
    tasks = TaskSerializer(many=True, read_only=True)
    assigned_reviewers = SimpleUserSerializer(many=True)
    class Meta:
        fields ="__all__"
        model = TaskCluster

class AssignedTaskSerializer(serializers.ModelSerializer):
    """
    Serializer for tasks assigned to specific users.
    
    Includes detailed user information for assigned reviewers.
    Used when displaying task assignments and reviewer details.
    """
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
    """
    Lightweight serializer for task status information.
    
    Contains only essential fields needed for status tracking.
    Optimized for performance in status update operations.
    """
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
    """
    Simple serializer for task ID validation.
    
    Used when operations only require a valid task identifier.
    """
    task_id = serializers.IntegerField()

class TaskReviewSerializer(serializers.Serializer):
    """
    Serializer for submitting task review feedback. Captures human corrections, justifications, and confidence scores
    for AI model improvement and task completion.
    """
    task_id = serializers.IntegerField()
    correction = serializers.ChoiceField(choices=TaskClassificationChoices.choices)
    justification = serializers.CharField()
    confidence = serializers.FloatField(min_value=0.0, max_value=1.0)

class AssignTaskSerializer(serializers.Serializer):
    """
    Serializer for task assignment operations. Used when reviewers need to assign tasks to themselves
    or when administrators assign tasks to specific reviewers.
    """
    task_id = serializers.IntegerField(
        help_text="ID of the task to assign to the current reviewer"
    )

from django.db import models
import string
import random
from account.models import CustomUser, Project, ProjectLog
import uuid

from task.choices import AnnotationMethodChoices, TaskInputTypeChoices, TaskTypeChoices


def generate_serial_no():
    """Generate a random 6-character alphanumeric string"""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


class TaskClassificationChoices(models.TextChoices):
    SAFE = (
        "Safe",
        "Safe",
    )
    MILDLY_OFFENSIVE = "Mildly Offensive", "Mildly Offensive"
    HIGHLY_OFFENSIVE = "Highly Offensive", "Highly Offensive"


class TaskCluster(models.Model):
    input_type = models.CharField(max_length=25, help_text="The type of input the labeller is to provide for the tasks in this cluster", choices=TaskInputTypeChoices.choices, default=TaskInputTypeChoices.TEXT)
    labeller_instructions = models.TextField(default="Default")
    deadline = models.DateField(null=True, blank=True)
    labeller_per_item_count = models.IntegerField(default=100)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    assigned_reviewers = models.ManyToManyField(
        CustomUser,
        related_name="assigned_clusters",
        help_text="Users assigned to review the tasks in this cluster",
        blank=True
    )
    task_type = models.CharField(choices=TaskTypeChoices.choices, max_length=25, default=TaskTypeChoices.TEXT)
    annotation_method = models.CharField(choices=AnnotationMethodChoices.choices, default=AnnotationMethodChoices.AI_AUTOMATED, max_length=20)
    

class MultiChoiceOption(models.Model):
    cluster = models.ForeignKey(TaskCluster, on_delete=models.CASCADE)
    option_text = models.CharField(max_length=100)
    

class Task(models.Model):
    """
    A task is a single object to be annotated, it can be a text, a single image, video, csv file, e.t.c
    """
   
    PRIORITY_LEVELS = (
        ("URGENT", "Urgent"),
        ("NORMAL", "Normal"),
        ("LOW", "Low"),
    )

    PROCESSING_STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("PROCESSING", "Processing"),
        ("REVIEW_NEEDED", "Review Needed"),
        ("ASSIGNED_REVIEWER", "Assigned Reviewer"),
        ("COMPLETED", "Completed"),
        ("ESCALATED", "Escalated"),
    )
    REVIEW_STATUS_CHOICES = (
        ("PENDING_REVIEW", "Pending Review"),
        ("PENDING_APPROVAL", "Pending Approval"),
        ("COMPLETED", "Completed"),
    )

    # Basic fields
    serial_no = models.CharField(
        max_length=6,
        unique=True,
        default=generate_serial_no,
        editable=False,
        help_text="Auto-generated 6-digit alphanumeric identifier",
    )

    task_type = models.CharField(
        max_length=10, choices=TaskTypeChoices.choices, default=TaskTypeChoices.TEXT, help_text="Type of content to be processed"
    )

    data = models.TextField()

    predicted_label = models.JSONField(
        null=True, blank=True, help_text="AI-generated predictions"
    )

    ai_output = models.JSONField(
        null=True, blank=True, help_text="The full json output of the ai model"
    )

    ai_confidence = models.FloatField(default=0.0)

    final_label = models.JSONField(
        null=True, blank=True, help_text="Human-reviewed final label"
    )

    # Task status and review tracking
    processing_status = models.CharField(
        max_length=17, choices=PROCESSING_STATUS_CHOICES, default="PENDING"
    )

    review_status = models.CharField(
        max_length=17, choices=REVIEW_STATUS_CHOICES, default=None, null=True
    )

    human_reviewed = models.BooleanField(
        default=False, help_text="Indicates if a human has reviewed this task"
    )
    
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_LEVELS,
        default="NORMAL",
        help_text="Task processing priority level",
    )

    # Relations
    group = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="created_tasks",
        help_text="Group who created the task",
    )
    
    cluster = models.ForeignKey(TaskCluster, on_delete=models.CASCADE, related_name='tasks', null=True, blank=False)

    assigned_to = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
        help_text="User assigned to review this task",
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="created_tasks",
        help_text="User who created the task",
        null=True,
        blank=True,
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    used_data_points = models.IntegerField(default=0, help_text="The amount of data points that was used during the submission of this task") 
    
    # this fields will have values if the task type is a file
    file_name = models.CharField(max_length=100, null=True, blank=True)
    file_type= models.CharField(max_length=10, null=True, blank=True)
    file_url = models.URLField(help_text="The cdn link to the file", null=True, blank=True)
    file_size_bytes = models.FloatField(null=True, blank=True)
    file_size_bytes = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["serial_no"]),
            models.Index(fields=["processing_status"]),
            models.Index(fields=["task_type"]),
            models.Index(fields=["human_reviewed"]),
        ]

    def __str__(self):
        return f"{self.serial_no} - {self.task_type}"

    def create_log(self, message: str):
        return ProjectLog.objects.create(project=self.group, message=message, task=self)

    def save(self, *args, **kwargs):
        # Generate serial_no if not set
        if not self.serial_no:
            self.serial_no = generate_serial_no()

        # Ensure unique serial_no
        while Task.objects.filter(serial_no=self.serial_no).exists():
            self.serial_no = generate_serial_no()

        super().save(*args, **kwargs)

class TaskLabel(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    label = models.CharField(max_length=255)
    labeller = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    

class UserReviewChatHistory(models.Model):
    reviewer = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True)
    ai_output = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    human_confidence_score = models.FloatField()
    human_justification = models.TextField()
    human_classification = models.CharField(
        max_length=25, choices=TaskClassificationChoices.choices
    )

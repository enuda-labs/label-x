from django.db import models
import string
import random
from account.models import CustomUser, Project


def generate_serial_no():
    """Generate a random 6-character alphanumeric string"""
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=6))


class TaskClassificationChoices(models.TextChoices):
    SAFE = 'Safe', 'Safe',
    MILDLY_OFFENSIVE = 'Mildly Offensive', 'Mildly Offensive'
    HIGHLY_OFFENSIVE = 'Highly Offensive', 'Highly Offensive'
class Task(models.Model):
    TASK_TYPES = (
        ("TEXT", "Text"),
        ("IMAGE", "Image"),
        ("VIDEO", "Video"),
        ("AUDIO", "Audio"),
        ("MULTIMODAL", "Multimodal"),
    )

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
        max_length=10, choices=TASK_TYPES, help_text="Type of content to be processed"
    )

    # JSON fields for data and labels
    data = models.JSONField(help_text="Task data (text content, file URLs, etc.)")

    predicted_label = models.JSONField(
        null=True, blank=True, help_text="AI-generated predictions"
    )

    ai_output = models.JSONField(
        null=True, blank=True, help_text="The full json output of the ai model"
    )

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

    def save(self, *args, **kwargs):
        # Generate serial_no if not set
        if not self.serial_no:
            self.serial_no = generate_serial_no()

        # Ensure unique serial_no
        while Task.objects.filter(serial_no=self.serial_no).exists():
            self.serial_no = generate_serial_no()

        super().save(*args, **kwargs)

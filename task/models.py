from django.db import models
import string
import random
from account.models import User, Project, ProjectLog
from task.choices import AnnotationMethodChoices, ManualReviewSessionStatusChoices, TaskClusterStatusChoices, TaskInputTypeChoices, TaskTypeChoices
from reviewer.models import LabelerDomain


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


def get_default_labeler_domain(as_id=True):
    # labeler_domain, created = LabelerDomain.objects.get_or_create(domain="Default")
    # if as_id:
    #     return labeler_domain.id
    return None

class TaskCluster(models.Model):
    """
    A TaskCluster represents a batch of related tasks that share common properties and are assigned to the same group of reviewers.
    
    TaskClusters serve as organizational units for grouping similar annotation tasks together. They allow for:
    - Batch assignment of tasks to multiple reviewers
    - Shared configuration across related tasks (input type, instructions, deadline)
    - Support for both manual and AI-automated annotation methods
    Each cluster can contain multiple tasks and can be assigned to multiple reviewers simultaneously.
    """
    name= models.CharField(max_length=100, default="Default")
    description= models.TextField(default="Default")
    input_type = models.CharField(max_length=25, help_text="The type of input the labeller is to provide for the tasks in this cluster", choices=TaskInputTypeChoices.choices, default=TaskInputTypeChoices.TEXT)
    labeller_instructions = models.TextField(default="Default")
    deadline = models.DateField(null=True, blank=True)
    labeller_per_item_count = models.IntegerField(default=15)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="clusters")
    assigned_reviewers = models.ManyToManyField(
        User,
        related_name="assigned_clusters",
        help_text="Users assigned to review the tasks in this cluster",
        blank=True
    )
    task_type = models.CharField(choices=TaskTypeChoices.choices, max_length=25, default=TaskTypeChoices.TEXT)
    annotation_method = models.CharField(choices=AnnotationMethodChoices.choices, default=AnnotationMethodChoices.AI_AUTOMATED, max_length=20)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_clusters', help_text="User who created this cluster", null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, choices=TaskClusterStatusChoices.choices, default=TaskClusterStatusChoices.PENDING)
    completion_percentage = models.FloatField(default=0, help_text="The percentage of the tasks in this cluster that has been labelled by the reviewers")
    labeler_domain = models.ForeignKey(LabelerDomain, on_delete=models.CASCADE, related_name='clusters', help_text="The domain of expertise that the labeler is allowed to label", null=True, blank=True)
    
    def update_completion_percentage(self):
        all_cluster_labels = TaskLabel.objects.filter(task__cluster=self).count() #get the total number of labels that has been made on this cluster
        required_cluster_labels = self.labeller_per_item_count * self.tasks.count() #get the total number of labels that are required to be made on this cluster
        cluster_completion_percentage = (all_cluster_labels / required_cluster_labels) * 100 if required_cluster_labels > 0 else 0
        self.completion_percentage = round(cluster_completion_percentage, 2) if cluster_completion_percentage else 0
        
        if cluster_completion_percentage >= 100:
            self.status = TaskClusterStatusChoices.COMPLETED
        elif cluster_completion_percentage > 0:
            self.status = TaskClusterStatusChoices.IN_REVIEW
        else:
            self.status = TaskClusterStatusChoices.PENDING
            
        self.save()
        
    class Meta:
        ordering = ["-created_at"]

class MultiChoiceOption(models.Model):
    """
    MultiChoiceOption represents predefined label choices for tasks within a cluster.
    
    This model is used when a cluster requires reviewers to select from a predefined set of labels
    rather than creating custom labels. It's particularly useful for:
    - Standardizing annotation responses across multiple reviewers
    - Ensuring consistency in labeling for specific project requirements
    - Supporting multiple-choice annotation workflows
    - Maintaining quality control in annotation projects
    
    Each option is associated with a specific cluster and can be used by any task within that cluster.
    """
    cluster = models.ForeignKey(TaskCluster, on_delete=models.CASCADE, related_name="choices")
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
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_tasks",
        help_text="User assigned to review this task",
    )

    user = models.ForeignKey(
        User,
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
    file_name = models.CharField(max_length=255, null=True, blank=True)
    file_type= models.CharField(max_length=50, null=True, blank=True)
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
    """
    TaskLabel represents individual labels applied to tasks by human reviewers.
    
    This model enables a flexible labeling system where:
    - Multiple labels can be applied to a single task
    - Each label is tracked with its creator and timestamp
    - Reviewers can add custom labels based on their analysis
    - Labels are not restricted to predefined categories
    - Full audit trail of who labeled what and when
    
    This model replaces the single classification approach used earlier with a more flexible,
    multi-label system that better captures the complexity of real-world content.
    """
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    label = models.CharField(max_length=255, null=True, blank=True, help_text="The text label if the submission type for the task is text") 
    label_file_url = models.URLField(null=True, blank=True, help_text="The url of the file label if the submission type for the task is a e.g a voice recording, video, image, etc")
    labeller = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(null=True)
    subtitles_url = models.URLField(null=True, blank=True, help_text="The url of the subtitles of the labeller for the task if any")
    
    def __str__(self):
        return f"{self.task.serial_no} - {self.labeller.username}"

class ManualReviewSession(models.Model):
    """
    This model is used to track the progress of a human reviewer on the tasks in a task cluster
    """
    labeller = models.ForeignKey(User, on_delete=models.CASCADE)
    cluster = models.ForeignKey(TaskCluster, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=50, choices=ManualReviewSessionStatusChoices.choices, default=ManualReviewSessionStatusChoices.STARTED)
class UserReviewChatHistory(models.Model):
    """
    Tracks the conversation history between human reviewers and AI models during task review.
    
    Stores reviewer feedback, corrections, and confidence scores for AI model improvement.
    Each record represents one interaction in the review process.
    """
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    ai_output = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    human_confidence_score = models.FloatField()
    human_justification = models.TextField()
    human_classification = models.CharField(
        max_length=25, choices=TaskClassificationChoices.choices
    )

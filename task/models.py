from django.db import models

from account.models import CustomUser


class Task(models.Model):
    TASK_TYPES = (
        ('TEXT', 'Text'),
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
    )
    
    PRIORITY_LEVELS = (
        ('URGENT', 'Urgent'),
        ('NORMAL', 'Normal'),
        ('LOW', 'Low'),
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('AI_REVIEWED', 'AI Reviewed'),
        ('HUMAN_REVIEW_NEEDED', 'Human Review Needed'),
        ('COMPLETED', 'Completed'),
    )
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='tasks')
    task_type = models.CharField(max_length=10, choices=TASK_TYPES)
    content = models.TextField(blank=True, null=True)  # For text content
    file = models.FileField(upload_to='content/', blank=True, null=True)  # For image/video
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='NORMAL')
    confidence_threshold = models.FloatField(default=0.9)  # Default 90% confidence required
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Task {self.task_id} ({self.task_type})"



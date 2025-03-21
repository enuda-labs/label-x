from django.db import models
import uuid
import string
import random
from account.models import CustomUser

def generate_serial_no():
    """Generate a random 6-character alphanumeric string"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))

class Task(models.Model):
    TASK_TYPES = (
        ('TEXT', 'Text'),
        ('IMAGE', 'Image'),
        ('VIDEO', 'Video'),
        ('AUDIO', 'Audio'),
        ('MULTIMODAL', 'Multimodal'),
    )
    
    PRIORITY_LEVELS = (
        ('URGENT', 'Urgent'),
        ('NORMAL', 'Normal'),
        ('LOW', 'Low'),
    )
    
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('REVIEW_NEEDED', 'Review Needed'),
        ('COMPLETED', 'Completed'),
        ('ESCALATED', 'Escalated'),
    )
    
    # Basic fields
    serial_no = models.CharField(
        max_length=6, 
        unique=True, 
        default=generate_serial_no,
        editable=False,
        help_text="Auto-generated 6-digit alphanumeric identifier"
    )
    
    task_type = models.CharField(
        max_length=10, 
        choices=TASK_TYPES,
        help_text="Type of content to be processed"
    )
    
    # JSON fields for data and labels
    data = models.JSONField(
        help_text="Task data (text content, file URLs, etc.)"
    )
    
    predicted_label = models.JSONField(
        null=True, 
        blank=True,
        help_text="AI-generated predictions"
    )
    
    final_label = models.JSONField(
        null=True, 
        blank=True,
        help_text="Human-reviewed final label"
    )
    
    # Task status and review tracking
    status = models.CharField(
        max_length=15, 
        choices=STATUS_CHOICES, 
        default='PENDING'
    )
    
    human_reviewed = models.BooleanField(
        default=False,
        help_text="Indicates if a human has reviewed this task"
    )
    
    # Relations
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='created_tasks',
        help_text="User who created the task"
    )
    
    assigned_to = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_tasks',
        help_text="User assigned to review this task"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['serial_no']),
            models.Index(fields=['status']),
            models.Index(fields=['task_type']),
            models.Index(fields=['human_reviewed']),
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



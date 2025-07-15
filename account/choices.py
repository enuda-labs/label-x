from django.db import models


class ProjectStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending"
    IN_PROGRESS = 'in_progress', "In progress"
    COMPLETED = 'completed', 'Completed'
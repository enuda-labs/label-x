from django.db import models

class TransactionStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending'
    FAILED = 'failed', 'Failed'
    SUCCESS = 'success', 'Success'
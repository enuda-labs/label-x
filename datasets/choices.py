from django.db import models

class CohereStatusChoices(models.TextChoices):
    PENDING_UPLOAD = 'pending_upload', 'Pending upload'
    UPLOAD_STARTED = 'upload_started', 'Upload started'
    UPLOADED = 'uploaded', "Uploaded"
    DELETED = 'deleted', 'Deleted'
    FAILED = 'failed', 'Failed'
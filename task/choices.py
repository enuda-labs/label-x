from django.db import models

class TaskInputTypeChoices(models.TextChoices):
    TEXT = 'text', 'Text'
    MULTIPLE_CHOICE = 'multiple_choice', 'Multiple choice'


class AnnotationMethodChoices(models.TextChoices):
    MANUAL = 'manual', "Manual" #means the task is strictly for human reviewers
    AI_AUTOMATED= 'ai_automated', 'Ai automated' #means the task can go through an ai model and if the confidence is low, it then passes through the human
    

class TaskTypeChoices(models.TextChoices):
    TEXT = "TEXT", "Text"
    IMAGE = "IMAGE", "Image"
    VIDEO = "VIDEO", "Video"
    AUDIO = "AUDIO", "Audio",
    CSV = 'CSV', 'Csv'
    MULTIMODAL = "MULTIMODAL", "Multimodal"


class TaskClusterStatusChoices(models.TextChoices):
    PENDING = 'pending', 'Pending' #review has not started for this cluster
    IN_REVIEW = 'in_review', 'In review' #at least one reviewer has reviewed at least one this cluster
    COMPLETED = "completed", 'Completed' #all the reviewers assigned to this cluster have completed the review every task in the cluster


class ManualReviewSessionStatusChoices(models.TextChoices):
    STARTED = 'started', 'Started' #the human has started review for the tasks in a cluster
    COMPLETED = 'completed', 'Completed' #the human has reviewed all the tasks in that cluster
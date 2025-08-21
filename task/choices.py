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
from django.db import models

from task.choices import TaskTypeChoices
from task.models import Task, TaskCluster, TaskLabel
from .choices import CohereStatusChoices
from django.conf import settings
import cohere
import uuid

co = cohere.Client(api_key=settings.CO_API_KEY)



class CohereDataset(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False, unique=True)
    cluster = models.ForeignKey(TaskCluster, on_delete=models.CASCADE, related_name="datasets", null=True)
    dataset_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(choices=CohereStatusChoices.choices, default=CohereStatusChoices.PENDING_UPLOAD, max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(null=True) #the time this dataset was uploaded to cohere
    updated_at = models.DateTimeField(auto_now=True)
    dataset_type = models.CharField(max_length=20, default="embed-input")
    
    def get_json_data(self):
        tasks = Task.objects.filter(cluster=self.cluster)
        parsed_data = []
        
        for task in tasks:
            labels = [str(label.label) for label in TaskLabel.objects.filter(task=task)]
            if task.final_label:
                labels.append(str(task.final_label))
                
            if task.task_type == TaskTypeChoices.TEXT:
                data= [{"text": str(task.file_url), "labels": labels}]
            else:
                data = [{"file_url": str(task.file_url), "labels": labels}]
            parsed_data.append(data)
        
        return parsed_data
        
    
    
    def upload_to_cohere(self):  
        from datasets.tasks import upload_to_cohere_async
        upload_to_cohere_async.delay(self)
        
    def delete_from_cohere(self):
        pass
    
    def retrieve_from_cohere(self):
        pass
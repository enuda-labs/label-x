from django.db import models

from task.models import Task
from .choices import CohereStatusChoices
from django.conf import settings
import cohere
import uuid
from django.utils import timezone

co = cohere.Client(api_key=settings.CO_API_KEY)
import json
import tempfile
import os


class CohereDataset(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False, unique=True)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="datasets")
    dataset_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(choices=CohereStatusChoices.choices, default=CohereStatusChoices.PENDING_UPLOAD, max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)
    uploaded_at = models.DateTimeField(null=True) #the time this dataset was uploaded to cohere
    updated_at = models.DateTimeField(auto_now=True)
    dataset_type = models.CharField(max_length=20, default="embed-input")
    
    def get_json_data(self):
        # return a list of json objects that
        return [    
            {"text": str(self.task.data), "label": str(self.task.final_label)},      
        ]
    
    
    def upload_to_cohere(self):         
        # create a temporary file and embed the jsonl data that is to be uploaded to cohere
        temp_file_path= None
        json_data = self.get_json_data()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding='utf-8') as f:
            for data in json_data:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            
            temp_file_path = f.name
            
        dataset = co.datasets.create(
            name=f"ds-{self.task.id}-{self.id}",
            data=open(temp_file_path, 'rb'),
            type=self.dataset_type
        )
        
       
        os.unlink(temp_file_path) #remove the temporary file from memory

        self.dataset_id = dataset.id
        self.status = CohereStatusChoices.UPLOAD_STARTED
        self.uploaded_at = timezone.now()
        self.save(update_fields=['dataset_id', 'status', 'uploaded_at'])
        
        # wait for cohere to complete validation on this dataset
        # completed_dataset = co.wait(dataset)
        # print(completed_dataset.dataset.validation_status)
        
    def delete_from_cohere(self):
        pass
    
    def retrieve_from_cohere(self):
        pass
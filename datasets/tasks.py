from celery import shared_task
import cohere
from django.conf import settings

from datasets.models import CohereDataset
import json
import tempfile
import os
from .choices import CohereStatusChoices
from django.utils import timezone


co = cohere.Client(api_key=settings.CO_API_KEY)


@shared_task
def upload_to_cohere_async(cohere_dataset_id):
    try:
        # create a temporary file and embed the jsonl data that is to be uploaded to cohere
        cohere_dataset= CohereDataset.objects.get(id=cohere_dataset_id)
        
        temp_file_path= None
        json_data = cohere_dataset.get_json_data()
        print('the json data', json_data)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding='utf-8') as f:
            for data in json_data:
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
            
            temp_file_path = f.name
            
        dataset = co.datasets.create(
            name=f"ds-{cohere_dataset.cluster.task_type}-{cohere_dataset.id}",
            data=open(temp_file_path, 'rb'),
            type=cohere_dataset.dataset_type
        )
        
        
        os.unlink(temp_file_path) #remove the temporary file from memory
        
        # wait for cohere to complete validation on this dataset
        completed_dataset = co.wait(dataset)
        
        upload_status=  completed_dataset.dataset.validation_status
        if upload_status == 'validated':            
            cohere_dataset.dataset_id = dataset.id
            cohere_dataset.status = CohereStatusChoices.UPLOAD_STARTED
            cohere_dataset.uploaded_at = timezone.now()
            cohere_dataset.save(update_fields=['dataset_id', 'status', 'uploaded_at'])
        
    except CohereDataset.DoesNotExist:
        print('could not find cohere dataset') #TODO: log this
    except Exception as e:
        cohere_dataset.status = CohereStatusChoices.FAILED
        cohere_dataset.save(update_fields=['status'])
        print(f'An error occurred, {e}')
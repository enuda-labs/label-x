from rest_framework import generics

from common.responses import ErrorResponse, SuccessResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

import cohere
from django.conf import settings

from datasets.choices import CohereStatusChoices
from datasets.models import CohereDataset
from datasets.tasks import upload_to_cohere_async
from task.models import TaskCluster

co = cohere.Client(api_key=settings.CO_API_KEY)


class UploadClusterDatasetView(generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        cluster_id = kwargs.get('cluster_id')
        print(cluster_id)
        
        try:
            cluster= TaskCluster.objects.get(id=cluster_id)
        except TaskCluster.DoesNotExist:
            return ErrorResponse(message="Cluster not found", status=status.HTTP_404_NOT_FOUND)
        
        cohere_dataset, created =  CohereDataset.objects.get_or_create(cluster=cluster)
        upload_to_cohere_async.delay(cohere_dataset.id)
        return SuccessResponse(message="Upload to cohere queued successfully")

class DeleteCohereDataset(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, *args, **kwargs):
        dataset_id = kwargs.get('id')
        local_dataset = CohereDataset.objects.filter(dataset_id=dataset_id).exclude(status=CohereStatusChoices.DELETED).first()
        if not local_dataset:
            return ErrorResponse(message="Dataset not found", status=status.HTTP_404_NOT_FOUND)
        
        try:
            co.datasets.delete(id=dataset_id)
            local_dataset.status = CohereStatusChoices.DELETED
            local_dataset.save(update_fields=['status'])
            return SuccessResponse(message="Dataset deleted successfully")
        except Exception as e:
            return ErrorResponse(message=f"Failed to delete dataset: {e}")
        



class GetCohereDatasetById(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, *args, **kwargs):
        dataset_id = kwargs.get('id')
        
        local_dataset = CohereDataset.objects.filter(dataset_id=dataset_id).exclude(status=CohereStatusChoices.DELETED).first()
        if not local_dataset:
            return ErrorResponse(message="Dataset not found", status=status.HTTP_404_NOT_FOUND)
        
        try:
            response = co.datasets.get(id=dataset_id)
            return SuccessResponse(data=response)
        except Exception as e:
            return ErrorResponse(message=f"Error fetching from cohere {e}")
        
        
        

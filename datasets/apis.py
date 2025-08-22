from rest_framework import generics

from common.responses import ErrorResponse, SuccessResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

import cohere
from django.conf import settings

from datasets.choices import CohereStatusChoices
from datasets.models import CohereDataset

co = cohere.Client(api_key=settings.CO_API_KEY)


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
        
        
        

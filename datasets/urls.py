from django.urls import path
from . import apis

urlpatterns = [
    path('<str:id>/cohere/', apis.GetCohereDatasetById.as_view(), name='get-cohere-dataset'),
    path('<str:id>/cohere/delete/', apis.DeleteCohereDataset.as_view(), name='delete-cohere-dataset'),
    path('cluster/<int:cluster_id>/upload/', apis.UploadClusterDatasetView.as_view(), name='upload-cohere-dataset')
]


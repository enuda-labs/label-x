from drf_spectacular.utils import extend_schema
from rest_framework import generics
from common.caching import cache_response_decorator
from account.models import LabelerDomain
from .serializers import LabelerDomainSerializer

class GetLabelerDomains(generics.ListAPIView):
    serializer_class = LabelerDomainSerializer
    queryset = LabelerDomain.objects.all()
    
    
    @cache_response_decorator('labeler_domains')
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(
        summary="Get all labeler domains",
        description="Get all labeler domains",
        responses={
            200: LabelerDomainSerializer(many=True),
        }
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
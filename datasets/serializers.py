from rest_framework import serializers

from datasets.models import CohereDataset


class CohereDatasetDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CohereDataset
        fields = "__all__"
    
    
    # 
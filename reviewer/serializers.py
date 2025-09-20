from rest_framework import serializers
from .models import LabelerDomain


class LabelerDomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabelerDomain
        fields = "__all__"
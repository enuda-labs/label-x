from django.contrib import admin
from .models import LabelerDomain

@admin.register(LabelerDomain)
class LabelerDomainAdmin(admin.ModelAdmin):
    list_display = ['domain', 'labeler_count', 'created_at', 'updated_at']
    search_fields = ['domain']
    readonly_fields = ['created_at', 'updated_at']
    
    def labeler_count(self, obj):
        return obj.labelers.count()
    labeler_count.short_description = 'Labelers'

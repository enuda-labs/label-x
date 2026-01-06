from django.core.management.base import BaseCommand
from reviewer.models import LabelerDomain

class Command(BaseCommand):
    help = "Seed initial labeler domains"

    def handle(self, *args, **kwargs):
        domains = [
            "Image Annotation",
            "Video Annotation",
            "Text Annotation",
            "Audio Annotation",
            "3D Point Cloud Annotation",
            "Lidar Annotation",
            "Medical Imaging Annotation",
            "Geospatial Annotation",
            "Document Processing",
            "Data Collection",
            "Data Validation",
            "Quality Assurance",
            "Other",
        ]

        for domain_name in domains:
            domain, created = LabelerDomain.objects.get_or_create(domain=domain_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created domain: {domain_name}"))
            else:
                self.stdout.write(f"Skipped domain: {domain_name} (already exists)")

        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully seeded {len(domains)} labeler domains!"))


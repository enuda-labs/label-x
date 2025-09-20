# core/management/commands/seed_system_settings.py
from django.core.management.base import BaseCommand
from common.models import SystemSetting

class Command(BaseCommand):
    help = "Seed initial system settings"

    def handle(self, *args, **kwargs):
        initial_settings = [
            {"key": "base_cost", "value": "10"},
            {"key": "dp_cost_per_labeller", "value": "10"},
            {"key": "video_cost", "value": "10"},
            {"key": "audio_cost", "value": "10"},
            {"key": "image_cost", "value": "5"},
            {"key": "text_cost", "value": "1"},
            {"key": "multiple_choice_cost", "value": "1"},
            {"key": "task_voice_cost", "value": "10"},
            {"key": "task_text_cost", "value": "5"},
            {"key": "task_image_cost", "value": "10"},
            {"key": "task_video_cost", "value": "20"},
            {"key": "task_audio_cost", "value": "15"},
            {"key": "task_csv_cost", "value": "8"},
        ]

        for setting in initial_settings:
            SystemSetting.objects.update_or_create(
                key=setting["key"], defaults={"value": setting["value"]}
            )

        self.stdout.write(self.style.SUCCESS("System settings seeded successfully!"))

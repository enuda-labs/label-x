from django.db import models


class SystemSetting(models.Model):
    """
    A system setting is a key-value pair that can be used to store configuration settings for the system.
    This is used to store the cost of different types of inputs and tasks.
    For example, the cost of an input video, the cost of a task video, the cost of a task audio, the cost of a task image, the cost of a task text.
    """
    key = models.CharField(max_length=50, unique=True) # example: input_video_cost
    value = models.CharField(max_length=100) # example: 10

    def __str__(self):
        return f"{self.key} → {self.value}"

    def as_int(self):
        try:
            return int(self.value)
        except ValueError:
            return 0

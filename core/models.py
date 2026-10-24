from django.db import models


class ExtractionJob(models.Model):
    """Tracks an async extraction job queued via django-tasks."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    task_name = models.CharField(max_length=64)
    source_path = models.CharField(max_length=512)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
    )
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"ExtractionJob<{self.pk} {self.task_name} {self.status}>"

from django.contrib import admin

from core.models import ExtractionJob


@admin.register(ExtractionJob)
class ExtractionJobAdmin(admin.ModelAdmin):
    """Admin view for monitoring extraction job status."""

    list_display = (
        "id",
        "task_name",
        "status",
        "created_at",
        "finished_at",
    )
    list_filter = ("status", "task_name", "created_at")
    search_fields = ("id", "task_name", "source_path", "error_message")
    readonly_fields = (
        "id",
        "task_name",
        "source_path",
        "status",
        "result",
        "error_message",
        "created_at",
        "finished_at",
    )
    ordering = ("-created_at",)

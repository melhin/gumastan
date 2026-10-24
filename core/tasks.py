"""Background tasks for the extraction pipeline."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.tasks import task
from django.utils import timezone

from core.extraction.exceptions import (
    ExtractionError,
    JSONParseError,
    LLMError,
    ModelLoadError,
    OCRError,
)
from core.extraction.pipeline import ExtractionPipeline
from core.models import ExtractionJob
from core.pipelines import TASKS


@lru_cache
def get_pipeline():
    return ExtractionPipeline(Path(settings.EVENT_MODEL_PATH))

@task
def run_extraction(job_id: int) -> None:
    """Run the extraction pipeline for a queued job."""
    job = ExtractionJob.objects.get(pk=job_id)
    job.status = ExtractionJob.Status.RUNNING
    job.save()

    pipeline = get_pipeline()
    task_config = TASKS.get(job.task_name)
    if task_config is None:
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"unknown task '{job.task_name}'"
        job.finished_at = timezone.now()
        job.save()
        return

    try:
        result = pipeline.run(job.source_path, task_config)
        job.status = ExtractionJob.Status.SUCCEEDED
        job.result = result.model_dump(mode="json")
    except OCRError as exc:
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"ocr_failed: {exc}"
    except JSONParseError as exc:
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"model_output_unparseable: {exc}"
    except LLMError as exc:
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"model_generation_failed: {exc}"
    except ModelLoadError as exc:
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"model_load_failed: {exc}"
    except ExtractionError as exc:
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"extraction_failed: {exc}"
    except FileNotFoundError as exc:
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"file_not_found: {exc}"
    except Exception as exc:  # noqa: BLE001
        job.status = ExtractionJob.Status.FAILED
        job.error_message = f"internal_error: {exc}"
    finally:
        job.finished_at = timezone.now()
        job.save()

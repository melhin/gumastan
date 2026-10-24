"""HTTP endpoints for extraction pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from asgiref.sync import sync_to_async
from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.models import ExtractionJob
from core.pipelines import TASKS
from core.tasks import run_extraction

MAX_BODY_BYTES = getattr(settings, "MAX_BODY_BYTES", 20 * 1024 * 1024)


def _read_source(request: HttpRequest) -> str | Path | bytes:
    """Pull the image out of a multipart, raw, or JSON request."""
    if request.FILES:
        upload = request.FILES.get("image")
        if upload is None:
            msg = "expected a file field named 'image'"
            raise ValueError(msg)
        if upload.size > MAX_BODY_BYTES:
            msg = f"upload exceeds {MAX_BODY_BYTES} bytes"
            raise ValueError(msg)
        return upload.read()

    content_type = request.content_type or ""
    if content_type.startswith("application/json"):
        if not settings.DEBUG:
            msg = "image_path is only available when DEBUG is on; upload instead"
            raise ValueError(msg)
        payload = json.loads(request.body)
        return Path(payload["image_path"])

    if content_type.startswith("image/"):
        body = request.body
        if len(body) > MAX_BODY_BYTES:
            msg = f"request body exceeds {MAX_BODY_BYTES} bytes"
            raise ValueError(msg)
        return body

    msg = "send an image file, raw image bytes, or {'image_path': ...}"
    raise ValueError(msg)


def _write_temp_file(source: bytes, suffix: str) -> str:
    """Persist raw request bytes to a temp file and return its path."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(source)
        return tmp.name


@require_GET
def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
async def extract(request: HttpRequest, task: str) -> JsonResponse:
    task_config = TASKS.get(task)
    if task_config is None:
        known = ", ".join(TASKS.keys())
        return JsonResponse(
            {"error": f"unknown task '{task}'; known: {known}"},
            status=404,
        )

    try:
        source = await sync_to_async(_read_source, thread_sensitive=False)(request)
    except (KeyError, TypeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if isinstance(source, Path):
        source_path = str(source)
    else:
        content_type = request.content_type or ""
        if content_type.startswith("image/"):
            ext = content_type.split("/")[-1].split("+")[0]
            suffix = f".{ext}"
        else:
            suffix = ".bin"
        source_path = await sync_to_async(_write_temp_file, thread_sensitive=False)(
            source, suffix
        )

    job = await ExtractionJob.objects.acreate(
        task_name=task,
        source_path=source_path,
        status=ExtractionJob.Status.PENDING,
    )

    await run_extraction.aenqueue(job.id)

    return JsonResponse({"job_id": job.id, "status": job.status})


@require_GET
def job_status(request: HttpRequest, job_id: int) -> JsonResponse:
    try:
        job = ExtractionJob.objects.get(pk=job_id)
    except ExtractionJob.DoesNotExist:
        return JsonResponse({"error": "not found"}, status=404)

    data = {
        "job_id": job.id,
        "status": job.status,
        "task_name": job.task_name,
        "created_at": job.created_at.isoformat(),
    }
    if job.finished_at:
        data["finished_at"] = job.finished_at.isoformat()
    if job.status == ExtractionJob.Status.SUCCEEDED:
        data["result"] = job.result
    elif job.status == ExtractionJob.Status.FAILED:
        data["error"] = job.error_message

    return JsonResponse(data)

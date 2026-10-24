"""HTTP endpoints for extraction pipeline."""

from __future__ import annotations

import json
import threading
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.extraction.exceptions import ExtractionError
from core.extraction.exceptions import JSONParseError
from core.extraction.exceptions import LLMError
from core.extraction.exceptions import ModelLoadError
from core.extraction.exceptions import OCRError
from core.extraction.pipeline import ExtractionPipeline
from core.pipelines import TASKS

MAX_BODY_BYTES = getattr(settings, "MAX_BODY_BYTES", 20 * 1024 * 1024)

_inference_lock = threading.Lock()
_pipeline_error: str | None = None


@lru_cache(maxsize=1)
def _get_pipeline() -> ExtractionPipeline:
    """Load the models once per process."""
    return ExtractionPipeline(Path(settings.EVENT_MODEL_PATH))


def _pipeline() -> ExtractionPipeline | JsonResponse:
    """Return the loaded pipeline, or a JsonResponse if the model is missing."""
    global _pipeline_error  # noqa: PLW0603
    if _pipeline_error is not None:
        return JsonResponse(
            {"error": f"model not loaded: {_pipeline_error}"},
            status=503,
        )
    try:
        return _get_pipeline()
    except Exception as exc:  # noqa: BLE001
        _pipeline_error = str(exc)
        return JsonResponse(
            {"error": f"model not loaded: {_pipeline_error}"},
            status=503,
        )


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


@require_GET
def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@csrf_exempt
@require_POST
def extract(request: HttpRequest, task: str) -> JsonResponse:
    task_config = TASKS.get(task)
    if task_config is None:
        known = ", ".join(TASKS.keys())
        return JsonResponse(
            {"error": f"unknown task '{task}'; known: {known}"},
            status=404,
        )

    try:
        source = _read_source(request)
    except (KeyError, TypeError, ValueError) as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    maybe_pipeline = _pipeline()
    if isinstance(maybe_pipeline, JsonResponse):
        return maybe_pipeline

    try:
        with _inference_lock:
            result = maybe_pipeline.run(source, task_config)
    except OCRError as exc:
        return JsonResponse(
            {"error": "ocr_failed", "message": str(exc)},
            status=422,
        )
    except JSONParseError as exc:
        return JsonResponse(
            {"error": "model_output_unparseable", "message": str(exc)},
            status=422,
        )
    except LLMError as exc:
        return JsonResponse(
            {"error": "model_generation_failed", "message": str(exc)},
            status=500,
        )
    except ModelLoadError as exc:
        return JsonResponse(
            {"error": "model_load_failed", "message": str(exc)},
            status=503,
        )
    except ExtractionError as exc:
        return JsonResponse(
            {"error": "extraction_failed", "message": str(exc)},
            status=422,
        )
    except FileNotFoundError as exc:
        return JsonResponse(
            {"error": "file_not_found", "message": str(exc)},
            status=400,
        )
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {"error": "internal_error", "message": str(exc)},
            status=500,
        )

    return JsonResponse(result.model_dump(mode="json"))

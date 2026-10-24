"""Django system checks for the extraction pipeline."""

from pathlib import Path

from django.conf import settings
from django.core.checks import Error, register


@register()
def check_model_files(app_configs, **kwargs):
    """Verify the ONNX model directory exists and contains required files."""
    errors = []
    model_path = getattr(settings, "EVENT_MODEL_PATH", None)

    if model_path is None:
        errors.append(
            Error(
                "EVENT_MODEL_PATH is not set in settings.",
                hint="Set EVENT_MODEL_PATH = BASE_DIR / 'models' in settings.py.",
                id="extraction.E001",
            ),
        )
        return errors

    model_path = Path(model_path)

    required_files = [
        "genai_config.json",
        "config.json",
        "tokenizer.json",
    ]

    if not model_path.exists():
        errors.append(
            Error(
                f"Model directory does not exist: {model_path}",
                hint="Run `python scripts/download_models.py` to fetch the model, "
                     "or set EVENT_MODEL_PATH env var to the correct path.",
                id="extraction.E002",
            ),
        )
        return errors

    for filename in required_files:
        if not (model_path / filename).is_file():
            errors.append(
                Error(
                    f"Model directory is missing required file: {filename}",
                    hint=f"Run `python scripts/download_models.py` to fetch the model "
                         f"into {model_path}.",
                    id="extraction.E003",
                ),
            )

    return errors

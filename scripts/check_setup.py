"""Pre-load OCR models and verify the extraction model exists.

Run during Docker build so both model sets are baked into the image.
"""

import io
import os
import sys
from pathlib import Path

from PIL import Image
from rapidocr import EngineType
from rapidocr import ModelType
from rapidocr import OCRVersion
from rapidocr import RapidOCR


def _download_ocr_models() -> None:
    """Create a dummy image and run it through OCR to force model downloads."""
    engine = RapidOCR(
        params={
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV4,
        },
    )

    # Create a blank white image — big enough for RapidOCR to process.
    img = Image.new("RGB", (100, 30), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    # Trigger lazy downloads for det + cls + rec in one call.
    engine(buf.read())
    print("RapidOCR models ready")


def _verify_extraction_model() -> None:
    """Check required extraction model files exist."""
    model_path = Path(os.environ.get("EVENT_MODEL_PATH", "/app/models"))
    required = ["genai_config.json", "config.json", "tokenizer.json"]
    missing = [f for f in required if not (model_path / f).is_file()]
    if missing:
        print(
            f"Model directory {model_path} is missing: {missing}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"Extraction model OK: {model_path}")


if __name__ == "__main__":
    _download_ocr_models()
    _verify_extraction_model()

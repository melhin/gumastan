"""OCR module — turn images into reading-order text."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidocr import EngineType, ModelType, OCRVersion, RapidOCR

from core.extraction.exceptions import OCRError


def _rapidocr_parts(result: Any) -> tuple[list[Any], list[str], list[float]]:
    if isinstance(result, tuple):
        result = result[0]
    if result is None:
        return [], [], []

    if hasattr(result, "boxes"):
        boxes = result.boxes if result.boxes is not None else []
        texts = result.txts if result.txts is not None else []
        scores = result.scores if result.scores is not None else []
        return list(boxes), list(texts), list(scores)

    boxes: list[Any] = []
    texts: list[str] = []
    scores: list[float] = []
    for item in result:
        if len(item) < 2:
            continue
        boxes.append(item[0])
        texts.append(item[1])
        scores.append(item[2] if len(item) > 2 else 1.0)
    return boxes, texts, scores


def _box_bounds(box: Any) -> tuple[float, float, float, float]:
    if hasattr(box, "tolist"):
        box = box.tolist()
    if isinstance(box, (list, tuple)) and box and isinstance(box[0], (list, tuple)):
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(box, (list, tuple)) and len(box) >= 4:
        return float(box[0]), float(box[1]), float(box[2]), float(box[3])
    return 0.0, 0.0, 0.0, 0.0


@dataclass
class TextLine:
    text: str
    box: tuple[float, float, float, float]
    confidence: float


@dataclass
class Layout:
    lines: list[TextLine]
    text: str
    annotated: str


class _LayoutAnnotator:
    """Turn OCR boxes into reading-order lines with coordinates."""

    def annotate(
        self,
        boxes: list[Any],
        texts: list[str],
        scores: list[float],
    ) -> Layout:
        lines: list[TextLine] = []
        for index, text in enumerate(texts):
            if not text:
                continue
            box = boxes[index] if index < len(boxes) else None
            score = scores[index] if index < len(scores) else 1.0
            x0, y0, x1, y1 = _box_bounds(box)
            lines.append(
                TextLine(
                    text=str(text).strip(),
                    box=(x0, y0, x1, y1),
                    confidence=float(score) if score is not None else 1.0,
                ),
            )

        lines.sort(key=lambda line: (line.box[1], line.box[0]))
        grouped = self._group_lines(lines)

        out_lines: list[TextLine] = []
        for group in grouped:
            group.sort(key=lambda line: line.box[0])
            text = " ".join(line.text for line in group)
            x0 = min(line.box[0] for line in group)
            y0 = min(line.box[1] for line in group)
            x1 = max(line.box[2] for line in group)
            y1 = max(line.box[3] for line in group)
            confidence = sum(line.confidence for line in group) / len(group)
            out_lines.append(TextLine(text, (x0, y0, x1, y1), confidence))

        text = "\n".join(line.text for line in out_lines)
        annotated = "\n".join(line.text for line in out_lines)
        return Layout(lines=out_lines, text=text, annotated=annotated)

    @staticmethod
    def _group_lines(lines: list[TextLine]) -> list[list[TextLine]]:
        groups: list[list[TextLine]] = []
        for line in lines:
            line_center = (line.box[1] + line.box[3]) / 2
            line_height = max(1.0, line.box[3] - line.box[1])
            placed = False
            for group in groups:
                reference = group[0]
                ref_center = (reference.box[1] + reference.box[3]) / 2
                ref_height = max(1.0, reference.box[3] - reference.box[1])
                tolerance = min(ref_height, line_height) * 0.5
                if abs(line_center - ref_center) <= tolerance:
                    group.append(line)
                    placed = True
                    break
            if not placed:
                groups.append([line])
        return groups


def create_engine() -> RapidOCR:
    """Build the OCR engine with the project's default models."""
    return RapidOCR(
        params={
            "Rec.engine_type": EngineType.ONNXRUNTIME,
            "Rec.model_type": ModelType.MOBILE,
            "Rec.ocr_version": OCRVersion.PPOCRV4,
        },
    )


def extract_layout(image: str | Path | bytes, engine: RapidOCR | None = None) -> Layout:
    """Run OCR on an image and return reading-order lines with coordinates."""
    try:
        engine = engine or create_engine()
        result = engine(image if isinstance(image, bytes) else str(image))
    except Exception as exc:
        raise OCRError(f"OCR engine failed: {exc}") from exc

    if result is None:
        raise OCRError("OCR returned no text — image may be blank or unreadable")

    boxes, texts, scores = _rapidocr_parts(result)

    if not texts:
        raise OCRError("OCR returned no text — image may be blank or unreadable")

    return _LayoutAnnotator().annotate(boxes, texts, scores)


def extract_text(image: str | Path | bytes, engine: RapidOCR | None = None) -> str:
    """Run OCR on an image and return the reading-order text."""
    return extract_layout(image, engine=engine).annotated

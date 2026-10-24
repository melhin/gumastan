"""Extraction-pipeline exception hierarchy."""


class ExtractionError(Exception):
    """Base class for extraction pipeline failures."""

    pass


class OCRError(ExtractionError):
    """OCR failed to produce text from the image."""

    pass


class LLMError(ExtractionError):
    """ONNX LLM loading or generation failed."""

    pass


class ModelLoadError(LLMError):
    """ONNX model files are missing, corrupt, or incompatible."""

    pass


class GenerationError(LLMError):
    """ONNX model failed to generate text for a prompt."""

    pass


class JSONParseError(LLMError):
    """Model output does not contain valid JSON."""

    pass

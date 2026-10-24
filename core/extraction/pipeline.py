"""Generic extraction pipeline: image → OCR → LLM → Pydantic model.

Each task differs only by its prompt / response model,
not by model or OCR layer.
"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from core.extraction.exceptions import ExtractionError
from core.extraction.llm import MODEL_PATH, generate, load_extractor, parse_json
from core.extraction.ocr import create_engine, extract_layout

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class TaskConfig:
    """Configuration for a single extraction task.

    All tasks share the same ONNX model and OCR engine.
    The prompt uses a concise schema string that is easy for small LLMs to
    follow, while the response_model validates the output afterwards.
    """

    name: str
    system_prompt: str
    response_model: type[BaseModel]
    user_template: str
    # Human-readable schema shown to the LLM in the prompt.
    schema_str: str
    # Max tokens the model may generate for this task.
    max_new_tokens: int = 500

    @property
    def schema(self) -> str:
        return self.schema_str


def _build_prompt(task: TaskConfig, text: str) -> str:
    """Render the Qwen3 ChatML prompt for a given task."""
    user = task.user_template.format(schema=task.schema, text=text)
    return (
        f"<|im_start|>system\n{task.system_prompt}ของ\n"
        f"<|im_start|>user\n{user}ของ\n"
        "<|im_start|>assistant\n"
        " thinking\n\n</think>\n\n"
    )


class ExtractionPipeline:
    """OCR + LLM extraction with models loaded once per process."""

    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.engine = create_engine()
        self.model, self.tokenizer = load_extractor(model_path)

    def run(
        self,
        image: str | Path | bytes,
        task: TaskConfig,
        *,
        echo: bool = False,
    ) -> BaseModel:
        """Extract structured data from a screenshot via OCR and LLM."""
        layout = extract_layout(image, engine=self.engine)
        prompt = _build_prompt(task, layout.annotated)
        raw = generate(
            self.model,
            self.tokenizer,
            prompt,
            max_new_tokens=task.max_new_tokens,
            echo=echo,
        )
        gc.collect()
        data = parse_json(raw)

        try:
            return task.response_model.model_validate(data)
        except PydanticValidationError as exc:
            details = exc.json(include_url=False, include_context=False)
            raise ExtractionError(
                f"Model output does not match expected schema: {details}",
            ) from exc


@lru_cache(maxsize=1)
def _default_pipeline() -> ExtractionPipeline:
    """Load the default pipeline once per process."""
    return ExtractionPipeline()


def extract(
    image: str | Path | bytes,
    task: TaskConfig,
    *,
    echo: bool = False,
) -> BaseModel:
    """One-shot wrapper around the cached default pipeline."""
    return _default_pipeline().run(image, task, echo=echo)

"""ONNX LLM module — load model and generate structured JSON from text."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import onnxruntime_genai as og

from core.extraction.exceptions import GenerationError
from core.extraction.exceptions import JSONParseError
from core.extraction.exceptions import ModelLoadError

MAX_NEW_TOKENS = 200


def _default_model_path() -> Path:
    if env_path := os.environ.get("EVENT_MODEL_PATH"):
        return Path(env_path)
    return Path(__file__).resolve().parents[2] / "models"


MODEL_PATH = _default_model_path()


def load_model(model_dir: Path) -> og.Model:
    """Load an ONNX model, patching incomplete genai configs on the fly."""
    try:
        config = og.Config(str(model_dir))
    except Exception as exc:
        raise ModelLoadError(f"Failed to create ONNX config for {model_dir}: {exc}") from exc

    config.clear_providers()

    try:
        genai = json.loads(
            (model_dir / "genai_config.json").read_text(encoding="utf-8"),
        )
    except FileNotFoundError as exc:
        raise ModelLoadError(f"genai_config.json not found in {model_dir}") from exc
    except json.JSONDecodeError as exc:
        raise ModelLoadError(f"genai_config.json is invalid JSON: {exc}") from exc

    if not genai.get("model", {}).get("vocab_size"):
        try:
            hf = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ModelLoadError(f"config.json not found in {model_dir}") from exc
        except json.JSONDecodeError as exc:
            raise ModelLoadError(f"config.json is invalid JSON: {exc}") from exc
        config.overlay(
            json.dumps(
                {
                    "model": {
                        "vocab_size": hf["vocab_size"],
                        "bos_token_id": hf["bos_token_id"],
                        "eos_token_id": hf["eos_token_id"],
                        "pad_token_id": hf.get("pad_token_id", hf["bos_token_id"]),
                    },
                },
            ),
        )
    try:
        return og.Model(config)
    except Exception as exc:
        raise ModelLoadError(f"ONNX model failed to load from {model_dir}: {exc}") from exc


def load_extractor(
    model_dir: Path = MODEL_PATH,
) -> tuple[og.Model, og.Tokenizer]:
    """Load the model and its tokenizer."""
    model = load_model(model_dir)
    try:
        tokenizer = og.Tokenizer(model)
    except Exception as exc:
        raise ModelLoadError(f"Tokenizer failed to load: {exc}") from exc
    return model, tokenizer


def generate(
    model: og.Model,
    tokenizer: og.Tokenizer,
    prompt: str,
    *,
    max_new_tokens: int = MAX_NEW_TOKENS,
    echo: bool = False,
) -> str:
    """Run greedy decoding and return the generated text."""
    try:
        input_tokens = tokenizer.encode(prompt)
    except Exception as exc:
        raise GenerationError(f"Tokenizer encode failed: {exc}") from exc

    params = og.GeneratorParams(model)
    params.set_search_options(
        max_length=len(input_tokens) + max_new_tokens,
        do_sample=False,
    )

    try:
        generator = og.Generator(model, params)
        generator.append_tokens(input_tokens)
    except Exception as exc:
        raise GenerationError(f"Failed to create ONNX generator: {exc}") from exc

    stream = tokenizer.create_stream()
    chunks: list[str] = []
    try:
        while not generator.is_done():
            generator.generate_next_token()
            chunk = stream.decode(generator.get_next_tokens()[0])
            chunks.append(chunk)
            if echo:
                print(chunk, end="", flush=True)
    except Exception as exc:
        raise GenerationError(f"Generation failed: {exc}") from exc

    if echo:
        print()

    return "".join(chunks)


def parse_json(raw: str) -> dict:
    """Pull the first JSON object out of the model output."""
    if not raw or not raw.strip():
        raise JSONParseError("Model returned empty output")

    start = raw.find("{")
    if start == -1:
        raise JSONParseError(f"No JSON object found in model output: {raw[:200]!r}")

    try:
        data, _ = json.JSONDecoder().raw_decode(raw[start:])
    except json.JSONDecodeError as exc:
        snippet = raw[start : start + 200]
        raise JSONParseError(
            f"Model output contains invalid JSON near: {snippet!r} ({exc})",
        ) from exc

    if not isinstance(data, dict):
        raise JSONParseError(f"Model output is JSON but not an object: {type(data).__name__}")

    return data


@lru_cache(maxsize=1)
def _default_extractor() -> tuple[og.Model, og.Tokenizer]:
    """Load the default model once per process."""
    return load_extractor()

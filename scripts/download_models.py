#!/usr/bin/env python3
"""Download the Qwen3-0.6B ONNX model (CPU variant) into ./models.

The model files are large (~500 MB) and are not committed to git. Run this
script once after cloning, or let the Docker build run it for you.

The upstream repo ships several variants (CPU, CUDA, WebGPU). This script
downloads only the CPU variant and copies its files to the top level of the
output directory, so ``EVENT_MODEL_PATH`` can point at ``./models`` directly.

Usage:
    python scripts/download_models.py
    python scripts/download_models.py --force
    python scripts/download_models.py --output-dir /path/to/models

Requires either the Hugging Face CLI (``hf``, from ``huggingface_hub``) or
network access to huggingface.co (falls back to plain HTTPS downloads).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_ID = "onnx-community/Qwen3-0.6B-ONNX"
VARIANT = "cpu-int4-kld-block-128"
VARIANT_PATH = f"onnxruntime/cpu_and_mobile/{VARIANT}"
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

# Files that must be present for the extraction pipeline to load the model.
REQUIRED_FILES = (
    "genai_config.json",
    "config.json",
    "tokenizer.json",
    "model.onnx",
)

# Files the CPU variant is expected to contain. Used by the HTTPS fallback.
VARIANT_FILES = (
    "chat_template.jinja",
    "config.json",
    "genai_config.json",
    "model.onnx",
    "tokenizer.json",
    "tokenizer_config.json",
)


def _is_complete(output_dir: Path) -> bool:
    return all((output_dir / name).is_file() for name in REQUIRED_FILES)


def _download_with_hf_cli(staging: Path) -> bool:
    """Download the variant with the `hf` CLI. Returns False if unavailable."""
    hf = shutil.which("hf")
    if hf is None:
        return False

    print(f"Downloading {REPO_ID} ({VARIANT}) with the hf CLI...")
    subprocess.run(
        [
            hf,
            "download",
            REPO_ID,
            "--local-dir",
            str(staging),
            "--include",
            f"{VARIANT_PATH}/*",
        ],
        check=True,
    )
    return True


def _download_with_urllib(staging: Path) -> None:
    """Download the variant files directly over HTTPS (no extra dependencies)."""
    print(f"Downloading {REPO_ID} ({VARIANT}) over HTTPS...")
    for name in VARIANT_FILES:
        url = f"https://huggingface.co/{REPO_ID}/resolve/main/{VARIANT_PATH}/{name}"
        destination = staging / VARIANT_PATH / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        print(f"  {name}")
        request = urllib.request.Request(url, headers={"User-Agent": "gumastan-model-downloader"})
        with urllib.request.urlopen(request) as response, destination.open("wb") as handle:
            shutil.copyfileobj(response, handle)


def _copy_variant(staging: Path, output_dir: Path) -> None:
    """Copy the downloaded CPU variant files to the top level of output_dir."""
    source = staging / VARIANT_PATH
    if not source.is_dir():
        raise FileNotFoundError(
            f"Downloaded variant not found at {source}. Check the repo layout.",
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        if item.is_file():
            shutil.copy2(item, output_dir / item.name)
            print(f"  copied {item.name}")


def _generate_genai_config(output_dir: Path) -> None:
    """Create genai_config.json from config.json when upstream does not ship one."""
    config = json.loads((output_dir / "config.json").read_text(encoding="utf-8"))
    eos_token_id = config.get("eos_token_id", config["bos_token_id"])
    if isinstance(eos_token_id, int):
        eos_token_id = [eos_token_id]

    genai_config = {
        "model": {
            "type": config.get("model_type", "qwen3"),
            "vocab_size": config["vocab_size"],
            "bos_token_id": config["bos_token_id"],
            "eos_token_id": eos_token_id,
            "pad_token_id": config.get("pad_token_id") or config["bos_token_id"],
            "context_length": config.get("max_position_embeddings", 40960),
            "decoder": {
                "filename": "model.onnx",
                "head_size": config.get("head_dim", 128),
                "hidden_size": config["hidden_size"],
                "num_attention_heads": config["num_attention_heads"],
                "num_hidden_layers": config["num_hidden_layers"],
                "num_key_value_heads": config["num_key_value_heads"],
                "session_options": {
                    "log_id": "onnxruntime-genai",
                    "provider_options": [],
                },
                "inputs": {
                    "input_ids": "input_ids",
                    "attention_mask": "attention_mask",
                    "past_key_names": "past_key_values.%d.key",
                    "past_value_names": "past_key_values.%d.value",
                },
                "outputs": {
                    "logits": "logits",
                    "present_key_names": "present.%d.key",
                    "present_value_names": "present.%d.value",
                },
            },
        },
        "search": {
            "diversity_penalty": 0.0,
            "do_sample": True,
            "early_stopping": True,
            "length_penalty": 1.0,
            "max_length": config.get("max_position_embeddings", 40960),
            "min_length": 0,
            "no_repeat_ngram_size": 0,
            "num_beams": 1,
            "num_return_sequences": 1,
            "past_present_share_buffer": True,
            "repetition_penalty": 1.0,
            "temperature": 0.6,
            "top_k": 20,
            "top_p": 0.95,
        },
    }

    path = output_dir / "genai_config.json"
    path.write_text(json.dumps(genai_config, indent=4) + "\n", encoding="utf-8")
    print(f"  generated {path.name} from config.json")


def _ensure_genai_config(output_dir: Path) -> None:
    path = output_dir / "genai_config.json"
    if path.is_file():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path} is not valid JSON: {exc}") from exc
        return
    _generate_genai_config(output_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=MODELS_DIR,
        help=f"Directory to place model files in (default: {MODELS_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if the model files already exist.",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    if _is_complete(output_dir) and not args.force:
        print(f"Model files already present in {output_dir}; nothing to do.")
        _ensure_genai_config(output_dir)
        return 0

    with tempfile.TemporaryDirectory(prefix="gumastan-model-") as tmp:
        staging = Path(tmp)
        if not _download_with_hf_cli(staging):
            _download_with_urllib(staging)
        _copy_variant(staging, output_dir)

    _ensure_genai_config(output_dir)

    missing = [name for name in REQUIRED_FILES if not (output_dir / name).is_file()]
    if missing:
        print(f"Download finished but these files are missing: {missing}", file=sys.stderr)
        return 1

    print(f"Model ready in {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

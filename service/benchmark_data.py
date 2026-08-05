"""Load benchmark resources and embedding matrices by registry identifier."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RESOURCES_DIRECTORY = ROOT / "resources"
EMBEDDINGS_DIRECTORY = ROOT / "embeddings"
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validated_id(benchmark_id: str) -> str:
    if not ID_PATTERN.fullmatch(benchmark_id):
        raise ValueError("Invalid benchmark id")
    return benchmark_id


def resource_path(benchmark_id: str) -> Path:
    return RESOURCES_DIRECTORY / f"{_validated_id(benchmark_id)}.json"


def embeddings_path(benchmark_id: str) -> Path:
    return EMBEDDINGS_DIRECTORY / f"{_validated_id(benchmark_id)}.npz"


@lru_cache(maxsize=64)
def load_examples(benchmark_id: str) -> tuple[dict[str, Any], ...]:
    path = resource_path(benchmark_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.name} must contain a JSON list")
    examples = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{path.name}: item {index} must be an object")
        if not isinstance(item.get("question"), str) or not isinstance(
            item.get("cypher"), str
        ):
            raise ValueError(
                f"{path.name}: item {index} must contain question and cypher strings"
            )
        examples.append(dict(item))
    return tuple(examples)


@lru_cache(maxsize=64)
def load_embeddings(benchmark_id: str) -> tuple[np.ndarray, np.ndarray]:
    path = embeddings_path(benchmark_id)
    with np.load(path, allow_pickle=False) as archive:
        if "document_ids" not in archive or "embeddings" not in archive:
            raise ValueError(
                f"{path.name} must contain document_ids and embeddings arrays"
            )
        document_ids = np.asarray(archive["document_ids"]).copy()
        embeddings = np.asarray(archive["embeddings"], dtype=np.float32).copy()
    if embeddings.ndim != 2:
        raise ValueError(f"{path.name}: embeddings must be a two-dimensional matrix")
    if document_ids.ndim != 1 or len(document_ids) != len(embeddings):
        raise ValueError(
            f"{path.name}: document_ids and embeddings must have the same length"
        )
    return document_ids, embeddings


def example_for_document(
    examples: tuple[dict[str, Any], ...], document_id: Any, row_index: int
) -> tuple[int, dict[str, Any]]:
    """Resolve zero- or one-based numeric IDs, explicit JSON IDs, then row order."""
    value = document_id.item() if hasattr(document_id, "item") else document_id
    if isinstance(value, int):
        if 1 <= value <= len(examples):
            return value, examples[value - 1]
        if 0 <= value < len(examples):
            return value, examples[value]
    for index, example in enumerate(examples):
        if str(example.get("id", "")) == str(value):
            return index + 1, example
    if 0 <= row_index < len(examples):
        return row_index + 1, examples[row_index]
    raise IndexError(f"Document id {value!r} has no matching resource item")

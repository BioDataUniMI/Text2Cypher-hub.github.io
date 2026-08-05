"""Semantic similarity search over benchmark question embeddings."""

from __future__ import annotations

import os
import threading
from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from service.benchmark_data import (
    embeddings_path,
    example_for_document,
    load_embeddings,
    load_examples,
    resource_path,
)

MODEL_NAME = os.getenv(
    "T2C_EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2"
)
DEFAULT_TOP_K = int(os.getenv("T2C_SIMILAR_TOP_K", "5"))
_MODEL_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME, device="cpu")


def _encode(query: str) -> np.ndarray:
    with _MODEL_LOCK:
        vector = _model().encode(
            query,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    return np.asarray(vector, dtype=np.float32).reshape(-1)


def _top_indices(scores: np.ndarray, limit: int) -> np.ndarray:
    count = min(limit, len(scores))
    if count == 0:
        return np.asarray([], dtype=np.int64)
    candidates = np.argpartition(scores, -count)[-count:]
    return candidates[np.argsort(scores[candidates])[::-1]]


def find_similar_queries(
    query: str,
    benchmarks: Sequence[Mapping[str, Any]],
    limit: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    """Embed a natural-language question and return the global associated top-k."""
    response: dict[str, Any] = {
        "provider": "sentence-transformers",
        "model": MODEL_NAME,
        "is_mock": False,
        "top_k": limit,
        "matches": [],
        "warnings": [],
    }
    searchable = []
    for benchmark in benchmarks:
        benchmark_id = str(benchmark.get("id", ""))
        if resource_path(benchmark_id).is_file() and embeddings_path(benchmark_id).is_file():
            searchable.append(benchmark)
        else:
            response["warnings"].append(
                f"{benchmark_id}: resource JSON or embedding NPZ is missing."
            )
    if not searchable:
        return response

    try:
        query_embedding = _encode(query)
    except Exception as error:
        response["warnings"].append(f"Cannot encode the query: {error}")
        return response

    matches = []
    for benchmark in searchable:
        benchmark_id = str(benchmark["id"])
        try:
            examples = load_examples(benchmark_id)
            document_ids, matrix = load_embeddings(benchmark_id)
            if matrix.shape[1] != query_embedding.shape[0]:
                raise ValueError(
                    f"embedding dimension {matrix.shape[1]} does not match "
                    f"model dimension {query_embedding.shape[0]}"
                )
            norms = np.linalg.norm(matrix, axis=1)
            denominator = np.where(norms == 0, 1.0, norms)
            scores = (matrix @ query_embedding) / denominator
            for row_index in _top_indices(scores, limit):
                document_id, example = example_for_document(
                    examples, document_ids[row_index], int(row_index)
                )
                matches.append(
                    {
                        "benchmark_id": benchmark_id,
                        "benchmark_name": benchmark.get("name"),
                        "benchmark_version": benchmark.get("version"),
                        "document_id": document_id,
                        "question": example["question"],
                        "cypher": example["cypher"],
                        "notes": example.get("notes"),
                        "similarity": round(float(scores[row_index]), 6),
                        "is_mock": False,
                    }
                )
        except Exception as error:
            response["warnings"].append(f"{benchmark_id}: {error}")

    matches.sort(key=lambda item: item["similarity"], reverse=True)
    response["matches"] = matches[:limit]
    for rank, match in enumerate(response["matches"], start=1):
        match["rank"] = rank
    response["searched_benchmarks"] = len(searchable)
    return response

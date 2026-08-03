#!/usr/bin/env python3
"""Validate the current T2C-Registry YAML structure."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

REGISTRY = Path(__file__).resolve().parents[1] / "docs" / "registry.yaml"

RESOURCE_TYPES = {
    "Dataset",
    "Benchmark",
    "Dataset + benchmark",
}

CURATION_METHODS = {
    "Manually curated",
    "LLM-assisted",
    "Synthetic",
    "Mixed",
}

BEST_REPORTED_METRICS = {
    "jaro_winkler",
    "jaccard",
    "coverage",
    "pass_at_1",
}

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def _is_text(value: Any) -> bool:
    """Return whether a value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def _is_integer(value: Any) -> bool:
    """Return whether a value is an integer, excluding booleans."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    """Return whether a value is numeric, excluding booleans."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _valid_url(value: Any, schemes: set[str]) -> bool:
    """Validate a URL against a set of accepted schemes."""
    if not _is_text(value):
        return False

    parsed = urlparse(value.strip())
    return parsed.scheme in schemes and bool(parsed.netloc)


def _valid_doi(value: Any) -> bool:
    """Return whether a value resembles a DOI."""
    if not _is_text(value):
        return False

    doi = value.strip()

    if doi.lower().startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/") :]

    return bool(DOI_PATTERN.fullmatch(doi))


def _valid_source(value: Any) -> bool:
    """Validate a scientific source expressed as a DOI or HTTP(S) URL."""
    return _valid_doi(value) or _valid_url(value, {"http", "https"})


def _valid_iso_date(value: Any) -> bool:
    """Validate a YAML date object or an ISO-formatted date string."""
    if isinstance(value, date):
        return True

    if not _is_text(value):
        return False

    try:
        date.fromisoformat(value.strip())
    except ValueError:
        return False

    return True


def _validate_string_list(
    value: Any,
    field_name: str,
    label: str,
    errors: list[str],
    *,
    allow_empty: bool = False,
) -> list[str]:
    """Validate a YAML list containing non-empty strings."""
    if not isinstance(value, list):
        errors.append(f"{label}: {field_name} must be a list")
        return []

    if not allow_empty and not value:
        errors.append(f"{label}: {field_name} must be a non-empty list")
        return []

    if not all(_is_text(item) for item in value):
        errors.append(f"{label}: {field_name} must contain only non-empty strings")
        return []

    normalized = [item.strip() for item in value]

    if len(normalized) != len(set(normalized)):
        errors.append(f"{label}: {field_name} must not contain duplicate values")

    return normalized


def _validate_best_reported_results(
    value: Any,
    label: str,
    errors: list[str],
) -> None:
    """Validate the best results reported for a benchmark."""
    field_prefix = f"{label}: best_reported_results"

    if not isinstance(value, dict):
        errors.append(f"{field_prefix} must be a mapping")
        return

    source = value.get("source")
    if not _valid_source(source):
        errors.append(
            f"{field_prefix}.source must be a valid DOI or HTTP(S) URL"
        )

    metrics = value.get("metrics")
    if not isinstance(metrics, dict):
        errors.append(f"{field_prefix}.metrics must be a mapping")
        return

    missing_metrics = BEST_REPORTED_METRICS - set(metrics)
    unknown_metrics = set(metrics) - BEST_REPORTED_METRICS

    for metric_name in sorted(missing_metrics):
        errors.append(
            f"{field_prefix}.metrics is missing required metric "
            f"{metric_name!r}"
        )

    for metric_name in sorted(unknown_metrics):
        errors.append(
            f"{field_prefix}.metrics contains unsupported metric "
            f"{metric_name!r}"
        )

    for metric_name in sorted(BEST_REPORTED_METRICS & set(metrics)):
        metric = metrics[metric_name]
        metric_prefix = f"{field_prefix}.metrics.{metric_name}"

        if not isinstance(metric, dict):
            errors.append(f"{metric_prefix} must be a mapping")
            continue

        score = metric.get("score")
        if not _is_number(score):
            errors.append(f"{metric_prefix}.score must be numeric")
        elif not 0 <= score <= 100:
            errors.append(
                f"{metric_prefix}.score must be between 0 and 100"
            )

        if not _is_text(metric.get("model")):
            errors.append(
                f"{metric_prefix}.model must be a non-empty string"
            )

        techniques = _validate_string_list(
            metric.get("techniques"),
            f"best_reported_results.metrics.{metric_name}.techniques",
            label,
            errors,
        )

        if "reported_as" in metric and not _is_text(metric.get("reported_as")):
            errors.append(
                f"{metric_prefix}.reported_as must be a non-empty string"
            )


def validate(path: Path = REGISTRY) -> list[str]:
    """Validate a T2C-Registry YAML file and return the detected errors."""
    errors: list[str] = []

    try:
        root = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        return [f"cannot read {path}: {exc}"]

    if not isinstance(root, dict):
        return ["registry root must be a YAML mapping"]

    registry_version = root.get("registry_version")
    if not _is_integer(registry_version):
        errors.append("registry_version must be an integer")
    elif registry_version < 1:
        errors.append("registry_version must be a positive integer")

    datasets = root.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        return errors + ["datasets must be a non-empty list"]

    seen_ids: set[str] = set()

    for number, record in enumerate(datasets, start=1):
        label = f"dataset {number}"

        if not isinstance(record, dict):
            errors.append(f"{label}: expected a mapping")
            continue

        resource_id = record.get("id")

        if not _is_text(resource_id) or not ID_PATTERN.fullmatch(resource_id):
            errors.append(f"{label}: id must be lowercase kebab-case")
        elif resource_id in seen_ids:
            errors.append(f"{label}: duplicate id {resource_id!r}")
        else:
            seen_ids.add(resource_id)
            label = resource_id

        for field in ("name", "version", "summary"):
            if not _is_text(record.get(field)):
                errors.append(
                    f"{label}: {field} must be a non-empty string"
                )

        resource_type = record.get("resource_type")
        if resource_type not in RESOURCE_TYPES:
            errors.append(
                f"{label}: invalid resource_type {resource_type!r}"
            )

        dataset = record.get("dataset")
        if not isinstance(dataset, dict):
            errors.append(f"{label}: dataset must be a mapping")
            dataset = {}

        for field in ("domains", "languages"):
            _validate_string_list(
                dataset.get(field),
                f"dataset.{field}",
                label,
                errors,
            )

        curation_method = dataset.get("curation_method")
        if curation_method not in CURATION_METHODS:
            errors.append(
                f"{label}: invalid dataset.curation_method "
                f"{curation_method!r}"
            )

        for field in ("total_pairs", "executable_pairs"):
            value = dataset.get(field)

            if not _is_integer(value) or value < 0:
                errors.append(
                    f"{label}: dataset.{field} must be a "
                    "non-negative integer"
                )

        total_pairs = dataset.get("total_pairs")
        executable_pairs = dataset.get("executable_pairs")

        if (
            _is_integer(total_pairs)
            and _is_integer(executable_pairs)
            and executable_pairs > total_pairs
        ):
            errors.append(
                f"{label}: executable_pairs cannot exceed total_pairs"
            )

        complexity_levels = dataset.get("complexity_levels")
        if not _is_integer(complexity_levels) or complexity_levels < 1:
            errors.append(
                f"{label}: dataset.complexity_levels must be a "
                "positive integer"
            )

        if not _is_text(dataset.get("complexity_description")):
            errors.append(
                f"{label}: dataset.complexity_description must be documented"
            )

        endpoint = record.get("endpoint")
        if endpoint is not None:
            if not isinstance(endpoint, dict):
                errors.append(f"{label}: endpoint must be a mapping")
            else:
                endpoint_url = endpoint.get("url")
                if (
                    endpoint_url is not None
                    and not _valid_url(endpoint_url, {"http", "https"})
                ):
                    errors.append(
                        f"{label}: endpoint.url must be an HTTP(S) URL"
                    )

                endpoint_bolt = endpoint.get("bolt")
                if (
                    endpoint_bolt is not None
                    and not _valid_url(
                        endpoint_bolt,
                        {"bolt", "bolt+s", "neo4j", "neo4j+s"},
                    )
                ):
                    errors.append(
                        f"{label}: endpoint.bolt must be a valid "
                        "Neo4j/Bolt URL"
                    )

                endpoint_dump = endpoint.get("dump")
                if (
                    endpoint_dump is not None
                    and not _valid_url(endpoint_dump, {"http", "https"})
                ):
                    errors.append(
                        f"{label}: endpoint.dump must be an HTTP(S) URL"
                    )

                for field in ("username", "password", "database"):
                    if field in endpoint and not _is_text(endpoint[field]):
                        errors.append(
                            f"{label}: endpoint.{field} must be a "
                            "non-empty string"
                        )

        evaluation = record.get("evaluation")
        if evaluation is not None and not isinstance(evaluation, dict):
            errors.append(
                f"{label}: evaluation must be a mapping when present"
            )

        materials = record.get("materials")
        if materials is not None and not isinstance(materials, list):
            errors.append(
                f"{label}: materials must be a list when present"
            )

        license_data = record.get("license")
        if not _is_text(license_data) and not isinstance(license_data, dict):
            errors.append(
                f"{label}: license must be text or a mapping"
            )

        best_reported_results = record.get("best_reported_results")
        if best_reported_results is not None:
            _validate_best_reported_results(
                best_reported_results,
                label,
                errors,
            )

        notes = record.get("notes")
        if notes is not None:
            _validate_string_list(
                notes,
                "notes",
                label,
                errors,
                allow_empty=True,
            )

        if "article_doi" in record:
            article_doi = record.get("article_doi")

            if not _valid_doi(article_doi):
                errors.append(
                    f"{label}: article_doi must be a valid DOI"
                )

        reviewed = record.get("last_reviewed")
        if not _valid_iso_date(reviewed):
            errors.append(
                f"{label}: last_reviewed must be an ISO date "
                "in YYYY-MM-DD format"
            )

    return errors


def main() -> int:
    """Run registry validation from the command line."""
    errors = validate()

    if errors:
        print("Registry validation failed:", file=sys.stderr)

        for error in errors:
            print(f"- {error}", file=sys.stderr)

        return 1

    try:
        root = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        print(f"Cannot read {REGISTRY}: {exc}", file=sys.stderr)
        return 1

    count = len(root["datasets"])
    noun = "dataset" if count == 1 else "datasets"

    print(f"Registry is valid ({count} {noun}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
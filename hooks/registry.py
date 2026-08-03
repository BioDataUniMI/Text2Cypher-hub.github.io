"""Render the T2C-Registry index and version-specific dataset pages."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path
from typing import Any

import yaml
from mkdocs.structure.files import File, Files, InclusionLevel


SUMMARY_MARKER = "{{ t2c_registry_summary }}"
ENTRIES_MARKER = "{{ t2c_registry_entries }}"

REGISTRY_PAGE_URIS = (
    "registry.md",
    "registry/index.md",
)

DETAILS_DIRECTORY = "registry"

ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

METRIC_LABELS = {
    "jaro_winkler": "Jaro–Winkler",
    "normalized_levenshtein": "Normalized Levenshtein",
    "jaccard": "Jaccard",
    "coverage": "Coverage",
    "pass_at_1": "Pass@1",
}

METRIC_ORDER = (
    "jaro_winkler",
    "normalized_levenshtein",
    "jaccard",
    "coverage",
    "pass_at_1",
)


def _is_text(value: Any) -> bool:
    """Return whether a value is a non-empty string."""
    return isinstance(value, str) and bool(value.strip())


def _load_registry(config: Any) -> list[dict[str, Any]]:
    """Load dataset records from registry.yaml."""
    registry_path = Path(config.docs_dir) / "registry.yaml"

    if not registry_path.exists():
        raise FileNotFoundError(
            f"T2C registry file not found: {registry_path}"
        )

    raw_data = yaml.safe_load(
        registry_path.read_text(encoding="utf-8")
    )

    if raw_data is None:
        return []

    if not isinstance(raw_data, Mapping):
        raise ValueError(
            "registry.yaml must contain a YAML mapping at the top level."
        )

    raw_datasets = raw_data.get("datasets", [])

    if raw_datasets is None:
        return []

    if not isinstance(raw_datasets, list):
        raise ValueError(
            "'datasets' in registry.yaml must be a YAML list."
        )

    datasets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, raw_record in enumerate(raw_datasets, start=1):
        if not isinstance(raw_record, Mapping):
            raise ValueError(
                f"Dataset entry {index} must be a YAML mapping, "
                f"but found {type(raw_record).__name__}."
            )

        record = dict(raw_record)
        record_id = record.get("id", f"entry-{index}")

        if (
            not _is_text(record_id)
            or not ID_PATTERN.fullmatch(record_id)
        ):
            raise ValueError(
                f"Dataset entry {index} has an invalid id "
                f"{record_id!r}. Expected lowercase kebab-case."
            )

        if record_id in seen_ids:
            raise ValueError(
                f"Duplicate dataset id: {record_id!r}."
            )

        seen_ids.add(record_id)

        version = record.get("version")

        if not _is_text(version):
            raise ValueError(
                f"Dataset '{record_id}' has an invalid 'version' field. "
                "Expected a non-empty string such as:\n\n"
                'version: "v1"'
            )

        record["version"] = version.strip()

        raw_dataset = record.get("dataset", {})

        if raw_dataset is None:
            raw_dataset = {}

        if not isinstance(raw_dataset, Mapping):
            raise ValueError(
                f"Dataset '{record_id}' has an invalid 'dataset' field. "
                "Expected a YAML mapping such as:\n\n"
                "dataset:\n"
                "  domains:\n"
                "    - Biomedical\n"
                "  languages:\n"
                "    - English"
            )

        record["dataset"] = dict(raw_dataset)

        for optional_mapping in (
            "endpoint",
            "evaluation",
            "best_reported_results",
        ):
            value = record.get(optional_mapping)

            if value is None:
                record[optional_mapping] = {}
            elif isinstance(value, Mapping):
                record[optional_mapping] = dict(value)
            else:
                raise ValueError(
                    f"Dataset '{record_id}' has an invalid "
                    f"'{optional_mapping}' field. "
                    "Expected a YAML mapping."
                )

        best_results = record["best_reported_results"]

        if best_results:
            raw_metrics = best_results.get("metrics", {})

            if raw_metrics is None:
                raw_metrics = {}

            if not isinstance(raw_metrics, Mapping):
                raise ValueError(
                    f"Dataset '{record_id}' has an invalid "
                    "'best_reported_results.metrics' field. "
                    "Expected a YAML mapping."
                )

            normalized_metrics: dict[str, dict[str, Any]] = {}

            for metric_name, raw_metric in raw_metrics.items():
                if not isinstance(raw_metric, Mapping):
                    raise ValueError(
                        f"Dataset '{record_id}' has an invalid metric "
                        f"definition for '{metric_name}'. "
                        "Expected a YAML mapping."
                    )

                normalized_metrics[str(metric_name)] = dict(raw_metric)

            best_results["metrics"] = normalized_metrics

        datasets.append(record)

    return datasets


def _mapping(value: Any) -> dict[str, Any]:
    """Return a mapping as a standard dictionary."""
    if isinstance(value, Mapping):
        return dict(value)

    return {}


def _as_list(value: Any) -> list[Any]:
    """Normalize a scalar or sequence to a list."""
    if value is None or value == "":
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, set):
        return list(value)

    if (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes, bytearray))
    ):
        return list(value)

    return [value]


def _text(
    value: Any,
    fallback: str = "Not documented",
) -> str:
    """Convert a registry value to displayable text."""
    if value is None or value == "":
        return fallback

    if isinstance(value, bool):
        return "Yes" if value else "No"

    return str(value)


def _cell(
    value: Any,
    fallback: str = "Not documented",
) -> str:
    """Escape a value for use inside a Markdown table cell."""
    return (
        escape(_text(value, fallback))
        .replace("|", "&#124;")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _attribute(
    value: Any,
    fallback: str = "",
) -> str:
    """Escape a value for use inside an HTML attribute."""
    return escape(
        _text(value, fallback),
        quote=True,
    )


def _number(value: Any) -> str:
    """Format integer values with thousands separators."""
    if isinstance(value, int) and not isinstance(value, bool):
        return f"{value:,}"

    return _text(value)


def _score(value: Any) -> str:
    """Format benchmark scores as percentages."""
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
    ):
        return f"{value:g}%"

    return _text(value)


def _join_values(value: Any) -> str:
    """Join scalar or list values into a comma-separated string."""
    values = _as_list(value)

    if not values:
        return "Not documented"

    return ", ".join(
        _text(item)
        for item in values
    )


def _code_value(
    value: Any,
    fallback: str = "Not documented",
) -> str:
    """Render a value as inline HTML code."""
    if value is None or value == "":
        return escape(fallback)

    return f"<code>{_cell(value, fallback)}</code>"


def _join_code_values(value: Any) -> str:
    """Render values as comma-separated inline code elements."""
    values = _as_list(value)

    if not values:
        return "Not documented"

    return ", ".join(
        _code_value(item)
        for item in values
    )


def _render_dataset_name(value: Any) -> str:
    """Render a dataset name, italicizing bio2C."""
    name = _text(value)

    if name.strip().lower() == "bio2c":
        return f"<em>{escape(name)}</em>"

    return escape(name)


def _external_link(
    label: Any,
    url: Any,
    fallback: str = "Not documented",
) -> str:
    """Render an external HTML link."""
    if url is None or url == "":
        return escape(fallback)

    safe_url = escape(
        str(url),
        quote=True,
    )
    safe_label = escape(
        _text(label)
    )

    return (
        f'<a href="{safe_url}" '
        'target="_blank" '
        'rel="noopener noreferrer">'
        f"{safe_label}"
        "</a>"
    )


def _internal_link(
    label: Any,
    url: Any,
    css_class: str | None = None,
) -> str:
    """Render an internal HTML link."""
    safe_url = escape(
        _text(url, ""),
        quote=True,
    )
    safe_label = escape(
        _text(label)
    )

    class_attribute = ""

    if css_class:
        class_attribute = (
            f' class="{escape(css_class, quote=True)}"'
        )

    return (
        f'<a{class_attribute} href="{safe_url}">'
        f"{safe_label}"
        "</a>"
    )


def _render_source(
    source: Any,
    fallback: str = "Not documented",
) -> str:
    """Render a scientific source expressed as a DOI or URL."""
    if source is None or source == "":
        return escape(fallback)

    source_text = str(source).strip()

    if source_text.startswith(("https://", "http://")):
        return _external_link(
            "Open article",
            source_text,
            fallback,
        )

    if source_text.lower().startswith("doi:"):
        source_text = source_text[4:].strip()

    return _external_link(
        f"DOI: {source_text}",
        f"https://doi.org/{source_text}",
        fallback,
    )


def _render_license(license_data: Any) -> str:
    """Render a scalar license or structured license mapping."""
    if isinstance(license_data, Mapping):
        license_mapping = dict(license_data)

        license_name = (
            license_mapping.get("id")
            or license_mapping.get("name")
            or license_mapping.get("title")
        )
        license_url = license_mapping.get("url")

        if license_url:
            return _external_link(
                _text(license_name, "License"),
                license_url,
                "Unknown",
            )

        return _cell(
            license_name,
            "Unknown",
        )

    return _cell(
        license_data,
        "Unknown",
    )


def _metric_display_name(metric_name: str) -> str:
    """Return the display label for an evaluation metric."""
    label = METRIC_LABELS.get(
        metric_name,
        metric_name.replace("_", " ").title(),
    )

    return escape(label)


def _ordered_metric_names(
    metrics: Mapping[str, Any],
) -> list[str]:
    """Order known metrics before unknown metrics."""
    ordered = [
        metric_name
        for metric_name in METRIC_ORDER
        if metric_name in metrics
    ]

    remaining = sorted(
        metric_name
        for metric_name in metrics
        if metric_name not in METRIC_ORDER
    )

    return ordered + remaining


def _detail_src_uri(record_id: str) -> str:
    """Return the virtual Markdown path for a dataset version."""
    return f"{DETAILS_DIRECTORY}/{record_id}.md"


def _find_registry_file(files: Files) -> File | None:
    """Find the registry index source file."""
    for src_uri in REGISTRY_PAGE_URIS:
        registry_file = files.get_file_from_path(src_uri)

        if registry_file is not None:
            return registry_file

    return None


def _render_version_link(
    record: Mapping[str, Any],
    current_file: File,
    files: Files,
) -> str:
    """Render the version link to its dedicated dataset page."""
    record_id = _text(
        record.get("id"),
        "",
    )

    detail_file = files.get_file_from_path(
        _detail_src_uri(record_id)
    )

    if detail_file is None:
        return _cell(
            record.get("version")
        )

    href = detail_file.url_relative_to(
        current_file
    )

    return _internal_link(
        record.get("version"),
        href,
        "registry-version-link",
    )


def _render_summary(
    datasets: list[dict[str, Any]],
    current_file: File,
    files: Files,
) -> str:
    """Render the compact registry summary table."""
    lines = [
        '<table class="registry-summary">',
        "<thead>",
        "<tr>",
        "<th>Name</th>",
        "<th>Version</th>",
        "<th>Pairs</th>",
        "<th>Executable pairs</th>",
        "<th>Domains</th>",
        "<th>Curation</th>",
        "</tr>",
        "</thead>",
        "<tbody>",
    ]

    for record in datasets:
        dataset = _mapping(
            record.get("dataset")
        )

        record_id = _attribute(
            record.get("id"),
            "dataset",
        )
        curation = _attribute(
            dataset.get("curation_method"),
        )

        total_pairs = _number(
            dataset.get("total_pairs")
        )
        executable_pairs = _number(
            dataset.get("executable_pairs")
        )
        domains = _join_values(
            dataset.get("domains")
        )

        version_link = _render_version_link(
            record,
            current_file,
            files,
        )

        lines.extend(
            [
                (
                    f'<tr data-registry-id="{record_id}" '
                    f'data-registry-curation="{curation}">'
                ),
                (
                    "<td>"
                    f"{_render_dataset_name(record.get('name'))}"
                    "</td>"
                ),
                (
                    "<td>"
                    f"{version_link}"
                    "</td>"
                ),
                (
                    "<td>"
                    f"{escape(total_pairs)}"
                    "</td>"
                ),
                (
                    "<td>"
                    f"{escape(executable_pairs)}"
                    "</td>"
                ),
                (
                    "<td>"
                    f"{_cell(domains)}"
                    "</td>"
                ),
                (
                    "<td>"
                    f"{_cell(dataset.get('curation_method'))}"
                    "</td>"
                ),
                "</tr>",
            ]
        )

    lines.extend(
        [
            "</tbody>",
            "</table>",
        ]
    )

    return "\n".join(lines)


def _render_material(
    material: Mapping[str, Any],
) -> str:
    """Render one material as a Markdown table row."""
    material_type = _text(
        material.get("type"),
        "",
    )
    title = _text(
        material.get("title"),
        "",
    )

    if title and material_type and title != material_type:
        material_name = f"{title} ({material_type})"
    else:
        material_name = title or material_type or "Material"

    status = _text(
        material.get("status"),
        "Planned",
    )

    return (
        f"| {_cell(material_name)} "
        f"| {_cell(material.get('description'))} "
        f"| {_cell(status)} "
        f"| {_cell(material.get('access'))} "
        f"| {_external_link('Open', material.get('url'), 'Not yet provided')} |"
    )


def _render_endpoint(
    endpoint: Mapping[str, Any],
) -> list[str]:
    """Render graph endpoint and dump information."""
    lines = [
        "## Endpoint",
        "",
        "| Property | Value |",
        "|---|---|",
    ]

    if endpoint.get("url"):
        lines.append(
            "| Web endpoint | "
            f"{_external_link(endpoint.get('url'), endpoint.get('url'))} |"
        )

    if endpoint.get("bolt"):
        lines.append(
            "| Bolt endpoint | "
            f"{_code_value(endpoint.get('bolt'))} |"
        )

    if endpoint.get("username"):
        lines.append(
            "| Username | "
            f"{_code_value(endpoint.get('username'))} |"
        )

    if endpoint.get("password"):
        lines.append(
            "| Password | "
            f"{_code_value(endpoint.get('password'))} |"
        )

    if endpoint.get("database"):
        lines.append(
            "| Database | "
            f"{_code_value(endpoint.get('database'))} |"
        )

    if endpoint.get("dump"):
        lines.append(
            "| Neo4j dump | "
            f"{_external_link('Download dump', endpoint.get('dump'))} |"
        )

    return lines


def _render_evaluation(
    evaluation: Mapping[str, Any],
) -> list[str]:
    """Render optional evaluation information."""
    validations = _as_list(
        evaluation.get("validation")
    )

    lines = [
        "## Evaluation",
        "",
        (
            "- **Benchmark ready:** "
            f"{escape(_text(evaluation.get('benchmark_ready')))}"
        ),
        (
            "- **Requires the graph:** "
            f"{escape(_text(evaluation.get('requires_graph')))}"
        ),
    ]

    if validations:
        lines.append("- **Validation:**")

        for validation in validations:
            lines.append(
                f"    - {escape(_text(validation))}"
            )
    else:
        lines.append(
            "- **Validation:** Not documented"
        )

    return lines


def _render_best_reported_results(
    best_results: Mapping[str, Any],
) -> list[str]:
    """Render the best published benchmark results."""
    metrics = _mapping(
        best_results.get("metrics")
    )

    lines = [
        "## Best reported results",
        "",
        (
            "- **Scientific source:** "
            f"{_render_source(best_results.get('source'))}"
        ),
    ]

    if not metrics:
        lines.extend(
            [
                "",
                "No benchmark results have been documented.",
            ]
        )

        return lines

    lines.extend(
        [
            "",
            "| Metric | Score | Model | Technique(s) |",
            "|---|---:|---|---|",
        ]
    )

    for metric_name in _ordered_metric_names(metrics):
        metric = _mapping(
            metrics.get(metric_name)
        )

        metric_label = _metric_display_name(
            metric_name
        )
        score = escape(
            _score(metric.get("score"))
        )
        model = _code_value(
            metric.get("model")
        )
        techniques = _join_code_values(
            metric.get("techniques")
        )

        lines.append(
            f"| {metric_label} "
            f"| {score} "
            f"| {model} "
            f"| {techniques} |"
        )

    return lines


def _render_detail_page(
    record: Mapping[str, Any],
) -> str:
    """Render one version-specific dataset page."""
    dataset = _mapping(
        record.get("dataset")
    )
    endpoint = _mapping(
        record.get("endpoint")
    )
    evaluation = _mapping(
        record.get("evaluation")
    )
    best_results = _mapping(
        record.get("best_reported_results")
    )

    domains = _join_values(
        dataset.get("domains")
    )
    languages = _join_values(
        dataset.get("languages")
    )
    version = _text(
        record.get("version"),
        "",
    )

    raw_materials = _as_list(
        record.get("materials")
    )
    materials = [
        dict(material)
        for material in raw_materials
        if isinstance(material, Mapping)
    ]

    notes = _as_list(
        record.get("notes")
    )

    plain_title = " ".join(
        part
        for part in (
            _text(record.get("name"), "").strip(),
            version.strip(),
        )
        if part
    )

    front_matter = yaml.safe_dump(
        {
            "title": plain_title,
            "hide": [
                "navigation",
            ],
        },
        allow_unicode=True,
        sort_keys=False,
    ).strip()

    lines = [
        "---",
        front_matter,
        "---",
        "",
        (
            "# "
            f"{_render_dataset_name(record.get('name'))} "
            f"{escape(version)}"
        ),
        "",
        (
            '<span class="registry-badge">'
            f"{_cell(record.get('resource_type'))}"
            "</span>"
        ),
        "",
        escape(
            _text(record.get("summary"))
        ),
        "",
        "## Statistics",
        "",
        "| Property | Value |",
        "|---|---|",
        (
            "| Version | "
            f"{_cell(version)} |"
        ),
        (
            "| Domains | "
            f"{_cell(domains)} |"
        ),
        (
            "| Languages | "
            f"{_cell(languages)} |"
        ),
        (
            "| Curation | "
            f"{_cell(dataset.get('curation_method'))} |"
        ),
        (
            "| Total NL–Cypher pairs | "
            f"{escape(_number(dataset.get('total_pairs')))} |"
        ),
        (
            "| Graph-executable pairs | "
            f"{escape(_number(dataset.get('executable_pairs')))} |"
        ),
        (
            "| Complexity levels | "
            f"{escape(_number(dataset.get('complexity_levels')))} |"
        ),
        (
            "| Complexity definition | "
            f"{_cell(dataset.get('complexity_description'))} |"
        ),
    ]

    if endpoint:
        lines.extend(
            [
                "",
                *_render_endpoint(endpoint),
            ]
        )

    if materials:
        lines.extend(
            [
                "",
                "## Materials",
                "",
                "| Material | Description | Status | Access | Link |",
                "|---|---|---|---|---|",
            ]
        )

        for material in materials:
            lines.append(
                _render_material(material)
            )

    if evaluation:
        lines.extend(
            [
                "",
                *_render_evaluation(evaluation),
            ]
        )

    if best_results:
        lines.extend(
            [
                "",
                *_render_best_reported_results(best_results),
            ]
        )

    lines.extend(
        [
            "",
            "## Reference and license",
            "",
            (
                "- **License:** "
                f"{_render_license(record.get('license'))}"
            ),
        ]
    )

    if record.get("article_doi"):
        lines.append(
            "- **Associated article:** "
            f"{_render_source(record.get('article_doi'))}"
        )

    lines.append(
        "- **Last reviewed:** "
        f"{_cell(record.get('last_reviewed'))}"
    )

    if notes:
        lines.extend(
            [
                "",
                "## Notes",
                "",
            ]
        )

        for note in notes:
            lines.append(
                f"- {escape(_text(note))}"
            )

    return "\n".join(lines)


def on_files(
    files: Files,
    config: Any,
) -> Files:
    """Create one virtual detail page for every dataset version."""
    datasets = _load_registry(config)

    registry_file = _find_registry_file(files)

    if registry_file is None:
        raise FileNotFoundError(
            "The registry index page was not found. "
            "Expected docs/registry.md or docs/registry/index.md."
        )

    for record in datasets:
        record_id = _text(
            record.get("id"),
            "",
        )
        src_uri = _detail_src_uri(
            record_id
        )

        existing_file = files.get_file_from_path(
            src_uri
        )

        if existing_file is not None:
            raise ValueError(
                f"Cannot generate '{src_uri}': "
                "a documentation file already uses the same path."
            )

        detail_file = File.generated(
            config,
            src_uri,
            content=_render_detail_page(record),
        )

        detail_file.inclusion = InclusionLevel.NOT_IN_NAV

        files.append(detail_file)

    return files


def on_page_markdown(
    markdown: str,
    page: Any,
    config: Any,
    files: Files,
) -> str:
    """Inject the summary table into the registry index page."""
    if page.file.src_uri not in REGISTRY_PAGE_URIS:
        return markdown

    datasets = _load_registry(config)

    summary = _render_summary(
        datasets,
        page.file,
        files,
    )

    rendered_markdown = markdown.replace(
        SUMMARY_MARKER,
        summary,
    )

    # Dataset details now live on separate pages.
    rendered_markdown = rendered_markdown.replace(
        ENTRIES_MARKER,
        "",
    )

    return rendered_markdown
"""Validate Cypher with CyVer and execute it on registered Neo4j databases."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import yaml
from CyVer import PropertiesValidator, SchemaValidator, SyntaxValidator
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from neo4j import GraphDatabase, Query, READ_ACCESS
from neo4j.exceptions import Neo4jError
from pydantic import BaseModel, Field

from service.benchmark_data import load_examples, resource_path
from service.similarity import find_similar_queries

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "docs" / "registry.yaml"
SITE_PATH = ROOT / "site"
QUERY_TIMEOUT_SECONDS = float(os.getenv("T2C_QUERY_TIMEOUT", "15"))
MAX_QUERY_LENGTH = int(os.getenv("T2C_MAX_QUERY_LENGTH", "20000"))

FORBIDDEN_CLAUSES = re.compile(
    r"\b(?:CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|ALTER|RENAME|"
    r"GRANT|DENY|REVOKE|FOREACH|CALL|LOAD\s+CSV|USE|SHOW|TERMINATE|"
    r"START\s+DATABASE|STOP\s+DATABASE)\b",
    re.IGNORECASE,
)

app = FastAPI(
    title="T2C-Hub Cypher Validator",
    description="Validate with CyVer and execute on a read-only Neo4j database.",
    version="1.2.0",
)


class SimilarityRequest(BaseModel):
    database_id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)



class ValidationRequest(BaseModel):
    database_id: str = Field(min_length=1, max_length=200)
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)


SAMPLE_ROW_LIMIT = 3
MAX_SAMPLE_QUERIES = 5


class SampleQueryRequest(BaseModel):
    database_id: str = Field(min_length=1, max_length=200)
    queries: list[str] = Field(min_length=1, max_length=MAX_SAMPLE_QUERIES)


def _load_registry() -> dict[str, Any]:
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    if not isinstance(data, Mapping):
        raise RuntimeError("docs/registry.yaml must contain a mapping")
    return dict(data)


def _records(root: Mapping[str, Any], field: str) -> list[dict[str, Any]]:
    values = root.get(field, [])
    if not isinstance(values, list):
        raise RuntimeError(f"docs/registry.yaml: '{field}' must be a list")
    return [dict(item) for item in values if isinstance(item, Mapping)]


def _associated_benchmarks(
    root: Mapping[str, Any], database_id: str
) -> list[dict[str, Any]]:
    return [
        benchmark
        for benchmark in _records(root, "datasets")
        if database_id in benchmark.get("databases", [])
    ]


def _find_benchmark(benchmark_id: str) -> dict[str, Any]:
    for benchmark in _records(_load_registry(), "datasets"):
        if benchmark.get("id") == benchmark_id:
            return benchmark
    raise HTTPException(status_code=404, detail="Benchmark not found in registry.yaml.")



def _public_benchmark(benchmark: Mapping[str, Any]) -> dict[str, Any]:
    return {key: benchmark.get(key) for key in ("id", "name", "version")}


def _public_database(
    database: Mapping[str, Any], benchmarks: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "id": database.get("id"),
        "name": database.get("name"),
        "benchmarks": [_public_benchmark(item) for item in benchmarks],
    }


def _find_database(
    database_id: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = _load_registry()
    for database in _records(root, "databases"):
        if database.get("id") != database_id:
            continue
        benchmarks = _associated_benchmarks(root, database_id)
        if not benchmarks:
            raise HTTPException(
                status_code=422,
                detail="The selected database is not associated with any benchmark.",
            )
        endpoint = database.get("endpoint")
        if not isinstance(endpoint, Mapping) or not all(
            endpoint.get(field)
            for field in ("bolt", "username", "password", "database")
        ):
            raise HTTPException(
                status_code=422,
                detail="The selected database has no complete Neo4j connection configuration.",
            )
        return database, benchmarks
    raise HTTPException(status_code=404, detail="Database not found in registry.yaml.")


def _strip_literals_and_comments(query: str) -> str:
    return re.sub(
        r"(?s)/\*.*?\*/|//[^\r\n]*|'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"|`(?:``|[^`])*`",
        " ",
        query,
    )


def _assert_read_only(query: str) -> None:
    match = FORBIDDEN_CLAUSES.search(_strip_literals_and_comments(query))
    if match:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Clause '{match.group(0).upper()}' is not allowed. "
                "The public validator accepts read-only Cypher queries only."
            ),
        )


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_value(item) for item in value]
    if hasattr(value, "item"):
        try:
            return _json_value(value.item())
        except (TypeError, ValueError):
            pass
    if hasattr(value, "items"):
        try:
            return {str(key): _json_value(item) for key, item in value.items()}
        except (TypeError, ValueError):
            pass
    return str(value)


def _score(value: Any) -> float | None:
    return None if value is None else float(value)


def _neo4j_error(error: Exception) -> dict[str, str]:
    if isinstance(error, Neo4jError):
        return {
            "code": str(error.code or "Neo4jError"),
            "message": str(error.message or error),
        }
    return {"code": type(error).__name__, "message": str(error)}


def _notification(item: Any) -> dict[str, Any]:
    return {
        "code": getattr(item, "code", None),
        "title": getattr(item, "title", None),
        "description": getattr(item, "description", None),
        "severity": getattr(item, "severity_level", None)
        or getattr(item, "severity", None),
        "category": getattr(item, "category", None),
    }


@app.get("/api/benchmarks/{benchmark_id}/examples")
def benchmark_examples(
    benchmark_id: str, offset: int = 0, limit: int = 10, search: str = ""
) -> dict[str, Any]:
    benchmark = _find_benchmark(benchmark_id)
    if offset < 0 or not 1 <= limit <= 100:
        raise HTTPException(status_code=422, detail="Invalid pagination values.")
    try:
        examples = load_examples(benchmark_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Benchmark resource JSON not found.")
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=500, detail=str(error))
    term = search.strip().lower()
    filtered = [
        (index, example)
        for index, example in enumerate(examples, start=1)
        if not term or term in " ".join(
            str(example.get(field, ""))
            for field in ("question", "cypher", "notes")
        ).lower()
    ]
    page = [
        {"document_id": index, **example}
        for index, example in filtered[offset : offset + limit]
    ]
    return {
        "benchmark": _public_benchmark(benchmark),
        "total": len(examples),
        "filtered_total": len(filtered),
        "offset": offset,
        "limit": limit,
        "examples": page,
    }


@app.get("/api/benchmarks/{benchmark_id}/resource")
def benchmark_resource(benchmark_id: str) -> FileResponse:
    _find_benchmark(benchmark_id)
    path = resource_path(benchmark_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Benchmark resource JSON not found.")
    return FileResponse(path, media_type="application/json", filename=path.name)



@app.get("/api/databases")
def databases() -> dict[str, Any]:
    root = _load_registry()
    available = []
    for database in _records(root, "databases"):
        database_id = database.get("id")
        endpoint = database.get("endpoint")
        benchmarks = _associated_benchmarks(root, str(database_id))
        if benchmarks and isinstance(endpoint, Mapping) and all(
            endpoint.get(field)
            for field in ("bolt", "username", "password", "database")
        ):
            available.append(_public_database(database, benchmarks))
    return {"databases": available}


@app.post("/api/similar")
def similar(request: SimilarityRequest) -> dict[str, Any]:
    question = request.question.strip()
    database, benchmarks = _find_database(request.database_id)
    return {
        "database": _public_database(database, benchmarks),
        "question": question,
        "similar_queries": find_similar_queries(question, benchmarks),
    }



@app.post("/api/validate")
def validate(request: ValidationRequest) -> dict[str, Any]:
    query = request.query.strip()
    _assert_read_only(query)
    database, benchmarks = _find_database(request.database_id)
    endpoint = database["endpoint"]
    report: dict[str, Any] = {
        "database": _public_database(database, benchmarks),
        "cyver": {
            "syntax": {"valid": False, "score": 0.0, "metadata": None},
            "schema": {"score": None, "metadata": None},
            "properties": {"score": None, "metadata": None},
            "kg_valid": False,
        },
        "execution": {
            "attempted": False,
            "succeeded": False,
            "columns": [],
            "rows": [],
            "returned_rows": 0,
            "warnings": [],
            "error": None,
        },
        "warnings": [],
        "errors": [],
    }

    try:
        with GraphDatabase.driver(
            endpoint["bolt"],
            auth=(endpoint["username"], endpoint["password"]),
            connection_timeout=QUERY_TIMEOUT_SECONDS,
        ) as driver:
            driver.verify_connectivity()
            syntax_valid, syntax_metadata = SyntaxValidator(
                driver, check_multilabeled_nodes=True
            ).validate(query, database_name=endpoint["database"])
            syntax_valid = bool(syntax_valid)
            report["cyver"]["syntax"] = {
                "valid": syntax_valid,
                "score": 1.0 if syntax_valid else 0.0,
                "metadata": _json_value(syntax_metadata),
            }
            if not syntax_valid:
                report["errors"].append(
                    {"code": "CyVerSyntaxError", "message": _json_value(syntax_metadata)}
                )
                return report

            schema_score, schema_metadata = SchemaValidator(driver).validate(
                query, database_name=endpoint["database"]
            )
            properties_score, properties_metadata = PropertiesValidator(driver).validate(
                query, database_name=endpoint["database"], strict=False
            )
            schema_score = _score(schema_score)
            properties_score = _score(properties_score)
            report["cyver"]["schema"] = {
                "score": schema_score,
                "metadata": _json_value(schema_metadata),
            }
            report["cyver"]["properties"] = {
                "score": properties_score,
                "metadata": _json_value(properties_metadata),
            }
            report["cyver"]["kg_valid"] = (
                schema_score == 1.0 and properties_score in (1.0, None)
            )
            if schema_score != 1.0:
                report["warnings"].append(
                    "CyVer found schema elements that do not match the selected graph."
                )
            if properties_score not in (1.0, None):
                report["warnings"].append(
                    "CyVer found properties that do not match the selected graph."
                )

            report["execution"]["attempted"] = True
            with driver.session(
                database=endpoint["database"], default_access_mode=READ_ACCESS
            ) as session:
                result = session.run(Query(query, timeout=QUERY_TIMEOUT_SECONDS))
                columns = list(result.keys())
                records = [_json_value(record.data()) for record in result]
                summary = result.consume()
                notifications = [
                    _notification(item) for item in (summary.notifications or [])
                ]
            report["execution"].update(
                {
                    "succeeded": True,
                    "columns": columns,
                    "rows": records,
                    "returned_rows": len(records),
                    "warnings": notifications,
                }
            )
    except Exception as error:
        item = _neo4j_error(error)
        report["errors"].append(item)
        if report["execution"]["attempted"]:
            report["execution"]["error"] = item
    return report


@app.post("/api/run-samples")
def run_samples(request: SampleQueryRequest) -> dict[str, Any]:
    database, _ = _find_database(request.database_id)
    endpoint = database["endpoint"]
    results: list[dict[str, Any]] = []
    try:
        with GraphDatabase.driver(
            endpoint["bolt"],
            auth=(endpoint["username"], endpoint["password"]),
            connection_timeout=QUERY_TIMEOUT_SECONDS,
        ) as driver:
            driver.verify_connectivity()
            for raw_query in request.queries:
                query = raw_query.strip()
                entry: dict[str, Any] = {"columns": [], "rows": [], "error": None}
                try:
                    if not query:
                        raise HTTPException(status_code=422, detail="Empty query.")
                    _assert_read_only(query)
                    with driver.session(
                        database=endpoint["database"], default_access_mode=READ_ACCESS
                    ) as session:
                        result = session.run(Query(query, timeout=QUERY_TIMEOUT_SECONDS))
                        columns = list(result.keys())
                        records = [_json_value(record.data()) for record in result]
                        result.consume()
                    entry["columns"] = columns
                    entry["rows"] = records[:SAMPLE_ROW_LIMIT]
                except HTTPException as error:
                    entry["error"] = str(error.detail)
                except Exception as error:
                    entry["error"] = _neo4j_error(error)["message"]
                results.append(entry)
    except Exception as error:
        raise HTTPException(status_code=502, detail=_neo4j_error(error)["message"])
    return {"results": results}


@app.get("/query-assistant")
def validator_redirect() -> RedirectResponse:
    return RedirectResponse(url="/query-assistant/")


@app.get("/query-validator")
@app.get("/query-validator/")
def legacy_validator_redirect() -> RedirectResponse:
    return RedirectResponse(url="/query-assistant/")


if SITE_PATH.is_dir():
    app.mount("/", StaticFiles(directory=SITE_PATH, html=True), name="site")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
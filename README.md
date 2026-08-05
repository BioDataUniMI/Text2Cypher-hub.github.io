# T2C-Hub

T2C-Hub is a community home for **Text2Cypher** resources: datasets, benchmarks, evaluation practices and tooling for translating natural-language questions into executable Cypher queries.

The Hub currently hosts **T2C-Registry**, a curated catalogue of Text2Cypher datasets and benchmarks. Registry records live in [`docs/registry.yaml`](docs/registry.yaml), so they are easy to review, diff and reuse programmatically.

The website is built with [MkDocs Material](https://squidfunk.github.io/mkdocs-material/).

## Run locally

Python 3.10 or newer is required.

```bash
poetry install
poetry run python3 utils/validate_registry.py
poetry run mkdocs build --strict -f mkdocs.yaml
poetry run uvicorn service.app:app --host 0.0.0.0 --port 8002
```

Without Poetry:

```bash
python3 -m pip install -r requirements.txt
python3 utils/validate_registry.py
mkdocs build --strict -f mkdocs.yaml
uvicorn service.app:app --host 0.0.0.0 --port 8002
```

Then open http://<server-ip-or-domain>:8002/. T2C-Registry is available at `/registry/` and the CyVer service at `/query-validator/`.

## Add a registry resource

1. Add one record to [`docs/registry.yaml`](docs/registry.yaml).
2. Run `python3 utils/validate_registry.py`.
3. Open a pull request, including primary links for the data, paper and code.

See the [contribution guide](docs/contribute.md) for field definitions and inclusion criteria.

## Deploy

The workflow in `.github/workflows/deploy.yml` validates and publishes T2C-Hub to GitHub Pages on every push to `main`. In the repository settings, select **GitHub Actions** as the Pages source.
The Pages workflow installs only the static-site dependencies from `requirements-docs.txt`; the FastAPI service uses the complete `requirements.txt`.

## License

The website code and original documentation use the license in [`LICENSE`](LICENSE). Each resource listed in T2C-Registry retains its own license; always check the upstream source before reuse.
## Database associations

Neo4j connections are defined once in the top-level `databases` list in `docs/registry.yaml`. Each benchmark references one or more entries through its `databases` list. The query validator therefore accepts database IDs, while retaining the association with the relevant benchmarks.

Natural-language questions are embedded with `sentence-transformers/all-mpnet-base-v2` and compared with the question embeddings in `embeddings/<benchmark-id>.npz`. The global top five are selected across every benchmark associated with the chosen database.

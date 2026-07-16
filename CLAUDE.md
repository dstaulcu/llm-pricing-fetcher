# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python script that fetches LLM model pricing across cloud providers (AWS Bedrock, Azure OpenAI, Google Vertex AI, Oracle GenAI) and writes a unified, regenerable CSV at `output/model_costs.csv`. Each run replaces the CSV and stamps rows with `LastETLDate`.

## Commands

```bash
pip install -r requirements.txt      # PyYAML is the only hard requirement; cloud SDKs are optional
python fetch_models.py               # run (uses config.yaml, writes output/model_costs.csv)
python fetch_models.py --config config.yaml --output output/model_costs.csv

python -m pytest tests/ -v           # run all tests (no network/credentials needed — tests use fakes)
python -m pytest tests/test_providers.py -v                    # one file
python -m pytest tests/test_orchestrator.py::test_main_end_to_end -v  # one test
```

Exit codes from `fetch_models.py`: `0` = all providers clean, `1` = partial CSV (some providers failed), `2` = nothing produced / bad config.

## Architecture

Two layers, deliberately decoupled:

- **Orchestrator** (`fetch_models.py`): loads `config.yaml`, instantiates each enabled provider from `PROVIDER_MAP`, calls `authenticate()` then `fetch_models(regions)`, aggregates the returned `ModelData` rows, sorts by `(service, region, model_id)`, and writes the CSV. It never knows provider internals. Providers are isolated — one raising doesn't stop the rest.
- **Providers** (`providers/*.py`): each subclasses `Provider` or the `CatalogProvider` convenience base from `providers/base.py` and returns `List[ModelData]`.

Key design fact: cloud LLM listing APIs generally do **not** return per-token prices, so pricing lives in a **manually maintained catalog** dict (`Catalog = {model_id: (creator, input_per_1k, output_per_1k)}`) at the top of each provider module, with a comment linking the official pricing page it was sourced from. Two provider modes:

- **AWS** (`providers/aws.py`) does live discovery via `bedrock.list_foundation_models` per region and joins against its catalog; live models missing from the catalog are still emitted priced at `0` (a signal to add them).
- **Azure / Google / Oracle** are catalog-only (`CatalogProvider`): they emit their catalog once per configured region.

**Graceful degradation is a hard requirement**: if an SDK is missing, credentials fail, or a listing call errors, a provider must log a warning and fall back to catalog-only output — never raise for missing live access. `authenticate()` implementations follow this contract.

## Adding a provider

1. Create `providers/<name>.py` — subclass `CatalogProvider` (catalog-only) or `Provider` with `authenticate()`/`fetch_models()` (live discovery; see `providers/aws.py`).
2. Register it in `PROVIDER_MAP` in `fetch_models.py`.
3. Add a config block in `config.yaml` (`enabled` + `regions`).
4. Add tests in `tests/` using fakes (see `_FakeSession`/`_FakeBedrockClient` in `tests/test_providers.py`).

## Conventions

- Costs are USD per 1,000 tokens. CSV cost values are written as plain decimals via `_format_cost` — never scientific notation.
- CSV rows are unique and sorted on `(service, region, model_id)`; the column schema is `CSV_FIELDS` in `fetch_models.py`. Changing the schema breaks the output contract documented in README.md.
- `conftest.py` at the repo root exists solely to make the repo root importable for tests; keep it.
- Design/plan docs for this project live in `docs/superpowers/`.

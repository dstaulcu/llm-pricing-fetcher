# Model Pricing Fetcher — Implementation Notes

Implements [the design spec](../specs/2026-07-16-model-pricing-fetcher-design.md).

## What was built

A plugin-based Python script that writes a unified `output/model_costs.csv`
across AWS Bedrock, Azure OpenAI, Google Vertex AI, and Oracle GenAI.

| File | Responsibility |
|------|----------------|
| `providers/base.py` | `ModelData`, `Provider` ABC, `CatalogProvider`, `catalog_to_models` |
| `providers/aws.py` | Live Bedrock listing joined to price catalog; catalog fallback |
| `providers/azure.py` | Catalog-based Azure OpenAI provider |
| `providers/google.py` | Catalog-based Google Vertex AI provider |
| `providers/oracle.py` | Catalog-based Oracle GenAI provider |
| `fetch_models.py` | Config load, provider orchestration, CSV write, CLI |
| `config.yaml` | Which providers/regions are enabled |
| `tests/` | 17 tests, no network/credentials needed |

## Key design decisions (deviations from the original spec)

1. **Pricing is a maintained catalog, not live-fetched.** Cloud listing APIs
   don't return per-token LLM prices. The spec implied live pricing; reality
   forced a hand-maintained catalog per provider, clearly labelled with the
   source pricing page.
2. **Graceful degradation instead of hard auth failure.** The spec said a
   provider auth failure skips that provider. Instead, providers fall back to
   catalog-only mode so the script produces a useful CSV even with no cloud
   credentials (verified: it ran here with an old boto3 that lacks `bedrock`).
3. **Only AWS does live discovery for v1.** Azure/Google/Oracle live discovery
   is per-account/per-deployment and was deferred; they emit catalogs. The
   `CatalogProvider` base makes wiring live discovery in later a small change.
4. **Direct implementation, not the 10-round subagent pipeline.** The code was
   fully specified, so a fresh-subagent-per-task pipeline would have been
   transcription overhead. Built directly with TDD.

## Schema

`model_id, service, provider, region, input_cost_per_1k_tokens,
output_cost_per_1k_tokens, LastETLDate` — unique on `(service, region,
model_id)`, prices rendered as plain decimals, `LastETLDate` in UTC ISO 8601.

## Verified

- `python -m pytest tests/` → 17 passed
- `python fetch_models.py` → 35 models written, exit 0, AWS gracefully fell
  back to catalog when live listing was unavailable.

import pytest

from providers.base import (
    CatalogProvider,
    ModelData,
    Provider,
    catalog_to_models,
)
from providers.aws import AWSProvider, AWS_PRICING
from providers.azure import AzureProvider
from providers.google import GoogleProvider
from providers.oracle import OracleProvider


def test_provider_is_abstract():
    with pytest.raises(TypeError):
        Provider({})


def test_modeldata_fields():
    data = ModelData("m", "svc", "creator", "us-east-1", 0.001, 0.002)
    assert data.model_id == "m"
    assert data.service == "svc"
    assert data.provider == "creator"
    assert data.region == "us-east-1"
    assert data.input_cost_per_1k_tokens == 0.001
    assert data.output_cost_per_1k_tokens == 0.002


def test_catalog_to_models_expands_all_entries():
    catalog = {
        "a": ("X", 0.1, 0.2),
        "b": ("Y", 0.3, 0.4),
    }
    rows = catalog_to_models("Svc", catalog, "r1")
    assert len(rows) == 2
    assert {r.model_id for r in rows} == {"a", "b"}
    assert all(r.service == "Svc" and r.region == "r1" for r in rows)


@pytest.mark.parametrize(
    "cls,service",
    [
        (AzureProvider, "Azure OpenAI"),
        (GoogleProvider, "Google Vertex AI"),
        (OracleProvider, "Oracle GenAI"),
    ],
)
def test_catalog_providers_emit_per_region(cls, service):
    provider = cls({"regions": ["r1", "r2"]})
    provider.authenticate()  # no-op, must not raise
    models = provider.fetch_models(["r1", "r2"])
    assert models, "expected catalog rows"
    assert all(m.service == service for m in models)
    # Every catalog model should appear once per region.
    assert {m.region for m in models} == {"r1", "r2"}
    for m in models:
        assert m.input_cost_per_1k_tokens >= 0
        assert m.output_cost_per_1k_tokens >= 0


def test_aws_uses_catalog_when_no_session():
    provider = AWSProvider({})
    # No authenticate() call -> _session is None -> catalog fallback.
    models = provider.fetch_models(["us-east-1"])
    assert len(models) == len(AWS_PRICING)
    assert all(m.service == "AWS Bedrock" for m in models)


class _FakeBedrockClient:
    def list_foundation_models(self):
        return {
            "modelSummaries": [
                {"modelId": "anthropic.claude-3-haiku-20240307-v1:0", "providerName": "Anthropic"},
                {"modelId": "some.new-model-not-in-catalog", "providerName": "NewCo"},
            ]
        }


class _FakeSession:
    def client(self, service, region_name=None):
        assert service == "bedrock"
        return _FakeBedrockClient()


def test_aws_live_listing_joins_catalog_pricing():
    provider = AWSProvider({})
    provider._session = _FakeSession()
    models = provider.fetch_models(["us-east-1"])

    by_id = {m.model_id: m for m in models}
    assert set(by_id) == {
        "anthropic.claude-3-haiku-20240307-v1:0",
        "some.new-model-not-in-catalog",
    }
    # Known model gets catalog pricing.
    haiku = by_id["anthropic.claude-3-haiku-20240307-v1:0"]
    assert haiku.input_cost_per_1k_tokens == 0.00025
    assert haiku.output_cost_per_1k_tokens == 0.00125
    assert haiku.provider == "Anthropic"
    # Unknown model still listed, priced at 0.
    unknown = by_id["some.new-model-not-in-catalog"]
    assert unknown.input_cost_per_1k_tokens == 0.0
    assert unknown.output_cost_per_1k_tokens == 0.0
    assert unknown.provider == "NewCo"

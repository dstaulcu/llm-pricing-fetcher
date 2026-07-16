"""Core abstractions shared by every cloud provider plugin.

A provider's job is to produce `ModelData` rows: one per (model, region).
Pricing is sourced from each provider's manually maintained catalog because
cloud LLM listing APIs generally do not expose per-token prices. Providers
that can enumerate models live (e.g. AWS Bedrock) join the live model list
against the catalog; the rest emit their catalog directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class ModelData:
    """One priced model in one region, normalized across providers."""

    model_id: str
    service: str                       # e.g. "AWS Bedrock"
    provider: str                      # model creator, e.g. "Anthropic"
    region: str                        # provider-specific region code
    input_cost_per_1k_tokens: float    # USD per 1,000 input tokens
    output_cost_per_1k_tokens: float   # USD per 1,000 output tokens


# A catalog maps model_id -> (creator, input_per_1k, output_per_1k).
Catalog = Dict[str, Tuple[str, float, float]]


class ProviderAuthError(Exception):
    """Raised when a provider cannot establish credentials it strictly needs."""


class ProviderFetchError(Exception):
    """Raised when a provider fails to produce any model data."""


def catalog_to_models(service: str, catalog: Catalog, region: str) -> List[ModelData]:
    """Expand a pricing catalog into ModelData rows for one region."""
    return [
        ModelData(
            model_id=model_id,
            service=service,
            provider=creator,
            region=region,
            input_cost_per_1k_tokens=input_cost,
            output_cost_per_1k_tokens=output_cost,
        )
        for model_id, (creator, input_cost, output_cost) in catalog.items()
    ]


class Provider(ABC):
    """Base class for a cloud LLM provider plugin."""

    service_name: str = "Unknown"

    def __init__(self, config: dict):
        self.config = config or {}

    @abstractmethod
    def authenticate(self) -> None:
        """Prepare any credentials/clients this provider needs.

        Implementations should degrade gracefully: if live access is
        unavailable, log and fall back to catalog-only mode rather than
        raising, so the script still produces a useful price book.
        """

    @abstractmethod
    def fetch_models(self, regions: List[str]) -> List[ModelData]:
        """Return priced models available across the given regions."""


class CatalogProvider(Provider):
    """Provider whose model list comes straight from its pricing catalog.

    Suitable for clouds where live per-region model discovery is not yet
    wired up. Emits the full catalog for each configured region.
    """

    catalog: Catalog = {}

    def authenticate(self) -> None:
        # Catalog providers need no live credentials; nothing to do.
        return

    def fetch_models(self, regions: List[str]) -> List[ModelData]:
        models: List[ModelData] = []
        for region in regions:
            models.extend(catalog_to_models(self.service_name, self.catalog, region))
        return models

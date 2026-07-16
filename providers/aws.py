"""AWS Bedrock provider.

Unlike the catalog-only providers, AWS Bedrock exposes a real model-listing
API (`bedrock.list_foundation_models`). We call it per region to discover
which models are actually available, then join against the maintained price
catalog. If boto3 is missing or credentials/listing fail, we fall back to
emitting the catalog so the run still yields a useful CSV.
"""

import logging
from typing import List

from .base import (
    Catalog,
    ModelData,
    Provider,
    catalog_to_models,
)

logger = logging.getLogger(__name__)

# USD per 1,000 tokens (input, output). Manually maintained.
# Verify against https://aws.amazon.com/bedrock/pricing/ before relying on these.
AWS_PRICING: Catalog = {
    # model_id: (creator, input_per_1k, output_per_1k)
    "anthropic.claude-3-5-sonnet-20241022-v2:0": ("Anthropic", 0.003, 0.015),
    "anthropic.claude-3-opus-20240229-v1:0": ("Anthropic", 0.015, 0.075),
    "anthropic.claude-3-sonnet-20240229-v1:0": ("Anthropic", 0.003, 0.015),
    "anthropic.claude-3-haiku-20240307-v1:0": ("Anthropic", 0.00025, 0.00125),
    "meta.llama3-70b-instruct-v1:0": ("Meta", 0.00265, 0.0035),
    "meta.llama3-8b-instruct-v1:0": ("Meta", 0.0003, 0.0006),
    "meta.llama2-70b-chat-v1": ("Meta", 0.00195, 0.00256),
    "meta.llama2-13b-chat-v1": ("Meta", 0.00075, 0.001),
    "mistral.mistral-7b-instruct-v0:2": ("Mistral", 0.00015, 0.0002),
    "mistral.mistral-large-2402-v1:0": ("Mistral", 0.004, 0.012),
    "mistral.mixtral-8x7b-instruct-v0:1": ("Mistral", 0.00045, 0.0007),
    "cohere.command-r-plus-v1:0": ("Cohere", 0.003, 0.015),
    "cohere.command-r-v1:0": ("Cohere", 0.0005, 0.0015),
    "amazon.nova-pro-v1:0": ("Amazon", 0.0008, 0.0032),
    "amazon.nova-lite-v1:0": ("Amazon", 0.00006, 0.00024),
    "amazon.nova-micro-v1:0": ("Amazon", 0.000035, 0.00014),
    "amazon.titan-text-express-v1": ("Amazon", 0.0002, 0.0006),
    "ai21.jamba-1-5-large-v1:0": ("AI21 Labs", 0.002, 0.008),
    "ai21.jamba-1-5-mini-v1:0": ("AI21 Labs", 0.0002, 0.0004),
}


class AWSProvider(Provider):
    """AWS Bedrock: live model discovery joined to a maintained price catalog."""

    service_name = "AWS Bedrock"

    def __init__(self, config: dict):
        super().__init__(config)
        self._session = None

    def authenticate(self) -> None:
        try:
            import boto3
        except ImportError:
            logger.warning(
                "boto3 not installed; AWS live listing disabled, using price catalog only"
            )
            self._session = None
            return

        try:
            profile = (self.config.get("auth") or {}).get("profile")
            self._session = (
                boto3.Session(profile_name=profile) if profile else boto3.Session()
            )
            logger.info("AWS session initialized")
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("AWS auth failed (%s); using price catalog only", exc)
            self._session = None

    def fetch_models(self, regions: List[str]) -> List[ModelData]:
        models: List[ModelData] = []

        for region in regions:
            live_ids = self._list_live_models(region)

            if live_ids:
                for model_id, creator in live_ids.items():
                    catalog_entry = AWS_PRICING.get(model_id)
                    if catalog_entry:
                        _, input_cost, output_cost = catalog_entry
                    else:
                        input_cost, output_cost = 0.0, 0.0
                    models.append(
                        ModelData(
                            model_id=model_id,
                            service=self.service_name,
                            provider=creator,
                            region=region,
                            input_cost_per_1k_tokens=input_cost,
                            output_cost_per_1k_tokens=output_cost,
                        )
                    )
            else:
                models.extend(catalog_to_models(self.service_name, AWS_PRICING, region))

        return models

    def _list_live_models(self, region: str):
        """Return {model_id: creator} from the Bedrock API, or None on failure."""
        if self._session is None:
            return None
        try:
            client = self._session.client("bedrock", region_name=region)
            response = client.list_foundation_models()
            summaries = response.get("modelSummaries", [])
            live = {
                s["modelId"]: s.get("providerName", "Unknown")
                for s in summaries
                if "modelId" in s
            }
            logger.info("AWS Bedrock: %d models listed in %s", len(live), region)
            return live or None
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning(
                "AWS live listing failed in %s (%s); using catalog for this region",
                region,
                exc,
            )
            return None

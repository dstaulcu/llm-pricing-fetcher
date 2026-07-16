"""Azure OpenAI provider (catalog-based).

Azure model availability is per-deployment and per-account, so there is no
simple global "list models in region" call the way Bedrock offers. For now
this provider emits its maintained price catalog for each configured region.
Live deployment discovery via azure-mgmt-cognitiveservices can be layered on
later without changing the output contract.
"""

from .base import Catalog, CatalogProvider

# USD per 1,000 tokens (input, output). Manually maintained.
# Verify against https://azure.microsoft.com/pricing/details/cognitive-services/openai-service/
AZURE_PRICING: Catalog = {
    "gpt-4o": ("OpenAI", 0.005, 0.015),
    "gpt-4o-mini": ("OpenAI", 0.00015, 0.0006),
    "gpt-4-turbo": ("OpenAI", 0.01, 0.03),
    "gpt-4": ("OpenAI", 0.03, 0.06),
    "gpt-35-turbo": ("OpenAI", 0.0005, 0.0015),
    "text-embedding-3-small": ("OpenAI", 0.00002, 0.0),
    "text-embedding-3-large": ("OpenAI", 0.00013, 0.0),
}


class AzureProvider(CatalogProvider):
    service_name = "Azure OpenAI"
    catalog = AZURE_PRICING

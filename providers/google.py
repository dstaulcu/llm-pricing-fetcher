"""Google Vertex AI provider (catalog-based).

Vertex exposes models through the aiplatform SDK, but pricing is not returned
by the listing calls. This provider emits its maintained price catalog for
each configured region; live model discovery can be added later without
changing the output contract.
"""

from .base import Catalog, CatalogProvider

# USD per 1,000 tokens (input, output). Manually maintained.
# Verify against https://cloud.google.com/vertex-ai/generative-ai/pricing
GOOGLE_PRICING: Catalog = {
    "gemini-1.5-pro": ("Google", 0.00125, 0.005),
    "gemini-1.5-flash": ("Google", 0.000075, 0.0003),
    "gemini-1.0-pro": ("Google", 0.000125, 0.000375),
    "text-bison": ("Google", 0.0001, 0.0002),
    "text-unicorn": ("Google", 0.001, 0.002),
}


class GoogleProvider(CatalogProvider):
    service_name = "Google Vertex AI"
    catalog = GOOGLE_PRICING

"""Oracle Cloud Infrastructure (OCI) Generative AI provider (catalog-based).

OCI Generative AI exposes models via the oci SDK, but pricing comes from the
OCI pricing pages rather than the API. This provider emits its maintained
price catalog for each configured region; live discovery via
oci.generative_ai can be added later without changing the output contract.
"""

from .base import Catalog, CatalogProvider

# USD per 1,000 tokens (input, output). Manually maintained.
# Verify against https://www.oracle.com/artificial-intelligence/generative-ai/pricing/
ORACLE_PRICING: Catalog = {
    "cohere.command-r-plus": ("Cohere", 0.003, 0.015),
    "cohere.command-r": ("Cohere", 0.0005, 0.0015),
    "meta.llama-3.1-70b-instruct": ("Meta", 0.00265, 0.0035),
    "meta.llama-3-70b-instruct": ("Meta", 0.00265, 0.0035),
}


class OracleProvider(CatalogProvider):
    service_name = "Oracle GenAI"
    catalog = ORACLE_PRICING

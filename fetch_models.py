"""Fetch LLM model pricing across cloud providers into a single CSV.

Usage:
    python fetch_models.py [--config config.yaml] [--output output/model_costs.csv]

Reads a YAML config listing which providers/regions to query, asks each
enabled provider for its priced models, and writes a unified CSV stamped with
the ETL run time. Providers are isolated: one failing does not stop the rest.
"""

import argparse
import csv
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

from providers.base import ModelData, ProviderAuthError, ProviderFetchError
from providers.aws import AWSProvider
from providers.azure import AzureProvider
from providers.google import GoogleProvider
from providers.oracle import OracleProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("fetch_models")

PROVIDER_MAP = {
    "aws": AWSProvider,
    "azure": AzureProvider,
    "google": GoogleProvider,
    "oracle": OracleProvider,
}

ROOT = Path(__file__).parent
DEFAULT_CONFIG = ROOT / "config.yaml"
DEFAULT_OUTPUT = ROOT / "output" / "model_costs.csv"

CSV_FIELDS = [
    "model_id",
    "service",
    "provider",
    "region",
    "input_cost_per_1k_tokens",
    "output_cost_per_1k_tokens",
    "LastETLDate",
]


def _format_cost(value: float) -> str:
    """Render a price as a plain decimal string (no scientific notation)."""
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    return text or "0"


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load the YAML configuration file."""
    with open(config_path, "r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    logger.info("Loaded config from %s", config_path)
    return config


def fetch_all_providers(config: Dict[str, Any]) -> tuple[List[ModelData], List[str]]:
    """Run every enabled provider. Returns (models, failed_provider_names)."""
    all_models: List[ModelData] = []
    failed: List[str] = []
    providers_config = config.get("providers", {}) or {}

    for name, provider_class in PROVIDER_MAP.items():
        provider_config = providers_config.get(name, {}) or {}

        if not provider_config.get("enabled", False):
            logger.info("Skipping %s (disabled)", name)
            continue

        regions = provider_config.get("regions", []) or []
        if not regions:
            logger.warning("%s is enabled but has no regions configured; skipping", name)
            continue

        try:
            logger.info("Processing %s...", name)
            provider = provider_class(provider_config)
            provider.authenticate()
            models = provider.fetch_models(regions)
            all_models.extend(models)
            logger.info("Fetched %d models from %s", len(models), name)
        except (ProviderAuthError, ProviderFetchError) as exc:
            logger.error("%s failed: %s", name, exc)
            failed.append(name)
        except Exception as exc:  # noqa: BLE001 - keep other providers alive
            logger.error("%s unexpected error: %s", name, exc)
            failed.append(name)

    return all_models, failed


def write_csv(models: List[ModelData], output_path: Path) -> None:
    """Write models to CSV, replacing the file and stamping LastETLDate."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    etl_date = datetime.now(timezone.utc).isoformat()

    ordered = sorted(models, key=lambda m: (m.service, m.region, m.model_id))

    with open(output_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for model in ordered:
            writer.writerow(
                {
                    "model_id": model.model_id,
                    "service": model.service,
                    "provider": model.provider,
                    "region": model.region,
                    "input_cost_per_1k_tokens": _format_cost(model.input_cost_per_1k_tokens),
                    "output_cost_per_1k_tokens": _format_cost(model.output_cost_per_1k_tokens),
                    "LastETLDate": etl_date,
                }
            )

    logger.info("Wrote %d models to %s", len(ordered), output_path)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch cloud LLM model pricing into a CSV.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Path to config YAML")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to output CSV")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
    except FileNotFoundError:
        logger.error("Config file not found: %s", args.config)
        return 2
    except yaml.YAMLError as exc:
        logger.error("Failed to parse config: %s", exc)
        return 2

    models, failed = fetch_all_providers(config)

    if not models:
        logger.error("No models fetched from any provider")
        return 2

    write_csv(models, args.output)

    if failed:
        logger.warning("Completed with failures: %s", ", ".join(failed))
        return 1

    logger.info("Done. %d models written.", len(models))
    return 0


if __name__ == "__main__":
    sys.exit(main())

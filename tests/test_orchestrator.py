import csv
from datetime import datetime

import pytest

from fetch_models import fetch_all_providers, write_csv, load_config, main, _format_cost
from providers.base import ModelData


def test_format_cost_avoids_scientific_notation():
    assert _format_cost(0.000035) == "0.000035"
    assert _format_cost(0.00002) == "0.00002"
    assert _format_cost(0.015) == "0.015"
    assert _format_cost(0.0) == "0"


def _sample_models():
    return [
        ModelData("b-model", "Svc", "Creator", "us-west-2", 0.002, 0.004),
        ModelData("a-model", "Svc", "Creator", "us-east-1", 0.001, 0.002),
    ]


def test_write_csv_creates_file_with_schema(tmp_path):
    out = tmp_path / "model_costs.csv"
    write_csv(_sample_models(), out)
    assert out.exists()

    with open(out, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 2
    assert set(rows[0].keys()) == {
        "model_id", "service", "provider", "region",
        "input_cost_per_1k_tokens", "output_cost_per_1k_tokens", "LastETLDate",
    }


def test_write_csv_sorted_by_service_region_model(tmp_path):
    out = tmp_path / "model_costs.csv"
    write_csv(_sample_models(), out)
    with open(out, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    # us-east-1 sorts before us-west-2.
    assert rows[0]["region"] == "us-east-1"
    assert rows[1]["region"] == "us-west-2"


def test_write_csv_stamps_iso_timestamp(tmp_path):
    out = tmp_path / "model_costs.csv"
    write_csv(_sample_models(), out)
    with open(out, newline="", encoding="utf-8") as handle:
        row = next(csv.DictReader(handle))
    # Must parse as ISO 8601.
    parsed = datetime.fromisoformat(row["LastETLDate"])
    assert parsed.tzinfo is not None  # UTC-aware


def test_fetch_all_providers_skips_disabled():
    config = {
        "providers": {
            "azure": {"enabled": True, "regions": ["eastus"]},
            "google": {"enabled": False, "regions": ["us-central1"]},
            "oracle": {"enabled": False},
        }
    }
    models, failed = fetch_all_providers(config)
    assert failed == []
    assert models
    assert all(m.service == "Azure OpenAI" for m in models)


def test_fetch_all_providers_skips_enabled_without_regions():
    config = {"providers": {"azure": {"enabled": True, "regions": []}}}
    models, failed = fetch_all_providers(config)
    assert models == []
    assert failed == []


def test_main_end_to_end(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "providers:\n"
        "  azure:\n"
        "    enabled: true\n"
        "    regions:\n"
        "      - eastus\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.csv"
    code = main(["--config", str(config_file), "--output", str(out)])
    assert code == 0
    assert out.exists()
    with open(out, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows
    assert rows[0]["service"] == "Azure OpenAI"


def test_main_missing_config_returns_2(tmp_path):
    code = main(["--config", str(tmp_path / "nope.yaml"), "--output", str(tmp_path / "o.csv")])
    assert code == 2


def test_load_config_reads_yaml(tmp_path):
    config_file = tmp_path / "c.yaml"
    config_file.write_text("providers:\n  aws:\n    enabled: false\n", encoding="utf-8")
    config = load_config(config_file)
    assert config["providers"]["aws"]["enabled"] is False

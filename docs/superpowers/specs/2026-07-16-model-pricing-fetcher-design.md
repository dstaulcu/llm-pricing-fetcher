# Model Pricing Fetcher Design Spec

**Date:** 2026-07-16  
**Scope:** Plugin-based script to fetch and maintain cloud LLM model pricing from multiple providers (AWS, Azure, Google, Oracle)

---

## Overview

A Python script that periodically fetches model pricing and availability data from cloud LLM services and outputs a unified CSV. The script uses a plugin architecture to support multiple cloud providers, with extensibility for future additions.

**Key features:**
- Plugin-based provider system (easy to add new clouds)
- Multi-region support per provider
- Flexible authentication (default chains + config overrides)
- Single unified CSV output with service, region, and LastETLDate tracking
- Isolation: provider failures don't block others

---

## Project Structure

```
model-pricing-fetcher/
├── .gitignore                # Ignore credentials, venv, __pycache__, .env, output cache
├── README.md                 # Getting started + architecture diagrams (mermaid)
├── fetch_models.py           # Main orchestrator
├── config.yaml               # Provider config and regions to fetch
├── output/
│   └── model_costs.csv       # Generated CSV (replaced each run)
├── providers/
│   ├── __init__.py
│   ├── base.py               # Abstract Provider base class
│   ├── aws.py                # AWS Bedrock provider implementation
│   ├── azure.py              # Azure OpenAI provider implementation
│   ├── google.py             # Google Vertex AI provider implementation
│   └── oracle.py             # Oracle provider implementation
├── requirements.txt          # Python dependencies
└── tests/                    # Unit tests (optional for v1)
```

---

## Architecture

### Provider Plugin System

**Base Class (`providers/base.py`):**
```python
class Provider(ABC):
    @abstractmethod
    def authenticate(self) -> None:
        """Authenticate using default chains + config overrides."""
        pass
    
    @abstractmethod
    def fetch_models(self, regions: List[str]) -> List[ModelData]:
        """
        Fetch all models available in specified regions.
        Returns: List[{model_id, input_cost, output_cost}]
        """
        pass
```

**ModelData dataclass:**
```python
@dataclass
class ModelData:
    model_id: str
    service: str                    # e.g., "AWS Bedrock"
    provider: str                   # e.g., "Anthropic"
    region: str                     # e.g., "us-east-1"
    input_cost_per_1k_tokens: float
    output_cost_per_1k_tokens: float
```

### Main Orchestrator (`fetch_models.py`)

1. **Load config** (`config.yaml`) → determine enabled providers and regions
2. **Authenticate:** Initialize each enabled provider using auth config
3. **Fetch:** Call `provider.fetch_models(regions)` for each provider
4. **Merge:** Combine results from all providers
5. **Deduplicate:** Uniqueness key is (service, region, model_id). If same model appears in multiple clouds, each is a separate row. Within a cloud, if a model is queried twice (e.g., same region), later result overwrites earlier.
6. **Write CSV:** Sort by (service, region, model_id), include LastETLDate (ISO 8601), replace `output/model_costs.csv`
7. **Log:** Summary of models fetched, any failures, total count

**Error handling:** If a provider fails, log error and continue. Script succeeds if at least one provider completes; exit code reflects how many failed (0 = all succeeded, 1+ = some failed).

---

## Configuration (`config.yaml`)

```yaml
providers:
  aws:
    enabled: true
    regions:
      - us-east-1
      - us-west-2
    auth:
      use_default_chain: true  # Use IAM/env var/profile auth
      profile: null             # Optional: override AWS profile
  
  azure:
    enabled: true
    regions:
      - eastus
      - westus
    auth:
      use_default_chain: true
      subscription_id: null     # Optional: override via config (not recommended)
  
  google:
    enabled: true
    regions:
      - us-central1
    auth:
      use_default_chain: true
      project_id: null          # Optional: override project
  
  oracle:
    enabled: true
    regions:
      - us-phoenix-1
    auth:
      use_default_chain: true
      region: null              # Optional: override region
```

**Notes:**
- `use_default_chain: true` → use provider's default credential discovery (IAM, gcloud, Azure CLI, etc.)
- Config overrides allow CI/CD to specify credentials via environment or secrets
- Disabled providers are skipped; missing config section defaults to disabled

---

## CSV Output Schema

**File:** `output/model_costs.csv`  
**Format:** CSV, replaced entirely on each run  
**LastETLDate:** ISO 8601 timestamp (UTC) when script completed

```csv
model_id,service,provider,region,input_cost_per_1k_tokens,output_cost_per_1k_tokens,LastETLDate
anthropic.claude-3-5-sonnet-20241022-v2:0,AWS Bedrock,Anthropic,us-east-1,0.003,0.015,2026-07-16T14:32:00Z
anthropic.claude-3-opus-20240229-v1:0,AWS Bedrock,Anthropic,us-east-1,0.015,0.075,2026-07-16T14:32:00Z
gpt-4-turbo,Azure OpenAI,OpenAI,eastus,0.01,0.03,2026-07-16T14:32:00Z
...
```

**Field definitions:**
- `model_id`: Cloud provider's model identifier (format varies: AWS uses prefixes like `anthropic.`, Azure uses generic names)
- `service`: Service name (e.g., "AWS Bedrock", "Azure OpenAI", "Google Vertex AI", "Oracle GenAI")
- `provider`: Model creator/organization (e.g., "Anthropic", "OpenAI", "Meta", "Google")
- `region`: Region code (provider-specific)
- `input_cost_per_1k_tokens`: USD, numeric (no $ prefix)
- `output_cost_per_1k_tokens`: USD, numeric
- `LastETLDate`: ISO 8601 timestamp, same for all rows in a run

---

## Error Handling & Resilience

### Per-Provider Isolation
- If AWS fetch fails: Azure/Google/Oracle complete independently
- Partial CSV output reflects only successful providers
- Failures logged with provider name and error

### Logging Strategy
- **INFO:** Models fetched (e.g., "AWS Bedrock: 25 models in us-east-1")
- **WARN:** Missing data or degraded results (e.g., pricing unavailable for 3 models)
- **ERROR:** Provider failure (e.g., "Azure auth failed: subscription ID not configured")
- **Summary:** Total models written, timestamp, which providers succeeded/failed

### Exit Codes
- `0`: All enabled providers succeeded
- `1`: One or more providers failed (partial CSV written)
- `2`: Critical error (e.g., no providers enabled, output directory missing)

### Retry Logic (Optional, v1)
- Exponential backoff for transient API errors (3xx, 429 rate limit)
- Max 3 retries, base delay 2s
- Provider timeout: 30s per region

---

## Dependencies

```
boto3>=1.26.0                           # AWS API
botocore>=1.29.0
azure-identity>=1.14.0                  # Azure auth
azure-mgmt-openai>=1.0.0                # Azure OpenAI API
google-cloud-aiplatform>=1.35.0         # Google Vertex AI
oci>=2.100.0                            # Oracle API
oci-cli>=3.0.0                          # Oracle CLI (optional, for local testing)
PyYAML>=6.0                             # Config parsing
python-dateutil>=2.8.0                  # Date utilities
requests>=2.28.0                        # HTTP (fallback/testing)
```

**Python version:** 3.9+

---

## Use Cases

### Manual Trigger
```bash
python fetch_models.py
# Reads config.yaml, fetches from enabled providers, writes output/model_costs.csv
```

### GitHub Actions (Future)
```yaml
- name: Fetch model pricing
  run: python fetch_models.py
  env:
    AWS_REGION: us-east-1
    AZURE_SUBSCRIPTION_ID: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
    GOOGLE_PROJECT_ID: ${{ secrets.GOOGLE_PROJECT_ID }}
```

---

## Testing Strategy (v1 Optional)

**Unit tests per provider** (if included):
- Mock provider APIs
- Test config parsing
- Test CSV generation
- Test error handling (one provider fails, others succeed)

**Manual validation:**
- Run against each cloud provider
- Verify CSV headers and data types
- Check LastETLDate format

---

## Future Extensibility

**Adding a new provider (e.g., Anthropic Workbench):**
1. Create `providers/anthropic_workbench.py`
2. Extend `Provider` base class, implement `authenticate()` and `fetch_models()`
3. Add config section to `config.yaml`
4. No changes to orchestrator

**On-prem MaaS (future):**
- Add `providers/onprem.py` with HTTP endpoint config
- Config specifies endpoint URLs + auth tokens
- Same ModelData output format

---

## Success Criteria

✅ Script runs manually with no external setup (assumes user is pre-authenticated)  
✅ Fetches models from AWS, Azure, Google, Oracle simultaneously  
✅ CSV includes service, provider, region, pricing, and LastETLDate  
✅ Provider failures don't block others (partial output acceptable)  
✅ Easily extensible for new providers  
✅ README includes mermaid architecture and sequence diagrams  
✅ .gitignore excludes credentials and cache  
✅ Works with GitHub Actions (environment-based auth)

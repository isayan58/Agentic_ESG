# Agent Deployment Guide

How to deploy one or more ESG Pilot agents to a client environment, separately from the bundled Streamlit app.

This doc is for the engineer landing the agents in the client's stack. It assumes the reader already understands what each agent does (see [RUNBOOK.md](RUNBOOK.md) for that). Here we focus on **what travels with the code**: dependencies, data, configuration, and the four deployment topologies the architecture supports.

---

## TL;DR

* Every agent is a plain Python class (`agents/*.py`) that subclasses `BaseAgent`. There is no service, no port, no message bus — agents talk to each other through an **in-process** pub/sub bus (`core/state_manager.py`).
* To run one agent standalone, you bring (a) its **inputs** as CSV files or as channels already published on that process's bus, (b) a small core/ + utils/ surface, and (c) a `data/company_profile.json`.
* AI calls (HF Inference API, Anthropic Claude) are **all optional** — every narrative path has a deterministic rule-based fallback. Production deployments without API keys still produce numerical outputs.
* The orchestrator (`core/orchestrator.py`) is **optional**. Agents have a stable `agent.run(**kwargs)` method that callers can invoke directly. The orchestrator only adds Claude-driven planning, dependency-graph enforcement, and an incremental-result cache.
* Multi-process deployments need a **state-manager replacement** (Redis / NATS / Kafka). The bundled state manager is a Python dict; it doesn't cross process boundaries.

---

## 1. The four deployment topologies

Pick the topology that matches the client's operational model. They differ only in how `state_manager` and orchestration are arranged — the agent code itself is the same in all four.

| Topology | When to pick it | Process count | State manager | Front-end |
| --- | --- | --- | --- | --- |
| **A. Monolith (the bundled app)** | Demos, internal tooling, single-tenant ESG team | 1 | Bundled in-process pub/sub | Streamlit |
| **B. Single-agent batch / lambda** | Client wants just one capability (e.g., carbon accounting) on a daily cron | 1 | Bundled in-process pub/sub | None — CLI / scheduled job |
| **C. Multi-agent batch (no Streamlit)** | Client has their own dashboard but wants the analytics pipeline | 1 | Bundled in-process pub/sub | None — CLI / scheduled job; results consumed by client's BI layer |
| **D. Distributed microservices** | Each agent owned by a different team; horizontal scale; cross-cluster | N | Networked pub/sub (Redis Streams, NATS, Kafka) — replaces `core/state_manager.py` | Client's own |

Topologies A–C are **drop-in**: same code, different entry points. Topology D requires writing a `state_manager` adapter that speaks the chosen network bus's API. The agents themselves don't change.

---

## 2. The shared core surface

Every agent — regardless of topology — needs this surface to import and instantiate cleanly. Treat this list as the **deployment baseline**: anything below must travel to the target environment.

### 2.1 Required Python modules

| Path | Why every agent needs it |
| --- | --- |
| [`config.py`](config.py) | Loads `HF_API_TOKEN`, `ANTHROPIC_API_KEY`, `DATA_DIR`, model names. Imported transitively by `core/hf_client.py`. |
| [`core/__init__.py`](core/__init__.py) | Package marker. |
| [`core/base_agent.py`](core/base_agent.py) | Abstract base class. Every agent inherits from it. |
| [`core/state_manager.py`](core/state_manager.py) | Per-user in-process pub/sub. Singleton instance `state_manager`. |
| [`core/data_access.py`](core/data_access.py) | `get_dataset(schema_name, fallback_loader)` — the canonical input helper. |
| [`core/company_config.py`](core/company_config.py) | `company_cfg` proxy. Resolves the active company profile per thread. |
| [`core/hf_client.py`](core/hf_client.py) | HuggingFace Inference API wrapper with rule-based fallbacks. Instantiated by `BaseAgent.__init__`. |
| [`utils/__init__.py`](utils/__init__.py) | Package marker. |
| [`utils/data_processing.py`](utils/data_processing.py) | `load_emissions()`, `load_esg_metrics()`, etc. — CSV loaders that `data_access.get_dataset` falls back to. |
| [`utils/agent_telemetry.py`](utils/agent_telemetry.py) | Persistent per-agent run history. `BaseAgent.__init__` calls into it. Best-effort — never crashes. |
| [`agents/__init__.py`](agents/__init__.py) | Package marker. |

These nine files are the **non-negotiable baseline**. Roughly ~30 KB on disk.

### 2.2 Required data files

| Path | Always required? | Notes |
| --- | --- | --- |
| [`data/company_profile.json`](data/company_profile.json) | **Yes** | Read by `company_cfg` on first access. Without it, every agent uses defaulted values that almost certainly don't match the client. See §6.1 for the schema. |
| [`data/regulatory_frameworks.json`](data/regulatory_frameworks.json) | Only for Regulatory Tracker | Used by `load_regulatory_frameworks()`. |
| `data/sample_*.csv` | Only when the agent has no upstream `data_collector` and no client-provided data | These are the **fallback** inputs. If the client is hooking in their own data, they don't need the samples. See §3 for which CSVs each agent reads via the fallback path. |

Note: `data/sample_*.csv` files are **not currently in the repo** — `utils/data_processing.py:load_csv` returns an empty `DataFrame()` when a sample file is missing. Agents handle empty inputs gracefully (they emit zeros / placeholders instead of crashing), but the resulting output isn't useful. You must supply real client data, sample CSVs, or run `data_collector` first to publish channels.

### 2.3 Optional dependencies

| Module | When you need it | Otherwise |
| --- | --- | --- |
| [`core/orchestrator.py`](core/orchestrator.py) + [`core/agent_loop.py`](core/agent_loop.py) | Topologies A or C, when you want Claude-driven planning across agents | Skip if you're calling `agent.run()` directly from your own scheduler. |
| [`utils/connection_manager.py`](utils/connection_manager.py), [`utils/connectors.py`](utils/connectors.py), [`utils/real_connectors.py`](utils/real_connectors.py), [`utils/schema_mapper.py`](utils/schema_mapper.py) | When deploying `data_collector` against real client systems (Snowflake, S3, BigQuery, etc.) | Skip if data is already in CSV / DataFrame form. |
| [`utils/connector_retry.py`](utils/connector_retry.py) | Same as above (referenced by `data_collector` for retry/timeout policy) | — |
| [`core/kpi_engine.py`](core/kpi_engine.py) | When deploying `roi_agent` | — |
| [`utils/feedback_store.py`](utils/feedback_store.py) | When deploying `report_generator` (it reads feedback into prompts) | Optional, not load-bearing — the agent works without prior feedback. |
| [`utils/whatif.py`](utils/whatif.py) | Only if exposing the what-if simulator UI | — |
| [`utils/framework_refresh.py`](utils/framework_refresh.py), [`utils/gap_suggestions.py`](utils/gap_suggestions.py), [`utils/industry_standards.py`](utils/industry_standards.py) | Only for `regulatory_tracker` advanced features and ROI agent peer benchmarking | — |

### 2.4 Python package dependencies

Required for **any** agent:

```
pandas
numpy
```

Required for the orchestrator + Claude tool-use loop:

```
anthropic        # only if running orchestrator with ANTHROPIC_API_KEY
```

Required only for HuggingFace fallback narratives (network calls; rule-based fallback works without):

```
requests         # already a transitive dep of pandas / hf_client
```

Optional, only if running `data_collector` against the corresponding source:

```
boto3                          # AWS S3
google-cloud-storage           # GCS
google-cloud-bigquery          # BigQuery
azure-storage-blob             # Azure Blob
deltalake                      # Delta Lake
snowflake-connector-python     # Snowflake
sqlalchemy                     # generic SQL DBs
huggingface_hub                # HF Datasets ingest
```

All cloud SDKs are imported lazily inside `utils/real_connectors.py`. A missing SDK shows an install hint in the UI / log, not an `ImportError` at startup.

---

## 3. Per-agent dependency map

Every agent has a stable `run(**kwargs)` entry point that returns a results dict and publishes one canonical channel. Inputs come from either (a) channels other agents already published, or (b) CSV / JSON files via the fallback loaders in `utils/data_processing.py`.

The **canonical pipeline order** (from [`core/orchestrator.py:37-47`](core/orchestrator.py#L37-L47)):

```
data_collector ─┬─► regulatory_tracker
                ├─► carbon_accountant
                ├─► risk_predictor      (also needs regulatory_tracker)
                ├─► audit_agent         (also needs regulatory_tracker, carbon_accountant)
                └─► roi_agent           (also needs carbon_accountant, risk_predictor)

audit_agent ─┐
carbon ──────┤
risk ────────┼─► report_generator
roi ─────────┘                      ─► action_agent  (also needs risk, audit, roi)
                                    └─► stakeholder_agent (also needs report, roi)
```

Reading the table: an agent can either **subscribe** to its dependencies' channels (if they ran in the same process) or **be given the dependency results as kwargs / by republishing the channel manually**. There is no third option — agents do not call each other directly.

| Agent | File | Reads channels (subscribes) | Reads CSV (fallback) | Publishes |
| --- | --- | --- | --- | --- |
| **Data Collector** | [`agents/data_collector.py`](agents/data_collector.py) | — | All `sample_*.csv` + real connectors via `connection_manager` | `dataset_<schema>` (one per ingested schema), `validated_<schema>`, `data_collection_results` |
| **Regulatory Tracker** | [`agents/regulatory_tracker.py`](agents/regulatory_tracker.py) | `dataset_esg_metrics` | `sample_esg_metrics.csv`, `regulatory_frameworks.json` | `regulatory_results` |
| **Carbon Accountant** | [`agents/carbon_accountant.py`](agents/carbon_accountant.py) | `dataset_emissions`, `dataset_supply_chain`, `dataset_energy` | `sample_emissions.csv`, `sample_supply_chain.csv`, `sample_energy.csv` | `carbon_results` |
| **Risk Predictor** | [`agents/risk_predictor.py`](agents/risk_predictor.py) | `dataset_emissions`, `dataset_esg_metrics`, `dataset_supply_chain`, `dataset_financials`, `regulatory_results` | `sample_emissions.csv`, `sample_esg_metrics.csv`, `sample_supply_chain.csv`, `sample_financials.csv` | `risk_results` |
| **Audit Agent** | [`agents/audit_agent.py`](agents/audit_agent.py) | `data_collection_results`, `regulatory_results`, `carbon_results`, `dataset_esg_metrics`, `dataset_supply_chain` | `sample_esg_metrics.csv`, `sample_supply_chain.csv` | `audit_results` |
| **ESG ROI Agent** | [`agents/roi_agent.py`](agents/roi_agent.py) | `carbon_results`, `risk_results`, `dataset_esg_metrics`, `dataset_supply_chain`, `dataset_energy`, `dataset_diversity`, `dataset_financials` | `sample_esg_metrics.csv`, `sample_supply_chain.csv`, `sample_energy.csv`, `sample_diversity.csv`, `sample_financials.csv` | `roi_results` |
| **Report Generator** | [`agents/report_generator.py`](agents/report_generator.py) | `carbon_results`, `regulatory_results`, `audit_results`, `data_collection_results`, `roi_results`, `risk_results`, `stakeholder_results` | — (reports are pure aggregation of upstream results) | `report_results` |
| **Action Agent** | [`agents/action_agent.py`](agents/action_agent.py) | `risk_results`, `audit_results`, `carbon_results`, `regulatory_results`, `roi_results` | — | `action_results` |
| **Stakeholder Agent** | [`agents/stakeholder_agent.py`](agents/stakeholder_agent.py) | — (configurable: when called from orchestrator it's seeded with `report_results`, `roi_results`, `action_results`) | — | `stakeholder_results` |

### 3.1 The data-input resolution rule

Every input read goes through `core.data_access.get_dataset(schema_name, fallback_loader=...)`. The function tries channels in this order ([`core/data_access.py:31-47`](core/data_access.py#L31-L47)):

1. `dataset_<schema>` — what `data_collector` publishes after column mapping.
2. `validated_<schema>` — what `data_collector` publishes after validation.
3. `validated_real_<schema>` — same, but specifically for real-connector data.
4. `fallback_loader()` — typically `load_emissions()` etc., which `pd.read_csv` from `DATA_DIR`.
5. Empty `DataFrame()` if all the above produced nothing.

**Implication for standalone deployment:** if you skip `data_collector`, the agent ends up at step 4. So either drop the right CSVs into `data/` **or** publish to the channels yourself before calling `agent.run()`:

```python
import pandas as pd
from core.state_manager import state_manager
from agents.carbon_accountant import CarbonAccountantAgent

# Inject client data directly
state_manager.publish("dataset_emissions", pd.read_csv("/var/data/client_emissions.csv"))
state_manager.publish("dataset_supply_chain", pd.read_csv("/var/data/client_supply.csv"))
state_manager.publish("dataset_energy", pd.read_csv("/var/data/client_energy.csv"))

agent = CarbonAccountantAgent()
results = agent.run()
```

---

## 4. Topology A — Monolith (the bundled app)

The current Streamlit deployment. Everything in the repo, `streamlit run Home.py`. Documented end-to-end in [RUNBOOK.md → Deployment](RUNBOOK.md#deployment). Nothing to add here other than a reminder that all nine agents share one Python process and one in-memory `state_manager`.

---

## 5. Topology B — Single-agent batch / lambda

Goal: deploy one agent (say, Carbon Accountant) as a daily batch job. No Streamlit, no orchestrator, no other agents.

### 5.1 Files to ship

```
core/                   (only the baseline files in §2.1)
utils/                  (data_processing.py, agent_telemetry.py)
agents/__init__.py
agents/carbon_accountant.py
data/company_profile.json
config.py
```

That's the entire deployment surface. ~50 KB excluding pandas / numpy.

### 5.2 Entry point

`runner.py` (write this — it is not in the repo):

```python
import os
import json
import pandas as pd

# Optional: point company_profile.json at a per-tenant location
os.environ.setdefault("ESG_DATA_DIR", "/etc/esg-pilot/<tenant>/data")

from core.state_manager import state_manager
from agents.carbon_accountant import CarbonAccountantAgent

# 1. Inject client data (skip if you ship sample_*.csv in data/)
state_manager.publish("dataset_emissions", pd.read_parquet("/var/data/emissions.parquet"))
state_manager.publish("dataset_supply_chain", pd.read_parquet("/var/data/supply.parquet"))
state_manager.publish("dataset_energy", pd.read_parquet("/var/data/energy.parquet"))

# 2. Run
agent = CarbonAccountantAgent()
results = agent.run()

# 3. Hand results to whatever consumes them downstream
with open("/var/output/carbon_results.json", "w") as fh:
    json.dump(results, fh, default=str)
```

The agent emits a results dict and also publishes `carbon_results` to `state_manager`. In Topology B nothing else reads that channel — the dict return value is the contract.

### 5.3 Container recipe (Docker)

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy only the deployment surface — keeps images small and surface auditable
COPY config.py ./config.py
COPY core/__init__.py core/base_agent.py core/state_manager.py core/data_access.py \
     core/company_config.py core/hf_client.py ./core/
COPY utils/__init__.py utils/data_processing.py utils/agent_telemetry.py ./utils/
COPY agents/__init__.py agents/carbon_accountant.py ./agents/
COPY data/company_profile.json ./data/
COPY runner.py ./

RUN pip install --no-cache-dir pandas numpy requests

# Optional: HF token for narrative polish
ENV HF_API_TOKEN=""

CMD ["python", "runner.py"]
```

### 5.4 What you don't need

* `huggingface_hub`, cloud SDKs (only `data_collector` uses real connectors)
* `streamlit`, `gradio`, `plotly`, `pyarrow`
* `anthropic` (orchestrator only)
* `core/orchestrator.py`, `core/agent_loop.py`
* Any `utils/` not listed in §2.1
* The `pages/` directory — it's all UI, never imported by agents

---

## 6. Topology C — Multi-agent batch, no Streamlit

Goal: run multiple agents in dependency order from a CLI / cron / Airflow / Lambda, write results to disk or a downstream system. This is the same as Topology A minus the Streamlit front-end.

### 6.1 Two ways to wire it

**Option 1 — Use the bundled orchestrator.** Easiest. Set `ANTHROPIC_API_KEY` and call:

```python
from core.orchestrator import Orchestrator
orchestrator = Orchestrator()
results = orchestrator.run_full_pipeline()  # all 9 agents, dependency-ordered
```

The orchestrator internally drives a Claude tool-use loop that decides which agents to call in which order, then `_ensure_complete` runs anything Claude skipped. The cost is one Claude call (~6–12 tool turns) per pipeline run.

**Option 2 — Hand-rolled dependency walker.** No Claude required, fully deterministic. Each agent is just a Python class:

```python
from agents.data_collector       import DataCollectorAgent
from agents.regulatory_tracker   import RegulatoryTrackerAgent
from agents.carbon_accountant    import CarbonAccountantAgent
from agents.risk_predictor       import RiskPredictorAgent
from agents.audit_agent          import AuditAgent
from agents.roi_agent            import ROIAgent
from agents.report_generator     import ReportGeneratorAgent
from agents.action_agent         import ActionAgent
from agents.stakeholder_agent    import StakeholderAgent

# Order matches PIPELINE_ORDER in core/orchestrator.py
DataCollectorAgent().run()
RegulatoryTrackerAgent().run()
CarbonAccountantAgent().run()
RiskPredictorAgent().run()
AuditAgent().run()
ROIAgent().run()
ReportGeneratorAgent().run()
ActionAgent().run()
StakeholderAgent().run()
```

Because every agent publishes its results to `state_manager` and downstream agents subscribe lazily inside `agent.run()`, the dependency graph "just works" as long as you go in PIPELINE_ORDER. No `ANTHROPIC_API_KEY` required.

### 6.2 Cherry-picking a subset

Pick the longest dependency chain you actually want:

```python
# "Just compute carbon + ROI + risk" — skip audit, regulatory, reports, etc.
DataCollectorAgent().run()              # publishes dataset_*
CarbonAccountantAgent().run()           # publishes carbon_results
RiskPredictorAgent().run()              # publishes risk_results (needs regulatory_results — see below)
ROIAgent().run()                        # publishes roi_results
```

Heads-up: `risk_predictor` reads `regulatory_results` opportunistically — without it, transition risk falls back to a sector-default ([`agents/risk_predictor.py:130-138`](agents/risk_predictor.py#L130-L138)). If you don't run `regulatory_tracker`, you accept that approximation.

### 6.3 Container recipe (Docker)

Same as Topology B (§5.3) but copy more agent files and (optionally) the orchestrator + agent loop. Cost is ~150 KB more on disk.

---

## 7. Topology D — Distributed microservices

Goal: each agent runs in its own process / container / pod. Horizontal scale, separate ownership per agent.

### 7.1 The state-manager problem

The bundled `core/state_manager.py` is an in-process Python dict. Two processes don't share state through it. So Topology D requires writing **one adapter** that exposes the same five-method surface (`publish`, `subscribe`, `get_all_channels`, `clear`, audit-trail readers) on top of a network bus.

Recommended bus options, in order of integration effort:

| Bus | Why pick it | Notes |
| --- | --- | --- |
| **Redis Streams** | Easiest; durable; cheap to operate | One stream per channel; consumers read from `$` for live, `0` for replay. Works well for the 7–10 channels the pipeline uses. |
| **NATS JetStream** | Higher throughput, simpler than Kafka | Good fit if the client already runs NATS. |
| **Apache Kafka** | Big-data scale, audit-grade durability | Overkill for ESG pipelines that run once per day. Pick it only if the client mandates it. |
| **PostgreSQL `LISTEN/NOTIFY`** | Zero new infrastructure if Postgres is already there | Loses audit history; payload size limits make it brittle for big DataFrames. Acceptable for orchestration signals only. |

### 7.2 Adapter shape

Replace `state_manager` with a thin shim. Example for Redis:

```python
# core/state_manager.py — distributed variant
import json
import pickle
import redis
from datetime import datetime

_redis = redis.Redis.from_url(os.environ["ESG_REDIS_URL"], decode_responses=False)
_KEY_PREFIX = os.environ.get("ESG_REDIS_PREFIX", "esg:channel:")

class StateManager:
    def publish(self, channel: str, data, agent_name: str = "system") -> None:
        payload = {"data": data, "published_by": agent_name,
                   "timestamp": datetime.now().isoformat()}
        _redis.set(_KEY_PREFIX + channel, pickle.dumps(payload))

    def subscribe(self, channel: str):
        raw = _redis.get(_KEY_PREFIX + channel)
        return pickle.loads(raw)["data"] if raw else None

    # get_all_channels, clear, etc. — same shape as the in-process version
```

Pickling DataFrames is fine for trusted internal traffic. For untrusted boundaries, swap pickle for parquet bytes + a small wrapper.

### 7.3 Per-agent service shape

Each agent runs as its own service that:

1. Watches an inbound queue (or runs on a schedule).
2. Reads its dependencies' channels via the network state manager.
3. Calls `agent.run()`.
4. Writes its results back to the network state manager and (optionally) emits a "done" event.

Example with FastAPI (one service per agent):

```python
# carbon-accountant-service.py
from fastapi import FastAPI
from agents.carbon_accountant import CarbonAccountantAgent

app = FastAPI()

@app.post("/run")
def run():
    return CarbonAccountantAgent().run()
```

A small driver (or Argo Workflow / Step Function / Airflow DAG) calls these services in dependency order.

### 7.4 Pitfalls

* **Channel discovery.** When `data_collector` publishes 7 schema channels, downstream agents read them by name. Ensure the network bus preserves channel naming exactly — no auto-prefixing surprises.
* **Per-tenant isolation.** The bundled state manager partitions channels by signed-in username (`core/state_manager.py:42-65`). In Topology D you replace that with a tenant prefix on Redis keys / Kafka topic.
* **Telemetry persistence.** `utils/agent_telemetry.py` writes to `data/agent_telemetry.json` by default. In a distributed deployment, every replica writing to the same file is a race. Either point each agent at its own file (via `ESG_TELEMETRY_PATH`, currently inferred from `DATA_DIR`) or replace the JSON store with a database adapter.
* **Latency.** A pipeline run that finishes in 2–4 s monolithic typically takes 8–15 s distributed (network round-trips dominate for the smaller agents). Acceptable for daily batches; not for real-time.

---

## 8. Configuration

### 8.1 `data/company_profile.json`

Read on first access of `company_cfg`. The fields agents actually consume:

```json
{
  "company_name": "Acme Industrials Pvt. Ltd.",
  "sector": "Manufacturing",
  "headquarters": "Mumbai, India",
  "current_fy": 2026,
  "previous_fy": 2025,
  "frameworks_adopted": ["BRSR", "GRI"],
  "frameworks_planned": ["CSRD"],
  "revenue": {
    "current_usd_millions": 480.0,
    "previous_usd_millions": 415.0,
    "current_local": 39800.0,
    "previous_local": 34400.0
  },
  "thresholds": {
    "completeness_warning": 70,
    "completeness_pass": 85,
    "audit_completeness_pass": 80,
    "audit_grade_a": 85,
    "audit_grade_b": 70,
    "audit_grade_c": 55,
    "risk_low": 30,
    "risk_medium": 60,
    "rating_aaa": 85,
    "rating_aa": 75,
    "rating_a": 65,
    "transition_risk_trigger": 60,
    "evidence_score_trigger": 60,
    "renewable_low_trigger": 30
  },
  "risk_weights": {
    "physical": 0.30,
    "transition": 0.40,
    "emission": 0.30,
    "compliance_baseline": 80
  },
  "sector_risk": {
    "physical_risk": 35,
    "transition_risk_base": 55
  },
  "industry_benchmarks": { "...": "...optional, peer-comparison only..." }
}
```

Missing fields fall back to defaults baked into [`core/company_config.py`](core/company_config.py). Set `ESG_COMPANY_CFG_WARN=1` in the environment to log every fallthrough — useful while migrating a real client config.

### 8.2 Environment variables

| Var | Required for | Default | Notes |
| --- | --- | --- | --- |
| `HF_API_TOKEN` | Narrative polish via HuggingFace Inference API | empty | When unset, all agents emit deterministic rule-based narratives. Production deployments often skip it — saves the network call and the API quota. |
| `ANTHROPIC_API_KEY` | Orchestrator's Claude tool-use loop | empty | Required for Topology A / C **only if** you use the orchestrator's planning. Topology B and Topology C with hand-rolled walker don't need it. |
| `ANTHROPIC_MODEL` | Orchestrator | `claude-opus-4-7` | Override to a smaller / cheaper model for high-volume runs. |
| `ANTHROPIC_EFFORT` | Orchestrator | `high` | `low` / `medium` / `high` / `xhigh` / `max`. Lower values cut cost at the price of less aggressive planning. |
| `ANTHROPIC_MAX_TOKENS` | Orchestrator | `16000` | — |
| `ESG_DEFAULT_ORG` | (Was used by removed notification flow; not currently consumed by any agent.) | — | Safe to leave unset. |
| `STREAMLIT_PORT` / `GRADIO_PORT` | UI deployments only | 8501 / 7860 | Topology A only. |

### 8.3 Per-tenant configuration

If you're deploying to a multi-tenant client environment, the cleanest pattern is one `data/` directory per tenant and one process per tenant, set via environment:

```bash
# Per-tenant launch
ESG_DATA_DIR=/etc/esg-pilot/tenants/acme/data python runner.py
```

The bundled `config.py:DATA_DIR` doesn't yet honour `ESG_DATA_DIR` — it's a small patch (one line in `config.py`). Apply that patch in the deployment, or symlink `data/` to the per-tenant location at container start.

---

## 9. AI surface and fallback behaviour

### 9.1 HuggingFace Inference API

[`core/hf_client.py`](core/hf_client.py) wraps four model categories:

| Category | Model | Used by |
| --- | --- | --- |
| `text_generation` | `mistralai/Mistral-7B-Instruct-v0.3` | Carbon, Risk, Audit, Regulatory, Action, Stakeholder narratives |
| `summarization` | `facebook/bart-large-cnn` | Stakeholder agent (executive briefs) |
| `zero_shot_classification` | `facebook/bart-large-mnli` | Action agent (categorising recommendations) |
| `sentiment_analysis` | `distilbert/distilbert-base-uncased-finetuned-sst-2-english` | Stakeholder agent (tone analysis) |

Every model call is wrapped: HTTP 5xx, timeouts, missing token, and missing `requests` package all route to a per-agent rule-based fallback ([`core/hf_client.py:151-343`](core/hf_client.py#L151-L343)). The fallbacks are pure-Python templates that pull numeric facts straight from the prompt and emit a coherent paragraph. **Output quality is lower; pipeline correctness is identical.**

For client deployments, decide:

* **Air-gapped / on-prem:** leave `HF_API_TOKEN` unset. Accept rule-based narratives.
* **Public cloud, cost-conscious:** leave `HF_API_TOKEN` unset. Same.
* **Public cloud, narrative quality matters:** set `HF_API_TOKEN`. Budget ~$0 (HF Inference is free-tier friendly for these small models, but rate-limited).

### 9.2 Anthropic Claude (orchestrator only)

Used by [`core/agent_loop.py`](core/agent_loop.py) to plan which agents to run and in what order, given a natural-language goal. **Agents themselves never call Claude.** If you skip the orchestrator (Topology B, or hand-rolled in C), you don't need an Anthropic key.

For deployments that keep the orchestrator: budget ~$0.10–$0.50 per pipeline run with `claude-opus-4-7` at `effort=high`, less with smaller models or lower effort.

---

## 10. Quick-reference deployment recipes

### 10.1 "Just compute carbon" (Topology B)

* **Files:** baseline (§2.1) + `agents/carbon_accountant.py` + `data/company_profile.json` + client emissions / supply / energy CSVs (or live channel publishes).
* **Python deps:** `pandas`, `numpy`.
* **Env:** none (rule-based narrative is fine).
* **Entry:** `CarbonAccountantAgent().run()`.

### 10.2 "Investor-readiness pack: carbon + ROI + reports" (Topology C)

* **Files:** baseline + `agents/{data_collector,carbon_accountant,risk_predictor,roi_agent,report_generator}.py` + `core/kpi_engine.py` + `data/company_profile.json` + client data.
* **Python deps:** `pandas`, `numpy` (+ cloud SDKs if `data_collector` uses real connectors).
* **Env:** optional `HF_API_TOKEN` for narrative polish.
* **Entry:** hand-rolled walker in `runner.py`, run nightly.

### 10.3 "Compliance audit only" (Topology B+)

* **Files:** baseline + `agents/{data_collector,regulatory_tracker,audit_agent}.py` + `data/regulatory_frameworks.json` + `data/company_profile.json` + client metrics.
* **Python deps:** `pandas`, `numpy`.
* **Env:** none.
* **Entry:** call the three agents in order. `audit_agent` produces the readiness grade and gap list.

### 10.4 "Full pipeline behind an internal API" (Topology D)

* **Files:** all 9 agents + baseline + orchestrator + a Redis state-manager adapter (you write this).
* **Python deps:** `pandas`, `numpy`, `redis`, `fastapi`, `uvicorn`, plus cloud SDKs as needed.
* **Env:** `ESG_REDIS_URL`, `HF_API_TOKEN` (optional), `ANTHROPIC_API_KEY` (optional, only for orchestrator).
* **Entry:** one FastAPI service per agent + a coordinator (Argo / Step Functions / Airflow).

---

## 11. What does NOT travel

The current bundle includes a lot of UI / persistence / dev infrastructure that is **never** needed for a server-side agent deployment:

| Path | Why it stays behind |
| --- | --- |
| [`Home.py`](Home.py), [`pages/`](pages/), [`gradio_app.py`](gradio_app.py) | UI — agents never import. |
| [`utils/auth.py`](utils/auth.py), [`utils/user_store.py`](utils/user_store.py), [`utils/session.py`](utils/session.py), [`utils/profile_store.py`](utils/profile_store.py), [`utils/source_store.py`](utils/source_store.py), [`utils/run_store.py`](utils/run_store.py) | Streamlit-specific persistence layer. The agent layer doesn't import these. |
| [`utils/charts.py`](utils/charts.py), [`utils/ui.py`](utils/ui.py), [`utils/streamlit_compat.py`](utils/streamlit_compat.py), [`utils/chat_drawer.py`](utils/chat_drawer.py) | Plotly / Streamlit rendering. |
| [`utils/whatif.py`](utils/whatif.py) | What-if simulator UI. Pure-functional helper; ship only if you expose the simulator. |
| [`tests/`](tests/) | Dev-time only. Don't ship tests in a slim deployment image. |
| [`docs/`](docs/), [`README.md`](README.md), [`RUNBOOK.md`](RUNBOOK.md), [`CALCULATIONS.md`](CALCULATIONS.md) | Source-side documentation. Ship the parts the client needs as separate handover docs. |
| [`data/auth_users.json`](data/auth_users.json), [`data/sources/`](data/sources/) | Per-developer auth state — must not travel to a client deployment under any circumstance. Add to `.gitignore` for the deployment image. |

---

## 12. Migration checklist (per client)

Before flipping the switch on a client deployment:

1. **Replace `data/company_profile.json`** with the client's. Run the agents once locally with the client's profile and confirm the output makes sense (revenues plausible, sector matches their reporting frameworks).
2. **Decide the data input mode** for each agent: published channels (in-process), CSVs at `DATA_DIR`, or replace `get_dataset` with a custom client-data fetcher. Document the choice.
3. **Decide the AI mode**: HF on / off, Anthropic on / off. Communicate the cost / quality tradeoff in writing.
4. **Decide the topology** (A / B / C / D). Document the chosen `runner.py` shape.
5. **Pin Python package versions** with `pip freeze` from the source environment. Ship `requirements.txt` with the deployment.
6. **Strip `data/auth_users.json`** and any developer-specific files from the deployment image.
7. **Verify telemetry persistence path** is writeable and per-tenant if you have multiple tenants. Default is `data/agent_telemetry.json`.
8. **Smoke test**: run the chosen entry point in the client's staging environment with a known input. Confirm result fingerprints match what you saw in source.

If any of those steps surface a gap, treat it as a blocker — the agent code is small and predictable, but deployments fail on configuration drift more often than on bugs.

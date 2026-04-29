# ESG Pilot — Agent Runbook

Complete technical reference for all 9 AI agents: architecture, calculations, scoring logic, data flows, and operational procedures.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Dependency Graph](#agent-dependency-graph)
3. [Core Infrastructure](#core-infrastructure)
4. [Data ETL & Freshness](#data-etl--freshness)
5. [Agent 1: Data Collector](#agent-1-data-collector)
6. [Agent 2: Regulatory Tracker](#agent-2-regulatory-tracker)
7. [Agent 3: Carbon Accountant](#agent-3-carbon-accountant)
8. [Agent 4: Report Generator](#agent-4-report-generator)
9. [Agent 5: Risk Predictor](#agent-5-risk-predictor)
10. [Agent 6: ESG ROI Agent](#agent-6-esg-roi-agent)
11. [Agent 7: Audit Agent](#agent-7-audit-agent)
12. [Agent 8: Action Agent](#agent-8-action-agent)
13. [Agent 9: Stakeholder Agent](#agent-9-stakeholder-agent)
14. [Data Connectors](#data-connectors) (incl. Delta Lake, folder/prefix mode)
15. [Schema Mapping & Validation](#schema-mapping--validation)
16. [AI Models & Fallbacks](#ai-models--fallbacks)
17. [Data Freshness & Pipeline Refresh](#data-freshness--pipeline-refresh)
18. [Identity, Persistence & Per-User Isolation](#identity-persistence--per-user-isolation)
19. [What-If Simulator (ROI page)](#what-if-simulator-roi-page)
20. [Deployment](#deployment)
21. [CI & Repository Hygiene](#ci--repository-hygiene)
22. [Troubleshooting](#troubleshooting)

> **Need a formula?** All numeric calculations, weights, and thresholds live in **[CALCULATIONS.md](CALCULATIONS.md)** — pulled directly from agent code with `file:line` citations.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ESG Pilot Platform                      │
├─────────────────────────────────────────────────────────────┤
│  UI Layer:  Streamlit (10 pages)  |  Gradio (tabbed)        │
├─────────────────────────────────────────────────────────────┤
│  Orchestrator: Manages dependency graph & pipeline execution │
├─────────────────────────────────────────────────────────────┤
│  9 Agents: Each inherits BaseAgent, uses HFClient           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Data     │→│ Regulatory│→│ Carbon   │→│ Risk     │       │
│  │ Collector│ │ Tracker   │ │ Accountant│ │ Predictor│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Audit    │→│ ROI      │→│ Report   │→│ Action   │       │
│  │ Agent    │ │ Agent    │ │ Generator│ │ Agent    │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                           ┌──────────┐                     │
│                           │Stakeholder│                    │
│                           │ Agent     │                    │
│                           └──────────┘                     │
├─────────────────────────────────────────────────────────────┤
│  State Manager (pub/sub)  | KPI Engine | HF API | Connectors│
├─────────────────────────────────────────────────────────────┤
│  Data: CSV/JSON samples + financials | Real Sources | Cloud  │
└─────────────────────────────────────────────────────────────┘
```

**Tech Stack:**
- Python 3.11+
- Streamlit (dashboard) / Gradio (single-page app)
- HuggingFace Inference API (Mistral-7B, BART, DistilBERT)
- Pandas, Plotly, NumPy, PyArrow
- Optional: boto3 (AWS), google-cloud-bigquery (GCP), azure-storage-blob (Azure), deltalake (Delta Lake)

---

## Agent Dependency Graph

The orchestrator executes agents in this exact order. Each agent can only access data published by its dependencies via `state_manager`.

```
Pipeline Order:
  1. data_collector       → depends on: (none)
  2. regulatory_tracker   → depends on: data_collector
  3. carbon_accountant    → depends on: data_collector
  4. risk_predictor       → depends on: data_collector, regulatory_tracker
  5. audit_agent          → depends on: data_collector, regulatory_tracker, carbon_accountant
  6. roi_agent            → depends on: data_collector, carbon_accountant, risk_predictor
  7. report_generator     → depends on: audit_agent, carbon_accountant, risk_predictor, roi_agent
  8. action_agent         → depends on: risk_predictor, audit_agent, report_generator, roi_agent
  9. stakeholder_agent    → depends on: action_agent, report_generator
```

**State Manager Channels** (pub/sub keys):

| Channel | Published By | Subscribed By |
|---------|-------------|---------------|
| `dataset_{schema}` | Data Collector | All downstream analytical agents |
| `validated_{dataset}` | Data Collector | Backward-compatible consumers |
| `data_collection_results` | Data Collector | Audit Agent, Report Generator |
| `regulatory_results` | Regulatory Tracker | Risk Predictor, Audit Agent, Report Generator, Action Agent |
| `carbon_results` | Carbon Accountant | Audit Agent, Report Generator, Stakeholder Agent, Action Agent |
| `risk_results` | Risk Predictor | Action Agent, Stakeholder Agent |
| `roi_results` | ESG ROI Agent | Report Generator, Action Agent, Stakeholder Agent |
| `audit_results` | Audit Agent | Report Generator, Action Agent |
| `report_results` | Report Generator | Stakeholder Agent |
| `action_results` | Action Agent | Stakeholder Agent |
| `stakeholder_results` | Stakeholder Agent | — |

---

## Core Infrastructure

### BaseAgent (`core/base_agent.py`)

All agents inherit from `BaseAgent`:

```python
class BaseAgent(ABC):
    def __init__(self, name, description):
        self.name = name
        self.hf = hf_client          # HuggingFace API wrapper (singleton)
        self.status = "idle"          # idle → running → completed | error
        self.audit_trail = []         # timestamped log entries

    def run(self, **kwargs):          # Wraps execute() with error handling
    def execute(self, **kwargs):      # Abstract — each agent implements this
    def log(self, message):           # Appends to audit_trail
```

### StateManager (`core/state_manager.py`)

Singleton pub/sub bus for inter-agent data sharing:

```python
state_manager.publish(channel, data, agent_name)  # Store data
state_manager.subscribe(channel)                    # Retrieve data (returns None if not published)
state_manager.get_all_channels()                    # List all published channels
```

### Canonical Data Access (`core/data_access.py`)

Downstream agents now read canonical datasets from shared state first:

```python
from core.data_access import get_dataset

emissions_df = get_dataset("emissions", fallback_loader=load_emissions)
financials_df = get_dataset("financials", fallback_loader=load_financials)
```

This keeps the full pipeline aligned to user-collected data while still allowing single-agent execution with sample fallbacks.

### KPI Engine (`core/kpi_engine.py`)

The KPI Engine is the ESG-to-financial backbone used by the ROI layer:

```python
kpi_results = kpi_engine.compute_all(
    financials_df,
    esg_metrics_df,
    emissions_df,
    energy_df,
    supply_chain_df,
    diversity_df,
)
```

Outputs:
- ESG-financial correlations
- Five value-creation channel scores
- CAGR and volatility
- Composite ESG-financial score

### Orchestrator (`core/orchestrator.py`)

```python
orchestrator = Orchestrator()
orchestrator.run_full_pipeline(progress_callback=None)  # All 9 agents in dependency order
orchestrator.run_single_agent("carbon_accountant")      # Single agent
orchestrator.get_agent("data_collector")                # Access agent instance
```

**Passing real data sources into the pipeline**

To wire user-uploaded or registered data sources into the pipeline, pass a `ConnectionManager` instance via `data_collector_kwargs`. This ensures the Data Collector's Phase 0 can fetch real sources instead of falling back to samples:

```python
orchestrator.run_full_pipeline(
    progress_callback=None,
    data_collector_kwargs={"connection_manager": conn_mgr}  # pass real sources
)
```

`conn_mgr` is the `ConnectionManager` instance from `st.session_state.conn_manager` (populated by Test & Preview). If `data_collector_kwargs` is omitted or `connection_manager` is `None`, Phase 0 is skipped and the pipeline runs on sample data only.

If a dependency fails, the orchestrator marks the downstream agent as skipped instead of continuing with inconsistent inputs.

### HFClient (`core/hf_client.py`)

Wraps HuggingFace Inference API with automatic fallback:

| Method | Model | Fallback |
|--------|-------|----------|
| `generate_text(prompt)` | Mistral-7B-Instruct-v0.3 | Rule-based keyword templates |
| `summarize(text)` | BART-large-CNN | First 3 sentences |
| `classify(text, labels)` | BART-large-MNLI (zero-shot) | Deterministic hash-based scoring |
| `analyze_sentiment(text)` | DistilBERT-SST-2 | Keyword positive/negative counting |

---

## Data ETL & Freshness

ESG Pilot does **not** use Airflow, dbt, Prefect, Dagster, Luigi, or any external orchestration framework. The ETL is a bespoke, in-process, per-user pipeline — all four stages run inside the Streamlit worker for the session that triggered them.

### Why in-process, not an external scheduler?

- **Per-user isolation.** Every source is owned by a specific signed-in account; there is no "global" dataset to schedule against. An external orchestrator would need per-user DAGs for no operational gain.
- **Deterministic freshness.** Pipelines fire on explicit Runs, not cron. A user always knows the dashboard reflects the last Run they initiated — no "is this stale" question.
- **Zero ops footprint.** Runs on any Streamlit-compatible host (HuggingFace Spaces, Streamlit Cloud, a laptop). No broker, no worker pool, no DB.

### Layers

```
┌─────────────────────────────────────────────────────────────┐
│  pages/<page>.py  →  refresh_real_data()  →  agent.run()    │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
  ┌──────────────────────────────────────────────────────┐
  │ L4. Publication  (core/state_manager.py)             │
  │      dataset_emissions, dataset_esg_metrics, …       │
  └──────────────────────────────────────────────────────┘
                           ▲
                           │   publish mapped DataFrame
  ┌──────────────────────────────────────────────────────┐
  │ L3. Orchestration  (utils/connection_manager.py)     │
  │      fetch_all_by_schema(use_cache=True)             │
  │      — per-source signature cache                    │
  │      — schema-level concatenation                    │
  └──────────────────────────────────────────────────────┘
                           ▲
                           │   fetch + map
  ┌──────────────────────────────────────────────────────┐
  │ L2. Schema mapping  (utils/schema_mapper.py)         │
  │      auto_detect_schema → suggest_column_mapping     │
  │      → apply_column_mapping                          │
  └──────────────────────────────────────────────────────┘
                           ▲
                           │   raw DataFrame
  ┌──────────────────────────────────────────────────────┐
  │ L1. Connectors  (utils/real_connectors.py,           │
  │                 utils/connectors.py)                 │
  │      CSV, Google Sheets, S3, GCS, Azure Blob,        │
  │      Snowflake, BigQuery, REST, SQL, Delta           │
  └──────────────────────────────────────────────────────┘
```

**Layer 1 – Connectors.** Each adapter implements `fetch(**config) → DataFrame`. SDK imports are lazy, so a missing `boto3` never blocks users who aren't using S3. Upload connectors stream bytes from `st.file_uploader`; cloud connectors accept a folder prefix and auto-discover CSV/JSON/Excel/Parquet.

**Layer 2 – Schema mapping.** Raw columns are matched against seven canonical schemas (`emissions`, `esg_metrics`, `supply_chain`, `energy`, `waste`, `diversity`, `financials`) plus five peer-benchmark schemas. `apply_column_mapping` renames, coerces types, and drops un-mappable columns so every agent downstream sees canonical field names.

**Layer 3 – Orchestration (`ConnectionManager`).** Per-user registry of configured sources, persisted via `utils.source_store`. Drives the ETL with two important properties:

- **Per-source SHA-256 signature cache** (`_signature(connector_type, target_schema, column_mapping, config)`). Unchanged sources skip the remote fetch on subsequent Runs. A config edit flips the signature and forces re-fetch.
- **Schema-level concatenation** (`fetch_all_by_schema`). Multiple sources targeting the same schema (e.g. two S3 folders of emissions data) are concatenated so agents see a single unified DataFrame.

**Layer 4 – Publication.** Mapped DataFrames are published to the in-memory `state_manager` pub/sub bus under `dataset_<schema>` channels. Every agent reads via `core.data_access.get_dataset(schema, fallback_loader)` which transparently falls back to the bundled sample files when the channel is empty — useful for first-time sign-in and for running an agent in isolation during development.

### Run trigger & freshness

Every page button that reads data calls `utils.pipeline_refresh.refresh_real_data()` before invoking the agent. The refresher:

1. Loads the signed-in user's `ConnectionManager` via `utils.session.get_session_connection_manager()`.
2. Calls `fetch_all_by_schema(use_cache=True)` — so unchanged sources are free, changed sources re-fetch.
3. Publishes results to shared state and records a `last_fetch` timestamp per source.
4. Exposes `data_freshness_caption()` which each page renders under its title so users can see "Fetched 42 seconds ago from 3 sources."

`core.orchestrator.Orchestrator` sequences agent execution respecting the dependency graph (Data → Regulatory/Carbon/Risk → Audit → Report/Action → Stakeholder) so published datasets are available before any dependent agent executes.

### Concurrency model

All persistence writes (`user_store.save`, `source_store.save`, `profile_store.save`) go through the same pattern:

1. In-process `threading.RLock` around every read-modify-write.
2. Retry loop (3 attempts with exponential backoff 0.25 → 0.5 → 1 s) on HF Dataset 409/412/503 responses so a racing commit from another process doesn't silently drop a write.
3. On terminal failure, fall back to ephemeral local JSON and surface the full exception chain via `store.diagnostic()` in the sidebar.
4. `user_store.create_user` additionally re-reads the user list inside each retry attempt so two concurrent signups can't both think the username is free.

Per-user files (`sources/{username}.json`, `profiles/{username}.json`) only collide when the same user has multiple tabs racing — the last write wins by design, and both the source store and profile store invalidate their process-wide cache on save so the "losing" tab sees the winning state on its next rerun.

### Size guardrails

`utils.source_store.MAX_PAYLOAD_BYTES` (default 4 MB, override via `ESG_SOURCE_MAX_BYTES`) caps a single user's serialised source registry. Inline-upload bytes are base64-encoded inside the JSON, so we reject saves that would balloon the profile file and ask the user to switch to an external connector (S3, Snowflake, Google Sheets) instead. This keeps session-state and HF commits well under HF's 100 MB-per-file limit and avoids the "why is sign-in taking 30 seconds" failure mode caused by multi-megabyte profile loads.

### Error surfacing

Every store exposes `diagnostic()` returning `{backend, label, has_token, dataset, last_error, last_error_at}`. The sidebar auth widget reads these and shows a coloured indicator (green = HF persistent, amber = local ephemeral, red = no token / write failure) with an expandable error panel that walks the exception chain (`__cause__` → `__context__`) — this is how we caught the `ValueError` wrapping issue in `hf_hub_download` when first-time users appeared to fall back to local storage.

### Connector retry/timeout policy (`utils/connector_retry.py`)

Every `ConnectionManager.fetch_source(...)` call is wrapped in a shared retry helper so a transient network blip on Snowflake / S3 / BigQuery / GCS doesn't fail the whole pipeline run.

**Knobs:**
| Constant | Default | Meaning |
| --- | --- | --- |
| `MAX_ATTEMPTS` | `3` | Initial call + 2 retries |
| `INITIAL_BACKOFF_SECONDS` | `0.4` | First failed attempt sleeps ~0.4 s |
| `BACKOFF_MULTIPLIER` | `2.0` | Doubles per failed attempt up to `MAX_BACKOFF_SECONDS` |
| `MAX_BACKOFF_SECONDS` | `4.0` | Sleep ceiling |
| `JITTER_FRACTION` | `0.25` | ±25 % jitter on each computed backoff |
| `DEADLINE_SECONDS` | `30.0` | Wall-clock cap across all attempts — prevents a pathological retry loop from hanging the ESG Command Center Run button |

**Transient (retried):** `requests.Timeout`, `requests.ConnectionError`, `requests.ChunkedEncodingError`, `socket.timeout`, `ConnectionError`, `TimeoutError`, exceptions whose class name contains `timeout`/`throttl`/`unavailable`, HTTP 408 / 425 / 429 / 5xx.

**Fatal (fail fast, no retry):** `ImportError`, `ValueError`, `KeyError`, `NotImplementedError`, every other HTTP 4xx (including 401 / 403 — auth failures should surface immediately, not keep hammering).

Why this lives at the ConnectionManager boundary, not inside each connector: the underlying SDKs (`boto3`, `snowflake-connector-python`, `huggingface_hub`, `google-cloud-bigquery`, `requests`) all have different retry idioms. Wrapping the whole `fetch()` call gives us one knob, one log line, and one place to tune behaviour as we learn what fails in production. Pinned by `tests/test_connector_retry.py` (30 tests).

### Incremental run cache (`core/orchestrator.py`)

The orchestrator memoises each agent's result keyed on a fingerprint of its **inputs**, so a second click of *Run Full Pipeline* with no upstream changes short-circuits every agent that already ran.

**Behaviour at a glance:**
- After every successful agent run, `(dep_fingerprint, result)` is stored in `Orchestrator._incremental_cache[agent_key]`.
- Errored runs are **not** cached so a transient failure doesn't get pinned.
- On the next pipeline turn, `_execute_tool()` recomputes the dep fingerprint and serves from cache on a match. Cache-hit agents log under status `cached` in the execution log and are listed under *Reused N cached agent result(s)* on the post-run banner.
- Force-bypass: the **♻️ Force full re-run** button on the ESG Command Center calls `invalidate_incremental_cache()` before the next run.

**Source-mutation auto-invalidation:** `utils/session.py:_build_on_change()` invalidates the cache after every `add_source` / `remove_source` / `replace`. This is belt-and-suspenders insurance — the fingerprint chain *should* propagate the change naturally (data_collector's dep fingerprint is keyed on `connection_manager.sources_signature()`), but explicit invalidation guarantees a fresh end-to-end run on the next click regardless of fingerprint subtleties.

**Post-pipeline `_ensure_complete()`:** the LLM-driven planner is goal-driven and may skip agents the goal doesn't strictly require. With `enforce_complete=True` (the default for `run_full_pipeline`), the orchestrator walks `agent_order` after the tool-use loop and runs any agent that was skipped (errored agents are not auto-retried). Each fill-in run is fingerprinted into the incremental cache so the next click correctly short-circuits.

The full fingerprint formula is documented in `CALCULATIONS.md` → *Incremental Run Cache*. Pinned by `tests/test_orchestrator_cache.py` (13 tests).

---

## Agent 1: Data Collector

**Class:** `DataCollectorAgent` (`agents/data_collector.py`)
**Purpose:** Auto-discovers, ingests, and validates ESG data from multiple sources.

### Execution Phases

| Phase | Description |
|-------|-------------|
| 0 | Fetch from real data sources via ConnectionManager (if configured) |
| 1 | Load 7 local sample datasets (emissions, esg_metrics, supply_chain, energy, waste, diversity, financials) |
| 2 | Auto-discover from enterprise connectors (SAP ERP, Workday HR, IoT, EcoVadis, PostgreSQL, CDP/MSCI) |
| 3 | Process user-uploaded files — CSV, Excel (.xlsx/.xls), JSON — with auto-schema detection and canonical dataset routing |
| 4 | Detect missing data — proactive gap alerts |
| 5 | Compute overall quality |
| 6 | AI-powered quality issue classification |
| 7 | Assign verifiable confidence scores |

### Upload Data Flow

This subsection describes exactly what happens from the moment a user uploads a file through to that data driving pipeline calculations.

**Trigger: Test & Preview**

When the user clicks "Test & Preview" in Data Collector → Connect Data Sources → File Upload:

1. The uploaded bytes are read into a `pd.DataFrame` (CSV via `pd.read_csv`, Excel via `pd.read_excel`, JSON via `pd.read_json`).
2. `auto_detect_schema(df)` scans the column names against indicator columns for each of the 7 schemas and returns the best match (see [Schema Mapping & Validation](#schema-mapping--validation)).
3. The detected schema and the raw DataFrame are written into:
   - `st.session_state.preview_df` — the raw preview frame (RAM, session-scoped)
   - `st.session_state.preview_config` — the detected schema name and suggested column mapping (RAM, session-scoped)
4. The source is immediately auto-registered in `st.session_state.conn_manager._sources` under the key `real_{schema}` (e.g. `real_emissions`). This canonical key is what the pipeline looks for when preferring real data over sample data.
5. A confirmation message is displayed on screen. No additional "Save Data Source" click is needed.

**What "canonical routing" means**

The Data Collector resolves datasets at runtime via `_resolve_canonical_datasets()`. It checks for `real_{schema}` keys first. If a `real_emissions` source is registered, it takes priority over the bundled `sample_emissions.csv`. Sources stored under arbitrary filenames (e.g. `my_data.xlsx`) do not match a canonical slot and are therefore ignored by downstream agents — this was the root cause of Bug 3 (fixed).

**Pipeline run**

When the user clicks "Run Full Pipeline" in ESG Command Center:

1. `st.session_state.conn_manager` (the session `ConnectionManager` with registered sources) is read from session state.
2. It is passed to `Orchestrator.run_full_pipeline()` via the `data_collector_kwargs` parameter:
   ```python
   orchestrator.run_full_pipeline(
       progress_callback=cb,
       data_collector_kwargs={"connection_manager": conn_mgr}
   )
   ```
3. The orchestrator forwards the kwargs into `DataCollectorAgent.run(connection_manager=conn_mgr)`.
4. Phase 0 fetches the real sources via the `connection_manager`. Real data is published to `state_manager` under `dataset_{schema}` channels.
5. All downstream agents consume the published real data through `core/data_access.py` before falling back to sample data.

**Data storage summary**

| Stage | Storage location | Scope |
|-------|-----------------|-------|
| After Test & Preview | `st.session_state.preview_df`, `st.session_state.preview_config` | RAM, session |
| After auto-registration | `st.session_state.conn_manager._sources[real_{schema}]` | RAM, session (also persisted to per-user HF Dataset via `utils.source_store`) |
| After pipeline run | `state_manager` pub/sub channels | RAM, process-wide (per-user partitioned) |

The signed-in user's source registry is durable across Space rebuilds when `HF_TOKEN` is set — see [Per-user persistence](#per-user-persistence). Pipeline results in `state_manager` remain RAM-only and are recomputed on each Run.

---

### Per-source actions on the Registered Sources list

Each row in *Data Collector → Registered Data Sources* exposes three actions: **🔄 Refresh** (or **📤 Replace** for file-upload sources), **🗑️ Delete**, plus a *Last fetched: N min ago* caption underneath the source title.

| Action | Connector types | What it does |
|---|---|---|
| **🔄 Refresh** | All non-file connectors (Snowflake, BigQuery, S3, Google Sheets, REST, Azure Blob, Delta Lake, GCS, SQL) | Calls `conn_mgr.invalidate_cache(src_id)` then `conn_mgr.fetch_source(src_id, use_cache=False)`. Re-queries the remote system live, updates the source's `last_row_count` and `last_fetch` fields, and surfaces a green success toast (or red error with the connector message). |
| **📤 Replace** | `file_upload` only | Opens an inline `st.file_uploader`. On Apply, the new bytes overwrite `config["file_bytes"]`; `display_name` and `target_schema` are preserved; `column_mapping` is re-derived against the new columns via `suggest_column_mapping(new_df, schema)` so a renamed or reordered header is handled gracefully. |
| **🗑️ Delete** | All | Two-click arm/confirm. Calls `conn_mgr.remove_source(src_id)`, fires the persistence callback, and clears stale `dataset_*` channels via `_clear_stale_state_datasets()` so removed-source data can't leak through. |

The *Last fetched* caption reads from `meta["last_fetch"]` (an ISO-8601 timestamp set inside `ConnectionManager.fetch_source`) and renders as `"42s ago"` / `"12 min ago"` / `"3h ago"` / `"2d ago"`. Sources that have not been fetched yet display `"never fetched"`.

**Why this matters operationally.** Before this UI existed, the only way to verify that a Snowflake table change was visible was to run the full pipeline and check the gap report. Now any user can click 🔄 next to a source, see the new row count in under a second, and confirm before triggering the orchestrator.

---

### Data Quality Formula

```
completeness = (non_null_cells / total_cells) × 100

avg_confidence = mean(df["confidence"]) × 100   # if column exists, else 0

overall_completeness = mean(completeness across all datasets)
overall_confidence   = mean(avg_confidence across datasets where avg_confidence > 0)
```

### Confidence Scoring Formula

Each dataset gets a weighted trust score for audit readiness:

```
weighted_confidence = completeness × 0.4
                    + raw_confidence × 0.4
                    + source_bonus
                    + freshness × 0.2

Source bonuses:
  real_ sources (verified):     +25
  connector_ sources (enterprise): +20
  sample data:                  +10

freshness = 18 (assumed recent for sample data)

Capped at 100.

Trust Levels:
  >= 80 → "High"   (audit_ready = true if >= 75)
  >= 60 → "Medium"
  <  60 → "Low"
```

### Quality Issue Classification

If dataset completeness < 90%, uses HuggingFace zero-shot classification with labels:
- `"critical issue"`, `"moderate concern"`, `"minor issue"`

If avg_confidence < 75%, flagged as `"moderate concern"`.

### Missing Data Detection

Expected datasets and their regulatory mappings:

| Dataset | Required For |
|---------|-------------|
| emissions | BRSR, CSRD, GRI — Scope 1/2/3 |
| esg_metrics | All framework reporting |
| supply_chain | Scope 3 and CSRD S2 |
| energy | BRSR, GRI 302, SASB |
| waste | BRSR, GRI 306 |
| diversity | BRSR, CSRD S1, GRI 405 |
| financials | ROI, KPI Engine, cost-of-capital and ESG capex analysis |

Alerts generated:
- **Critical:** Dataset completely missing
- **Warning:** Completeness < 80%

### Published State

```python
state_manager.publish("data_collection_results", {
    "datasets_loaded": int,
    "total_records": int,
    "quality_scores": {dataset_name: {completeness, total_records, total_fields, null_count, avg_confidence}},
    "overall_completeness": float,
    "overall_confidence": float,
    "quality_issues": [{dataset, issue, severity, null_count}],
    "dataset_names": [str],
    "connector_statuses": {connector_key: {name, type, status, records, last_sync}},
    "missing_data_alerts": [{severity, dataset, message, action}],
    "confidence_scores": {dataset: {score, level, audit_ready}},
})

state_manager.publish("dataset_financials", financials_df, "Data Collector")
state_manager.publish("dataset_emissions", emissions_df, "Data Collector")
```

---

## Agent 2: Regulatory Tracker

**Class:** `RegulatoryTrackerAgent` (`agents/regulatory_tracker.py`)
**Purpose:** Monitors ESG frameworks and performs compliance gap analysis.

### Frameworks Tracked

| Framework | Full Name | Jurisdiction | Type |
|-----------|-----------|-------------|------|
| BRSR | Business Responsibility and Sustainability Reporting | India/SEBI | Mandatory |
| CSRD | Corporate Sustainability Reporting Directive | EU | Mandatory |
| GRI | Global Reporting Initiative | Global | Voluntary |
| SASB | Sustainability Accounting Standards Board | Global | Investor-focused |
| SOX | Sarbanes-Oxley (ESG-relevant internal controls) | US | Mandatory |
| SEC Climate Rule | SEC Climate-Related Disclosures | US | Mandatory |

### Live Framework Reload

`execute()` reloads `data/regulatory_frameworks.json` from disk on every call. There is **no in-memory cache short-circuit** — when a user approves an update through *Global Framework Updates* (which writes the new requirement to disk via `utils.framework_refresh.apply_update`), the very next click of **Run Compliance Analysis** sees the new requirement in its gap calculation. The Compliance Radar percentage shifts immediately; no page reload, no session restart.

The agent retains a `frameworks_cache` field — but its only purpose is to preserve in-memory `external_updates` metadata accumulated by the 24-hour background updater thread (`_fetch_external_regulatory_data`). Those entries are merged on top of the freshly-loaded disk data on every `execute()`, so live disk updates and synthetic background alerts coexist.

### Framework refresh & LLM-JSON tolerance

`utils/framework_refresh.fetch_framework_updates()` calls Claude with the `web_search_20250305` tool against authoritative regulator pages (SEBI, EFRAG, SEC, PCAOB, GRI, IFRS/SASB) and parses the response back into a JSON array. Real-world LLM output is not always RFC-strict — Claude routinely emits literal newlines or tabs inside string values, which `json.loads()` rejects in strict mode.

**Parsing fallback ladder** (`utils/framework_refresh.py`):

1. `json.loads(raw, strict=False)` — Python's built-in tolerance for control characters in string values (the bytes `\x00`–`\x1f`, including raw `\n`, `\t`, `\r`).
2. If that still fails: scrub remaining truly-disallowed control bytes (`\x00–\x08`, `\x0b`, `\x0c`, `\x0e–\x1f`) via regex and retry `json.loads(strict=False)`.
3. Only if both passes fail, the original `JSONDecodeError` is re-raised as a `RuntimeError` and surfaced in the UI as *"Refresh failed: …"*.

Operational impact: a single unescaped whitespace character in Claude's response no longer drops the entire batch of detected regulatory updates.

### Approval audit log + revert

Every approval / dismissal / revert action lands in an append-only `audit_log` array on the `regulatory_updates.json` overlay store. The Regulatory Tracker page renders the log under a **🔍 Audit log** expander and adds an **↩️ Revert** button on every Applied row.

**API surface (`utils/framework_refresh.py`):**

| Function | What it does |
| --- | --- |
| `apply_update(update_id, *, actor=None)` | Appends the proposed requirement to `regulatory_frameworks.json`, marks the update as `applied`, captures `applied_by` + `applied_requirement_id`, writes one `apply` entry to the audit log. Idempotent. |
| `revert_update(update_id, *, actor=None, reason="")` | Removes the requirement that `apply_update` appended (matched on `applied_requirement_id` with a fallback to `proposed_requirement.id`), flips status back to `pending`, drops the apply markers so a re-apply runs cleanly. Writes a `revert` entry. Idempotent: reverting an already-reverted update is a no-op that still records the operator's intent under `revert_skipped`. |
| `dismiss_update(update_id, reason="", *, actor=None)` | Marks the update `dismissed` with actor + reason, appends a `dismiss` entry. |
| `audit_log(store=None, *, framework=None, limit=None)` | Reads the log; optional framework filter, optional head truncation. Returns newest-first. |

**Audit-entry schema:** `{action, update_id, framework, title, requirement_id, actor, timestamp, … action-specific extras (reason, requirement_removed)}`. The schema is intentionally permissive so new action types don't break older entries.

The Regulatory Tracker page captures the signed-in user (`st.session_state["user"]["username"]`) as `actor` on every apply / revert / dismiss button so the log answers *"who approved this?"*. Pinned by `tests/test_framework_audit.py` (10 tests including a full apply → revert → re-apply round-trip and a framework filter).

### Compliance Calculation

For each framework:

```
For each requirement:
  1. Map requirement's data_fields → metric IDs via DATA_FIELD_MAPPING
  2. Check if mapped metric IDs exist in available_metrics (from sample ESG data)
  3. Classification:
     - All mapped metrics available → "covered" (count += 1)
     - Some available → "partial" (partial += 1, added to gaps list)
     - None available → "missing" (added to gaps list)

compliance_pct = (covered + partial × 0.5) / total_requirements × 100
overall_compliance = mean(compliance_pct across all frameworks)
```

**Key:** Partial compliance counts as 0.5 coverage.

### Data Field Mapping (52 mappings)

Maps raw data field names to ESG metric IDs. Examples:

| Data Field | Metric IDs | Description |
|-----------|-----------|-------------|
| `emissions_scope1` | E01, E02 | Scope 1 emissions |
| `renewable_energy_pct` | E03 | Renewable energy share |
| `gender_diversity` | S03, S04 | Workforce diversity |
| `board_governance` | G01, G02, G03 | Board oversight |
| `anti_corruption_training` | G04 | Ethics training |

### Gap Narrative Generation

Uses HuggingFace text generation with critical gaps as context. Generates 2-3 recommendations.

### Reporter Classification

The regulatory layer also derives a reporter profile from framework mix and compliance posture:

- Mandatory-led
- Voluntary-maturing
- Mixed / transitional

This profile is reused downstream in reporting and stakeholder messaging.

### Published State

```python
state_manager.publish("regulatory_results", {
    "framework_results": {
        "BRSR": {full_name, mandatory, total, covered, partial, missing, compliance_pct, gaps: [{requirement_id, requirement, status, priority, reason}]},
        "CSRD": {...}, "GRI": {...}, "SASB": {...}
    },
    "overall_compliance": float,
    "gap_narrative": str,
    "frameworks_analyzed": int,
})
```

---

## Agent 3: Carbon Accountant

**Class:** `CarbonAccountantAgent` (`agents/carbon_accountant.py`)
**Purpose:** Tracks Scope 1/2/3 emissions, identifies supply chain hotspots, analyzes energy.

### Key Calculations

**Scope Totals:**
```
scope_totals = emissions_df[year==Y].groupby("scope")["emissions_tco2e"].sum()
```

**Year-over-Year Change:**
```
yoy_change_pct = (total_2024 - total_2023) / total_2023 × 100
```

**Carbon Intensity:**
```
carbon_intensity = total_2024 / 462   # per $M revenue (FY2024)
carbon_intensity_prev = total_2023 / 420  # per $M revenue (FY2023)
```

**Energy Analysis:**
```
renewable_pct = renewable_mwh / total_mwh × 100
by_source = energy_df[year==2024].groupby("energy_source")["consumption_mwh"].sum()
```

### Supply Chain Hotspot Detection

```
hotspots = supply_chain_df[risk_rating == "High"]
           .sort_values("emission_contribution_tco2e", descending)
           .head(5)

Fields extracted per hotspot:
  supplier, country, sector, emissions, esg_score, risk_factors
```

### Emissions → Cost Linkage (H2: Profitability)

Directly maps emission changes to financial impact:

```
cost_saving_from_reduction = max(0, prev_emissions - curr_emissions) × 0.0015
                              # INR crores; proxy INR 1,500/tCO2e avoided
energy_cost_saving         = max(0, prev_energy_cost - curr_energy_cost) / 100
                              # lakhs → crores
scope2_additional_opportunity = (100 - renewable_pct) × 0.3
```

Published under `cost_linkage` for consumption by ROI / Action agents.

### Carbon Tax Risk Assessment

Estimates carbon tax exposure under current + future regimes:

```
taxable_emissions        = scope1 + scope2  (tCO2e)
current_domestic_exposure = taxable × INR 400 / 100,000   (INR crores)
cbam_equivalent_exposure  = taxable × INR 7,200 / 100,000 (EU CBAM proxy)
projected_3yr_exposure    = current × (1.10 ^ 3)          (10% annual escalation)

Risk level:
  > INR 5 Cr  → "High"
  > INR 2 Cr  → "Medium"
  otherwise   → "Low"
```

Published under `carbon_tax_risk`.

### Published State

```python
state_manager.publish("carbon_results", {
    "scope_totals_current": {"Scope 1": float, "Scope 2": float, "Scope 3": float},
    "scope_totals_previous": {...},
    "total_emissions_current": float,
    "total_emissions_previous": float,
    "yoy_change_pct": float,
    "quarterly_trends": [{period, scope, emissions_tco2e}],
    "category_breakdown": [{scope, category, emissions_tco2e}],
    "hotspots": [{supplier, country, sector, emissions, esg_score, risk_factors}],
    "carbon_intensity": float,
    "carbon_intensity_prev": float,
    "energy_analysis": {total_mwh, renewable_pct, by_source: {}},
    "cost_linkage": {...},
    "carbon_tax_risk": {...},
    "narrative": str,
})
```

---

## Agent 4: Report Generator

**Class:** `ReportGeneratorAgent` (`agents/report_generator.py`)
**Purpose:** Generates multi-framework, audit-ready ESG reports with AI narratives.

### Data Dependencies

Subscribes to:
- `carbon_results` → emissions highlights
- `regulatory_results` → framework compliance
- `audit_results` → audit trail data
- `roi_results` → value-creation channels and ROI summary
- `data_collection_results` → data quality info

### Report Sections Generated

1. **Executive Summary** — AI-generated 3-4 sentences using company profile + carbon + compliance + ROI data
2. **Environmental Performance** — narrative + metrics table (pillar == "Environmental")
3. **Social Performance** — narrative + metrics table (pillar == "Social")
4. **Governance Performance** — narrative + metrics table (pillar == "Governance")
5. **Framework Sections** — per-framework compliance percentages and gap counts
6. **Carbon Highlights** — total emissions, YoY change, carbon intensity
7. **Compliance Summary** — overall + per-framework percentages
8. **ROI Snapshot** — financial ROI, net benefit, and investment quality summary
9. **Audit Trail** — timestamped steps (data collection, validation, report generation)

### Metrics Tables Compilation

```python
for each pillar in ["Environmental", "Social", "Governance"]:
    table = metrics_df[pillar][["metric_id", "metric_name", "unit",
                                 "value_2023", "value_2024", "target_2024", "status"]]
```

### Gradio UI Report Types

The Gradio interface offers 5 report modes:
- Full ESG Report (all sections)
- Framework Compliance (compliance-focused)
- Carbon & Environment (emissions + environmental metrics)
- Social & Governance (S+G sections only)
- Executive Summary Only

Output tabs: Report | Metrics Tables | Framework Compliance | Audit Trail

---

## Agent 5: Risk Predictor

**Class:** `RiskPredictorAgent` (`agents/risk_predictor.py`)
**Purpose:** Climate risk forecasting, ESG rating prediction, scenario analysis.

### Climate Risk Scoring

```
Overall Risk Score = physical_risk × 0.25
                   + transition_risk × 0.45
                   + emission_risk × 0.30

Risk components:
  physical_risk = 28 (fixed — low for IT sector)

  transition_risk = max(20, 100 - compliance)
    where compliance = regulatory_results.overall_compliance (or 75 if unavailable)

  emission_risk:
    If emissions increasing: min(80, 50 + (increase_pct × 100))
    If emissions decreasing: max(15, 50 - (decrease_pct × 100))
    Default: 35

Risk Levels:
  < 30  → "Low"
  < 60  → "Medium"
  >= 60 → "High"
```

### ESG Rating Prediction

```
met_pct = (metrics with status == "Met") / total_metrics × 100

Rating thresholds:
  >= 90% → "A"
  >= 80% → "A-"
  >= 70% → "BBB+"
  >= 60% → "BBB"
  <  60% → "BB+"

confidence = min(95, met_pct + 10)
```

**Pillar scores:** For each of Environmental/Social/Governance:
```
pillar_score = met_count / total_in_pillar × 100
```

### Scenario Analysis

Three scenarios projected from base emissions:

| Scenario | Emission Reduction | Projected Rating | Timeline |
|----------|-------------------|-----------------|----------|
| Accelerated Transition | 35% | A | 18-24 months |
| Current Trajectory | 18% | A- | 12-18 months |
| Stalled Progress | 5% | BBB | 24+ months |

### Supplier Risk Analysis

```
high_risk_count = count(supply_chain_df[risk_rating == "High"])
overdue_audits  = count(supply_chain_df[audit_status == "Overdue"])
avg_esg_score   = mean(supply_chain_df.esg_score)
```

### Multi-Agency Rating Predictions (H3)

In addition to the internal letter rating, the agent emits translations
across three well-known scales:

| Agency | Output | Basis |
|--------|--------|-------|
| MSCI-style | `AA` / `A` / `BBB` / `BB` / `B` | Overall met-target %  |
| Sustainalytics | Risk score (lower = better) + Negligible/Low/Medium/High/Severe | Unmanaged ESG risk exposure |
| CDP-style | `A` / `A-` / `B` / `B-` / `C` | Environmental pillar score |

Published under `rating_prediction.multi_agency_ratings`.

### Market Regime Detection (H3 — cyclical ESG outperformance)

Uses the most recent 4 quarters of financial data to classify the current
operating regime:

```
revenue_trend   = mean(quarterly pct change) last 4 q
margin_trend    = mean(bps change) last 4 q

Regime:
  Bull      → revenue_trend > 0.01 AND margin_trend > 0
  Stress    → revenue_trend < -0.005 OR margin_trend < -0.5
  Transition → otherwise
```

Each regime carries an ESG context interpretation used by the ROI,
Report, and Stakeholder agents to tune narrative emphasis.

### Downside Protection Score (H4)

Composite 0-100 measuring ESG-driven resilience to negative shocks:

```
DPS = governance_strength × 0.30
    + financial_resilience × 0.25
    + esg_momentum × 0.25
    + climate_risk_shield × 0.20

Levels:
  >= 70 → "Strong"
  >= 50 → "Moderate"
  <  50 → "Weak"
```

Published under `downside_protection` for consumption by the ROI and
Action agents.

---

## Agent 6: ESG ROI Agent

**Class:** `ROIAgent` (`agents/roi_agent.py`)
**Purpose:** Quantifies ESG-linked financial return, strategic value, J-curve payoff, and investment quality.

### Data Dependencies

Reads canonical datasets and analytical outputs from:
- `dataset_financials`
- `dataset_emissions`
- `dataset_esg_metrics`
- `dataset_energy`
- `dataset_supply_chain`
- `dataset_diversity`
- `risk_results`
- `carbon_results`

### KPI Backbone

The ROI agent runs the KPI Engine across five value-creation channels:

1. Growth
2. Cost
3. Risk
4. Human Capital
5. Capital Efficiency

### Financial ROI

```
Financial ROI = (total_savings / total_esg_capex) × 100

where:
  total_savings = emission_reduction_savings
                + energy_efficiency_savings
                + carbon_tax_avoided
```

Additional uplift is estimated through ESG-linked revenue contribution.

### Strategic ROI

Strategic ROI estimates:
- Cost-of-capital reduction in basis points
- Risk reduction value
- Talent retention savings
- Brand premium score
- ESG rating trajectory

### J-Curve

The J-curve models cumulative ESG cost vs cumulative benefit by quarter:

```
net_position = cumulative_benefit - cumulative_cost

# Breakeven only counts when the curve actually went underwater first.
breakeven_quarter = first quarter q where:
    cumulative_cost(q) > 0           # some investment has happened
    AND net_position(q) >= 0         # back above water
    AND ∃ earlier quarter where net_position < 0    # was underwater before
```

A pure-positive trajectory (benefits ≥ costs from the start) returns `breakeven_quarter = None` — there's no J-Curve to break even on.

**Fix history.** An earlier version checked `net_position >= 0 and i > 0`, which trivially fired on the all-zero pre-investment quarters where `cumulative_cost == 0`. The deployed Space showed *"Breakeven: 2021 Q2 | Current net position: INR -187.83 Cr"* — a falsely-reported breakeven despite a still-negative position. Pinned by `tests/test_roi_agent.py::TestJCurve::test_no_breakeven_when_position_starts_positive`.

### Investment Quality Score (IQS)

Weighted composite:

```
IQS = financial_roi_score × 0.25
    + value_channel_average × 0.25
    + strategic_value_score × 0.20
    + momentum_score × 0.15
    + risk_reduction_score × 0.15
```

Published state:

```python
state_manager.publish("roi_results", {
    "kpi_engine": {...},
    "financial_roi": {...},
    "strategic_roi": {...},
    "j_curve": {...},
    "investment_quality_score": {...},
    "narrative": str,
})
```

---

## Agent 7: Audit Agent

**Class:** `AuditAgent` (`agents/audit_agent.py`)
**Purpose:** Compliance verification, audit readiness scoring, evidence mapping.

### Audit Readiness Score

```
Readiness = completeness_avg × 0.30
          + compliance_avg × 0.40
          + evidence_pct × 0.30

Components:
  completeness_avg = mean(completeness across expected datasets where completeness > 0)
  compliance_avg   = mean(scores across compliance checklist items)
  evidence_pct     = verifiable_metrics / total_metrics × 100
    where verifiable = confidence >= 0.8

Grade:
  >= 90 → "A"
  >= 75 → "B"
  >= 60 → "C"
  <  60 → "D"
```

### Data Completeness Audit

For each of 7 expected datasets:

| Dataset | Label | Priority |
|---------|-------|----------|
| emissions | Scope 1/2/3 Emissions Data | critical |
| esg_metrics | ESG KPI Metrics | critical |
| supply_chain | Supply Chain Data | high |
| energy | Energy Consumption Data | high |
| waste | Waste Management Data | medium |
| diversity | Workforce Diversity Data | medium |
| financials | Financial KPI & ESG CapEx Data | high |

Status thresholds:
```
completeness >= 90 → "Pass"
completeness >= 70 → "Warning"
completeness <  70 → "Fail"
Dataset not found  → "Missing"
```

### Compliance Checklist

Framework-level checks (status thresholds):
```
compliance_pct >= 80 → "Pass"
compliance_pct >= 60 → "Warning"
compliance_pct <  60 → "Fail"
```

General audit checks (hardcoded scores):

| Check | Score | Status |
|-------|-------|--------|
| Data Traceability | 88 | Pass |
| Confidence Scoring | 82 | Pass |
| Year-over-Year Comparability | 95 | Pass |
| Third-Party Verification | 70 | Warning |
| Board ESG Oversight | 90 | Pass |
| Materiality Assessment | 60 | Warning |

### Evidence Mapping

For each ESG metric: checks if `confidence >= 0.8` → marks as `verifiable: true`.

### ESG Integrity Gap Detector

Cross-references self-reported ESG metrics against operational data to flag
inconsistencies (the "greenwashing gap"):

```
For each metric:
  - carbon_intensity → verify against emissions_df / revenue
  - renewable_%      → verify against energy_df (renewable_mwh / total_mwh)
  - target "Met"     → flag if reported < 90% of target

Mismatch score = mismatches_found / total_checked × 100

Risk levels:
  > 30%  → "Critical"
  > 15%  → "High"
  >  5%  → "Medium"
  <= 5%  → "Low"
```

Published under `integrity_gaps` with every flagged metric, the derived
value, the reported value, and a severity classification. Used by the
Action Agent to raise remediation tasks when the mismatch rate exceeds
thresholds.

---

## Agent 8: Action Agent

**Class:** `ActionAgent` (`agents/action_agent.py`)
**Purpose:** Generates prioritized, actionable ESG recommendations with timelines and costs.

### Recommendation Sources

| Source | Trigger | Priority |
|--------|---------|----------|
| Risk Predictor: high-risk suppliers | `high_risk_count > 0` | Critical |
| Risk Predictor: overdue audits | `overdue_audits > 0` | High |
| Risk Predictor: transition risk | `transition_risk > 50` | High |
| Audit Agent: compliance failures | Any checklist item with status == "Fail" | Critical |
| Audit Agent: evidence gaps | `evidence_score < 80` | Medium |
| Carbon Accountant: insufficient reduction | `yoy_change > -10` (not decreasing fast enough) | High |
| Carbon Accountant: hotspots exist | `len(hotspots) > 0` | High |
| Carbon Accountant: low renewables | `renewable_pct < 50` | Medium |
| Regulatory Tracker: critical gaps | Critical-priority gaps in any framework | Critical |

### Deduplication & Ranking

```
1. Deduplicate by first 50 chars of action text
2. Sort by priority: Critical > High > Medium > Low
3. Assign sequential IDs: ACT-001, ACT-002, ...
4. Assign staggered timelines (2-week offsets between start dates)
```

### Summary Statistics

```python
summary = {
    "total_actions": count,
    "critical": count(priority == "Critical"),
    "high": count(priority == "High"),
    "medium": count(priority == "Medium"),
    "low": count(priority == "Low"),
    "total_investment": sum(estimated_cost_lakhs),  # in INR lakhs
}
```

### Investment Friction & Target Setting Enhancements

The action layer adjusts recommendations for execution realism and computes
Net ROI per action.

**Implementation Friction Score (0-100):**

```
friction_pct = 6
             + duration_weeks × 0.35
             + category_adj         # 2-6 points by category
             + regime_adj           # 0 (Bull), 2 (Transition), 5 (Stress)

transaction_cost = base_cost × friction_pct / 100
adjusted_cost    = base_cost + transaction_cost
```

**Benefit & Net ROI:**

```
benefit_multiplier: 1.10 – 1.35 by category
gross_benefit = max(base_cost × multiplier, base_cost + anchor_share)
  where anchor_share = max(0, roi_anchor × 0.08)
net_value   = gross_benefit - adjusted_cost
net_roi_pct = net_value / adjusted_cost × 100
```

**Liquidity Risk:**

```
spend_ratio = adjusted_cost / current_revenue × 100

liquidity_risk:
  > 4% → "High"
  > 2% → "Medium"
  <= 2% → "Low"
```

**Execution mode:** `"Phased rollout"` when friction ≥ 60 or liquidity
risk ≠ Low, otherwise `"Accelerated rollout"`.

**Target Recommendations:** The agent also emits explicit targets derived
from risk, audit, carbon, regulatory, and ROI outputs — each with metric,
current value, target, unit, deadline, owner, and linked action IDs:

- Renewable Energy Share
- Overall Regulatory Compliance
- Evidence Verifiability
- High-Risk Suppliers
- ESG Investment Quality Score

---

## Agent 9: Stakeholder Agent

**Class:** `StakeholderAgent` (`agents/stakeholder_agent.py`)
**Purpose:** Generates audience-tailored ESG communications.

### Audience Profiles

| Audience | Tone | Focus |
|----------|------|-------|
| Investors & Shareholders | Professional, data-driven | Financial materiality, risk-adjusted returns, ESG rating trajectory |
| Regulators & Compliance | Formal, precise | Compliance status, framework alignment, data traceability |
| Employees & Internal | Inspiring, inclusive | Workplace impact, diversity, safety, community |
| General Public & Media | Accessible, honest | Environmental impact, community benefit, commitments |

### Communication Generation

For each audience:
1. Generate message using HuggingFace text generation with audience profile + ESG context
2. Run sentiment analysis on generated message → `tone_analysis`
3. Generate audience-specific subject line
4. Select relevant metrics subset

Stakeholder context now also includes:
- Reporter profile from the regulatory layer
- Financial ROI and investment quality summaries
- J-curve framing for expectation-setting

### Metrics Selection by Audience

| Audience | Base Metrics | Additional Metrics |
|----------|-------------|-------------------|
| All | Total Emissions, YoY Change | — |
| Investors | + ESG Rating, Carbon Intensity, Risk Score | |
| Regulators | + Compliance %, Pending Actions | |
| Employees | + Renewable Energy % | |
| Public | + Renewable Energy %, ESG Rating | |

---

## Data Connectors

ESG Pilot supports 9 data connector types. All are defined in `utils/real_connectors.py`.

### Local Connectors (always available)

| Type | Class | Description |
|------|-------|-------------|
| File Upload | `FileUploadConnector` | CSV, Excel (.xlsx/.xls), JSON |
| Google Sheets | `GoogleSheetsConnector` | Public Google Sheets via CSV export URL |
| REST API | `RESTAPIConnector` | Any JSON REST endpoint (GET/POST), custom headers |
| SQL Database | `SQLDatabaseConnector` | PostgreSQL, MySQL, SQLite via SQLAlchemy |

### Cloud Connectors (optional dependencies)

| Type | Class | Install | Folder Mode |
|------|-------|---------|-------------|
| AWS S3 | `AWSS3Connector` | `pip install boto3` | Yes |
| Google BigQuery | `GCPBigQueryConnector` | `pip install google-cloud-bigquery` | N/A (SQL queries) |
| Google Cloud Storage | `GCPStorageConnector` | `pip install google-cloud-storage` | Yes |
| Azure Blob Storage | `AzureBlobConnector` | `pip install azure-storage-blob` | Yes |

### Delta Lake Connector (optional)

| Type | Class | Install |
|------|-------|---------|
| Delta Lake | `DeltaLakeConnector` | `pip install deltalake` |

The Delta Lake connector reads Delta tables without requiring Apache Spark (uses the `deltalake` / delta-rs Python package).

**Supported table URIs:**
- Local file system: `/path/to/delta_table`
- AWS S3: `s3://bucket/path/to/delta_table`
- Google Cloud Storage: `gs://bucket/path/to/delta_table`
- Azure: `az://container/path/to/delta_table`

**Features:**
- **Version pinning:** Read a specific Delta table version (time travel)
- **Column selection:** Provide a comma-separated list to read only specific columns
- **Row filters:** Simple filter expressions like `year = 2024, scope = Scope 1` (parsed into partition filter tuples)
- **Cloud credentials:** Provide `storage_options` as a JSON dict for cloud-hosted tables
- **Row limit:** Default 50,000 row cap per fetch (configurable)

```python
from utils.real_connectors import get_connector

connector = get_connector("delta_lake")

# Test connection
result = connector.test_connection(
    table_uri="s3://my-bucket/esg/emissions_delta",
    storage_options_json='{"AWS_ACCESS_KEY_ID": "...", "AWS_SECRET_ACCESS_KEY": "..."}'
)

# Fetch data with column selection and row filters
df = connector.fetch(
    table_uri="s3://my-bucket/esg/emissions_delta",
    version=5,
    columns="scope, category, emissions_tco2e, year",
    row_filter="year = 2024, scope = Scope 1",
    storage_options_json='{"AWS_ACCESS_KEY_ID": "...", "AWS_SECRET_ACCESS_KEY": "..."}'
)
```

### Folder / Prefix Mode (S3, GCS, Azure)

Cloud storage connectors support **folder mode** for batch ingestion. When the object key/path ends with `/`, the connector:

1. Lists all objects under that prefix
2. Filters for supported file extensions: `.csv`, `.json`, `.xlsx`, `.xls`, `.parquet`
3. Reads each file into a DataFrame
4. Concatenates all DataFrames with `pd.concat(ignore_index=True)`

**Example (S3):**
```python
connector = get_connector("aws_s3")

# Single file
df = connector.fetch(bucket="my-bucket", key="data/emissions.csv", ...)

# Folder mode — reads ALL supported files under data/esg/
df = connector.fetch(bucket="my-bucket", key="data/esg/", ...)
```

**Implementation details:**
- **S3:** Uses `list_objects_v2` paginator with `Prefix` filter
- **GCS:** Uses `bucket.list_blobs(prefix=...)` via google-cloud-storage
- **Azure:** Uses `container_client.list_blobs(name_starts_with=...)` via azure-storage-blob

The `test_connection()` method in folder mode reports the number of discovered files and lists the first 5 filenames.

### Connector Interface

Every connector implements:
```python
class RealConnector:
    connector_type = "type_name"
    display_name = "Human Name"
    icon = "emoji"

    def test_connection(self, **config) -> {"success": bool, "message": str}
    def fetch(self, **config) -> pd.DataFrame
```

### Using Connectors

```python
from utils.real_connectors import get_connector, get_available_connectors

# Check what's available on this installation
available = get_available_connectors()
for key, info in available.items():
    status = "ready" if info["available"] else f"install: {info.get('install_hint', '?')}"
    print(f"  {info['icon']} {info['name']}: {status}")

# Get a connector instance
connector = get_connector("aws_s3")

# Test the connection
result = connector.test_connection(bucket="my-bucket", key="data.csv",
                                    aws_access_key_id="...", aws_secret_access_key="...")

# Fetch data
df = connector.fetch(bucket="my-bucket", key="data.csv", ...)
```

### Connection Manager

The `ConnectionManager` class (`utils/connection_manager.py`) manages multiple registered data sources in a session-scoped registry, with per-source config-signature caching so unchanged sources don't re-execute remotely on every pipeline Run.

```python
from utils.connection_manager import ConnectionManager

mgr = ConnectionManager()

# Register a source
mgr.add_source(source_id="my_s3_data", connector_type="aws_s3",
               config={...}, target_schema="emissions",
               column_mapping={...}, display_name="S3 Emissions")

# Register a Delta Lake source
mgr.add_source(source_id="delta_emissions", connector_type="delta_lake",
               config={"table_uri": "s3://bucket/delta_table", "columns": "scope,emissions_tco2e"},
               target_schema="emissions", display_name="Delta Lake Emissions")

# Fetch all sources, grouped by schema
by_schema = mgr.fetch_all_by_schema()
# Returns: {"emissions": pd.DataFrame, "esg_metrics": pd.DataFrame, ...}

# Fetch with per-source cache reuse — unchanged sources skip the remote round-trip
by_schema = mgr.fetch_all_by_schema(use_cache=True)

# Stable hashes (SHA-256) for change detection
sig_one = mgr.source_signature("my_s3_data")   # per source
sig_all = mgr.sources_signature()              # every registered source

# Inspect / recover from failures
errors = mgr.source_errors()                   # {source_id: "error message", ...}
mgr.invalidate_cache("my_s3_data")             # force next fetch to hit the remote
mgr.invalidate_cache()                         # clear cache for every source
```

**Caching contract.** Each source keeps an internal `(_cached_signature, _cached_df)` pair. Signatures are full SHA-256 digests over the connector type, target schema, column mapping, and config (file bytes included). When `use_cache=True` and the signature matches, `fetch_source()` returns a **copy** of the cached DataFrame without calling the connector. Any change to the config — a new Snowflake query, a different S3 key, a re-uploaded file — invalidates the signature automatically.

**Error semantics.** `fetch_all*()` never raises for a single source; failures are recorded on the source (`status = "error"`, `error = "..."`) and returned as an empty DataFrame so the pipeline can proceed on sample data for that schema. Call `source_errors()` afterward to surface them to the user.

---

## Schema Mapping & Validation

7 target schemas are defined in `utils/schema_mapper.py`. The sections below document every column for each schema, the auto-detection logic, and the column-mapping strategy.

---

### Schema: `emissions`

Scope 1/2/3 carbon accounting data.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `year` | int | Required | Reporting year (e.g. 2024) |
| `quarter` | str | Required | Quarter (Q1, Q2, Q3, Q4) |
| `scope` | str | Required | Emission scope (Scope 1, Scope 2, Scope 3) |
| `category` | str | Required | Emission category (e.g. Fleet Vehicles, Electricity) |
| `emissions_tco2e` | float | Required | Emissions in tonnes CO2 equivalent |
| `unit` | str | Optional | Unit of measurement (default: tCO2e) |
| `source` | str | Optional | Data source (e.g. Fuel logs, Utility bills) |
| `confidence` | float | Optional | Confidence score 0–1 |

---

### Schema: `esg_metrics`

ESG KPI tracking across Environmental, Social, and Governance pillars.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `metric_id` | str | Required | Unique metric identifier (e.g. E01, S03) |
| `pillar` | str | Required | ESG pillar (Environmental, Social, Governance) |
| `category` | str | Required | Metric category (e.g. Climate, Workforce) |
| `metric_name` | str | Required | Human-readable metric name |
| `unit` | str | Optional | Unit of measurement |
| `value_2023` | float | Optional | Value for 2023 |
| `value_2024` | float | Optional | Value for 2024 |
| `target_2024` | float | Optional | Target value for 2024 |
| `status` | str | Optional | Status (Met, Not Met, On Track) |
| `data_source` | str | Optional | Data source description |
| `confidence` | float | Optional | Confidence score 0–1 |

---

### Schema: `supply_chain`

Supplier ESG scores, risk ratings, and emission contributions.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `supplier_id` | str | Required | Unique supplier identifier |
| `supplier_name` | str | Required | Supplier company name |
| `country` | str | Required | Country of operation |
| `sector` | str | Optional | Industry sector |
| `tier` | str | Optional | Supply chain tier (Tier 1, Tier 2, Tier 3) |
| `esg_score` | float | Optional | ESG score (0–100) |
| `risk_rating` | str | Optional | Risk rating (Low, Medium, High, Critical) |
| `emission_contribution_tco2e` | float | Optional | Emission contribution in tCO2e |
| `audit_status` | str | Optional | Audit status |
| `last_audit_date` | str | Optional | Last audit date (YYYY-MM-DD) |
| `key_risk_factors` | str | Optional | Key risk factors (comma-separated) |

---

### Schema: `energy`

Energy consumption by source, facility, and period.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `year` | int | Required | Reporting year |
| `quarter` | str | Required | Quarter (Q1–Q4) |
| `energy_source` | str | Required | Energy source (Grid Electricity, Solar, etc.) |
| `consumption_mwh` | float | Required | Energy consumption in MWh |
| `cost_inr_lakhs` | float | Optional | Cost in INR lakhs |
| `location` | str | Optional | Facility location |
| `renewable` | str | Optional | Is renewable? (Yes/No) |

---

### Schema: `waste`

Waste generation, type, and disposal methods.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `year` | int | Required | Reporting year |
| `quarter` | str | Required | Quarter (Q1–Q4) |
| `waste_type` | str | Required | Waste type (Hazardous, Non-Hazardous) |
| `category` | str | Required | Waste category (e.g. Paper, Plastic, E-waste) |
| `quantity_mt` | float | Required | Quantity in metric tonnes |
| `disposal_method` | str | Optional | Disposal method (Recycling, Landfill, etc.) |
| `recycled_pct` | float | Optional | Recycled percentage (0–100) |
| `location` | str | Optional | Facility location |

---

### Schema: `diversity`

Workforce diversity and representation metrics.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `year` | int | Required | Reporting year |
| `category` | str | Required | Diversity category (Gender, Age, etc.) |
| `subcategory` | str | Required | Subcategory (Overall, Leadership, etc.) |
| `metric` | str | Required | Metric name |

---

### Schema: `financials`

Financial performance and ESG-linked investment data.

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `year` | int | Required | Reporting year |
| `quarter` | str | Required | Quarter (Q1–Q4) |
| `revenue_inr_crores` | float | Required | Revenue in INR crores |
| `ebitda_inr_crores` | float | Optional | EBITDA in INR crores |
| `ebitda_margin_pct` | float | Optional | EBITDA margin percentage |
| `pat_inr_crores` | float | Optional | Profit after tax in INR crores |
| `roa_pct` | float | Optional | Return on assets percentage |
| `roe_pct` | float | Optional | Return on equity percentage |
| `debt_equity_ratio` | float | Optional | Debt to equity ratio |
| `cost_of_capital_pct` | float | Optional | Cost of capital percentage |
| `pe_ratio` | float | Optional | Price to earnings ratio |
| `carbon_tax_exposure_lakhs` | float | Optional | Carbon tax exposure in INR lakhs |
| `energy_cost_inr_crores` | float | Optional | Energy cost in INR crores |
| `employee_turnover_pct` | float | Optional | Employee turnover percentage |
| `brand_value_index` | float | Optional | Brand value index |
| `talent_retention_score` | float | Optional | Talent retention score |
| `esg_linked_capex_inr_crores` | float | Optional | ESG-linked CapEx in INR crores |

---

### Auto-Detection

`auto_detect_schema(df)` identifies the schema from indicator columns present in the uploaded DataFrame:

| Indicator Column(s) | Detected Schema |
|--------------------|----------------|
| `emissions_tco2e` | `emissions` |
| `metric_id` | `esg_metrics` |
| `supplier_name` or `esg_score` | `supply_chain` |
| `consumption_mwh` or `energy_source` | `energy` |
| `quantity_mt` or `waste_type` | `waste` |
| `subcategory` + a diversity category value | `diversity` |
| `revenue_inr_crores` or `esg_linked_capex` | `financials` |

Detection is done by scanning column names for these indicators. The schema with the highest indicator score wins. If no indicator matches, returns `None`.

---

### Column Mapping Strategy

`suggest_column_mapping(df, target_schema)` maps source columns in the uploaded file to ESG schema columns in three steps, tried in order:

1. **Exact match** — source column name matches schema column name character-for-character.
2. **Normalized match** — both names are lowercased and underscores/whitespace stripped before comparing (e.g. `Emissions tCO2e` → `emissionstco2e` matches `emissionstco2e`).
3. **Synonym match** — source column name is looked up in the `_SYNONYMS` dictionary. Common synonym mappings include:
   - `"co2"`, `"co2_emissions"`, `"ghg"` → `emissions_tco2e`
   - `"scope1"`, `"scope_1"` → `scope`
   - `"mwh"`, `"energy_mwh"` → `consumption_mwh`
   - `"revenue"`, `"total_revenue"` → `revenue_inr_crores`
   - `"capex"`, `"esg_capex"` → `esg_linked_capex_inr_crores`
   - `"gender"` → `category` (for diversity schema)

---

### Validation Output

`validate_mapped_data(df, target_schema)` returns a structured result:

```python
{
    "errors":   ["Missing required column: emissions_tco2e", ...],
    "warnings": ["Optional column not mapped: confidence", ...],
    "stats": {
        "rows":             int,    # total rows in DataFrame
        "columns_mapped":   int,    # schema columns successfully mapped
        "columns_total":    int,    # total schema columns for this schema
        "completeness":     float,  # mapped / total as a fraction
    }
}
```

Errors are raised for missing required columns. Warnings are raised for unmapped optional columns. A DataFrame with no errors is accepted for pipeline use even if optional columns are absent.

---

## AI Models & Fallbacks

### HuggingFace Models

| Task | Model | Parameters |
|------|-------|-----------|
| Text Generation | `mistralai/Mistral-7B-Instruct-v0.3` | max_new_tokens=300, temperature=0.7 |
| Summarization | `facebook/bart-large-cnn` | max_length=150, min_length=30 |
| Zero-Shot Classification | `facebook/bart-large-mnli` | candidate_labels provided per call |
| Sentiment Analysis | `distilbert/distilbert-base-uncased-finetuned-sst-2-english` | — |

### Fallback Behavior

When no HF API token is set or the API is unreachable, all methods fall back to rule-based implementations:

- **Text generation:** Keyword-matched template responses (risk, carbon, stakeholder, audit, etc.)
- **Summarization:** Returns first 3 sentences
- **Classification:** Deterministic hash-based random scoring (same input → same output)
- **Sentiment:** Keyword counting (positive vs. negative word sets)

The fallback ensures the platform always works without an API token — ideal for demos and HuggingFace Spaces deployment.

---

## Data Freshness & Pipeline Refresh

Every agent is a pure function of what the Data Collector last published to `state_manager`. Because `state_manager` is a module-level singleton, a cached dataset from an earlier run would otherwise leak into the next page the user visits. This section documents how the platform guarantees that **any change to any registered data source is picked up on the next Run**, and how it behaves when sources fail.

### Guarantees

- **Edit any source → next Run sees it.** Every single-agent page (Regulatory, Carbon, Report, Risk, Audit, Action, Stakeholder, ESG ROI) calls `refresh_real_data()` *before* its agent runs. ESG Command Center's full-pipeline run does the equivalent by forwarding the `ConnectionManager` into the Data Collector and stamping the same session-state keys afterwards.
- **Remote-side data changes are always visible on the next full Run.** In full-refresh mode (the default — `only_changed=False`), `refresh_real_data()` calls `conn_mgr.invalidate_cache()` *before* the Data Collector fetches, and ESG Command Center invalidates before `run_full_pipeline()`. So a row delete in a Snowflake table, an edit to a Google Sheet, or an updated S3 object is reflected on the very next click — no signature-collision footgun, no stale `_cached_df` reuse.
- **Removed sources leave no residue.** Stale `dataset_*` / `validated_*` channels in `state_manager` are cleared before the Data Collector republishes.
- **Unchanged sources are free.** With `only_changed=True`, sources whose config signature matches the last successful fetch reuse a cached DataFrame; the remote system is not hit. (`invalidate_cache()` is *not* called in this mode — that's the whole point of the optimisation.)
- **Per-source live-refresh, no full pipeline needed.** Each row in *Registered Data Sources* has a 🔄 Refresh button that calls `invalidate_cache(src_id)` then `fetch_source(src_id, use_cache=False)` — re-queries the remote system right now, updates `last_row_count` + `last_fetch`, and surfaces success/error inline. See [Per-source actions on the Registered Sources list](#per-source-actions-on-the-registered-sources-list).
- **Errors are visible.** A failed fetch (bad Snowflake credential, revoked S3 key, 404 on a Sheet) is surfaced as `st.warning()` plus a second line on the freshness caption — no silent fallback to sample data.

### Component map

| Component | File | Role |
|---|---|---|
| `refresh_real_data()` | `utils/pipeline_refresh.py` | Public helper every page's Run button calls. Re-invokes the Data Collector, clears stale state, surfaces errors, stamps session keys. |
| `data_freshness_caption()` | `utils/pipeline_refresh.py` | Renders "Real data refreshed N sec ago from M source(s). Click Run to pull the latest." plus a warning line when the last refresh had errors. |
| `stamp_refresh_from_pipeline()` | `utils/pipeline_refresh.py` | Called by ESG Command Center after `run_full_pipeline` to keep every page's freshness caption honest when the Data Collector ran outside the helper. |
| `ConnectionManager.sources_signature()` | `utils/connection_manager.py` | Full SHA-256 digest over every registered source's connector type, schema, mapping, and config. |
| `ConnectionManager.source_errors()` | `utils/connection_manager.py` | Returns `{source_id: message}` for every source currently in error state. |
| `ConnectionManager.fetch_all_by_schema(use_cache=True)` | `utils/connection_manager.py` | Selective re-fetch: unchanged sources return cached DataFrames; changed sources hit the connector. |

### `refresh_real_data()` API

```python
from utils.pipeline_refresh import refresh_real_data, data_freshness_caption

# Every single-agent page does this:
if st.button("Run …", type="primary"):
    with st.spinner("Refreshing data from registered sources..."):
        refresh_real_data()
    with st.spinner("Running the agent..."):
        results = agent.run()
```

**Signature**

```python
refresh_real_data(
    only_changed: bool = False,   # reuse cache for sources whose signature is unchanged
    show_toast:   bool = False,   # render a ✅ toast on success
    show_errors:  bool = True,    # render st.warning() per failed source
) -> dict
```

**Return payload**

```python
{
    "refreshed": True,                  # False only when no sources are registered
    "reason":    "full" | "only_changed" | "no_sources",
    "sources":   3,
    "records":   12_450,
    "timestamp": "2026-04-18T12:34:56.789",
    "signature": "a1b2c3…",             # 64-char SHA-256 of all source configs
    "errors":    {"snow_fin": "Authentication failed"},
}
```

**Session-state keys it writes** (also written by `stamp_refresh_from_pipeline`):

| Key | Purpose |
|---|---|
| `_last_data_refresh` | ISO-8601 timestamp of the most recent refresh — drives the "N sec ago" caption. |
| `_last_data_refresh_signature` | SHA-256 hash of source configs at refresh time. |
| `_last_data_refresh_records` | Total rows ingested across all real sources. |
| `_last_data_refresh_errors` | `{source_id: message}` so every page can display outstanding errors. |

### Stale-channel clearing

Before the Data Collector re-publishes, `refresh_real_data()` drops every key in `state_manager._channels` whose name starts with `dataset_` or `validated_`. This is how the platform handles the "user removed a source" case: the Data Collector only re-publishes what's *currently* registered, so a previously-published `dataset_supply_chain` no longer leaks through if the Snowflake source that produced it was deleted.

### DataCollector integration

`DataCollectorAgent.execute()` accepts `use_cache: bool = False`. When the helper passes `only_changed=True` through, the agent forwards it to `ConnectionManager.fetch_all_by_schema(use_cache=True)`. The agent is backward-compatible: if it encounters an older manager without the kwarg, it catches `TypeError` and falls back to the cacheless call.

### Behaviour matrix

| User action | Next Run behaviour |
|---|---|
| Edits a Snowflake query and clicks Run on any agent page | Helper fires → signature changes → connector re-executes → fresh DataFrame → agent runs on fresh data. |
| **Reduces row count of a Snowflake table without changing the query** | Default full mode: `invalidate_cache()` runs before fetch → connector re-executes → new row count visible on the next Run. With `only_changed=True`: signature unchanged, cached DF reused — use the per-source 🔄 button or run the full pipeline to force a fresh fetch. |
| Clicks Run a second time without touching anything | Default: full re-fetch (safest, cache invalidated up front). With `only_changed=True`: cache hit, no remote traffic. |
| **Clicks the per-source 🔄 Refresh button** | `invalidate_cache(src_id)` then `fetch_source(src_id, use_cache=False)` — re-queries the one source immediately, updates `last_row_count` + `last_fetch`, no other sources or agents touched. Used to verify a remote change without running the orchestrator. |
| **Clicks the per-source 📤 Replace button (file_upload only)** | Inline `st.file_uploader` opens. On Apply: `add_source` overwrites `config["file_bytes"]` (and re-derives `column_mapping` against the new columns), preserving `display_name` and `target_schema`. Cache is wiped because `add_source` resets `_cached_df`. |
| Removes a registered source, clicks Run | Stale `dataset_{schema}` channel cleared → Data Collector re-publishes without it → downstream agents read via `core.data_access.get_dataset(...)` which falls back to sample data for that schema. |
| Re-uploads a CSV with identical bytes | Signature stable (full SHA-256 over the bytes) → cache hit when `only_changed=True`. |
| Re-uploads a CSV with different bytes | Signature changes (length differs, or hash differs) → connector re-parses. |
| Runs the full pipeline from ESG Command Center | ESG Command Center calls `conn_mgr.invalidate_cache()` first, then `Orchestrator.run_full_pipeline()` invokes the Data Collector with the active `ConnectionManager`; afterwards `stamp_refresh_from_pipeline()` updates every agent page's "N sec ago" caption. |
| **Approves a regulatory framework update** | `apply_update()` writes the new requirement to `data/regulatory_frameworks.json`. The Regulatory Tracker reloads from disk on every `execute()` (no in-memory cache short-circuit), so the next *Run Compliance Analysis* sees the new requirement and the Compliance Radar shifts immediately. |
| Snowflake credential expires mid-session | `source_errors()` contains the failure → `st.warning()` on the page → caption grows a "Last refresh had errors on `snow_fin` — sample data used for affected schemas." line. |
| Opens a second browser tab | `st.session_state` is per-tab. Each tab has its own `conn_manager` and its own freshness timestamps. By design. |

### Caveats that still apply

- The signature does **not** hash remote data content — only config. With the default `only_changed=False`, this doesn't matter: full mode now invalidates the cache before fetching, so remote-side row changes are always visible. With `only_changed=True`, a Snowflake table whose rows change while the query string stays identical will return cached data until either: (a) the user clicks the per-source 🔄 Refresh button (which calls `invalidate_cache(src_id)` directly), (b) the user runs the full pipeline (full-mode invalidation), or (c) the source config is edited (signature changes).
- `state_manager` is still a module-level singleton. All current agents re-read on `.run()`, so the clearing step is sufficient; future agents that cache a reference at `__init__` would bypass it.
- The `_cached_df` field is still maintained inside `ConnectionManager._sources[sid]` even in full-refresh mode — full mode wipes it *before* fetching, then repopulates it after a successful fetch. This preserves the optimisation for any downstream caller that does opt into `use_cache=True`.

---

## Identity, Persistence & Per-User Isolation

This section documents how a signed-in user is identified, where their state lives, and how concurrent users on the same Streamlit replica stay isolated. Read this before debugging any "I see someone else's numbers" or "my settings vanished after a Space rebuild" reports.

### Authentication

Implemented in `utils/auth.py`. Public surface is documented at the top of the module; the operationally important pieces are:

| Concern | Implementation | Notes |
| --- | --- | --- |
| Password hashing | `bcrypt` | Never plaintext, ever. |
| Session cookie | `itsdangerous.URLSafeTimedSerializer` with a 14-day TTL | Bridge to the browser via `extra_streamlit_components`. Cookie name configurable via `ESG_AUTH_COOKIE`. |
| Cookie signing secret | `SESSION_SECRET` env var → `STREAMLIT_SESSION_SECRET` → `.streamlit/.session_secret` file → process-ephemeral random key | On HF Spaces the file path is ephemeral, so **set `SESSION_SECRET` as a Space secret** to keep cookies valid across rebuilds. |
| Rate limits | In-memory rolling window per identifier | 10 logins / 5 min, 5 signups / 1 hr; tunable via `ESG_AUTH_*` env vars. Resets on process restart, not shared across replicas. |
| Bucket eviction | `_sweep_idle_keys()` runs every ~500 check calls | Keeps the bucket dict bounded under enumeration attacks. |

**To protect a page**, add at the top of the page script:

```python
from utils.auth import require_login
require_login()
```

`require_login()` calls `st.stop()` on unauthenticated visitors after rendering an "Authentication required" hero block + Sign In / Home buttons. The Sign In page is hidden from the sidebar nav once the user is authenticated.

### Per-user state partitioning

`core/state_manager.py` partitions every pub/sub channel by the active user's ID:

```
publish("carbon_results", value)   →  writes to "<user_id>:carbon_results"
subscribe("carbon_results")        →  reads from "<user_id>:carbon_results"
```

The active user ID is resolved on each call from `st.session_state` via a thread-local proxy. Anonymous sessions get a synthetic ID derived from the Streamlit session ID. **No agent code had to change** — all calls go through the existing `state_manager.publish` / `subscribe` API.

**Pinning test:** `tests/test_state_manager_isolation.py` uses the `FakeStreamlit` fixture in `tests/conftest.py` to simulate two users on one replica and asserts that User B's publish does not leak into User A's read.

### Per-user persistence

| Store | Module | Backend order |
| --- | --- | --- |
| Auth (users) | `utils/user_store.py` | `hf_dataset` → `local_json` (ephemeral) |
| Source registry | `utils/source_store.py` | `hf_dataset` → `local_json` (ephemeral) |
| Company profile | `utils/profile_store.py` | `hf_dataset` → `local_json` (ephemeral) |
| Pipeline run snapshots | `utils/run_store.py` | `hf_dataset` → `local_json` (ephemeral) |
| Session-cookie signing secret | `utils/auth.py:_resolve_secret` | env var → `hf_dataset` → local file → ephemeral random |

**HF Dataset format.** Each store writes JSON files into a private dataset (configured via `ESG_USERS_DATASET`, `ESG_SOURCES_DATASET`, `ESG_PROFILES_DATASET`, `ESG_AUTH_DATASET` env vars or the defaults baked into each module). One file per user, namespaced by user ID.

**Failure semantics.** On any HF API error (including `huggingface_hub` wrapping `EntryNotFoundError` as `ValueError`), the store:
1. Captures the exception into `last_error`.
2. Falls back to local-JSON storage so the app keeps working.
3. Surfaces both the active backend and the captured error in the sidebar via `_render_storage_diagnostic()`.

**Operator action: if the sidebar shows "Local JSON (ephemeral)" on the deployed Space, set `HF_TOKEN` as a Space secret.** Otherwise every Space rebuild loses all user-scoped data (accounts, sources, profiles, run snapshots, **and the session-cookie signing secret** — see below).

### Session-cookie signing secret

`utils/auth.py:_resolve_secret()` resolves the secret used by `itsdangerous` to sign session cookies. Resolution order:

1. `SESSION_SECRET` env var (recommended for prod)
2. `STREAMLIT_SESSION_SECRET` (alternative name)
3. The auth HF Dataset, file `auth/.session_secret` — persists across HF Space rebuilds when `HF_TOKEN` is set
4. Local file `.streamlit/.session_secret` — dev-only; does not survive container restarts
5. Process-ephemeral `secrets.token_urlsafe(48)` — last resort, invalidates every cookie on restart

**Why path 3 was added.** Before HF Dataset persistence, every Space deploy minted a new ephemeral secret (the local file doesn't survive HF container rebuilds), invalidating every browser's cookie and forcing a re-login on the next refresh. Now the secret is generated once, written to both the local file and the HF Dataset on first cold start, and re-used on subsequent rebuilds.

**Operator note:** the first time a Space starts after this code shipped, all existing users still need to log in once — their cookies were signed with the prior ephemeral secret. From that point forward, deploys don't kick anyone out.

### Pipeline run snapshots & auto-rehydrate

`utils/run_store.py` persists full pipeline-run snapshots per user under `runs/{username}/index.json` + `runs/{username}/{run_id}.json` in the auth HF Dataset.

**Save policy:**
- A successful pipeline run on the ESG Command Center auto-saves with the label `Auto · YYYY-MM-DD HH:MM`. Errored runs are deliberately *not* saved (so a half-finished pipeline never gets pinned as the latest).
- The user can also save manually via the **💾 Save / Load Pipeline Runs** expander, which accepts a custom label.

**Load policy:**
- ESG Command Center on first render in a session: if `st.session_state.pipeline_results` is empty, calls `run_store.latest_run(username)` and republishes each agent's result onto `state_manager` so per-agent pages see live numbers immediately. Gated by an `_mc_autoloaded` flag so this fires once per session.
- ESG ROI Agent page: same auto-load pattern, gated by `_roi_autoloaded`. Seeds both `st.session_state.roi_results` and `st.session_state.pipeline_results` for cross-page consistency.

**Limits:**
- `DEFAULT_HISTORY_CAP = 25` snapshots per user. Older runs rotate out and their backend file is deleted to prevent orphans.
- `MAX_SNAPSHOT_BYTES = 4 MB` (configurable via `ESG_RUN_MAX_BYTES`). Saves above that raise `ValueError` so the UI can surface a clear "snapshot too large" error rather than silently truncating.

**Index schema** (one entry per run): `id`, `label`, `saved_at`, `saved_by`, `goal`, `agent_count`, `errored_agents`, `headline.{total_records, audit_grade, iqs_grade, emissions_total}`. The headline lets the **Load** picker render meaningful labels without fetching every snapshot.

### Concurrent-user invariants

| Invariant | Where it's enforced |
| --- | --- |
| User A's pipeline run never overwrites User B's `state_manager` channels | `core/state_manager.py` per-user partitioning |
| User A's company profile never resolves for User B | `core/company_config.py` thread-local proxy that re-reads `profile_store` per call |
| User A's registered sources never appear in User B's Data Collector | `utils/connection_manager.py` is constructed per-session and stored under `st.session_state.conn_manager` |
| Logout actually clears user-scoped session_state | `utils/auth.py:logout()` pops `*_agent`, `*_results`, `data_collector`, `conn_manager`, profile keys |

**Known gap:** `logout()` does not currently clear `preview_df` / `preview_config` / `preview_source_type`. On a shared browser, the next user could see the previous user's uploaded file preview. Tracked as a follow-up.

---

## What-If Simulator (ROI page)

Module: `utils/whatif.py`. UI: a third tab on `pages/11_ESG_ROI_Agent.py`.

### Inputs

```python
@dataclass
class WhatIfInputs:
    carbon_price_uplift_pct: float = 0.0     # -50 … +300
    capex_uplift_pct: float = 0.0            # -50 … +200
    benefit_uplift_pct: float = 0.0          # -50 … +200
    discount_rate_pct: float = 12.0          # 0 … 25
```

All values are in *percent units* (so `25` means +25%). Defaults produce a no-op simulation.

### Why pure-functional re-projection?

The simulator deliberately does **not** re-execute any agents. Re-running the full pipeline takes 10–30s; the user wants "what if?" answered in milliseconds. The cached ROI run already contains the quarterly J-curve and the IQS components; we walk them under the slider multipliers and re-derive the results.

### Algorithm

1. **J-curve trajectory** — for each quarter in the cached run:
   - `capex_t' = capex_t × (1 + capex_uplift / 100)`
   - `benefit_t' = benefit_t × (1 + benefit_uplift / 100) + per_quarter_carbon_lift`
   - `per_quarter_carbon_lift = baseline_carbon_tax_avoided × (carbon_uplift / 100) / N`
   - Accumulate cumulative cost / benefit / net position.
2. **Breakeven** — same "must go underwater first" rule as `agents/roi_agent.py:_compute_j_curve`. Pure-positive trajectories return `None`. Δ breakeven is computed in *quarters* against the baseline index.
3. **Financial ROI** — `new_roi_pct = (adjusted_savings / adjusted_capex) × 100`.
4. **IQS recompute** — `_recompute_iqs()` replaces just the `financial_roi` sub-score (using the same `min(100, max(0, roi × 2))` compression as the agent) and reapplies the original component weights. Other components (channel performance, strategic value, ESG momentum, risk reduction) stay fixed — sliders don't synthesise data the agent didn't see.
5. **NPV** — `_net_present_value(quarterly_net, rate)`:
   - `rate = 0` returns the undiscounted sum (intuitive "money is free" extreme).
   - Otherwise `npv = Σ net_t / (1 + rate/4)^t` — per-quarter rate is `rate/4` so the slider stays in annual units.

### What's surfaced on the page

- **Four KPI cards top row:** baseline IQS · scenario IQS · Δ IQS · scenario breakeven (with Δ in quarters)
- **Three KPI cards second row:** scenario savings · scenario NPV · scenario net position
- **Quarterly trajectory chart** — three traces (cumulative cost, cumulative benefit, net position) under the slider settings
- **Quarterly trajectory table** — fallback when Plotly is missing

### Bounded outputs

Every IQS component clamps at 0–100, so a 100× slider value can't flip the IQS to 9999. The financial-ROI sub-score saturates at 100 once `roi_pct ≥ 50`.

`tests/test_whatif.py` pins: zero-slider reproducibility (within 0.5 IQS of baseline), capex uplift pushing breakeven out, carbon uplift increasing savings + lifting IQS, higher discount rates lowering NPV.

---

## Deployment

### Local Development

```bash
# Clone the repository
git clone https://github.com/isayan58/Agentic_ESG.git
cd Agentic_ESG

# Install dependencies
pip install -r requirements.txt

# Run Streamlit (port 8501)
streamlit run app.py --server.port 8501

# Run Gradio (port 7860)
python gradio_app.py
```

Local runtime notes:
- `pyarrow` is required for Streamlit's native dataframe component.
- If `pyarrow` is unavailable, the app falls back to HTML tables via `utils/streamlit_compat.py`.
- If `plotly` is unavailable, chart components render informational placeholders instead of crashing.

### Optional: AI Narratives

Set a HuggingFace API token for AI-generated narratives (agents work without it via rule-based fallbacks):

```bash
export HF_API_TOKEN="hf_your_token_here"
```

Or enter the token in the Streamlit sidebar at runtime.

### HuggingFace Spaces

Two Spaces are deployed using Docker SDK:

| Space | SDK | URL |
|-------|-----|-----|
| ESG-CoPilot (Gradio) | Docker | [huggingface.co/spaces/isayan58/ESG-CoPilot](https://huggingface.co/spaces/isayan58/ESG-CoPilot) |
| ESG-CoPilot-Dashboard (Streamlit) | Docker | [huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard](https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard) |

**Dockerfile pattern (Streamlit):**
```dockerfile
FROM python:3.11-slim
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Gradio-specific patches** (in `gradio_app.py`):

These monkey-patches resolve known issues when running Gradio inside Docker/HuggingFace Spaces:

1. `jinja2.Environment.get_template` — fixes unhashable dict in template cache (jinja2 + starlette version interaction)
2. `gradio.networking.url_ok` — bypasses localhost health check that fails in containerized environments
3. `gradio_client.utils._json_schema_to_python_type` — handles bool `additionalProperties` that causes `TypeError: argument of type 'bool' is not iterable`

### Deploying from GitHub to the Streamlit Space

The Streamlit Space (`isayan58/ESG-CoPilot-Dashboard`) is hosted by HuggingFace as a separate git remote. Deploys are explicit pushes from a green `dev` branch on GitHub into the Space's `main` branch. The Space rebuilds automatically once `main` advances.

**One-time remote setup** (already configured in this worktree, do once on a fresh clone):

```bash
git remote add hf-streamlit https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard
# Authenticate either via the macOS keychain helper or a HF write token in the URL:
#   https://USER:hf_TOKEN@huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard
git fetch hf-streamlit
```

**Standard deploy (clean dev history, no LFS-eligible binaries in any commit):**

```bash
# 1. Make sure your local dev mirrors GitHub.
git fetch origin
git fetch hf-streamlit

# 2. Sanity-check what will change on the Space.
git log hf-streamlit/main..origin/dev --oneline
git diff --stat hf-streamlit/main origin/dev

# 3. Push origin/dev to the Space's main branch.
git push hf-streamlit origin/dev:main
```

That's the happy path — a fast-forward push that the Space picks up within ~30 seconds.

**Recovery deploy (HF Space was reverted, or a binary blocks a normal push):**

HuggingFace's pre-receive hook scans the *full history* of every pushed branch and rejects any commit that contains a file LFS would track (binaries, large blobs). Even a commit that *adds* and *immediately removes* the file (e.g. a one-pager `.pptx` that we deleted) is enough to break a normal push.

The fix: build a single commit whose **tree** is your target state and whose **parent** is the current Space tip. HF only scans that one new commit, so deleted-but-historically-present binaries are invisible.

```bash
# 1. Confirm the Space tip and the gap to dev.
git fetch hf-streamlit
git diff --stat hf-streamlit/main origin/dev

# 2. Build a one-shot commit on top of the Space tip whose tree == origin/dev's tree.
TREE=$(git rev-parse origin/dev^{tree})
COMMIT=$(git commit-tree "$TREE" -p hf-streamlit/main \
  -m "deploy: sync to dev — <reason for the deploy>")
echo "Built deploy commit: $COMMIT"

# 3. Push that loose commit straight to main.
git push hf-streamlit "$COMMIT:main" --force

# 4. Verify the trees now match (output should be empty).
git fetch hf-streamlit
git diff --stat origin/dev hf-streamlit/main
```

The commit is loose (not on any local branch) — it lives only in the Space's history. Your working tree, local branches, and GitHub remote are untouched.

**Troubleshooting deploy push rejections:**

Each row below quotes the literal error you'll see in the terminal so you can grep for it. The "Fix" column is the *minimum* command sequence — drop in for drop in.

#### 1. Binary file rejected by xet/LFS hook

```
remote: Your push was rejected because it contains binary files.
remote: Please use https://huggingface.co/docs/hub/xet to store binary files.
remote: Offending files:
remote:   - ESG_CoPilot_OnePager.pptx (ref: refs/heads/main)
 ! [remote rejected] origin/dev -> main (pre-receive hook declined)
```

**Cause.** HF scans the *full history* of every pushed branch. Even if the file was added in commit `A` and removed in commit `B`, both `A` and `B` are in the pushed history, so HF sees the binary and rejects.

**Fix.** Use the recovery-deploy flow — `git commit-tree` produces exactly one commit on top of `hf-streamlit/main`, and HF only scans that single commit's tree:

```bash
TREE=$(git rev-parse origin/dev^{tree})
COMMIT=$(git commit-tree "$TREE" -p hf-streamlit/main \
  -m "deploy: bypass historical binary <filename>")
git push hf-streamlit "$COMMIT:main" --force
```

**Permanent fix** (so the next normal deploy works): keep large binaries out of the repo entirely. Move presentation decks, screenshots, generated PDFs, etc. to an out-of-tree `~/Drive/esg-copilot/` folder and reference them in `.gitignore`. If a binary already snuck in, either accept the recovery-deploy workflow forever or scrub history with `git filter-repo --invert-paths --path <file>` (destructive — coordinate with the team first).

#### 2. Non-fast-forward push

```
 ! [remote rejected] origin/dev -> main (non-fast-forward)
error: failed to push some refs to '…ESG-CoPilot-Dashboard'
hint: Updates were rejected because the remote contains work that you do
hint: not have locally. This is usually caused by another repository pushing
```

**Cause.** Someone (or some web edit on the Space's "Files" tab) added a commit to `hf-streamlit/main` that isn't in your local history.

**Fix — preserve the remote commit:**
```bash
git fetch hf-streamlit
git log hf-streamlit/main --oneline -5     # inspect what landed
git checkout -B deploy/sync hf-streamlit/main
git merge origin/dev --no-edit
git push hf-streamlit deploy/sync:main
```

**Fix — discard the remote commit (when it's a known-bad revert, as happened on 2026-04-20):**
```bash
TREE=$(git rev-parse origin/dev^{tree})
COMMIT=$(git commit-tree "$TREE" -p hf-streamlit/main \
  -m "deploy: restore reverted state")
git push hf-streamlit "$COMMIT:main" --force
```

#### 3. Authentication / authorization failure

```
remote: Invalid username or password.
fatal: Authentication failed for 'https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard/'
```

or

```
remote: Authorization error.
remote: Sorry, you don't have write access to this repository.
```

**Cause.** Token missing, expired, or read-only.

**Fix.**
1. Generate a **write** token at <https://huggingface.co/settings/tokens> (role: `Write`, scope: this Space or all repos).
2. Update the remote URL with the token embedded:
   ```bash
   git remote set-url hf-streamlit \
     https://isayan58:hf_xxxYourTokenxxx@huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard
   ```
3. Or store it in the macOS keychain once:
   ```bash
   git config --global credential.helper osxkeychain
   git push hf-streamlit …    # prompts once, caches forever
   ```

#### 4. Space stuck on "Building" / build failed

```
ERROR: Could not find a version that satisfies the requirement <pkg>
ModuleNotFoundError: No module named '<pkg>'
```

**Cause.** `requirements.txt` references a package name HF's pip mirror can't resolve, or a transitive dep pinned in `pip freeze` style is unavailable.

**Fix.**
1. Open the Space → **Logs** tab → **Build logs** to see the failing pip line.
2. If the package is genuinely needed: pin a known-good version (`pkg>=1.0,<2`) and re-deploy.
3. If it's a stale transitive (`pkg-only-on-mac`): drop it from `requirements.txt` — we keep that file curated, not generated by `pip freeze`.
4. After fixing, redeploy via the standard or recovery flow.

#### 5. Space runs but renders the wrong commit

**Cause.** Browser cache, or HF's CDN held a stale build manifest for ~1 minute.

**Fix.**
1. Confirm the deploy actually advanced `main`:
   ```bash
   git fetch hf-streamlit
   git log hf-streamlit/main --oneline -1
   ```
2. Open the Space's **Logs → App logs** and look for the build banner timestamp.
3. Hard-reload the browser tab: `Cmd+Shift+R` (macOS) / `Ctrl+Shift+F5` (Windows/Linux).
4. If still stale after 2 minutes, click **Settings → Restart this Space** to force a rebuild.

#### 6. App logs show "ImportError" or per-user data leaks after deploy

**Cause.** A new module or per-user invariant (e.g. the `state_manager` per-user partitioning shipped on 2026-04-20) was introduced in `dev` but not exercised in tests, so a regression slipped through.

**Fix.**
1. Roll back the Space to the previous good commit while you investigate:
   ```bash
   git push hf-streamlit <previous-good-sha>:main --force
   ```
2. Reproduce locally: `streamlit run Home.py`, sign in as two distinct users in two browser profiles, and confirm the failure mode.
3. Add a regression test (see `tests/test_state_manager_isolation.py` for the fake-Streamlit fixture pattern), fix on `claude/<branch>`, merge to `dev`, redeploy.

**Post-deploy verification:**

```bash
# Should print the deploy commit you just pushed.
git log hf-streamlit/main --oneline -1

# Tree-level diff should be empty if the deploy is in sync with dev.
git diff --stat origin/dev hf-streamlit/main
```

Then open [the Space](https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard) and watch the "Building" → "Running" transition in the top-right status badge.

### Cloud Connector Dependencies

All cloud connector imports are optional (`try/except`), so missing packages never crash the app. For cloud data access, install only the packages you need:

```
boto3>=1.28.0              # AWS S3
google-cloud-bigquery>=3.0  # GCP BigQuery
google-cloud-storage>=2.0   # GCP Cloud Storage
azure-storage-blob>=12.0    # Azure Blob Storage
deltalake>=0.17.0           # Delta Lake tables (no Spark required)
```

The deployed HuggingFace Spaces already include all cloud dependencies in their `requirements.txt`.

---

## CI & Repository Hygiene

### GitHub Actions (`.github/workflows/test.yml`)

Triggers on every push to `main`, `dev`, and any `claude/**` branch, and on every PR targeting `main` or `dev`.

| Job | What it does | Why |
| --- | --- | --- |
| `pytest` (matrix: 3.12, 3.13) | `pip install -r requirements.txt && pip install pytest && pytest tests/ -v --tb=short --color=yes` | 3.12 = local dev, 3.13 = HF Space runtime. Both must stay green so a Python-version-specific regression (e.g. an stdlib API that changed between minor versions) is caught before merge. |

**Concurrency:** `cancel-in-progress: true` cancels superseded runs on rapid pushes.

**pip cache:** keyed on `requirements.txt` content. First run takes ~90s; subsequent runs ~10s.

**Failure artifacts:** `.pytest_cache/` and `tests/**/__snapshots__/` are uploaded for 7 days on failure to make remote triage easier.

### Pre-push hook (`scripts/git-hooks/pre-push`)

Blocks any push to the `hf-streamlit` remote whose tip doesn't match `origin/dev`. Documented in detail in `scripts/git-hooks/README.md`.

**Activate (once per clone):**

```bash
git config core.hooksPath scripts/git-hooks
```

**The contract.** Deploys to the HF Space `main` branch must originate from `origin/dev` (which gates merges through PR + CI). The hook reads stdin in `<local-ref> <local-sha> <remote-ref> <remote-sha>` format, intervenes only when:

- The remote URL contains `huggingface.co/spaces/`, AND
- The push targets `refs/heads/main`, AND
- `local_sha != $(git rev-parse origin/dev)`.

When these match, the hook fails with a diagnostic that prints both SHAs (with their commit messages), the deploy procedure, and the bypass command.

**Bypass for an emergency hotfix:**

```bash
git push --no-verify hf-streamlit <sha>:main
```

The `--no-verify` flag is the standard Git escape hatch — use it sparingly and document why in the deploy commit message.

**Verification.** After installing:

```bash
git config --get core.hooksPath        # → scripts/git-hooks
```

A push to `origin` (any branch) is unaffected. A push to `hf-streamlit refs/heads/main` of any SHA other than `origin/dev`'s tip is refused.

### Regression test pattern (init-ordering)

`tests/test_data_collector_page_init.py` pins the fix for the 2026-04-20 production `AttributeError`. It has two layers:

1. **Behavioural test** — replays the user's page-navigation order (`utils/pipeline_refresh.py` seeds `st.session_state["data_collector"]`, then the user opens the Data Collector page, then the page top-level reads `data_collector_results`) and asserts both keys are initialised.
2. **Structural test** — AST-walks `pages/2_Data_Collector.py` and asserts that `data_collector_results` is **not** assigned inside the `if "data_collector" not in st.session_state:` block. A future refactor that re-merges the two guards fails this test before the bug ships.

**This pattern (behavioural + structural AST guard) is reusable** for any other page that has independent session-state keys initialised together. See "Test gaps" in any caveat-audit output for candidates.

### `.gitignore` & binary file policy

The HuggingFace pre-receive hook scans the **full history** of every pushed branch for files xet/LFS would track. A binary added in commit A and removed in commit B is still in the pushed history, so HF rejects the push.

**Policy:** keep large binaries (`.pptx`, `.pdf`, `.png` over a few hundred KB, generated images, etc.) out of the repo entirely. Move them to an out-of-tree folder and reference them in `.gitignore`. If a binary already snuck in:

- **One-off:** use the `git commit-tree` recovery flow (see [Deployment → Recovery deploy](#deploying-from-github-to-the-streamlit-space)).
- **Permanent:** scrub history with `git filter-repo --invert-paths --path <file>` (destructive — coordinate with the team first; everyone needs to re-clone).

The 2026-04-20 `.pptx` incident was permanently fixed via the latter; standard deploys now work without the recovery dance.

---

## Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `TypeError: unhashable type: 'dict'` | jinja2 + starlette version mismatch | Force-install `starlette==0.36.3 jinja2==3.1.4` |
| `TypeError: argument of type 'bool' is not iterable` | Gradio API info generation bug | Monkey-patch `_json_schema_to_python_type` (already applied in `gradio_app.py`) |
| `ValueError: Could not find a server` | Gradio localhost health check fails in Docker | Patch `gradio.networking.url_ok = lambda url: True` (already applied) |
| `TypeError: text_area() got an unexpected keyword argument 'type'` | Streamlit `st.text_area()` doesn't support `type="password"` | Use `st.text_input(type="password")` for credential fields |
| Agents return empty/N/A data | Dependencies not run first | Run full pipeline or run prerequisite agents first |
| `ModuleNotFoundError: No module named 'pyarrow'` | Streamlit dataframe dependency missing | Install `pyarrow` or rely on the built-in HTML table fallback |
| Chart areas show placeholder messages | `plotly` missing in local env | Install `plotly` for full charts, or continue with fallback mode |
| No AI narratives generated | HF_API_TOKEN not set | Set token in sidebar or env var (fallback mode still works) |
| Cloud connector "not installed" | Optional dependency missing | Install with pip (see Connectors section) |
| Delta Lake "deltalake not installed" | `deltalake` package not installed | `pip install deltalake` |
| Delta Lake cloud table fails | Missing storage credentials | Provide `storage_options_json` with cloud credentials (see Delta Lake Connector section) |
| Folder mode returns empty DataFrame | No supported files under prefix | Ensure files have extensions: `.csv`, `.json`, `.xlsx`, `.xls`, `.parquet` |
| S3/GCS/Azure "No supported files found" | Path doesn't end with `/` | Append `/` to enable folder mode (e.g., `data/esg/` not `data/esg`) |
| Uploaded Excel file ignored by pipeline | `.xlsx`/`.xls` not handled in Phase 3 (now fixed — use latest version) | Update to latest version; use `.csv` if issue persists on older builds |
| Data not reflected in calculations after upload | "Save Data Source" step was skipped | Now auto-registered on Test & Preview; check that the green banner appears in ESG Command Center before running |
| Pipeline uses sample data despite upload | `connection_manager` not passed to orchestrator (now fixed) | Update to latest version; verify the green banner in ESG Command Center shows registered sources before clicking Run |
| Icon text shows instead of icon symbol (e.g. "arrow_forward" as text) | Material Symbols font overridden by body font CSS rule | Now fixed; hard-refresh the browser (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows/Linux) to clear the cached stylesheet |
| Raw HTML tags visible on Sign In page or other pages | `st.markdown()` HTML string had 8+ spaces of leading indentation, triggering CommonMark indented-code-block rule | Now fixed; if running locally, delete `__pycache__` directories and restart Streamlit |
| Agent page shows stale data after editing a Snowflake query / S3 key / Sheet ID | Page was built before the refresh helper was added, or `refresh_real_data()` was removed from the Run handler | Re-add `from utils.pipeline_refresh import refresh_real_data, data_freshness_caption` and call `refresh_real_data()` in a spinner before the agent's `.run()` (pattern used on pages 3–9, 11). |
| "Refreshed 2 hr ago" caption on an agent page right after a full-pipeline run | ESG Command Center forgot to stamp the session-state keys | Verify `stamp_refresh_from_pipeline(...)` is called inside the `run_pipeline` block in `pages/1_ESG_Command_Center.py` after `orch.run_full_pipeline(...)` completes. |
| Source silently returns empty DataFrame, agents fall back to sample data with no warning | Connector errored but the page isn't calling `refresh_real_data()` (which surfaces `source_errors()` as `st.warning()`) | Wire the helper in; or call `conn_mgr.source_errors()` manually and render warnings in the page. |
| Removed a source but old data still appears in carbon / risk / audit totals | Stale `dataset_{schema}` channel in `state_manager` from a previous run | Click Run on any agent page once — the helper clears `dataset_*` / `validated_*` channels before the Data Collector republishes. For a full wipe: `state_manager.clear()`. |
| Unchanged Snowflake query re-executes on every Run (slow / costly) | Default `refresh_real_data()` call re-fetches all sources | Call `refresh_real_data(only_changed=True)` in the Run handler to reuse per-source cached DataFrames when config signatures match. |
| Changed Snowflake table rows aren't visible even though the query is the same | With `only_changed=True`, cache is keyed on config signature, not on remote row counts | Edit the query (anything triggers a new signature), click "Test" on the Data Collector page, or call `conn_mgr.invalidate_cache(source_id)` to force the next fetch. |
| `AttributeError: st.session_state has no attribute "data_collector_results"` on Data Collector page after navigating from ESG Command Center / ROI | Combined session-state init guard short-circuited because `utils/pipeline_refresh.py` pre-populated `data_collector` | Now fixed by splitting into two independent guards in `pages/2_Data_Collector.py`. Pinned by `tests/test_data_collector_page_init.py` (behavioural + AST structural). |
| Sidebar shows "Storage: Local JSON (ephemeral)" on the deployed Space | `HF_TOKEN` not set, or the token doesn't have write access to the configured dataset | Set `HF_TOKEN` as a Space secret with **Write** scope. The diagnostic also surfaces the last persistence error in an expander. |
| User's accounts / sources / profiles vanish after a Space rebuild | Storage backend resolved to `local_json` (ephemeral container FS) instead of `hf_dataset` | Same as above — set `HF_TOKEN`. After fixing, signups will land in the dataset and survive rebuilds. |
| Cookies invalidated on every Space rebuild → users get logged out | `SESSION_SECRET` not set, falling back to `.streamlit/.session_secret` (ephemeral) or process-random | Set `SESSION_SECRET` as a Space secret to a stable random string. |
| Two concurrent users see each other's pipeline output | Pre-isolation `state_manager` was process-global | Now fixed — `core/state_manager.py` partitions every channel by user ID. Pinned by `tests/test_state_manager_isolation.py`. |
| Push to HF Space rejected by `pre-push` hook with "Refusing to deploy" | Local SHA doesn't match `origin/dev` — deploy contract is `git push hf-streamlit dev:main` | Run `git fetch origin && git push hf-streamlit origin/dev:main`. For an emergency hotfix only, `git push --no-verify hf-streamlit <sha>:main`. |
| Push to HF Space rejected with `pre-receive hook declined` mentioning a binary file no longer in the repo | HF scans full pushed history; the binary is still in old commits | Use the `git commit-tree` recovery flow (RUNBOOK → Deployment → "Recovery deploy"); permanently fix with `git filter-repo --invert-paths --path <file>`. |
| CI fails on Python 3.13 but passes on 3.12 (or vice versa) | Stdlib API or behaviour changed between versions | Both are required — the HF Space runs 3.13, local dev runs 3.12. Reproduce with `pyenv install 3.13 && pyenv shell 3.13 && pytest tests/`. |

### Checking Agent State

```python
from core.state_manager import state_manager

# See what's been published
channels = state_manager.get_all_channels()
for ch, info in channels.items():
    print(f"{ch}: published by {info['published_by']} at {info['timestamp']}")

# Check specific data
carbon = state_manager.subscribe("carbon_results")
```

### Resetting State

```python
from core.state_manager import state_manager
state_manager.clear()  # Wipe all channels — agents will need to re-run
```

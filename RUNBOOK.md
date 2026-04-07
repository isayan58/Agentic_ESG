# ESG CoPilot — Agent Runbook

Complete technical reference for all 8 AI agents: architecture, calculations, scoring logic, data flows, and operational procedures.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Agent Dependency Graph](#agent-dependency-graph)
3. [Core Infrastructure](#core-infrastructure)
4. [Agent 1: Data Collector](#agent-1-data-collector)
5. [Agent 2: Regulatory Tracker](#agent-2-regulatory-tracker)
6. [Agent 3: Carbon Accountant](#agent-3-carbon-accountant)
7. [Agent 4: Report Generator](#agent-4-report-generator)
8. [Agent 5: Risk Predictor](#agent-5-risk-predictor)
9. [Agent 6: Audit Agent](#agent-6-audit-agent)
10. [Agent 7: Action Agent](#agent-7-action-agent)
11. [Agent 8: Stakeholder Agent](#agent-8-stakeholder-agent)
12. [Data Connectors](#data-connectors) (incl. Delta Lake, folder/prefix mode)
13. [Schema Mapping & Validation](#schema-mapping--validation)
14. [AI Models & Fallbacks](#ai-models--fallbacks)
15. [Deployment](#deployment)
16. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    ESG CoPilot Platform                      │
├─────────────────────────────────────────────────────────────┤
│  UI Layer:  Streamlit (9 pages)   |  Gradio (tabbed)        │
├─────────────────────────────────────────────────────────────┤
│  Orchestrator: Manages dependency graph & pipeline execution │
├─────────────────────────────────────────────────────────────┤
│  8 Agents: Each inherits BaseAgent, uses HFClient           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Data     │→│ Regulatory│→│ Carbon   │→│ Risk     │       │
│  │ Collector│ │ Tracker   │ │ Accountant│ │ Predictor│       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Report   │→│ Audit    │→│ Action   │→│Stakeholder│      │
│  │ Generator│ │ Agent    │ │ Agent    │ │ Agent     │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
├─────────────────────────────────────────────────────────────┤
│  State Manager (pub/sub)  |  HF Inference API  |  Connectors│
├─────────────────────────────────────────────────────────────┤
│  Data: CSV/JSON samples  |  Real Sources  |  Cloud Storage   │
└─────────────────────────────────────────────────────────────┘
```

**Tech Stack:**
- Python 3.11+
- Streamlit (dashboard) / Gradio (single-page app)
- HuggingFace Inference API (Mistral-7B, BART, DistilBERT)
- Pandas, Plotly, NumPy
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
  6. report_generator     → depends on: audit_agent, carbon_accountant, risk_predictor
  7. action_agent         → depends on: risk_predictor, audit_agent, report_generator
  8. stakeholder_agent    → depends on: action_agent, report_generator
```

**State Manager Channels** (pub/sub keys):

| Channel | Published By | Subscribed By |
|---------|-------------|---------------|
| `validated_{dataset}` | Data Collector | — |
| `data_collection_results` | Data Collector | Audit Agent, Report Generator |
| `regulatory_results` | Regulatory Tracker | Risk Predictor, Audit Agent, Report Generator, Action Agent |
| `carbon_results` | Carbon Accountant | Audit Agent, Report Generator, Stakeholder Agent, Action Agent |
| `risk_results` | Risk Predictor | Action Agent, Stakeholder Agent |
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

### Orchestrator (`core/orchestrator.py`)

```python
orchestrator = Orchestrator()
orchestrator.run_full_pipeline(progress_callback=None)  # All 8 agents in dependency order
orchestrator.run_single_agent("carbon_accountant")      # Single agent
orchestrator.get_agent("data_collector")                # Access agent instance
```

### HFClient (`core/hf_client.py`)

Wraps HuggingFace Inference API with automatic fallback:

| Method | Model | Fallback |
|--------|-------|----------|
| `generate_text(prompt)` | Mistral-7B-Instruct-v0.3 | Rule-based keyword templates |
| `summarize(text)` | BART-large-CNN | First 3 sentences |
| `classify(text, labels)` | BART-large-MNLI (zero-shot) | Deterministic hash-based scoring |
| `analyze_sentiment(text)` | DistilBERT-SST-2 | Keyword positive/negative counting |

---

## Agent 1: Data Collector

**Class:** `DataCollectorAgent` (`agents/data_collector.py`)
**Purpose:** Auto-discovers, ingests, and validates ESG data from multiple sources.

### Execution Phases

| Phase | Description |
|-------|-------------|
| 0 | Fetch from real data sources via ConnectionManager (if configured) |
| 1 | Load 6 local sample datasets (emissions, esg_metrics, supply_chain, energy, waste, diversity) |
| 2 | Auto-discover from enterprise connectors (SAP ERP, Workday HR, IoT, EcoVadis, PostgreSQL, CDP/MSCI) |
| 3 | Process user-uploaded files (CSV/JSON) |
| 4 | Detect missing data — proactive gap alerts |
| 5 | Compute overall quality |
| 6 | AI-powered quality issue classification |
| 7 | Assign verifiable confidence scores |

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
- `data_collection_results` → data quality info

### Report Sections Generated

1. **Executive Summary** — AI-generated 3-4 sentences using company profile + carbon + compliance data
2. **Environmental Performance** — narrative + metrics table (pillar == "Environmental")
3. **Social Performance** — narrative + metrics table (pillar == "Social")
4. **Governance Performance** — narrative + metrics table (pillar == "Governance")
5. **Framework Sections** — per-framework compliance percentages and gap counts
6. **Carbon Highlights** — total emissions, YoY change, carbon intensity
7. **Compliance Summary** — overall + per-framework percentages
8. **Audit Trail** — timestamped steps (data collection, validation, report generation)

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

---

## Agent 6: Audit Agent

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

For each of 6 expected datasets:

| Dataset | Label | Priority |
|---------|-------|----------|
| emissions | Scope 1/2/3 Emissions Data | critical |
| esg_metrics | ESG KPI Metrics | critical |
| supply_chain | Supply Chain Data | high |
| energy | Energy Consumption Data | high |
| waste | Waste Management Data | medium |
| diversity | Workforce Diversity Data | medium |

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

---

## Agent 7: Action Agent

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

---

## Agent 8: Stakeholder Agent

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

ESG CoPilot supports 9 data connector types. All are defined in `utils/real_connectors.py`.

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

The `ConnectionManager` class (`utils/connection_manager.py`) manages multiple registered data sources in a session-scoped registry:

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
```

---

## Schema Mapping & Validation

### ESG Schemas

6 target schemas defined in `utils/schema_mapper.py`:

| Schema | Key Columns | Use Case |
|--------|------------|----------|
| `emissions` | scope, category, emissions_tco2e, year, quarter | Scope 1/2/3 carbon accounting |
| `esg_metrics` | metric_id, metric_name, pillar, unit, value_2024, target_2024, status | KPI tracking |
| `supply_chain` | supplier_name, country, sector, esg_score, risk_rating, emission_contribution_tco2e | Supplier risk |
| `energy` | facility, energy_source, consumption_mwh, renewable, year | Energy mix |
| `waste` | waste_type, quantity_tonnes, disposal_method, year | Waste management |
| `diversity` | department, gender, count, percentage, year | Workforce diversity |

### Auto-Detection

`auto_detect_schema(df)` uses a scoring heuristic:
1. Check for indicator columns (e.g., "emissions_tco2e" → emissions, "metric_id" → esg_metrics)
2. Score each schema by counting how many of its column names appear in the DataFrame
3. Return the highest-scoring schema (or None if no match)

### Column Mapping

`suggest_column_mapping(df, target_schema)` matches source columns to ESG schema columns:
1. Exact name match
2. Normalized match (lowercase, strip whitespace/underscores)
3. Synonym matching via `_SYNONYMS` dict (e.g., "co2" → "emissions_tco2e")

### Validation

`validate_mapped_data(df, target_schema)` returns:
```python
{
    "errors": ["Missing required column: ..."],
    "warnings": ["Optional column not mapped: ..."],
    "stats": {"rows": int, "columns_mapped": int, "columns_total": int, "completeness": float}
}
```

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

## Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `TypeError: unhashable type: 'dict'` | jinja2 + starlette version mismatch | Force-install `starlette==0.36.3 jinja2==3.1.4` |
| `TypeError: argument of type 'bool' is not iterable` | Gradio API info generation bug | Monkey-patch `_json_schema_to_python_type` (already applied in `gradio_app.py`) |
| `ValueError: Could not find a server` | Gradio localhost health check fails in Docker | Patch `gradio.networking.url_ok = lambda url: True` (already applied) |
| `TypeError: text_area() got an unexpected keyword argument 'type'` | Streamlit `st.text_area()` doesn't support `type="password"` | Use `st.text_input(type="password")` for credential fields |
| Agents return empty/N/A data | Dependencies not run first | Run full pipeline or run prerequisite agents first |
| No AI narratives generated | HF_API_TOKEN not set | Set token in sidebar or env var (fallback mode still works) |
| Cloud connector "not installed" | Optional dependency missing | Install with pip (see Connectors section) |
| Delta Lake "deltalake not installed" | `deltalake` package not installed | `pip install deltalake` |
| Delta Lake cloud table fails | Missing storage credentials | Provide `storage_options_json` with cloud credentials (see Delta Lake Connector section) |
| Folder mode returns empty DataFrame | No supported files under prefix | Ensure files have extensions: `.csv`, `.json`, `.xlsx`, `.xls`, `.parquet` |
| S3/GCS/Azure "No supported files found" | Path doesn't end with `/` | Append `/` to enable folder mode (e.g., `data/esg/` not `data/esg`) |

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

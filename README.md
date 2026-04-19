---
title: ESG CoPilot Dashboard
emoji: 🌍
colorFrom: red
colorTo: yellow
sdk: streamlit
sdk_version: 1.56.0
app_file: Home.py
pinned: false
license: mit
---

# ESG CoPilot: Autonomous ESG Intelligence

> From manual compliance to autonomous ESG excellence.

ESG CoPilot is an agentic AI platform for enterprise ESG intelligence. It connects fragmented enterprise data, monitors changing regulations, automates carbon accounting, predicts ESG risk, and generates audit-ready reporting — all from one coordinated multi-agent system.

| | |
| --- | --- |
| **Product** | Agentic AI platform for ESG intelligence |
| **Users** | Enterprise ESG, compliance, sustainability, audit, and reporting teams |
| **Core promise** | Turn fragmented data into predictive, audit-ready ESG outputs |
| **Operating model** | Continuous monitoring instead of periodic manual reporting |

**Live Demos:**

| Interface | URL |
| --- | --- |
| Gradio (Interactive) | [huggingface.co/spaces/isayan58/ESG-CoPilot](https://huggingface.co/spaces/isayan58/ESG-CoPilot) |
| Streamlit (Dashboard) | [huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard](https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard) |

---

## The Problem

Most ESG programs still depend on:

- Siloed data across ERP, HR, finance, supplier, and operational systems
- Manual collection and reconciliation in spreadsheets
- Slow reporting cycles that take weeks or months
- Constant regulatory change across frameworks such as BRSR, CSRD, GRI, and SASB
- Reactive compliance processes with limited forecasting or decision support

This creates a gap between what enterprises are expected to report and what their existing systems can reliably produce.

## The Solution

ESG CoPilot is an agentic AI layer for ESG operations. Instead of treating reporting as a periodic manual task, it treats ESG as an always-on intelligence workflow.

Core outcomes:

- Autonomous data ingestion from enterprise systems and cloud storage
- Real-time data quality monitoring and confidence scoring
- Faster report generation with audit trails built in
- Automated regulatory tracking and gap analysis
- Scope 1, 2, and 3 carbon intelligence with supply chain X-Ray
- Predictive risk modeling and scenario analysis
- Prioritized action recommendations with implementation roadmaps
- Audience-tailored stakeholder communications

---

## Autonomous Agent Network

At the center of the platform is the CoPilot Engine (orchestrator), managing nine specialized agents in a dependency graph:

```
Pipeline Execution Order:

  1. Data Collector       ─── (no dependencies)
       ├──→ 2. Regulatory Tracker
       ├──→ 3. Carbon Accountant
       └──→ 4. Risk Predictor ←── Regulatory Tracker
                  ├──→ 5. Audit Agent ←── Regulatory + Carbon
                  ├──→ 6. ESG ROI Agent ←── Carbon + Risk
                  │         ├──→ 7. Report Generator ←── Audit + Carbon + Risk + ROI
                  │         └──→ 8. Action Agent ←── Risk + Audit + Report + ROI
                  └──→ 9. Stakeholder Agent ←── Action + Report
```

| Agent | Role | Key Outputs |
| --- | --- | --- |
| **Data Collector** | Pulls and structures ESG data from 9 connector types | Quality scores, confidence levels, gap alerts |
| **Regulatory Tracker** | Maps data against BRSR, CSRD, GRI, SASB requirements | Compliance %, gap analysis, remediation guidance |
| **Carbon Accountant** | Tracks Scope 1/2/3 emissions, energy, supply chain | Emissions breakdown, YoY trends, hotspot detection |
| **Risk Predictor** | Forecasts climate, supplier, and ESG rating risks | Risk scores, scenario analysis, rating predictions |
| **Audit Agent** | Validates traceability, confidence, and evidence | Readiness score (A-D grade), compliance checklist |
| **ESG ROI Agent** | Converts ESG performance into financial and strategic return signals | Dual ROI, J-curve, Investment Quality Score |
| **Report Generator** | Produces board-ready, multi-framework ESG reports | 5 report types with AI-generated narratives |
| **Action Agent** | Recommends follow-up actions with cost-benefit analysis | Prioritized action items, implementation roadmap |
| **Stakeholder Agent** | Shapes outputs for investors, regulators, employees, public | Audience-tailored messages with tone analysis |

Recent platform enhancements:

- Canonical dataset flow via `core/data_access.py`, so downstream agents prefer collected and validated state over bundled sample reloads.
- KPI Engine and ESG ROI Agent are now part of the live orchestrated pipeline instead of being standalone-only logic.
- Action planning now includes implementation friction, transaction-cost adjustments, liquidity risk, net ROI, and suggested targets.
- Local Streamlit fallback support now avoids hard failures when `pyarrow` or `plotly` are missing in constrained environments.

### What sets this platform apart

| Capability | What it answers |
| --- | --- |
| **5 Value Creation Channels** (Growth, Cost, Risk, Human Capital, Capital Efficiency) | How is ESG performance actually moving the P&L? |
| **Dual ROI Framework** (Financial + Strategic) | What is the tangible return on our ESG spend, and what is the soft value (brand, cost-of-capital, talent)? |
| **ESG Investment Quality Score (IQS)** | Is our ESG CapEx generating real business value? Letter grade A+ to D. |
| **J-Curve Payback Modeller** | When will our ESG investments break even, and how deep is the trough? |
| **ESG Integrity Gap Detector** | Where do self-reported metrics diverge from operational data? (73%+ greenwashing-style mismatches surface here) |
| **Market Regime Detection** (Bull / Transition / Stress) | Should we lead with growth framing or defensive framing given today's cycle? |
| **Downside Protection Score** | How well does our ESG posture shield us from negative shocks? |
| **Multi-Agency Rating Translations** (MSCI / Sustainalytics / CDP) | How does our ESG performance read on each major external scale? |
| **Emissions → Cost Linkage & Carbon Tax Risk** | What are our current and projected (3-yr, CBAM) carbon tax exposures? |
| **Implementation Friction & Net ROI per Action** | Which actions actually survive execution realism — accounting for regime, category, liquidity, and transaction cost? |

---

## Data Connectors

ESG CoPilot supports 9 data connector types — from local files to cloud data lakes:

| Connector | Type | Features |
| --- | --- | --- |
| **File Upload** | Local | CSV, Excel (.xlsx/.xls), JSON |
| **Google Sheets** | Web | Public sheets via CSV export URL |
| **REST API** | Web | Any JSON endpoint (GET/POST), custom headers |
| **SQL Database** | Enterprise | PostgreSQL, MySQL, SQLite via SQLAlchemy |
| **AWS S3** | Cloud | Single file or folder/prefix mode (reads all files under a path) |
| **Google BigQuery** | Cloud | SQL queries against BigQuery datasets |
| **Google Cloud Storage** | Cloud | Single file or folder/prefix mode |
| **Azure Blob Storage** | Cloud | Single file or folder/prefix mode |
| **Delta Lake** | Data Lake | Local or cloud Delta tables with version pinning, column selection, row filters |

Cloud connectors support **folder mode** — provide a path ending with `/` to automatically discover and concatenate all supported files (CSV, JSON, Excel, Parquet) under that prefix.

All external imports are optional. Missing packages show install hints instead of crashing.

---

## ETL Engine

ESG CoPilot ships its own lightweight ETL engine rather than depending on Airflow, dbt, Prefect, Dagster, or any external orchestrator. Everything runs in-process on the Streamlit replica — zero scheduler, zero worker pool, zero broker.

The engine has four layers:

| Layer | Module | Responsibility |
| --- | --- | --- |
| **Connectors** | `utils/real_connectors.py`, `utils/connectors.py` | Per-source `fetch(**config) → DataFrame` adapters for every data connector listed above. Lazy imports so a missing cloud SDK doesn't block the app. |
| **Schema mapping** | `utils/schema_mapper.py` | Auto-detects canonical schema (`emissions`, `esg_metrics`, `supply_chain`, `energy`, `waste`, `diversity`, `financials`) from raw columns; suggests a column mapping; applies it so downstream agents see canonical names. |
| **Orchestration** | `utils/connection_manager.py` | Per-user registry of configured sources. SHA-256 **config signatures** drive a per-source cache so an unchanged query doesn't re-execute on every pipeline Run. `fetch_all_by_schema()` concatenates multiple sources targeting the same schema. |
| **Publication** | `core/state_manager.py`, `core/data_access.py` | After fetch + map, each DataFrame is published to a pub/sub channel (`dataset_<schema>`). Every downstream agent reads via `get_dataset(schema)` so they transparently consume real data when it's present and fall back to bundled samples otherwise. |

Refresh flow on each Mission Control **Run**:

1. `utils/pipeline_refresh.refresh_real_data()` walks the signed-in user's registered sources.
2. Each source is fetched through its connector; the column mapping runs; the result is signature-hashed.
3. Unchanged signatures hit the cache; changed ones repopulate it and publish to shared state.
4. Agents then execute against canonical datasets — no agent talks to a connector directly.

Personalisation note: both the **source registry** and the **company profile** are per-user and persisted to a private HuggingFace Dataset (`utils.source_store`, `utils.profile_store`). Each signed-in user drives the ETL engine against their own inputs, with their own thresholds, on their own profile — concurrent users on the same Space replica see isolated data via a thread-local `CompanyConfig` proxy.

See `RUNBOOK.md` → *Data ETL & freshness* for deeper internals including cache invalidation, concurrency guarantees, and error surfacing.

---

## Project Structure

```
.
├── app.py                              # Main Streamlit entry point
├── config.py                           # HF API config, model names, company profile
├── gradio_app.py                       # Gradio tabbed interface (all agents)
├── requirements.txt
├── RUNBOOK.md                          # Full technical runbook (850+ lines)
├── core/
│   ├── base_agent.py                   # Abstract base agent class
│   ├── data_access.py                  # Canonical dataset retrieval from shared state
│   ├── hf_client.py                    # HuggingFace Inference API wrapper + fallbacks
│   ├── kpi_engine.py                   # ESG-to-financial KPI and value-channel engine
│   ├── state_manager.py               # Pub/sub state bus for inter-agent data sharing
│   └── orchestrator.py                # Dependency graph pipeline runner
├── agents/
│   ├── data_collector.py              # Agent 1: Data ingestion + quality scoring
│   ├── regulatory_tracker.py          # Agent 2: Framework compliance gap analysis
│   ├── carbon_accountant.py           # Agent 3: Scope 1/2/3 emissions accounting
│   ├── report_generator.py            # Agent 7: Multi-framework ESG reports
│   ├── risk_predictor.py              # Agent 4: Climate & ESG risk forecasting
│   ├── audit_agent.py                 # Agent 5: Compliance verification & audit readiness
│   ├── roi_agent.py                   # Agent 6: Dual ROI, J-curve, investment quality
│   ├── action_agent.py               # Agent 8: Prioritized recommendations
│   └── stakeholder_agent.py          # Agent 9: Audience-tailored communications
├── pages/
│   ├── 1_Mission_Control.py           # Overview dashboard — KPIs, pipeline runner
│   ├── 2_Data_Collector.py            # Data sources, connectors, schema mapping
│   ├── 3_Regulatory_Tracker.py        # Compliance radar, gap analysis
│   ├── 4_Carbon_Accountant.py         # Emissions charts, supply chain X-Ray
│   ├── 5_Report_Generator.py          # Report builder with 5 report types
│   ├── 6_Risk_Predictor.py            # Risk gauges, scenario analysis
│   ├── 7_Audit_Agent.py              # Audit readiness, compliance checklist
│   ├── 8_Action_Agent.py             # Action items table, roadmap
│   ├── 9_Stakeholder_Agent.py        # Communication templates, tone analysis
│   └── 11_ESG_ROI_Agent.py           # ROI dashboard — dual ROI, J-curve, IQS
├── data/
│   ├── company_profile.json           # Fictional company: GreenTech Solutions Pvt. Ltd.
│   ├── regulatory_frameworks.json     # BRSR, CSRD, GRI, SASB requirements
│   ├── sample_financials.csv          # Quarterly finance, ESG capex, cost-of-capital data
│   ├── sample_emissions.csv           # Scope 1/2/3 quarterly emissions (2023-2024)
│   ├── sample_esg_metrics.csv         # 30 KPIs across E/S/G pillars
│   ├── sample_supply_chain.csv        # 20 suppliers with ESG scores + risk ratings
│   ├── sample_energy.csv              # Energy consumption by facility and source
│   ├── sample_waste.csv               # Waste management data
│   └── sample_diversity.csv           # Workforce diversity metrics
└── utils/
    ├── charts.py                       # Plotly chart builders (gauges, radars, heatmaps)
    ├── data_processing.py             # Common data helpers
    ├── real_connectors.py             # 9 data source connectors (file, cloud, Delta Lake)
    ├── connectors.py                  # Simulated enterprise connectors (SAP, Workday, etc.)
    ├── connection_manager.py          # Session-scoped source registry
    ├── schema_mapper.py               # ESG schema definitions + auto-mapping
    ├── streamlit_compat.py            # Fallback renderers for constrained local installs
    └── monitoring.py                  # Operational monitoring utilities
```

---

## Tech Stack

| Layer | Technologies |
| --- | --- |
| **AI** | HuggingFace Inference API — Mistral-7B, BART-large-CNN, BART-large-MNLI, DistilBERT-SST-2 |
| **Dashboard** | Streamlit (multi-page app, 10 pages including Mission Control + ROI page) |
| **Interactive UI** | Gradio (tabbed interface, all agents) |
| **Data** | Pandas, NumPy, Plotly, PyArrow |
| **Cloud (optional)** | boto3 (AWS), google-cloud-bigquery, google-cloud-storage (GCP), azure-storage-blob (Azure), deltalake (Delta Lake) |
| **Deployment** | Docker on HuggingFace Spaces |

All AI features include **rule-based fallbacks** — the platform works fully without an API token, making it demo-ready out of the box.

---

## Quick Start

### Prerequisites

- Python 3.11+
- (Optional) HuggingFace API token for AI-generated narratives

### Install & Run

```bash
# Clone
git clone https://github.com/isayan58/Agentic_ESG.git
cd Agentic_ESG

# Install dependencies
pip install -r requirements.txt

# Run Streamlit dashboard (port 8501)
streamlit run app.py

# OR run Gradio interface (port 7860)
python gradio_app.py
```

`pyarrow` is required for Streamlit's native `st.dataframe` rendering. If it is missing, the app falls back to static HTML tables for local constrained environments, but a full install should include `pyarrow`.

`plotly` powers the dashboard charts. In constrained local environments, the app now degrades gracefully and shows informational placeholders instead of crashing if chart dependencies are unavailable.

### Optional: Enable AI Narratives

Set your HuggingFace API token as an environment variable or enter it in the app sidebar:

```bash
export HF_API_TOKEN="hf_your_token_here"
```

Without the token, all agents still run using intelligent rule-based fallbacks.

### Optional: Cloud Connectors

Cloud connector dependencies are optional. Install only the ones you need:

```bash
pip install boto3                    # AWS S3
pip install google-cloud-bigquery    # Google BigQuery
pip install google-cloud-storage     # Google Cloud Storage
pip install azure-storage-blob       # Azure Blob Storage
pip install deltalake                # Delta Lake tables
```

---

## How It Works

1. **Connect your data** — Upload files, connect to cloud storage (S3, GCS, Azure, Delta Lake), or use APIs. The Data Collector validates quality, detects schemas, and maps columns to ESG standards.

2. **Run the pipeline** — The orchestrator executes all 9 agents in dependency order. The Data Collector publishes canonical datasets into shared state, and downstream agents consume those validated datasets before falling back to bundled samples.

3. **Explore results** — Navigate through 10 dashboard pages: compliance radar charts, emissions breakdowns, risk gauges, audit checklists, ROI views, and more.

4. **Generate reports** — Choose from 5 report types (Full ESG, Carbon & Environment, Framework Compliance, Social & Governance, Executive Summary). Reports now also incorporate ROI context and value-creation channel summaries when ROI results are available.

5. **Act on insights** — Review prioritized action items with timelines, cost estimates, friction adjustments, net ROI, and proposed targets. Share tailored communications with investors, regulators, employees, or the public.

---

## ESG Frameworks Supported

| Framework | Full Name | Jurisdiction |
| --- | --- | --- |
| **BRSR** | Business Responsibility and Sustainability Reporting | India (SEBI) |
| **CSRD** | Corporate Sustainability Reporting Directive | European Union |
| **GRI** | Global Reporting Initiative | Global |
| **SASB** | Sustainability Accounting Standards Board | Global |

---

## Sample Data

The platform ships with demo-ready sample data for **GreenTech Solutions Pvt. Ltd.**, a fictional Indian IT company:

- 8 quarters of Scope 1/2/3 emissions data (2023-2024)
- Quarterly financial and ESG-linked capex data for ROI and KPI analysis
- 30 ESG KPIs across Environmental, Social, and Governance pillars
- 20 suppliers with ESG scores, risk ratings, and emission contributions
- Energy consumption data by facility and source
- Waste management and workforce diversity metrics
- Regulatory framework requirements (BRSR, CSRD, GRI, SASB)

---

## Documentation

See **[RUNBOOK.md](RUNBOOK.md)** for the complete technical reference including:

- Architecture diagrams and agent dependency graph
- Every calculation formula and scoring threshold
- State manager pub/sub channels
- Connector interfaces and usage examples
- AI model assignments and fallback behavior
- Deployment and troubleshooting guide

---

## Business Impact

| Metric | Target |
| --- | --- |
| Reporting velocity | Up to 80% faster cycles |
| Team efficiency | Thousands of hours saved annually |
| Data confidence | Lower audit risk through validation and traceability |
| Monitoring model | Always-on ESG intelligence |

---

## Rollout Path

| Phase | Timeline | Goal |
| --- | --- | --- |
| Discover | 2 weeks | Assess the data landscape, systems, and reporting priorities |
| Build & PoC | 6 weeks | Connect core systems and produce initial autonomous outputs |
| Deploy & Scale | 12-16 weeks | Roll out enterprise-wide and activate the full multi-agent workflow |

---

## Platform Changes

This section documents verified changes introduced in recent development cycles.

---

### Authentication & Access Control

ESG CoPilot now ships with a lightweight but production-grade authentication layer (`utils/auth.py`, `pages/0_Sign_In.py`).

**How it works:**

- Passwords are stored as bcrypt hashes (never in plaintext).
- Sessions are managed via an [itsdangerous](https://itsdangerous.palletsprojects.com/) signed cookie with a 14-day expiry.
- Two storage backends are available:
  - `MemoryBackend` — default; stores users in RAM for the lifetime of the process. Suitable for Spaces demos.
  - `FileBackend` — persists users to `users.json` on disk. Use this for self-hosted deployments where you need accounts to survive restarts.
- Every page calls `sidebar_auth_widget()`, which renders a sign-in form or a sign-out button in the Streamlit sidebar depending on session state.
- Protected pages call `require_login()` at the top; unauthenticated visitors are redirected to the Sign In page.
- Once a user is authenticated, the Sign In page is hidden from the sidebar navigation via a CSS injection so the nav stays clean.

**To protect a page**, add this at the top of the page script:

```python
from utils.auth import require_login
require_login()
```

---

### Home Page & Design System

The application entry point has been renamed from `app.py` to `Home.py`. The README frontmatter (`app_file: Home.py`) and the HuggingFace Spaces configuration reflect this change.

The Home page has been fully redesigned as a product landing experience:

- **Hero section** — headline, sub-headline, and primary call-to-action.
- **Stat band** — key platform metrics in a horizontal strip.
- **Feature grid** — capability tiles with icons and short descriptions.
- **Agent tiles** — one tile per agent showing name, role, and status.
- **Trust strip** — frameworks, certifications, and data partnerships.
- **Footer** — links and legal notice.

**Typography** is loaded from Google Fonts:

| Role | Font |
| --- | --- |
| Display / headings | Plus Jakarta Sans |
| Body copy | Inter |
| Code blocks | JetBrains Mono |

---

### Data Upload → Pipeline Wiring

Four bugs in the upload-to-pipeline flow were identified and fixed. The correct end-to-end workflow is now:

**Step-by-step upload workflow:**

1. Go to **Data Collector → Connect Data Sources → File Upload**.
2. Upload a CSV, Excel (`.xlsx` / `.xls`), or JSON file.
3. Click **Test & Preview**. The file is immediately auto-registered with auto-detected schema. A confirmation message is shown — no additional save step is required.
4. Go to **Mission Control**. A green banner confirms that your real data sources are wired in.
5. Click **Run Full Pipeline**. Your uploaded data drives all calculations.

> **Note:** Data is session-scoped. It lives in RAM only and is lost on browser refresh or Space restart. See [Known Limitation: Session-Scoped Storage](#known-limitation-session-scoped-storage) below.

**Bugs fixed:**

| # | Bug | Root Cause | Fix |
| --- | --- | --- | --- |
| 1 | Upload required a separate "Save Data Source" click that users routinely missed | Auto-registration did not run on Test & Preview | "Test & Preview" now immediately auto-registers the source with auto-detected schema |
| 2 | Excel files were silently ignored | Phase 3 of `DataCollectorAgent.execute()` only handled `.csv` and `.json` | Added `pd.read_excel()` handling for `.xlsx` / `.xls` |
| 3 | Uploaded data never reached pipeline calculations | Files stored under their original filename (e.g. `my_data.xlsx`), never matching a `real_{schema}` canonical slot | Auto-detection now stores uploaded data under `real_{schema}` (e.g. `real_emissions`), giving it priority over sample data |
| 4 | `connection_manager` always arrived as `None` in the orchestrator | `Orchestrator.run_full_pipeline()` called `DataCollectorAgent.run()` with no kwargs | Added `data_collector_kwargs` parameter to `run_full_pipeline()`; Mission Control now reads `st.session_state.conn_manager` and passes it through |

---

### Known Limitation: Session-Scoped Storage

All data in ESG CoPilot is stored exclusively in process RAM. There is no database, no disk persistence, and no cross-session sharing.

| Stage | Where data lives |
| --- | --- |
| After Test & Preview | `st.session_state.preview_df`, `st.session_state.preview_config` |
| After auto-registration | `st.session_state.conn_manager._sources` |
| After pipeline run | `state_manager` pub/sub channels (process-wide RAM) |

**Practical implications:**

- Refreshing the browser tab clears all uploaded data and pipeline results.
- Restarting the Streamlit server (or a HuggingFace Space restart) clears everything.
- Multiple browser tabs do not share session data; each tab is its own isolated session.
- If you need to re-run the pipeline after a refresh, re-upload your file and click "Test & Preview" again before running.

There is currently no option to persist data to a database or download session state. This is a planned improvement.

---

## License

This project is proprietary. All rights reserved.

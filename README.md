---
title: ESG Pilot Dashboard
emoji: 🌍
colorFrom: red
colorTo: yellow
sdk: streamlit
sdk_version: 1.56.0
app_file: Home.py
pinned: false
license: mit
---

# ESG Pilot: Autonomous ESG Intelligence

> From manual compliance to autonomous ESG excellence.

ESG Pilot is an agentic AI platform for enterprise ESG intelligence. It connects fragmented enterprise data, monitors changing regulations, automates carbon accounting, predicts ESG risk, and generates audit-ready reporting — all from one coordinated multi-agent system.

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

ESG Pilot is an agentic AI layer for ESG operations. Instead of treating reporting as a periodic manual task, it treats ESG as an always-on intelligence workflow.

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

ESG Pilot supports 9 data connector types — from local files to cloud data lakes:

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

ESG Pilot ships its own lightweight ETL engine rather than depending on Airflow, dbt, Prefect, Dagster, or any external orchestrator. Everything runs in-process on the Streamlit replica — zero scheduler, zero worker pool, zero broker.

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

| Doc | Audience | What's in it |
| --- | --- | --- |
| **[RUNBOOK.md](RUNBOOK.md)** | Operators, on-call | Architecture, every agent's behaviour, ETL internals, deployment + troubleshooting (incl. HF Space deploy + recovery flows) |
| **[CALCULATIONS.md](CALCULATIONS.md)** | Analysts, auditors, anyone defending a number on screen | Every formula, weight, threshold, magic constant — pulled directly from the agent code with `file:line` citations. The "show your working" doc. |
| **[SCHEMA.md](SCHEMA.md)** | Data engineers preparing uploads | Canonical column names + expected types per schema (emissions, esg_metrics, supply_chain, energy, waste, diversity, financials) |
| **[TESTS.md](TESTS.md)** | Contributors | Test-suite layout, what each test pins, how to add a regression test |

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

This section documents verified functional and operational changes introduced in recent development cycles. Each entry names the user-visible behaviour, the affected modules, and (where relevant) the bug or production incident it closed.

**Quick index**

| Area | Entry |
| --- | --- |
| Identity & isolation | [Authentication](#authentication--access-control) · [Per-user state isolation](#per-user-state-isolation) · [Per-user persistence](#per-user-persistence-profile--source-store) |
| Data flow | [Pipeline refresh & data freshness](#pipeline-refresh--data-freshness) · [Snowflake connector](#snowflake-connector-promoted-to-first-class) · [Data Upload → Pipeline wiring](#data-upload--pipeline-wiring) |
| UI / theming | [Home page & design system](#home-page--design-system) · [PwC orange theming](#pwc-orange-theming--tagline) · [Material Symbols icon ligatures](#material-symbols-icon-ligatures-fixed) |
| Deploy / CI | [HF Space push guard (pre-push hook)](#hf-space-push-guard-pre-push-hook) · [CI matrix (Python 3.12 + 3.13)](#ci-matrix-python-312--313) · [`.pptx` history scrub](#pptx-history-scrub) |
| Reliability | [Data Collector init guard split (`AttributeError` fix)](#data-collector-init-guard-split-attributeerror-fix) · [HF persistence error surfacing](#hf-persistence-errors-now-surfaced-not-swallowed) |

---

### Authentication & Access Control

ESG Pilot now ships with a lightweight but production-grade authentication layer (`utils/auth.py`, `pages/0_Sign_In.py`).

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

All data in ESG Pilot is stored exclusively in process RAM. There is no database, no disk persistence, and no cross-session sharing.

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

### Per-user state isolation

`core/state_manager.py` was refactored from a process-global pub/sub bus to a per-user partitioned bus keyed on the signed-in user's ID. **Why it shipped:** under the previous design, two concurrent users on the same Streamlit replica saw each other's pipeline output — User B's "Run" would publish onto a shared channel that User A's page would then read.

**What changed operationally:**

- Every `state_manager.publish(channel, value, ...)` call now writes to `<user_id>:<channel>` under the hood. Reads are similarly scoped.
- A thread-local proxy resolves the active user from `st.session_state` on each call, so existing agent code did not need to be touched.
- Anonymous (signed-out) sessions get a synthetic per-session ID, so demo flows still work.
- Test pinning lives in `tests/test_state_manager_isolation.py` using a `FakeStreamlit` fixture in `tests/conftest.py`.

**Failure mode this prevents.** Two analysts at two desks loading their own `.xlsx` files no longer see each other's emission totals.

---

### Per-user persistence (profile + source store)

`utils/profile_store.py` (company profile) and `utils/source_store.py` (registered data sources) persist per-user state to a private HuggingFace Dataset when `HF_TOKEN` is set, with a local-JSON fallback otherwise. This replaces the earlier session-only behaviour for these two surfaces.

**Operational notes:**

- Backend resolution order: `hf_dataset` (preferred) → `local_json` (ephemeral) → in-memory.
- The active backend and the last persistence error surface in the sidebar via `_render_storage_diagnostic()`. **If you see "Local JSON (ephemeral)" on the deployed Space, the HF token is misset** — data will vanish on Space rebuild.
- HF errors (e.g. `EntryNotFoundError` wrapped as `ValueError` by `huggingface_hub`) are caught explicitly and surfaced in the diagnostic instead of silently degrading. See `RUNBOOK.md` → *Data ETL & freshness → Error surfacing*.

---

### Pipeline refresh & data freshness

`utils/pipeline_refresh.py` now centralises the "re-fetch every registered source on every Run" behaviour. Earlier, individual agent pages had drifted into different patterns — some called the connection manager directly, some never refreshed at all.

**What changed operationally:**

- Mission Control (`pages/1_Mission_Control.py`) calls `refresh_real_data()` inside the Run handler, then `stamp_refresh_from_pipeline(...)` after `orchestrator.run_full_pipeline(...)` completes, so the per-page "Refreshed N min ago" caption is accurate.
- Agent pages 3–9 and 11 each call `refresh_real_data()` in a spinner before invoking their `.run()`, then render `data_freshness_caption()` so the user can see when the data was last fetched.
- `refresh_real_data(only_changed=True)` reuses the per-source SHA-256 config-signature cache (in `utils/connection_manager.py`) to skip the remote round-trip when nothing changed — useful for slow Snowflake / BigQuery sources.
- Stale `dataset_*` / `validated_*` channels in `state_manager` are cleared before the Data Collector republishes, so removing a source actually removes its contribution from downstream totals.
- `conn_mgr.source_errors()` is rendered as `st.warning()` by the helper, so a connector that silently returns an empty DataFrame is now visible to the user.

See `RUNBOOK.md` → *Data Freshness & Pipeline Refresh* for the full API and behaviour matrix.

---

### Snowflake connector promoted to first-class

The Data Collector's connector list now includes Snowflake alongside the existing 9 (file, Sheets, REST, SQL, S3, BigQuery, GCS, Azure Blob, Delta Lake). Snowflake configuration covers account/warehouse/database/schema + a free-form SQL query, and integrates with the same per-source caching as the other connectors.

---

### PwC orange theming + tagline

The full UI now follows the PwC brand palette via `utils/ui.py:TOKENS`:

| Token | Hex | Usage |
| --- | --- | --- |
| `brand_primary` | `#D04A02` | Primary orange |
| `brand_primary_dark` | `#A23A02` | Hover / depth |
| `brand_accent` | `#E0301E` | Tomato accent |
| `brand_warn` | `#FFB600` | Amber warnings |

Two surfaces previously rendered in green were re-skinned to match: the "Authentication required" hero block on protected pages and the sidebar user-avatar gradient (`utils/auth.py`). The page header tagline is now `"Powered by PwC India"` (was `"Powered by PwC"`).

---

### Material Symbols icon ligatures (fixed)

Streamlit's icon spans were rendering as raw text — `"upload"`, `"keyboard_double_arrow_left"`, etc. — instead of the corresponding glyphs. Two compounding root causes:

1. The earlier global CSS used `[class*="st-"]` to set body typography, which matched Streamlit's `st-emotion-cache-*` icon spans and overrode the icon font.
2. `font-feature-settings` was set without `'liga' 1`, which the OpenType spec interprets as **disable all unlisted features** — including the ligature feature that converts `"upload"` → 📤.

**Fix in `utils/ui.py`:** body typography is now scoped narrowly to specific Streamlit containers (`stMarkdown`, `stText`, `stCaption`, app shell), and the `font-feature-settings` rule explicitly enables `'liga' 1`. Icon font links (Rounded, Outlined, Sharp, legacy Material Icons) are injected via `st.markdown` instead of a sandboxed `components.html` iframe so they reach the document head on HuggingFace Spaces.

---

### Data Collector init guard split (`AttributeError` fix)

**Production incident (2026-04-20):** users hitting Mission Control or the ESG ROI page first caused `utils/pipeline_refresh.py` to seed `st.session_state["data_collector"]`. When the user later navigated to the Data Collector page, this combined guard short-circuited:

```python
if "data_collector" not in st.session_state:
    st.session_state.data_collector = DataCollectorAgent()
    st.session_state.data_collector_results = None  # ← never ran
```

Line 626 of the page then exploded with `AttributeError: st.session_state has no attribute "data_collector_results"`.

**Fix in `pages/2_Data_Collector.py`:** split into two independent guards. **Regression coverage:** `tests/test_data_collector_page_init.py` pins both the behavioural fix (replays the production page-navigation order) and the structural fix (AST-walks the page file to assert the two guards remain separate, so a future refactor that re-merges them fails CI before the bug reaches production).

---

### HF persistence errors now surfaced, not swallowed

Earlier, `utils/user_store.py` and `utils/source_store.py` would silently fall back to local-JSON storage on any HF API error — including `huggingface_hub` wrapping `EntryNotFoundError` as a generic `ValueError`. The user saw "everything works" but their data quietly lived in an ephemeral container path.

**Fix:** specific exceptions are now matched and re-raised as the original error type, captured into `last_error`, and rendered in the sidebar storage diagnostic. The fallback to local-JSON still happens, but it's loud now.

---

### HF Space push guard (pre-push hook)

The HuggingFace Space's `main` branch has no native branch protection. On 2026-04-20 a stray push reverted `main` to a state ~7,300 lines behind. To prevent a recurrence, `scripts/git-hooks/pre-push` blocks any push to the `hf-streamlit` remote whose tip doesn't match `origin/dev`.

**Activate (once per clone):**

```bash
git config core.hooksPath scripts/git-hooks
```

**Bypass for an emergency hotfix:**

```bash
git push --no-verify hf-streamlit <sha>:main
```

The hook's diagnostic prints the offending SHA, the expected `origin/dev` tip, and the remediation steps. See `scripts/git-hooks/README.md`.

---

### CI matrix (Python 3.12 + 3.13)

`.github/workflows/test.yml` runs `pytest` on every push to `main`, `dev`, and `claude/**` branches plus every PR targeting `main` or `dev`. The matrix covers both Python 3.12 (local dev) and Python 3.13 (the HF Space runtime, per the production traceback). Both must stay green to merge.

- `concurrency.cancel-in-progress: true` cancels superseded runs on rapid pushes.
- `pip` cache keyed on `requirements.txt` keeps the second-onwards run under ~10s.
- On failure, the `.pytest_cache/` directory uploads as an artifact for triage.

---

### `.pptx` history scrub

A one-pager `.pptx` deck added to the repo earlier had since been deleted, but HuggingFace's xet/LFS pre-receive hook scans the **full history** of every pushed branch, not just the diff. That meant every standard deploy to the Space was rejected with `pre-receive hook declined`, forcing the use of the `git commit-tree` recovery flow.

**Permanent fix:** `git filter-repo --invert-paths --path <file>` scrubbed the binary from history. Standard deploys (`git push hf-streamlit dev:main`) now work without the recovery dance. The recovery flow is still documented in the RUNBOOK as a fallback for future similar incidents.

---

### Code architecture additions

| Module | Role | Why it was added |
| --- | --- | --- |
| `core/data_access.py` | Canonical dataset retrieval (`get_dataset(schema)`) | Single source of truth for "real data first, samples as fallback" — replaces ad-hoc lookups scattered across agents |
| `core/kpi_engine.py` | Cross-channel ESG-to-financial KPI engine | Powers the ROI Agent's value-creation channels (Growth, Cost, Risk, Human Capital, Capital Efficiency) |
| `core/company_config.py` | Per-user `CompanyConfig` proxy | Resolves the active user's company profile from `profile_store` on every access — supports concurrent users on one replica |
| `utils/streamlit_compat.py` | HTML table fallback when `pyarrow` is missing | Lets the app run in constrained local environments without crashing |
| `utils/profile_validator.py` | Profile schema validation | Catches malformed profile JSON before it reaches the orchestrator |
| `utils/gap_suggestions.py` | Remediation suggestions for regulatory gaps | Used by the Regulatory Tracker's gap narrative |
| `utils/industry_standards.py` | Industry-specific benchmarks for peer comparisons | Drives the ROI page's peer-benchmarking section |
| `utils/monitoring.py` | Operational counters / timers | Lightweight in-process telemetry, no external sink required |

---

## License

This project is proprietary. All rights reserved.

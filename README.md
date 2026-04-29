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

# ESG Pilot — Autonomous ESG Intelligence

> **Continuous ESG intelligence, not quarterly spreadsheet rituals.**
> Nine specialised AI agents, one orchestrator, six regulatory frameworks, every number traceable back to its source.

ESG Pilot is an agentic AI platform for enterprise ESG intelligence. It connects fragmented enterprise data, watches authoritative regulators for live mandate changes, automates Scope 1/2/3 carbon accounting, predicts climate and rating risk, and produces audit-ready reporting — all from one coordinated multi-agent pipeline that runs in-process on a single Streamlit replica.

| | |
| --- | --- |
| **Product** | Agentic AI platform for ESG intelligence |
| **Users** | Enterprise ESG, compliance, sustainability, audit, and reporting teams |
| **Core promise** | Turn fragmented data into predictive, audit-ready ESG outputs |
| **Operating model** | Continuous monitoring, not periodic manual reporting |
| **Architecture** | 9 agents · 6 frameworks · 9 connector types · per-user isolation · zero external scheduler |

**Live demos:**

| Interface | URL |
| --- | --- |
| Streamlit (Dashboard) | [huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard](https://huggingface.co/spaces/isayan58/ESG-CoPilot-Dashboard) |
| Gradio (Interactive) | [huggingface.co/spaces/isayan58/ESG-CoPilot](https://huggingface.co/spaces/isayan58/ESG-CoPilot) |

---

## ✨ Why ESG Pilot Stands Out

The ESG tooling market is full of dashboards. ESG Pilot is built differently — every design choice below is something competing tools either don't have or punt on.

> **🧠 Coordinated multi-agent pipeline, not a chat wrapper.**
> Nine specialised agents (Data Collector, Regulatory Tracker, Carbon Accountant, Risk Predictor, Audit, ESG ROI, Report, Action, Stakeholder) run in dependency order under a single orchestrator, each publishing canonical state that the next one consumes — auditable handoffs, no LLM "magic black box."

> **📡 Live regulatory tracking with human-in-the-loop approvals.**
> The Regulatory Tracker uses Claude with web-search to continuously monitor SEBI, EFRAG, SEC, PCAOB, GRI, and IFRS/SASB for real mandate changes. Every detected change lands in an approval queue with the source URL — humans approve, the live framework set updates, and the next Compliance Analysis run reflects the change immediately (no cache lag, no re-registration).

> **💸 Dual ROI Framework with five value-creation channels.**
> Most ESG tools stop at compliance. ESG Pilot quantifies *return*: financial ROI + strategic ROI, an Investment Quality Score (A+ to D letter grade), a J-Curve payback model that names the trough depth and break-even quarter, and an ESG Integrity Gap Detector that flags greenwashing-style mismatches between self-reported metrics and operational data.

> **🔌 Nine first-class data connectors with live refresh, no re-registration.**
> File upload (CSV/Excel/JSON), Google Sheets, REST API, AWS S3, Google BigQuery, Google Cloud Storage, Azure Blob, Delta Lake, Snowflake — all unified through one schema-mapping layer. Every registered source has a one-click **🔄 Refresh** to re-query the remote system live, and file uploads have a **📤 Replace** button that swaps bytes in place without redoing the registration wizard.

> **🛡️ Per-user isolation by construction.**
> The state bus and the source registry are partitioned per signed-in user, persisted to a private HuggingFace Dataset, and bound to the active thread via a `CompanyConfig` proxy. Two analysts on the same Space replica each run their own pipeline, on their own data, against their own thresholds — no cross-contamination.

> **💾 Persistent runs that survive refreshes, deploys, and devices.**
> Every successful pipeline run auto-saves to the user's private HF Dataset; on next login, the ESG Command Center and ESG ROI page auto-rehydrate the latest snapshot — last quarter's IQS, J-Curve, and ROI numbers are right there, no re-running required. The featured ROI card shows a real *"+5 vs last run"* delta against the previous saved IQS. History capped at 25 snapshots with orphan cleanup.

> **♻️ Incremental pipeline runs that know what changed.**
> The orchestrator memoises each agent's result keyed on a fingerprint of its inputs. Click *Run Full Pipeline* twice with no upstream changes and every cached agent short-circuits ("Reused 9 cached agent result(s)"). Mutate any source (replace a CSV, swap a Snowflake query) and the cache invalidates automatically — next run is end-to-end fresh. **♻️ Force full re-run** button bypasses the cache when you need it, plus `_ensure_complete()` guarantees every agent runs even when the LLM planner skipped some.

> **📜 "Show your working" by default.**
> Every formula, weight, and threshold is documented in [CALCULATIONS.md](CALCULATIONS.md) with `file:line` citations into the agent code. The Audit Agent produces an A–D readiness grade against the same evidence map. If a regulator asks "where did this number come from?", the answer is one search away.

> **🧯 Defensive by design — fallbacks everywhere.**
> No HuggingFace token? Rule-based fallbacks keep every agent running. No `pyarrow`? HTML table renderer kicks in. No `plotly`? Charts degrade to placeholders, the data still flows. Caches invalidated before every full pipeline run, so a remote table change is always visible on the next click. Errors are surfaced loudly, never swallowed.

> **🔮 What-if simulator over the cached ROI run.**
> A new tab on the ESG ROI page with sliders for carbon-price uplift, ESG-capex change, benefit-realisation timing, and discount rate. Recomputes the J-curve, IQS, NPV, and breakeven in milliseconds — pure-functional re-projection, no agent re-runs. Lets a CFO answer "what if CBAM doubled our carbon tax?" without waiting for a fresh pipeline.

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
| **What-if Simulator** (carbon price, capex, benefit realisation, discount rate) | What does the J-curve, IQS, and NPV look like under stress? Pure re-projection — no pipeline re-run. |

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

Refresh flow on each ESG Command Center **Run**:

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
├── Home.py                             # Main Streamlit entry point (landing page)
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
│   ├── 1_ESG_Command_Center.py           # Overview dashboard — KPIs, pipeline runner
│   ├── 2_Data_Collector.py            # Data sources, connectors, schema mapping
│   ├── 3_Regulatory_Tracker.py        # Compliance radar, gap analysis
│   ├── 4_Carbon_Accountant.py         # Emissions charts, supply chain X-Ray
│   ├── 5_Report_Generator.py          # Report builder with 5 report types
│   ├── 6_Risk_Predictor.py            # Risk gauges, scenario analysis
│   ├── 7_Audit_Agent.py              # Audit readiness, compliance checklist
│   ├── 8_Action_Agent.py             # Action items table, roadmap
│   ├── 9_Stakeholder_Agent.py        # Communication templates, tone analysis
│   └── 11_ESG_ROI_Agent.py           # ROI dashboard — dual ROI, J-curve, IQS, what-if simulator
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
    ├── whatif.py                       # Pure-functional ROI re-projection (J-curve, IQS, NPV)
    └── monitoring.py                  # Operational monitoring utilities
```

---

## Tech Stack

| Layer | Technologies |
| --- | --- |
| **AI** | HuggingFace Inference API — Mistral-7B, BART-large-CNN, BART-large-MNLI, DistilBERT-SST-2 |
| **Dashboard** | Streamlit (multi-page app, 10 pages including ESG Command Center + ROI page) |
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
streamlit run Home.py

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

| Framework | Full Name | Jurisdiction | Type |
| --- | --- | --- | --- |
| **BRSR** | Business Responsibility and Sustainability Reporting | India (SEBI) | Mandatory |
| **CSRD** | Corporate Sustainability Reporting Directive | European Union | Mandatory |
| **GRI** | Global Reporting Initiative | Global | Voluntary |
| **SASB** | Sustainability Accounting Standards Board | Global | Investor-focused |
| **SOX** | Sarbanes-Oxley Act (ESG-relevant internal controls) | United States | Mandatory |
| **SEC Climate Rule** | SEC Climate-Related Disclosures (Reg S-K, Reg S-X) | United States | Mandatory |

The Regulatory Tracker monitors all six frameworks live — see *Live regulatory tracking* in the [Selling Points](#-why-esg-pilot-stands-out) above.

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
| Identity & isolation | [Authentication](#authentication--access-control) · [Per-user state isolation](#per-user-state-isolation) · [Per-user persistence](#per-user-persistence-profile--source-store) · [Session-cookie secret persistence](#session-cookie-secret-persistence) |
| Data flow | [Pipeline refresh & data freshness](#pipeline-refresh--data-freshness) · [Live source refresh & file replace](#live-source-refresh--file-replace) · [Snowflake connector](#snowflake-connector-promoted-to-first-class) · [Data Upload → Pipeline wiring](#data-upload--pipeline-wiring) · [Connector retry/timeout policy](#connector-retrytimeout-policy) |
| Decision tooling | [What-if simulator (ROI page)](#what-if-simulator-roi-page) |
| Reliability & state | [Persistent pipeline runs (auto-save + auto-load)](#persistent-pipeline-runs-auto-save--auto-load) · [Incremental run cache](#incremental-run-cache--ensure-complete) · [Featured ROI card stale-read fix](#featured-roi-card-no-longer-goes-stale-after-a-run) · [J-Curve breakeven repair](#j-curve-breakeven-repair) · [Recommendation cache: don't pin failures](#recommendation-cache-dont-pin-failures) |
| Regulatory | [Live framework reloads](#live-regulatory-framework-reloads) · [LLM-JSON parser tolerance](#llm-json-parser-tolerance-for-framework-updates) · [Approval audit log + revert](#approval-audit-log--revert) |
| UI / theming | [Mission Control → ESG Command Center rename](#mission-control--esg-command-center-rename) · [Sidebar hierarchy + layout-ratio lock](#sidebar-hierarchy--layout-ratio-lock) · [Per-agent observability panel](#per-agent-observability-panel) · [Home page & design system](#home-page--design-system) · [PwC orange theming](#pwc-orange-theming--tagline) · [Material Symbols icon ligatures](#material-symbols-icon-ligatures-fixed) · [Cleaner gap table](#cleaner-gap-table-only-show-what-needs-attention) |
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
4. Go to **ESG Command Center**. A green banner confirms that your real data sources are wired in.
5. Click **Run Full Pipeline**. Your uploaded data drives all calculations.

> **Note:** Data is session-scoped. It lives in RAM only and is lost on browser refresh or Space restart. See [Known Limitation: Session-Scoped Storage](#known-limitation-session-scoped-storage) below.

**Bugs fixed:**

| # | Bug | Root Cause | Fix |
| --- | --- | --- | --- |
| 1 | Upload required a separate "Save Data Source" click that users routinely missed | Auto-registration did not run on Test & Preview | "Test & Preview" now immediately auto-registers the source with auto-detected schema |
| 2 | Excel files were silently ignored | Phase 3 of `DataCollectorAgent.execute()` only handled `.csv` and `.json` | Added `pd.read_excel()` handling for `.xlsx` / `.xls` |
| 3 | Uploaded data never reached pipeline calculations | Files stored under their original filename (e.g. `my_data.xlsx`), never matching a `real_{schema}` canonical slot | Auto-detection now stores uploaded data under `real_{schema}` (e.g. `real_emissions`), giving it priority over sample data |
| 4 | `connection_manager` always arrived as `None` in the orchestrator | `Orchestrator.run_full_pipeline()` called `DataCollectorAgent.run()` with no kwargs | Added `data_collector_kwargs` parameter to `run_full_pipeline()`; ESG Command Center now reads `st.session_state.conn_manager` and passes it through |

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

- ESG Command Center (`pages/1_ESG_Command_Center.py`) calls `refresh_real_data()` inside the Run handler, then `stamp_refresh_from_pipeline(...)` after `orchestrator.run_full_pipeline(...)` completes, so the per-page "Refreshed N min ago" caption is accurate.
- Agent pages 3–9 and 11 each call `refresh_real_data()` in a spinner before invoking their `.run()`, then render `data_freshness_caption()` so the user can see when the data was last fetched.
- `refresh_real_data(only_changed=True)` reuses the per-source SHA-256 config-signature cache (in `utils/connection_manager.py`) to skip the remote round-trip when nothing changed — useful for slow Snowflake / BigQuery sources.
- **Full-refresh mode now wipes the per-source DataFrame cache before fetching** (`conn_mgr.invalidate_cache()` is called inside `refresh_real_data()` whenever `only_changed=False`, and ESG Command Center invalidates before `run_full_pipeline()`). This guarantees a remote-side row change — e.g. rows deleted from a Snowflake table — is always visible on the next Run, regardless of what `use_cache` flag flows through the agent stack. The signature-based cache reuse for `only_changed=True` is unchanged.
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

**Production incident (2026-04-20):** users hitting ESG Command Center or the ESG ROI page first caused `utils/pipeline_refresh.py` to seed `st.session_state["data_collector"]`. When the user later navigated to the Data Collector page, this combined guard short-circuited:

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

### Live regulatory framework reloads

The Regulatory Tracker (`agents/regulatory_tracker.py`) used to memoise `regulatory_frameworks.json` into an in-memory cache on the first `execute()` and reuse that snapshot for the rest of the session. Approving an update via *Global Framework Updates* correctly wrote the new requirement to disk, but the next Compliance Analysis served the stale cached version — users had to restart the page to see their own change.

**Fix:** `execute()` now reloads `regulatory_frameworks.json` from disk on every run. Background-thread `external_updates` metadata (which is in-memory only) is merged on top, so the awareness alerts feature still works. The Compliance Radar reflects an applied framework update on the very next click of **Run Compliance Analysis** — no page reload, no cache clear, no re-registration.

---

### LLM-JSON parser tolerance for framework updates

`utils/framework_refresh.py` calls Claude with web-search to find recent regulatory changes. The model's response is post-processed back into a JSON array, and `json.loads()` was used in strict mode. Whenever Claude emitted a literal newline or tab inside a string value (RFC-disallowed but common in real-world LLM output), the entire refresh failed with *"Invalid control character at: line 6 column 21"* and zero pending updates were surfaced — even when most of the array was valid.

**Fix:** the parse path now uses `json.loads(strict=False)` (Python's built-in tolerance for control characters in string values) and falls back to a scrubbed-and-retry pass for the remaining disallowed bytes (NULs, etc.) before surfacing the original error. Real regulatory updates are no longer dropped because of one unescaped whitespace character.

---

### Live source refresh & file replace

The Data Collector's *Registered Data Sources* list now exposes two per-source actions next to **🗑️ Delete**:

- **🔄 Refresh** (Snowflake, BigQuery, S3, Google Sheets, REST, Azure Blob, Delta Lake, GCS) — re-queries the remote system immediately, bypasses the per-source cache, and updates the displayed row count + *Last fetched: N min ago* caption. Gives users instant verification that a remote-side change is visible *without* running the full pipeline.
- **📤 Replace** (file upload sources only) — opens an inline file uploader so a user with an edited CSV can swap the bytes in place; `display_name` and `target_schema` are preserved, and `column_mapping` is re-derived against the new columns so a renamed or reordered header is handled gracefully. Users no longer have to repeat the full registration wizard to pick up a local edit.

Each source card also now shows a *Last fetched: N min ago* caption (or *never fetched* before its first refresh), so staleness is always visible at a glance.

This entry pairs with the [Pipeline refresh & data freshness](#pipeline-refresh--data-freshness) update — together they make data-freshness deterministic regardless of source type.

---

### Cleaner gap table: only show what needs attention

The *Registered sources — unmapped fields* table on ESG Command Center used to render a row for every registered source, including fully-mapped ones whose "Missing required" / "Missing optional" columns just said `—`. Clients reported the visual noise made it hard to spot the actual gaps.

**Fix in `pages/1_ESG_Command_Center.py`:** the table now lists only sources that have at least one missing required or optional column. Fully-mapped sources collapse into a single green ✅ success line ("All 4 registered sources are fully mapped — no gaps to address"), and a small *"Hiding N fully-mapped sources with no gaps"* caption keeps the filter transparent. The CSV export is filtered the same way.

---

### Mission Control → ESG Command Center rename

The original "Mission Control" page is now branded **ESG Command Center**, pairing it with **ESG ROI Agent** as the two primary surfaces in the sidebar. Renamed end-to-end: `pages/1_Mission_Control.py` → `pages/1_ESG_Command_Center.py` (URL slug becomes `/ESG_Command_Center`), every `st.switch_page(...)` call updated, every `[href*="Mission_Control"]` CSS selector retargeted, every user-visible string refreshed (Home greeting CTA, Sign In button, Data Collector hint, gradio tab, ROI featured-card greeting), every comment in tests / utils brought in line, and all four docs (README, RUNBOOK, SCHEMA, TESTS) updated. Old `/Mission_Control` bookmarks 404 — clean break, no redirect.

### Sidebar hierarchy + layout-ratio lock

The sidebar previously rendered all 10 pages as equal peers. Now ESG Command Center + ESG ROI Agent (the two surfaces the product is sold on) render larger / bolder / weight 700 with a 3px orange accent rail when inactive; the eight supporting agent pages + Settings render at 0.78 rem with 78% opacity (lifts to 100% on hover) so the visual hierarchy reads as "command centre + investment thesis · then the agents that feed them".

Layout-ratio locks added at the same time:
- Sidebar pinned to `min-width / max-width: 280px` so it stops auto-snapping narrower (and the **collapse/hamburger toggle is hidden** so users can't accidentally lose it).
- Main `.block-container` capped at `max-width: 1440px` with auto margins, so on 27"+ monitors the hero card no longer sprawls into a wonky aspect ratio.

### Per-agent observability panel

The ESG Command Center renders a *Pipeline Observability* panel below the Activity Log: one row per agent with **Status · Last run · Last runtime (s) · Median runtime · p95 · Total runs · Errors (history) · Last error**. Plus five KPI cards summarising the most recent run's planner surface — **Planner Steps**, **Input Tokens**, **Output Tokens**, **Cache Hit %**, **Est. Cost (USD)** based on Opus 4.x list-price ratios. Reads from `utils/agent_telemetry.load_all()` and the orchestrator's `planning_log` — no schema changes required.

### Persistent pipeline runs (auto-save + auto-load)

Closes the README-flagged "session-scoped storage" gap: every successful pipeline run on the ESG Command Center is now auto-saved to a private HF Dataset (path 4 of the persistence stack: `runs/{username}/{run_id}.json`) with the label `Auto · YYYY-MM-DD HH:MM`. On the next session start, both the Command Center and the ESG ROI Agent page auto-load the latest snapshot — republishing each agent's result onto `state_manager` so per-agent pages see live numbers without re-running. Errored runs are deliberately *not* auto-saved (a half-finished pipeline never gets pinned as the latest). History capped at 25 snapshots per user with orphan cleanup; size cap at 4 MB per snapshot. New `💾 Save / Load Pipeline Runs` expander on the Command Center for explicit save / load / delete with custom labels.

### Incremental run cache + ensure-complete

The orchestrator memoises each agent's result keyed on a fingerprint of its inputs. On a second click of *Run Full Pipeline* with no upstream changes, every cached agent short-circuits and the post-run banner reads *"Reused N cached agent result(s)"*. A new **♻️ Force full re-run** button bypasses the cache when needed.

The cache busts automatically on any source mutation (`add` / `remove` / `replace`) via `ConnectionManager.on_change` → `orchestrator.invalidate_incremental_cache()`. Belt-and-suspenders insurance: the fingerprint chain *should* propagate a source change naturally, but explicit invalidation guarantees a fresh end-to-end run on the next click regardless of fingerprint subtleties.

The LLM-driven planner is goal-driven and may skip agents the goal doesn't require. New `Orchestrator._ensure_complete()` walks `agent_order` after the tool-use loop and runs any agent that was skipped (errored agents not auto-retried) — so *Run Full Pipeline* now always produces all 9 agents in the result dict.

### Featured ROI card no longer goes stale after a Run

Earlier the card on the Command Center read `orch.agents["roi_agent"].results` directly. That instance attribute is only updated when the orchestrator's tool-use loop actually executes the ROI agent — and the planner could skip it, plus the incremental cache could serve prior results without re-calling `agent.run()`. New read order: `state_manager.subscribe("roi_results")` (always populated by `ROIAgent.execute` on every successful run) → `st.session_state["roi_results"]` → `st.session_state["pipeline_results"]["roi_agent"]` → `agent.results` (final fallback). Plus the card now renders a real **"+5 vs last run"** delta against the user's previous saved IQS, replacing the previously-hardcoded `"↑ live · updated now"` string.

### J-Curve breakeven repair

The deployed Space showed *"Breakeven: 2021 Q2 | Current net position: INR -187.83 Cr"* — a falsely-reported breakeven despite a still-negative position. Root cause: the loop matched `net_position >= 0 and i > 0`, which trivially fired on the all-zero pre-investment quarters. Corrected semantics: breakeven requires (a) `cumulative_cost > 0` (some investment has happened) and (b) the position was negative at some prior point and has now climbed back. Pure-positive trajectories (benefits ≥ costs from quarter 1) return `breakeven_quarter = None`. Pinned by `tests/test_roi_agent.py::TestJCurve` (4 tests).

### Recommendation cache: don't pin failures

The Command Center's *Prioritized recommendations* block caches its result keyed on the gap report. Earlier code path stored the formatted error string under the same key as a successful response — so a transient 4xx/5xx (rate limit, brief credit gap, network blip) would stay pinned on the page until the gap report changed. Reproduced live after a recent Anthropic credit gap: even after credits were restored, the page kept serving the cached 400 error message until the user re-ran the full pipeline. Fix: cache successes only; on read, skip any entry starting with the failure marker; on write of a new failure, drop any prior cached entry under the same key.

### Connector retry/timeout policy

New `utils/connector_retry.py` adds an opinionated retry helper (3 attempts, exp backoff 0.4–4 s with jitter, 30 s wall-clock deadline) shared across all 10 connectors. `ConnectionManager.fetch_source` wraps `connector.fetch()` through `with_retry`, so a flaky 5xx on Snowflake / BigQuery / S3 / GCS no longer fails the pipeline run. Fatal errors (auth, bad config, missing optional dependency, 4xx client errors) bypass retries and surface immediately. 30 tests pin the contract.

### Approval audit log + revert

The Regulatory Tracker mutates `regulatory_frameworks.json` live when an operator approves a pending update. Previously there was no way to undo a bad approval and no record of who approved what. Now:

- Every approval / dismissal / revert action lands in an append-only `audit_log` with actor + timestamp + requirement id touched.
- New `revert_update()` removes the requirement that `apply_update` appended, flips status back to `pending`, and drops the apply markers so a re-apply runs cleanly. Idempotent (reverting an already-reverted update logs a `revert_skipped` entry).
- Per-row **↩️ Revert** button on the Applied list. New **🔍 Audit log** expander shows the full event history.

10 tests pin the apply → revert → re-apply round-trip.

### Session-cookie secret persistence

Login was being lost on every page refresh after a Space redeploy. Root cause: `utils/auth.py:_resolve_secret()` resolved the cookie-signing secret in this order: `SESSION_SECRET` env → local file → ephemeral random key. `SESSION_SECRET` wasn't set on the Space, the local file doesn't survive HF container rebuilds, so every restart minted a new ephemeral secret and invalidated every browser's cookie.

Fix: persist the secret to the same private HF Dataset that backs the user / source / profile / run stores, under `auth/.session_secret`. New resolution order: env var → HF Dataset → local file → ephemeral. The HF Dataset path survives Space rebuilds, so cookies signed yesterday verify cleanly today. Best-effort writes (failures are swallowed; the secret still works for the current process). The first time a Space starts after this code shipped, all existing users still need to log in once — their cookies were signed with the prior ephemeral secret. From that point forward, deploys don't kick anyone out.

---

### What-if simulator (ROI page)

A new **🔮 What-if Simulator** tab on `pages/11_ESG_ROI_Agent.py` with four sliders:

| Slider | What it changes |
| --- | --- |
| Carbon price uplift (-50% … +300%) | Bumps the carbon-tax-avoided line, cascades to financial ROI |
| ESG capex change (-50% … +200%) | Scales every quarter's ESG-linked capex |
| Benefit realisation (-50% … +200%) | Scales the per-quarter ESG benefit |
| Discount rate (0% … 25%) | Annualised hurdle for the NPV column |

**Pure-functional re-projection** — `utils/whatif.py:simulate` walks the cached J-curve, applies the slider multipliers, re-derives breakeven (same "must go underwater first" rule the agent uses), and recomputes the IQS using the same weight vector as `agents/roi_agent.py:_investment_quality_score`. **No agents are re-executed.** A scenario takes milliseconds.

The tab renders four side-by-side reads — baseline IQS, scenario IQS, Δ IQS, scenario breakeven — plus scenario savings, NPV, and net position cards. The quarterly trajectory plot overlays cumulative cost / benefit / net under the slider settings.

NPV semantics: per-quarter rate is `rate / 4` (so the slider stays in annual units), and `rate=0` returns the undiscounted sum. `tests/test_whatif.py` pins zero-slider reproducibility (within 0.5 of the baseline IQS), capex uplift pushing breakeven out, carbon-price uplift lifting savings, and higher discount rates lowering NPV.

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
| `utils/run_store.py` | Per-user pipeline-run snapshots | Persists full `pipeline_results` dicts to the auth HF Dataset so the Command Center + ESG ROI page auto-rehydrate on the next session start. History capped at 25 with orphan cleanup. |
| `utils/connector_retry.py` | Shared retry/timeout policy for connector fetches | Wraps every `ConnectionManager.fetch_source` call. Transient HTTP 5xx / network blips retry with jittered backoff; auth + config failures fail fast. |
| `utils/agent_telemetry.py` | Persistent per-agent run history (file-backed) | Survives Streamlit reruns + Space restarts so the *Pipeline Observability* panel always shows the last-run timestamp / runtime / error per agent. |
| `utils/whatif.py` | Pure-functional re-projection of an ROI run under slider scenarios | Sub-second "what if carbon prices doubled?" answers without re-running the agents. |

---

## License

This project is proprietary. All rights reserved.

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

At the center of the platform is the CoPilot Engine (orchestrator), managing eight specialized agents in a dependency graph:

```
Pipeline Execution Order:

  1. Data Collector       ─── (no dependencies)
       ├──→ 2. Regulatory Tracker
       ├──→ 3. Carbon Accountant
       └──→ 4. Risk Predictor ←── Regulatory Tracker
                  ├──→ 5. Audit Agent ←── Regulatory + Carbon
                  │         ├──→ 6. Report Generator ←── Carbon + Risk
                  │         └──→ 7. Action Agent ←── Risk + Report
                  └──→ 8. Stakeholder Agent ←── Action + Report
```

| Agent | Role | Key Outputs |
| --- | --- | --- |
| **Data Collector** | Pulls and structures ESG data from 9 connector types | Quality scores, confidence levels, gap alerts |
| **Regulatory Tracker** | Maps data against BRSR, CSRD, GRI, SASB requirements | Compliance %, gap analysis, remediation guidance |
| **Carbon Accountant** | Tracks Scope 1/2/3 emissions, energy, supply chain | Emissions breakdown, YoY trends, hotspot detection |
| **Report Generator** | Produces multi-framework, audit-ready ESG reports | 5 report types with AI-generated narratives |
| **Risk Predictor** | Forecasts climate, supplier, and ESG rating risks | Risk scores, scenario analysis, rating predictions |
| **Audit Agent** | Validates traceability, confidence, and evidence | Readiness score (A-D grade), compliance checklist |
| **Action Agent** | Recommends follow-up actions with cost-benefit analysis | Prioritized action items, implementation roadmap |
| **Stakeholder Agent** | Shapes outputs for investors, regulators, employees, public | Audience-tailored messages with tone analysis |

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
│   ├── hf_client.py                    # HuggingFace Inference API wrapper + fallbacks
│   ├── state_manager.py               # Pub/sub state bus for inter-agent data sharing
│   └── orchestrator.py                # Dependency graph pipeline runner
├── agents/
│   ├── data_collector.py              # Agent 1: Data ingestion + quality scoring
│   ├── regulatory_tracker.py          # Agent 2: Framework compliance gap analysis
│   ├── carbon_accountant.py           # Agent 3: Scope 1/2/3 emissions accounting
│   ├── report_generator.py            # Agent 4: Multi-framework ESG reports
│   ├── risk_predictor.py              # Agent 5: Climate & ESG risk forecasting
│   ├── audit_agent.py                 # Agent 6: Compliance verification & audit readiness
│   ├── action_agent.py               # Agent 7: Prioritized recommendations
│   └── stakeholder_agent.py          # Agent 8: Audience-tailored communications
├── pages/
│   ├── 1_Mission_Control.py           # Overview dashboard — KPIs, pipeline runner
│   ├── 2_Data_Collector.py            # Data sources, connectors, schema mapping
│   ├── 3_Regulatory_Tracker.py        # Compliance radar, gap analysis
│   ├── 4_Carbon_Accountant.py         # Emissions charts, supply chain X-Ray
│   ├── 5_Report_Generator.py          # Report builder with 5 report types
│   ├── 6_Risk_Predictor.py            # Risk gauges, scenario analysis
│   ├── 7_Audit_Agent.py              # Audit readiness, compliance checklist
│   ├── 8_Action_Agent.py             # Action items table, roadmap
│   └── 9_Stakeholder_Agent.py        # Communication templates, tone analysis
├── data/
│   ├── company_profile.json           # Fictional company: GreenTech Solutions Pvt. Ltd.
│   ├── regulatory_frameworks.json     # BRSR, CSRD, GRI, SASB requirements
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
    └── monitoring.py                  # Operational monitoring utilities
```

---

## Tech Stack

| Layer | Technologies |
| --- | --- |
| **AI** | HuggingFace Inference API — Mistral-7B, BART-large-CNN, BART-large-MNLI, DistilBERT-SST-2 |
| **Dashboard** | Streamlit (multi-page app, 9 pages) |
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

2. **Run the pipeline** — The orchestrator executes all 8 agents in dependency order. Each agent publishes results via a shared state bus for downstream agents to consume.

3. **Explore results** — Navigate through 9 dashboard pages: compliance radar charts, emissions breakdowns, risk gauges, audit checklists, and more.

4. **Generate reports** — Choose from 5 report types (Full ESG, Carbon & Environment, Framework Compliance, Social & Governance, Executive Summary). Reports include AI narratives, metrics tables, and audit trails.

5. **Act on insights** — Review prioritized action items with timelines and cost estimates. Share tailored communications with investors, regulators, employees, or the public.

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

## License

This project is proprietary. All rights reserved.

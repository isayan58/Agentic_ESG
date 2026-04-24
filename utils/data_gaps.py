"""Data-gap analyzer — compares the client's registered data sources against
the full ESG schema catalog and the pipeline results so the UI can tell the
client exactly what's missing and which downstream analysis it would unlock.

Deterministic: no LLM calls here. The caller can feed this report into Claude
for a natural-language recommendation on top."""
from __future__ import annotations

from utils.schema_mapper import ESG_SCHEMAS


# Which downstream agents depend on each target schema being present.
# Used to explain *why* a missing schema matters, in plain business terms.
_SCHEMA_IMPACT: dict[str, dict] = {
    "emissions": {
        "agents": ["carbon_accountant", "risk_predictor", "roi_agent"],
        "why": (
            "Scope 1/2/3 decomposition, carbon-tax exposure, and the emissions "
            "leg of the ROI thesis all key off this table."
        ),
        "example_source": (
            "Quarterly fuel/utility ledger (CSV) with columns: year, quarter, "
            "scope, category, emissions_tco2e."
        ),
    },
    "energy": {
        "agents": ["carbon_accountant", "roi_agent"],
        "why": (
            "Without energy mix data we can't isolate Scope 2 from grid vs. "
            "renewables, nor price the energy-cost lever in the ROI model."
        ),
        "example_source": (
            "Utility-bill extract or BMS export with: year, quarter, "
            "energy_source, consumption_mwh, cost_inr_lakhs, renewable."
        ),
    },
    "waste": {
        "agents": ["carbon_accountant", "audit_agent"],
        "why": (
            "Waste-stream data lets us quantify Scope 3 category 5 "
            "(operational waste) and diversion KPIs for BRSR/GRI."
        ),
        "example_source": (
            "Hauler invoices or EHS log with: year, quarter, waste_type, "
            "quantity_mt, disposal_method, recycled_pct."
        ),
    },
    "esg_metrics": {
        "agents": ["audit_agent", "report_generator", "roi_agent"],
        "why": (
            "The structured KPI library feeds the readiness score, "
            "disclosure-framework mapping, and target-vs-actual tracking."
        ),
        "example_source": (
            "Your internal ESG KPI tracker (Excel/Sheets) with: metric_id, "
            "pillar, metric_name, value_2023, value_2024, target_2024, status."
        ),
    },
    "financials": {
        "agents": ["roi_agent", "report_generator"],
        "why": (
            "Revenue, EBITDA margin, ROA/ROE, and cost of capital drive the "
            "financial leg of the ROI/IQS and CAGR/volatility calculations."
        ),
        "example_source": (
            "Finance team's quarterly P&L + balance sheet export: year, "
            "quarter, revenue_inr_crores, ebitda_margin_pct, roa_pct, roe_pct, "
            "cost_of_capital_pct, esg_linked_capex_inr_crores."
        ),
    },
    "supply_chain": {
        "agents": ["risk_predictor", "stakeholder_agent"],
        "why": (
            "Tier-1/2 supplier exposure is the largest Scope 3 driver and "
            "the top source of regulatory/transition risk."
        ),
        "example_source": (
            "Procurement master (SAP Ariba export, Snowflake, or CSV): "
            "supplier_id, supplier_name, country, tier, esg_score, "
            "risk_rating, emission_contribution_tco2e."
        ),
    },
    "diversity": {
        "agents": ["audit_agent", "report_generator", "stakeholder_agent"],
        "why": (
            "The S-pillar of BRSR/GRI and most stakeholder-materiality "
            "disclosures require workforce diversity breakdowns."
        ),
        "example_source": (
            "HRIS export (Workday/SuccessFactors) with: year, category "
            "(Gender/Age), subcategory (Overall/Leadership), metric, value."
        ),
    },
    "peer_companies": {
        "agents": ["roi_agent"],
        "why": "Anchors sector-peer list for benchmarking.",
        "example_source": "CSV with: company, sector, company_no.",
    },
    "peer_financials": {
        "agents": ["roi_agent"],
        "why": (
            "Peer P&L enables ROA/margin/leverage deltas vs the client — "
            "the most-asked slide in any CFO-ready ESG review."
        ),
        "example_source": (
            "Capital IQ / Bloomberg export: company, year, revenue, "
            "net_profit, total_assets, ebitda, operating_cash_flow."
        ),
    },
    "peer_esg": {
        "agents": ["roi_agent", "risk_predictor"],
        "why": (
            "Peer ESG scores + Scope 1/2 unlock the relative-performance "
            "overlay on the IQS dashboard."
        ),
        "example_source": (
            "Sustainalytics / MSCI / CDP export: company, year, esg_score, "
            "scope1_emissions_tco2e, scope2_emissions_tco2e, esg_capex, "
            "green_assets."
        ),
    },
    "peer_metrics": {
        "agents": ["roi_agent"],
        "why": "Pre-computed peer ratios for faster benchmark rendering.",
        "example_source": (
            "Derived from peer_financials + peer_esg — or pulled from an "
            "internal benchmarking dataset."
        ),
    },
    "peer_benchmark": {
        "agents": ["roi_agent"],
        "why": "5-year sector averages for the 'vs peers' band on the IQS view.",
        "example_source": "Sector averages CSV per the peer_benchmark schema.",
    },
}


def _schema_fields(schema_name: str) -> tuple[list[str], list[str]]:
    """Return (required_fields, optional_fields) for a schema."""
    schema = ESG_SCHEMAS.get(schema_name, {})
    required = [col for col, spec in schema.items() if spec.get("required")]
    optional = [col for col, spec in schema.items() if not spec.get("required")]
    return required, optional


def _missing_from_mapping(mapping: dict, fields: list[str]) -> list[str]:
    """A field is 'missing' if it's not in the mapping or the mapping's
    source column for it is falsy (None / empty string)."""
    mapping = mapping or {}
    return [f for f in fields if not mapping.get(f)]


def compute_data_gaps(conn_mgr, pipeline_results: dict | None) -> dict:
    """Return a structured data-gap report.

    Shape:
        {
          "has_sources": bool,
          "using_sample_data": bool,
          "source_count": int,
          "schema_coverage": {"covered": int, "total": int},
          "sources": [
            {"id", "display_name", "connector_type", "target_schema",
             "missing_required", "missing_optional"},
            ...
          ],
          "missing_schemas": [
            {"schema", "why", "example_source", "blocks_agents"}, ...
          ],
          "agents_errored": [agent_key, ...],
          "agents_completed": [agent_key, ...],
        }
    """
    pipeline_results = pipeline_results or {}
    has_sources = bool(conn_mgr and getattr(conn_mgr, "has_sources", lambda: False)())
    sources_meta = (conn_mgr.list_sources() if has_sources else [])

    # Per-source gap analysis
    source_rows = []
    registered_schemas: set[str] = set()
    for src in sources_meta:
        schema_name = src.get("target_schema") or ""
        required, optional = _schema_fields(schema_name)
        mapping = src.get("column_mapping") or {}
        missing_req = _missing_from_mapping(mapping, required)
        missing_opt = _missing_from_mapping(mapping, optional)
        registered_schemas.add(schema_name)
        source_rows.append({
            "id": src.get("id"),
            "display_name": src.get("display_name") or src.get("id"),
            "connector_type": src.get("connector_type"),
            "target_schema": schema_name,
            "missing_required": missing_req,
            "missing_optional": missing_opt,
        })

    # Missing-schema analysis — schemas we have a mapping for (in _SCHEMA_IMPACT)
    # but that the client hasn't registered any source against.
    missing_schemas = []
    for schema_name, impact in _SCHEMA_IMPACT.items():
        if schema_name in registered_schemas:
            continue
        missing_schemas.append({
            "schema": schema_name,
            "why": impact["why"],
            "example_source": impact["example_source"],
            "blocks_agents": impact["agents"],
        })

    # Pipeline execution signals
    agents_errored = [
        agent_key for agent_key, res in pipeline_results.items()
        if agent_key != "planning" and isinstance(res, dict) and "error" in res
    ]
    agents_completed = [
        agent_key for agent_key, res in pipeline_results.items()
        if agent_key != "planning" and isinstance(res, dict) and "error" not in res
    ]

    return {
        "has_sources": has_sources,
        "using_sample_data": not has_sources,
        "source_count": len(sources_meta),
        "schema_coverage": {
            "covered": len(registered_schemas),
            "total": len(_SCHEMA_IMPACT),
        },
        "sources": source_rows,
        "missing_schemas": missing_schemas,
        "agents_errored": agents_errored,
        "agents_completed": agents_completed,
    }

"""Gap-fill data-suggestion helpers for the Regulatory Tracker and Audit
agents.

Both agents surface "you're missing data for X" items. Historically the
UI just told the user *which* requirement was unmet; there was no path
from the gap back to a concrete "upload this CSV / wire up this
connector" action. This module is the lookup that closes that loop:

* :func:`suggestion_for_regulatory_field` — given a regulatory data-field
  name (e.g. ``emissions_scope1``, ``diversity``), return a list of
  concrete data additions that would satisfy it (schema, example
  columns, example sources).

* :func:`suggestion_for_audit_dataset` — given an audit-completeness
  dataset label (e.g. ``"Workforce Diversity Data"``), return the same
  shape of suggestion so the Audit Agent page can surface identical
  gap-fill chrome.

The tables below are hand-curated and intentionally small: they point at
the canonical ESG schemas (``emissions``, ``esg_metrics``, ``energy``,
``supply_chain``, ``waste``, ``diversity``, ``financials``) that already
exist in :mod:`utils.schema_mapper`. Anything outside that set returns
``None`` so the UI can fall back to a generic hint.
"""
from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Schema-level suggestions
# ---------------------------------------------------------------------------
# Each entry describes what the user should upload / connect to satisfy a
# regulatory data-field. The suggestion is *intentionally actionable*:
# - ``schema`` names a canonical ESG schema from ``utils.schema_mapper``.
# - ``example_columns`` shows the minimum column set that should be in
#   the upload so auto-detection picks the right schema.
# - ``example_sources`` lists realistic upstream systems / file formats.
# - ``rationale`` is a one-line "why this closes the gap" the UI renders
#   as help text under the gap card.

_SCHEMA_SUGGESTIONS: dict[str, dict[str, Any]] = {
    "emissions": {
        "schema": "emissions",
        "example_columns": [
            "year", "quarter", "scope", "category", "emissions_tco2e",
        ],
        "example_sources": [
            "Fuel / electricity invoices exported to CSV",
            "Snowflake / BigQuery table of emission factors × activity data",
            "Supplier-provided Scope 3 disclosures (Google Sheet)",
        ],
        "rationale": (
            "Direct measurement of GHG emissions by scope and category is "
            "the canonical input for Scope 1/2/3 compliance questions."
        ),
    },
    "esg_metrics": {
        "schema": "esg_metrics",
        "example_columns": [
            "metric_id", "pillar", "category", "metric_name",
            "value_2024", "target_2024", "status",
        ],
        "example_sources": [
            "CSR / HR / EHS team KPI trackers",
            "Board-approved ESG target sheets",
            "CDP / BRSR disclosure preparation workbooks",
        ],
        "rationale": (
            "Most framework requirements expect at least one quantified "
            "metric with a target and a 'current vs prior year' comparison."
        ),
    },
    "energy": {
        "schema": "energy",
        "example_columns": [
            "year", "quarter", "energy_source", "consumption_mwh",
            "renewable",
        ],
        "example_sources": [
            "Utility-bill exports (electricity, gas, steam)",
            "On-site solar / wind meter readings",
            "Facilities-team energy dashboards",
        ],
        "rationale": (
            "Energy consumption and renewable-share data feed both Scope 2 "
            "emissions and renewable-energy percentage KPIs."
        ),
    },
    "supply_chain": {
        "schema": "supply_chain",
        "example_columns": [
            "supplier_id", "supplier_name", "country", "tier",
            "esg_score", "risk_rating", "emission_contribution_tco2e",
            "audit_status",
        ],
        "example_sources": [
            "Procurement / ERP supplier master + ESG screening scores",
            "EcoVadis / third-party supplier-ESG exports",
            "Annual supplier audit tracker spreadsheet",
        ],
        "rationale": (
            "Value-chain, Scope 3, and supplier-due-diligence requirements "
            "all need a supplier-level table with at minimum an ESG and "
            "risk rating per tier-1 partner."
        ),
    },
    "waste": {
        "schema": "waste",
        "example_columns": [
            "year", "quarter", "waste_type", "category", "quantity_mt",
            "disposal_method", "recycled_pct",
        ],
        "example_sources": [
            "Waste-hauler monthly manifests",
            "Hazardous-waste disposal certificates",
            "Recycling-vendor aggregated quarterly reports",
        ],
        "rationale": (
            "Waste generation, hazardous-waste handling, and circularity "
            "metrics all require a tonnage + disposal-method breakdown."
        ),
    },
    "diversity": {
        "schema": "diversity",
        "example_columns": [
            "year", "category", "subcategory", "metric", "value", "unit",
        ],
        "example_sources": [
            "HRIS export (Workday / SAP SuccessFactors) filtered by gender, "
            "age band, and leadership level",
            "Pay-equity analysis spreadsheet",
            "Employee-engagement survey results",
        ],
        "rationale": (
            "Workforce diversity, pay-equity, and board-composition "
            "requirements need a row-per-slice table of headcount / "
            "percentage values."
        ),
    },
    "governance_docs": {
        "schema": "esg_metrics",
        "example_columns": [
            "metric_id", "pillar", "metric_name", "value_2024", "data_source",
        ],
        "example_sources": [
            "Board-committee charters and meeting-minute attendance logs",
            "Whistleblower / ethics-hotline case tracker",
            "Anti-corruption training completion report from the LMS",
        ],
        "rationale": (
            "Governance-pillar requirements (ethics, anti-corruption, "
            "whistleblower, board oversight) need both a quantitative "
            "coverage metric and a documentary data-source reference."
        ),
    },
    "hr_docs": {
        "schema": "esg_metrics",
        "example_columns": [
            "metric_id", "pillar", "metric_name", "value_2024", "data_source",
        ],
        "example_sources": [
            "HR policy documents (human-rights, non-discrimination)",
            "Due-diligence assessment completion tracker",
            "Grievance-mechanism case logs",
        ],
        "rationale": (
            "Human-rights, stakeholder-engagement, and community-impact "
            "requirements are typically satisfied with a coverage-% KPI "
            "plus a pointer to the underlying policy/audit document."
        ),
    },
}


# Regulatory data_field name → list of suggestion keys from the table
# above. A single field can map to multiple schemas (e.g. Scope 2 wants
# both emissions tonnes *and* energy-consumption context).
_FIELD_TO_SUGGESTIONS: dict[str, tuple[str, ...]] = {
    # Environmental — emissions
    "emissions_scope1": ("emissions",),
    "emissions_scope2": ("emissions", "energy"),
    "emissions_scope3": ("emissions", "supply_chain"),
    "emissions_all_scopes": ("emissions",),
    "supply_chain_emissions": ("supply_chain", "emissions"),
    "climate_targets": ("esg_metrics",),
    # Energy
    "energy_consumption": ("energy",),
    "energy_intensity": ("energy", "esg_metrics"),
    "renewable_energy": ("energy",),
    "renewable_energy_pct": ("energy", "esg_metrics"),
    # Water
    "water_consumption": ("esg_metrics",),
    "water_recycling": ("esg_metrics",),
    "water_discharge": ("esg_metrics",),
    "water_stress": ("esg_metrics",),
    "water_pollution": ("esg_metrics",),
    "air_pollution": ("esg_metrics",),
    # Waste
    "waste_generated": ("waste",),
    "waste_recycled": ("waste",),
    "hazardous_waste": ("waste",),
    # Biodiversity / land
    "biodiversity_impact": ("esg_metrics",),
    "land_use": ("esg_metrics",),
    # Social — workforce
    "employee_wellbeing": ("esg_metrics", "diversity"),
    "diversity": ("diversity",),
    "gender_diversity": ("diversity",),
    "board_diversity": ("diversity", "esg_metrics"),
    "pay_equity": ("diversity",),
    "ltifr": ("esg_metrics",),
    "safety_training": ("esg_metrics",),
    "training_hours": ("esg_metrics",),
    "new_hires": ("diversity", "esg_metrics"),
    "turnover": ("esg_metrics", "diversity"),
    "voluntary_turnover": ("esg_metrics",),
    "involuntary_turnover": ("esg_metrics",),
    "engagement_score": ("esg_metrics",),
    "benefits": ("esg_metrics",),
    "incidents": ("esg_metrics",),
    # Social — supply chain & community
    "supplier_audits": ("supply_chain",),
    "supplier_env_audits": ("supply_chain",),
    "supplier_social_audits": ("supply_chain",),
    "supply_chain_labor": ("supply_chain",),
    "community_impact": ("hr_docs", "esg_metrics"),
    "indigenous_rights": ("hr_docs",),
    "stakeholder_engagement": ("hr_docs",),
    "csr_spending": ("esg_metrics",),
    "beneficiaries": ("esg_metrics",),
    # Social — human rights / HR
    "hr_training": ("hr_docs", "esg_metrics"),
    "hr_assessment": ("hr_docs",),
    # Product / consumer
    "product_safety": ("esg_metrics",),
    "product_sustainability": ("esg_metrics",),
    "consumer_complaints": ("esg_metrics",),
    "data_privacy": ("governance_docs", "esg_metrics"),
    "data_breaches": ("governance_docs",),
    # Governance
    "board_governance": ("governance_docs",),
    "anti_corruption": ("governance_docs",),
    "anti_corruption_training": ("governance_docs",),
    "whistleblower": ("governance_docs",),
    "lobbying": ("governance_docs",),
    "policy_advocacy": ("governance_docs",),
    "materiality_assessment": ("governance_docs",),
}


# Audit-agent dataset label → single suggestion key. The labels come
# from ``_audit_data_completeness`` in ``agents/audit_agent.py``.
_AUDIT_DATASET_TO_SUGGESTION: dict[str, str] = {
    "Scope 1/2/3 Emissions Data": "emissions",
    "ESG KPI Metrics": "esg_metrics",
    "Supply Chain Data": "supply_chain",
    "Energy Consumption Data": "energy",
    "Waste Management Data": "waste",
    "Workforce Diversity Data": "diversity",
}


def suggestion_for_regulatory_field(field: str) -> list[dict[str, Any]]:
    """Return concrete data-addition suggestions for a regulatory field.

    ``field`` is a data-field name from
    ``data/regulatory_frameworks.json`` (e.g. ``emissions_scope1``). An
    unknown field returns an empty list so the caller can fall back to a
    generic "no tailored suggestion" message.
    """
    keys = _FIELD_TO_SUGGESTIONS.get(field, ())
    out = []
    for key in keys:
        sugg = _SCHEMA_SUGGESTIONS.get(key)
        if sugg:
            out.append({"field": field, **sugg})
    return out


def suggestions_for_gap(gap: dict[str, Any]) -> list[dict[str, Any]]:
    """Aggregate suggestions across every ``missing_fields`` entry.

    De-duplicated by target schema so we don't render the same "add an
    emissions CSV" card three times when a requirement lists three
    scope-related fields.
    """
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for field in gap.get("missing_fields") or []:
        for sugg in suggestion_for_regulatory_field(field):
            key = sugg["schema"]
            if key in seen:
                # Merge the source field into the existing suggestion so
                # the user sees which missing field it closes.
                for existing in out:
                    if existing["schema"] == key:
                        existing.setdefault("fields", []).append(field)
                        break
                continue
            seen.add(key)
            out.append({**sugg, "fields": [field]})
    return out


def suggestion_for_audit_dataset(dataset_label: str) -> dict[str, Any] | None:
    """Return the data-addition suggestion for a failing audit dataset.

    Returns ``None`` for unknown labels.
    """
    key = _AUDIT_DATASET_TO_SUGGESTION.get(dataset_label)
    if not key:
        return None
    sugg = _SCHEMA_SUGGESTIONS.get(key)
    return {**sugg, "dataset": dataset_label} if sugg else None


def render_suggestion_block(st_module, suggestion: dict[str, Any]) -> None:
    """Render a single suggestion as a Streamlit info block.

    Factored out so the Regulatory Tracker and Audit Agent pages render
    identical chrome. Accepts the Streamlit module as an argument so
    this stays importable from non-Streamlit contexts (tests).
    """
    schema = suggestion.get("schema", "")
    st_module.markdown(f"**Add a `{schema}` dataset** via the Data Collector page.")
    fields = suggestion.get("fields")
    if fields:
        st_module.caption(
            "Closes missing field(s): "
            + ", ".join(f"`{f}`" for f in fields)
        )
    cols = suggestion.get("example_columns") or []
    if cols:
        st_module.markdown(
            "_Expected columns:_ " + ", ".join(f"`{c}`" for c in cols)
        )
    sources = suggestion.get("example_sources") or []
    if sources:
        st_module.markdown("_Where this data typically lives:_")
        for s in sources:
            st_module.markdown(f"- {s}")
    rationale = suggestion.get("rationale")
    if rationale:
        st_module.caption(f"💡 {rationale}")

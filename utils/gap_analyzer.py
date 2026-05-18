"""Claude-powered specific gap analyzer.

The legacy narrative generators (`_generate_gap_narrative`,
`_generate_findings_summary`, `_generate_data_quality_summary`) collapsed
rich per-requirement / per-dataset data down to "N gaps found" before
asking a small text model for prose. The result was generic. This module
keeps the *structured* data intact and uses Claude with tool-use to
produce both a tight narrative AND a list of field-level remediation
rows the UI can render as a table.

Tool-use mirrors the pattern proven in `utils/framework_refresh.py`:
forcing the model to return JSON via `tool_choice` so we never parse
prose. Failures fall back to the legacy HF prompt path so the pipeline
stays resilient on missing API key / network blips.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

import anthropic
import config


# ── Cache ───────────────────────────────────────────────────────────────
#
# Each surface produces its own structured analysis on every pipeline
# run. Without caching, that's 3 Anthropic calls per Run button click —
# expensive and slow. We hash the structured input payload (frameworks
# results, audit completeness, etc.) and cache the analysis. When the
# inputs don't change between runs, we serve from cache for free.
_CACHE_DIR = Path.home() / ".cache" / "esg" / "gap_analyzer"


def _cache_key(kind: str, payload: dict) -> str:
    blob = json.dumps({"kind": kind, "payload": payload}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _cache_get(key: str) -> dict | None:
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def _cache_put(key: str, value: dict) -> None:
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _CACHE_DIR / f"{key}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2)
    except OSError:
        # Cache is a best-effort optimization — never block the pipeline
        # on disk failures.
        pass


# ── Tool schemas ────────────────────────────────────────────────────────

_GAP_ROW_SCHEMA = {
    "type": "object",
    "description": (
        "One specific gap. Name the actual missing data point and the "
        "concrete dataset/source the user should onboard to close it."
    ),
    "properties": {
        "missing_data": {
            "type": "string",
            "description": (
                "Plain-English name of the specific data point that is "
                "missing or insufficient, e.g. 'Scope 3 Category 11 "
                "use-of-sold-products emissions' or 'Board independence "
                "percentage by tenure band'."
            ),
        },
        "dataset": {
            "type": "string",
            "description": (
                "Canonical ESG schema that holds this data — one of "
                "emissions, esg_metrics, supply_chain, energy, waste, "
                "diversity, financials, governance_docs, hr_docs. If "
                "none fit, name the custom dataset that should be "
                "created."
            ),
        },
        "source": {
            "type": "string",
            "description": (
                "Realistic upstream system or document the data should "
                "come from — e.g. 'ERP System (SAP)', 'HR System "
                "(Workday)', 'Supplier Portal (EcoVadis)', 'CDP "
                "disclosure', 'utility invoices', 'board minutes'. Be "
                "specific to what the user can actually wire up."
            ),
        },
        "framework_impact": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Frameworks / requirement IDs blocked by this gap, "
                "e.g. ['BRSR P6', 'CSRD E1-6', 'GRI 305-3']."
            ),
        },
        "action": {
            "type": "string",
            "description": (
                "Concrete next step in one sentence — what to upload, "
                "which connector to enable, or which team to ask."
            ),
        },
        "priority": {
            "type": "string",
            "enum": ["critical", "high", "medium", "low"],
        },
    },
    "required": ["missing_data", "dataset", "action", "priority"],
}


def _report_tool(name: str, description: str) -> dict:
    """Build a report tool schema for one of the three surfaces."""
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": (
                        "Two-to-three-sentence executive summary that "
                        "names specific frameworks/datasets and the "
                        "biggest concrete gap. No generic phrases like "
                        "'data is missing' or 'improve compliance'."
                    ),
                },
                "specific_gaps": {
                    "type": "array",
                    "description": (
                        "Field-level gaps. Order by priority (critical "
                        "first). Aim for 4-8 rows — enough to be "
                        "actionable, few enough to scan."
                    ),
                    "items": _GAP_ROW_SCHEMA,
                },
                "recommendations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "3-4 prioritized action bullets that name "
                        "specific datasets/connectors/frameworks. "
                        "Avoid generic advice."
                    ),
                },
            },
            "required": ["summary", "specific_gaps", "recommendations"],
        },
    }


_REG_TOOL = _report_tool(
    "report_regulatory_gaps",
    (
        "Report a structured ESG framework gap analysis. Identify the "
        "exact missing data fields per framework, the canonical dataset "
        "each field should live in, and a concrete remediation action."
    ),
)

_AUDIT_TOOL = _report_tool(
    "report_audit_gaps",
    (
        "Report a structured ESG audit gap analysis. Identify specific "
        "completeness, compliance, and integrity gaps blocking audit "
        "readiness, plus the dataset/evidence each gap depends on."
    ),
)

_DATA_TOOL = _report_tool(
    "report_data_quality_gaps",
    (
        "Report a structured ESG data-quality gap analysis. Identify "
        "specific missing schemas / under-populated datasets, the "
        "upstream system that owns the data, and a sequenced sourcing "
        "plan."
    ),
)


# ── Claude call wrapper ─────────────────────────────────────────────────


def _call_claude(tool: dict, system: str, user: str) -> dict | None:
    """Run a single tool-forced Claude call.

    Returns the parsed tool input dict, or ``None`` if the API key is
    missing or the call fails. Callers decide whether to fall back.
    """
    api_key = config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool["name"]},
            messages=[{"role": "user", "content": user}],
        )
    except Exception:
        # Network / auth / rate-limit issues all collapse to "no Claude
        # output" — callers fall back gracefully.
        return None

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == tool["name"]:
            payload = getattr(block, "input", None) or {}
            if isinstance(payload, dict):
                return payload
    return None


def _empty_result() -> dict:
    return {"summary": "", "specific_gaps": [], "recommendations": []}


# ── Public surfaces ─────────────────────────────────────────────────────


_SYSTEM_PROMPT = (
    "You are an ESG data and assurance specialist. You receive structured "
    "audit/regulatory data and must identify gaps at the field level — "
    "naming specific data points (e.g. 'Scope 3 Category 11 emissions'), "
    "specific datasets (e.g. emissions, supply_chain), and specific "
    "upstream systems (e.g. 'Supplier Portal (EcoVadis)', 'ERP System "
    "(SAP)'). Never write generic phrases like 'improve data quality' or "
    "'address missing data' — always name what is missing and where it "
    "should come from."
)


def analyze_regulatory_gaps(
    framework_results: dict[str, Any],
    *,
    fallback: Callable[[], str] | None = None,
) -> dict:
    """Produce a structured + narrative gap analysis for regulatory frameworks.

    ``framework_results`` is the per-framework dict produced by
    ``RegulatoryTrackerAgent._analyze_framework`` (covered / partial /
    missing counts plus a ``gaps`` list with ``missing_fields``).

    Returns ``{summary, specific_gaps, recommendations}``. On any
    failure the dict is populated from ``fallback`` (a callable that
    returns the legacy HF summary string) so the pipeline keeps moving.
    """
    payload = _compact_framework_payload(framework_results)
    if not payload["frameworks"]:
        return _empty_result()

    key = _cache_key("regulatory", payload)
    cached = _cache_get(key)
    if cached:
        return cached

    user = (
        "Analyze the structured framework gap data below and return a "
        "field-level gap report via the report_regulatory_gaps tool.\n\n"
        f"```json\n{json.dumps(payload, indent=2, default=str)}\n```\n\n"
        "For each specific gap, identify the EXACT missing data field "
        "(use the requirement text and missing_fields entries — don't "
        "just say 'emissions data'), the canonical ESG dataset that "
        "should hold it, the real upstream system, and the affected "
        "framework requirement IDs."
    )
    result = _call_claude(_REG_TOOL, _SYSTEM_PROMPT, user)

    if not result:
        narrative = fallback() if fallback else ""
        return {"summary": narrative, "specific_gaps": [], "recommendations": []}

    _cache_put(key, result)
    return result


def analyze_audit_gaps(
    readiness: dict[str, Any],
    completeness_audit: list[dict[str, Any]],
    compliance_checklist: list[dict[str, Any]],
    integrity_gaps: dict[str, Any],
    *,
    company_name: str = "",
    fallback_summary: Callable[[], str] | None = None,
    fallback_recommendations: Callable[[], list[str]] | None = None,
) -> dict:
    """Produce a structured audit gap analysis covering completeness,
    compliance, and integrity gaps.
    """
    payload = {
        "company": company_name,
        "readiness": {
            "overall": readiness.get("overall"),
            "grade": readiness.get("grade"),
            "completeness": readiness.get("completeness"),
            "compliance": readiness.get("compliance"),
            "evidence": readiness.get("evidence"),
        },
        "completeness_audit": [
            {
                "dataset": item.get("dataset"),
                "status": item.get("status"),
                "completeness": item.get("completeness"),
                "records": item.get("records"),
                "priority": item.get("priority"),
            }
            for item in (completeness_audit or [])
        ],
        "failed_compliance_checks": [
            {
                "framework": item.get("framework"),
                "requirement": item.get("requirement"),
                "status": item.get("status"),
                "score": item.get("score"),
                "covered": item.get("covered"),
                "total": item.get("total"),
            }
            for item in (compliance_checklist or [])
            if item.get("status") in {"Fail", "Warning"}
        ],
        "integrity_gaps": [
            {
                "metric_id": g.get("metric_id"),
                "metric_name": g.get("metric_name"),
                "pillar": g.get("pillar"),
                "gap_detail": g.get("gap_detail"),
                "severity": g.get("severity"),
            }
            for g in (integrity_gaps.get("gaps") or [])
        ],
    }
    if not payload["completeness_audit"] and not payload["failed_compliance_checks"] and not payload["integrity_gaps"]:
        return _empty_result()

    key = _cache_key("audit", payload)
    cached = _cache_get(key)
    if cached:
        return cached

    user = (
        "Analyze the audit readiness data below and return a field-level "
        "gap report via the report_audit_gaps tool. For each specific "
        "gap, name the exact dataset (from the completeness_audit list) "
        "or compliance requirement that is failing, the upstream system "
        "that owns the evidence, and the concrete remediation step.\n\n"
        f"```json\n{json.dumps(payload, indent=2, default=str)}\n```\n"
    )
    result = _call_claude(_AUDIT_TOOL, _SYSTEM_PROMPT, user)

    if not result:
        return {
            "summary": fallback_summary() if fallback_summary else "",
            "specific_gaps": [],
            "recommendations": fallback_recommendations() if fallback_recommendations else [],
        }

    _cache_put(key, result)
    return result


def analyze_data_quality_gaps(
    quality_scores: dict[str, Any],
    missing_data_alerts: list[dict[str, Any]],
    canonical_datasets: dict[str, Any] | None = None,
    connector_statuses: dict[str, Any] | None = None,
    *,
    fallback_summary: Callable[[], list[str]] | None = None,
) -> dict:
    """Produce a structured data-quality gap analysis: what schemas are
    missing or under-populated, which upstream system owns each, and the
    sequenced sourcing plan.
    """
    payload = {
        "quality_scores": {
            name: {
                "completeness": q.get("completeness"),
                "total_records": q.get("total_records"),
                "avg_confidence": q.get("avg_confidence"),
                "null_count": q.get("null_count"),
            }
            for name, q in (quality_scores or {}).items()
        },
        "missing_data_alerts": [
            {
                "severity": a.get("severity"),
                "dataset": a.get("dataset"),
                "message": a.get("message"),
                "action": a.get("action"),
            }
            for a in (missing_data_alerts or [])
        ],
        "canonical_datasets": {
            name: {"source": p.get("source"), "records": p.get("records")}
            for name, p in (canonical_datasets or {}).items()
        },
        "connectors": {
            key: {
                "name": s.get("name"),
                "type": s.get("type"),
                "status": s.get("status"),
                "records": s.get("records"),
            }
            for key, s in (connector_statuses or {}).items()
        },
    }
    if not payload["quality_scores"] and not payload["missing_data_alerts"]:
        return _empty_result()

    key = _cache_key("data_quality", payload)
    cached = _cache_get(key)
    if cached:
        return cached

    user = (
        "Analyze the data collection status below and return a "
        "field-level data-quality gap report via the "
        "report_data_quality_gaps tool. For each specific gap, name the "
        "exact dataset/schema that is missing or under-populated, the "
        "actual upstream connector or system (use the connectors list "
        "for real names like 'ERP System (SAP)'), and the concrete "
        "sourcing action.\n\n"
        f"```json\n{json.dumps(payload, indent=2, default=str)}\n```\n"
    )
    result = _call_claude(_DATA_TOOL, _SYSTEM_PROMPT, user)

    if not result:
        bullets = fallback_summary() if fallback_summary else []
        return {
            "summary": " ".join(bullets) if bullets else "",
            "specific_gaps": [],
            "recommendations": bullets,
        }

    _cache_put(key, result)
    return result


# ── Helpers ─────────────────────────────────────────────────────────────


def render_specific_gaps(st_module, gap_analysis: dict | None, *, heading: str = "Specific gaps") -> None:
    """Render the structured Claude gap analysis as summary + table + bullets.

    Pages call this when they have a ``gap_analysis`` dict on agent
    results. If the dict is empty (Claude key missing, fallback path),
    we render nothing so the legacy narrative block above still works.
    """
    if not gap_analysis:
        return
    specific = gap_analysis.get("specific_gaps") or []
    recommendations = gap_analysis.get("recommendations") or []
    summary = gap_analysis.get("summary") or ""

    if not specific and not recommendations:
        return

    if summary:
        st_module.markdown(f"_{summary}_")

    if specific:
        st_module.markdown(f"##### {heading}")
        import pandas as pd
        from utils.streamlit_compat import safe_dataframe

        priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        rows = []
        for gap in specific:
            rows.append({
                "Priority": f"{priority_icon.get(gap.get('priority', 'medium'), '⚪')} {gap.get('priority', '').title()}",
                "Missing data": gap.get("missing_data", ""),
                "Dataset": gap.get("dataset", ""),
                "Source": gap.get("source", ""),
                "Frameworks impacted": ", ".join(gap.get("framework_impact") or []),
                "Action": gap.get("action", ""),
            })
        safe_dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if recommendations:
        st_module.markdown("##### Prioritized actions")
        for rec in recommendations:
            st_module.markdown(f"- {rec}")


def _compact_framework_payload(framework_results: dict[str, Any]) -> dict:
    """Strip framework_results down to fields Claude needs.

    The full ``framework_results`` dict can include 100+ requirements
    with verbose text. We send only what's needed to identify field-level
    gaps (status, missing_fields, priorities, reasons) so prompts stay
    inside reasonable token budgets.
    """
    out_frameworks = {}
    for fw_name, result in (framework_results or {}).items():
        gaps = []
        for gap in result.get("gaps", []) or []:
            # Skip "Pass" rows — only send gaps the model needs to act
            # on. We send up to 15 per framework, prioritized.
            gaps.append({
                "requirement_id": gap.get("requirement_id"),
                "requirement": gap.get("requirement"),
                "status": gap.get("status"),
                "priority": gap.get("priority"),
                "missing_fields": gap.get("missing_fields") or [],
                "covered_fields": gap.get("covered_fields") or [],
                "reason": gap.get("reason"),
            })
        # Critical/high priority first so truncation drops low-impact rows.
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        gaps.sort(key=lambda g: priority_order.get(g.get("priority", "medium"), 2))
        out_frameworks[fw_name] = {
            "full_name": result.get("full_name", fw_name),
            "mandatory": result.get("mandatory"),
            "compliance_pct": result.get("compliance_pct"),
            "covered": result.get("covered"),
            "partial": result.get("partial"),
            "missing": result.get("missing"),
            "total": result.get("total"),
            "gaps": gaps[:15],
        }
    return {"frameworks": out_frameworks}

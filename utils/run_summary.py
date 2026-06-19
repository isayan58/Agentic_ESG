"""Headline-metrics summariser for a pipeline-run snapshot.

Extracted verbatim from ``utils/chat_drawer._headline_metrics`` during the
LangGraph + MCP migration so the exact same grounding string is produced
whether it is built inline for the system prompt or served over the
``esg-data`` MCP server's ``get_headline_metrics`` tool. Pure dict-in /
str-out — no Streamlit, no network.
"""
from __future__ import annotations


def headline_metrics(run: dict) -> str:
    """Compact, model-facing summary of the run's headline numbers.

    Returns an empty string when ``run`` carries nothing worth summarising,
    so callers can ``if headline:`` cheaply.
    """
    if not run:
        return ""
    roi    = run.get("roi_agent",          {}) or {}
    audit  = run.get("audit_agent",        {}) or {}
    carbon = run.get("carbon_accountant",  {}) or {}
    risk   = run.get("risk_predictor",     {}) or {}
    data   = run.get("data_collector",     {}) or {}
    regs   = run.get("regulatory_tracker", {}) or {}
    iqs    = roi.get("investment_quality_score", {}) or {}
    readiness = audit.get("readiness_score", {}) or {}

    lines: list[str] = ["HEADLINE METRICS FOR THIS RUN (always reference these):"]
    if iqs:
        lines.append(
            f"  • IQS: {iqs.get('score','—')}/100  •  Grade: {iqs.get('grade','—')}"
        )
        comps = iqs.get("components") or {}
        if comps:
            lines.append("      components → " + " | ".join(
                f"{k}: {v}" for k, v in comps.items()
            ))
    if readiness:
        lines.append(
            f"  • Audit readiness: {readiness.get('overall','—')}/100 "
            f"(grade {readiness.get('grade','—')})"
        )
    if carbon:
        lines.append(
            f"  • Total emissions: {carbon.get('total_emissions_current','—')} tCO2e "
            f"(YoY {carbon.get('yoy_change_pct','—')}%)"
        )
    if risk:
        lines.append(
            f"  • Risk: {risk.get('overall_risk_score','—')}/100 "
            f"({risk.get('risk_level','—')})"
        )
    if data:
        lines.append(
            f"  • Data: {data.get('total_records','—')} records / "
            f"{data.get('datasets_loaded','—')} datasets  •  "
            f"completeness {data.get('overall_completeness','—')}%"
        )
    fw = (regs or {}).get("framework_results") or {}
    if fw:
        lines.append("  • Frameworks → " + "; ".join(
            f"{n}: {f.get('compliance_pct','—')}%" for n, f in list(fw.items())[:6]
        ))
    return "\n".join(lines) if len(lines) > 1 else ""


__all__ = ["headline_metrics"]

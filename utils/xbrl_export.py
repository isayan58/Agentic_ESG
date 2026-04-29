"""XBRL / Inline XBRL exporter for ESG Pilot reports.

The SEC Climate-Related Disclosures rule and CSRD/ESRS both require
machine-readable digital tagging. Most ESG dashboards stop at PDF;
shipping XBRL closes the regulatory gap.

Scope of this MVP
-----------------
* Quantitative facts only — emissions (Scope 1/2/3), energy, financials,
  ESG Investment Quality Score. Narrative tagging (block tags) is
  intentionally out of scope here; that's the next iteration.
* Two output formats:
    * ``build_xbrl_instance(...)`` → raw XBRL 2.1 instance document (XML)
    * ``build_inline_xbrl(...)``   → iXBRL HTML wrapper that embeds the
      facts inside an audit-ready human-readable report. iXBRL is what
      the SEC and EFRAG actually accept for filings.
* Custom taxonomy URI — we declare facts under a synthetic
  ``http://esg-pilot.dev/taxonomy/2026`` namespace. For a real filing
  you'd swap this for the regulator's published taxonomy (ESRS-XBRL,
  ESEF, SEC Climate). The element names are deliberately aligned with
  ESRS / SEC concept names (``ScopeOneEmissions``, etc.) so that swap
  is mechanical.

Why not jinja or a pip package?
-------------------------------
``python-xbrl`` and friends pin specific taxonomy assumptions (US-GAAP,
IFRS) that don't apply to a custom ESG concept set. Hand-rolling the
XML keeps the dependency surface flat (Python stdlib only) and the
generator auditable in one screen.

Public API
----------
``build_xbrl_instance(report) -> str``
``build_inline_xbrl(report) -> str``
``build_facts_csv(report) -> str``       # debug / cross-check helper
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Iterable
from xml.sax.saxutils import escape, quoteattr

# Synthetic namespace for ESG Pilot facts. Replace with the regulator's
# taxonomy URI when filing for real (e.g.
# "http://www.efrag.org/xbrl/esrs/2026" or the SEC equivalent).
ESG_NS = "http://esg-pilot.dev/taxonomy/2026"
ESG_PREFIX = "esg"

# Standard XBRL namespaces
XBRLI_NS = "http://www.xbrl.org/2003/instance"
LINK_NS = "http://www.xbrl.org/2003/linkbase"
XLINK_NS = "http://www.w3.org/1999/xlink"
ISO4217_NS = "http://www.xbrl.org/2003/iso4217"


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------
@dataclass
class Fact:
    """One XBRL fact: a concept + a value + the period/entity context.

    ``decimals`` follows the XBRL spec: ``-3`` means "rounded to thousands",
    ``0`` means "rounded to ones", ``"INF"`` means exact. ESG Pilot's
    aggregated outputs are rounded to a couple of decimals at most so
    we default to ``0`` for integers and ``2`` for floats.
    """
    concept: str
    value: str
    unit_ref: str | None      # e.g. "tCO2e", "USD", "kWh", "Pure"
    decimals: str = "0"
    period_start: str = ""    # ISO date for duration facts; empty for instant
    period_end: str = ""      # ISO date


def _money_unit(currency: str = "INR") -> str:
    """Return an XBRL unit ref for a currency. Uppercased ISO 4217 code."""
    return currency.strip().upper() or "INR"


def _to_iso_date(value: str | None) -> str:
    """Coerce common date strings into ``YYYY-MM-DD``.

    ESG Pilot agents emit a mix of ISO timestamps (``2026-04-29T10:32:00``),
    bare ISO dates, and free-form strings (``"FY2026"``). We strip down
    to the date prefix when possible and fall back to today otherwise so
    XBRL validation doesn't choke.
    """
    if not value:
        return date.today().isoformat()
    s = str(value).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if re.fullmatch(r"\d{4}", s):
        return f"{s}-12-31"
    return date.today().isoformat()


def _safe_number(value, default: float = 0.0) -> float:
    """Tolerant float coercion for agent outputs that occasionally come
    back as ``"N/A"`` or ``None``."""
    if value is None:
        return default
    try:
        if isinstance(value, str):
            cleaned = re.sub(r"[^\d.\-]", "", value)
            return float(cleaned) if cleaned else default
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_facts(report: dict) -> list[Fact]:
    """Walk a Report Generator output dict and produce a flat fact list.

    We only emit facts we have ground truth for — missing or non-numeric
    fields are skipped rather than tagged as zero, because XBRL
    consumers (XBRL US, SEC EDGAR) treat absent and zero very
    differently.
    """
    facts: list[Fact] = []

    # Period: prefer the report's generated_at; fall back to today.
    fy_end = _to_iso_date(report.get("generated_at"))
    fy_start = f"{fy_end[:4]}-04-01"  # Indian FY default; harmless for US/EU

    # ── Carbon Accountant -----------------------------------------------
    carbon = report.get("carbon_highlights") or {}
    total_emissions = _safe_number(carbon.get("total_emissions"))
    if total_emissions:
        facts.append(Fact(
            concept="TotalGreenhouseGasEmissions",
            value=f"{total_emissions:.2f}",
            unit_ref="tCO2e",
            decimals="2",
            period_start=fy_start, period_end=fy_end,
        ))

    # Scope-level breakdown if available — the report's full payload may
    # include it under nested carbon results, depending on the agent
    # version. Be defensive about shape.
    scope_totals = (report.get("scope_totals_current")
                    or (report.get("carbon_results") or {}).get("scope_totals_current")
                    or {})
    scope_concept = {
        "Scope 1": "ScopeOneEmissions",
        "Scope 2": "ScopeTwoEmissions",
        "Scope 3": "ScopeThreeEmissions",
    }
    for label, concept in scope_concept.items():
        v = _safe_number(scope_totals.get(label))
        if v:
            facts.append(Fact(
                concept=concept,
                value=f"{v:.2f}",
                unit_ref="tCO2e",
                decimals="2",
                period_start=fy_start, period_end=fy_end,
            ))

    # ── Compliance -------------------------------------------------------
    compliance = report.get("compliance_summary") or {}
    if compliance.get("overall") not in (None, "N/A"):
        facts.append(Fact(
            concept="OverallRegulatoryCompliancePercent",
            value=f"{_safe_number(compliance['overall']):.2f}",
            unit_ref="Pure",
            decimals="2",
            period_start=fy_start, period_end=fy_end,
        ))
    for fw_name, pct in (compliance.get("frameworks") or {}).items():
        # Concept names are conventionally PascalCase
        concept = f"Compliance{re.sub(r'[^A-Za-z0-9]', '', fw_name)}Percent"
        facts.append(Fact(
            concept=concept,
            value=f"{_safe_number(pct):.2f}",
            unit_ref="Pure",
            decimals="2",
            period_start=fy_start, period_end=fy_end,
        ))

    # ── ROI Agent --------------------------------------------------------
    roi = report.get("roi_summary") or {}
    iqs = report.get("investment_quality") or {}
    company = report.get("company") or {}
    currency = company.get("currency_code") or "INR"

    if roi.get("total_esg_capex") is not None:
        facts.append(Fact(
            concept="ESGLinkedCapitalExpenditure",
            value=f"{_safe_number(roi['total_esg_capex']):.2f}",
            unit_ref=_money_unit(currency),
            decimals="-5",  # crores → 5 decimals scale, illustrative
            period_start=fy_start, period_end=fy_end,
        ))
    if roi.get("net_financial_benefit") is not None:
        facts.append(Fact(
            concept="ESGNetFinancialBenefit",
            value=f"{_safe_number(roi['net_financial_benefit']):.2f}",
            unit_ref=_money_unit(currency),
            decimals="-5",
            period_start=fy_start, period_end=fy_end,
        ))
    if roi.get("roi_pct") is not None:
        facts.append(Fact(
            concept="ESGFinancialReturnPercent",
            value=f"{_safe_number(roi['roi_pct']):.2f}",
            unit_ref="Pure",
            decimals="2",
            period_start=fy_start, period_end=fy_end,
        ))
    if iqs.get("score") is not None:
        facts.append(Fact(
            concept="ESGInvestmentQualityScore",
            value=f"{_safe_number(iqs['score']):.2f}",
            unit_ref="Pure",
            decimals="2",
            period_start=fy_start, period_end=fy_end,
        ))

    return facts


# ---------------------------------------------------------------------------
# XBRL instance (raw XML)
# ---------------------------------------------------------------------------
def _entity_identifier(report: dict) -> tuple[str, str]:
    """Return (scheme, identifier) for the reporting entity.

    Default scheme is the LEI (Legal Entity Identifier) URL — most
    regulators accept it. Falls back to a synthetic identifier if the
    company profile didn't supply one, so the export still validates
    structurally even on the demo data.
    """
    company = report.get("company") or {}
    lei = (company.get("lei") or "").strip()
    if lei:
        return ("http://standards.iso.org/iso/17442", lei)
    name = (company.get("company_name") or "ESGPilotEntity").strip()
    return (
        "http://esg-pilot.dev/identifier",
        re.sub(r"[^A-Za-z0-9]", "", name)[:32] or "ESGPilotEntity",
    )


def _render_unit(unit_id: str) -> str:
    """Render the XML for one ``<xbrli:unit>`` element."""
    if unit_id == "Pure":
        measure = "xbrli:pure"
    elif unit_id in ("tCO2e", "kWh", "MWh", "kg", "kl"):
        # Custom non-monetary units — declare under our taxonomy ns
        measure = f"{ESG_PREFIX}:{unit_id}"
    elif re.fullmatch(r"[A-Z]{3}", unit_id):
        # ISO-4217 currency code
        measure = f"iso4217:{unit_id}"
    else:
        measure = f"{ESG_PREFIX}:{unit_id}"
    return (
        f'  <xbrli:unit id={quoteattr(unit_id)}>\n'
        f'    <xbrli:measure>{escape(measure)}</xbrli:measure>\n'
        f'  </xbrli:unit>\n'
    )


def _render_context(context_id: str, *, scheme: str, identifier: str,
                    period_start: str, period_end: str) -> str:
    """Render an ``<xbrli:context>`` block. Duration period only — instant
    facts aren't currently emitted."""
    return (
        f'  <xbrli:context id={quoteattr(context_id)}>\n'
        f'    <xbrli:entity>\n'
        f'      <xbrli:identifier scheme={quoteattr(scheme)}>'
        f'{escape(identifier)}</xbrli:identifier>\n'
        f'    </xbrli:entity>\n'
        f'    <xbrli:period>\n'
        f'      <xbrli:startDate>{period_start}</xbrli:startDate>\n'
        f'      <xbrli:endDate>{period_end}</xbrli:endDate>\n'
        f'    </xbrli:period>\n'
        f'  </xbrli:context>\n'
    )


def build_xbrl_instance(report: dict) -> str:
    """Return a complete XBRL 2.1 instance document as a UTF-8 XML string.

    Output is well-formed XML; dropping it through ``xmllint`` should
    return success. Schema validation against a published taxonomy is
    out of scope here — the synthetic ``ESG_NS`` doesn't have a public
    XSD. Wire your regulator's XSD in when filing for real.
    """
    facts = extract_facts(report)
    scheme, identifier = _entity_identifier(report)

    # Group facts by (start, end) so each context_id is reused.
    contexts: dict[str, tuple[str, str]] = {}
    units: set[str] = set()
    for f in facts:
        key = f"P{f.period_start}_{f.period_end}".replace("-", "")
        contexts[key] = (f.period_start, f.period_end)
        if f.unit_ref:
            units.add(f.unit_ref)

    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>\n')
    parts.append(
        '<xbrli:xbrl '
        'xmlns:xbrli="http://www.xbrl.org/2003/instance" '
        'xmlns:link="http://www.xbrl.org/2003/linkbase" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'xmlns:iso4217="{ISO4217_NS}" '
        f'xmlns:{ESG_PREFIX}="{ESG_NS}">\n'
    )
    # Schema reference — points at our synthetic taxonomy. Replace with
    # the regulator-published XSD when filing for real.
    parts.append(
        f'  <link:schemaRef xlink:type="simple" '
        f'xlink:href="{ESG_NS}/esg-taxonomy.xsd"/>\n'
    )

    for context_id, (start, end) in sorted(contexts.items()):
        parts.append(_render_context(
            context_id, scheme=scheme, identifier=identifier,
            period_start=start, period_end=end,
        ))
    for unit_id in sorted(units):
        parts.append(_render_unit(unit_id))

    for f in facts:
        context_id = f"P{f.period_start}_{f.period_end}".replace("-", "")
        unit_attr = f' unitRef={quoteattr(f.unit_ref)}' if f.unit_ref else ""
        decimals_attr = f' decimals={quoteattr(f.decimals)}' if f.decimals else ""
        parts.append(
            f'  <{ESG_PREFIX}:{f.concept} '
            f'contextRef={quoteattr(context_id)}'
            f'{unit_attr}{decimals_attr}>'
            f'{escape(f.value)}'
            f'</{ESG_PREFIX}:{f.concept}>\n'
        )

    parts.append('</xbrli:xbrl>\n')
    return "".join(parts)


# ---------------------------------------------------------------------------
# Inline XBRL (iXBRL) — embedded in HTML
# ---------------------------------------------------------------------------
def build_inline_xbrl(report: dict) -> str:
    """Return an iXBRL HTML document with facts inline-tagged.

    Layout: a minimally-styled report wrapper (executive summary +
    headline numbers) where every quantitative figure is wrapped in
    ``<ix:nonFraction>`` so an iXBRL viewer can extract it. This is the
    format SEC EDGAR and EFRAG ESEF actually accept.
    """
    facts = extract_facts(report)
    scheme, identifier = _entity_identifier(report)
    company = report.get("company") or {}
    company_name = html.escape((company.get("company_name") or "ESG Entity"))

    # Group by context the same way the instance does
    contexts: dict[str, tuple[str, str]] = {}
    units: set[str] = set()
    for f in facts:
        key = f"P{f.period_start}_{f.period_end}".replace("-", "")
        contexts[key] = (f.period_start, f.period_end)
        if f.unit_ref:
            units.add(f.unit_ref)

    fact_rows: list[str] = []
    for f in facts:
        context_id = f"P{f.period_start}_{f.period_end}".replace("-", "")
        # Each <ix:nonFraction> needs the same attrs an offline XBRL
        # processor would expect: name, contextRef, unitRef, decimals.
        attrs = (
            f'name="{ESG_PREFIX}:{f.concept}" '
            f'contextRef="{context_id}" '
            f'{f"unitRef={quoteattr(f.unit_ref)}" if f.unit_ref else ""} '
            f'decimals={quoteattr(f.decimals)}'
        )
        fact_rows.append(
            f'<tr><td>{escape(f.concept)}</td>'
            f'<td><ix:nonFraction {attrs}>{escape(f.value)}</ix:nonFraction></td>'
            f'<td>{escape(f.unit_ref or "")}</td>'
            f'<td>{escape(f.period_start)} → {escape(f.period_end)}</td></tr>'
        )

    contexts_xml = "".join(
        f'<xbrli:context id={quoteattr(cid)}>'
        f'<xbrli:entity><xbrli:identifier scheme={quoteattr(scheme)}>'
        f'{escape(identifier)}</xbrli:identifier></xbrli:entity>'
        f'<xbrli:period><xbrli:startDate>{start}</xbrli:startDate>'
        f'<xbrli:endDate>{end}</xbrli:endDate></xbrli:period>'
        f'</xbrli:context>'
        for cid, (start, end) in sorted(contexts.items())
    )
    units_xml = "".join(_render_unit(u).strip() for u in sorted(units))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL"
      xmlns:xbrli="{XBRLI_NS}"
      xmlns:link="{LINK_NS}"
      xmlns:xlink="{XLINK_NS}"
      xmlns:iso4217="{ISO4217_NS}"
      xmlns:{ESG_PREFIX}="{ESG_NS}">
<head>
<title>iXBRL ESG Report — {company_name}</title>
<style>
 body {{ font-family: -apple-system, sans-serif; max-width: 960px; margin: 2rem auto;
         color: #1a202c; }}
 h1 {{ color: #D04A02; border-bottom: 2px solid #D04A02; padding-bottom: .35rem; }}
 table {{ width: 100%; border-collapse: collapse; margin-top: 1rem; }}
 th, td {{ text-align: left; padding: .55rem .75rem; border-bottom: 1px solid #e2e8f0; }}
 th {{ background: #f8fafc; }}
 .meta {{ color: #64748b; font-size: .9rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
<div style="display:none;">
  <ix:header>
    <ix:hidden>
      <link:schemaRef xlink:type="simple" xlink:href="{ESG_NS}/esg-taxonomy.xsd"/>
    </ix:hidden>
    <ix:references>
      <link:schemaRef xlink:type="simple" xlink:href="{ESG_NS}/esg-taxonomy.xsd"/>
    </ix:references>
    <ix:resources>{contexts_xml}{units_xml}</ix:resources>
  </ix:header>
</div>

<h1>{company_name} — ESG Disclosure (iXBRL)</h1>
<p class="meta">Generated by ESG Pilot. Each numeric value below is
inline-tagged using the
<code>{escape(ESG_PREFIX)}:</code> taxonomy at <code>{escape(ESG_NS)}</code>.</p>
<table>
  <thead><tr><th>Concept</th><th>Value</th><th>Unit</th><th>Period</th></tr></thead>
  <tbody>
    {''.join(fact_rows) or '<tr><td colspan="4">No quantitative facts available — run the pipeline first.</td></tr>'}
  </tbody>
</table>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Debug helper
# ---------------------------------------------------------------------------
def build_facts_csv(report: dict) -> str:
    """Return the extracted facts as a CSV string. Useful for cross-checking."""
    import io as _io
    import csv

    buf = _io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["concept", "value", "unit", "decimals",
                     "period_start", "period_end"])
    for f in extract_facts(report):
        writer.writerow([
            f.concept, f.value, f.unit_ref or "", f.decimals,
            f.period_start, f.period_end,
        ])
    return buf.getvalue()


__all__ = [
    "Fact",
    "extract_facts",
    "build_xbrl_instance",
    "build_inline_xbrl",
    "build_facts_csv",
    "ESG_NS",
    "ESG_PREFIX",
]

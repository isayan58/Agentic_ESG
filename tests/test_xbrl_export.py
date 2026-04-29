"""XBRL exporter: well-formed output, fact extraction, taxonomy mapping."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from utils.xbrl_export import (
    ESG_NS,
    ESG_PREFIX,
    build_facts_csv,
    build_inline_xbrl,
    build_xbrl_instance,
    extract_facts,
)


def _sample_report() -> dict:
    """Minimal but realistic Report Generator output for the exporter to chew on."""
    return {
        "generated_at": "2026-04-29T10:32:00",
        "company": {
            "company_name": "GreenTech Solutions Pvt Ltd",
            "currency_code": "INR",
            "lei": "5493001KJTIIGC8Y1R12",
        },
        "carbon_highlights": {
            "total_emissions": 14250.42,
            "yoy_change": -8.2,
            "carbon_intensity": 12.4,
        },
        "scope_totals_current": {
            "Scope 1": 3200.0,
            "Scope 2": 5600.0,
            "Scope 3": 5450.42,
        },
        "compliance_summary": {
            "overall": 78.5,
            "frameworks": {"BRSR": 82.0, "CSRD": 68.0, "GRI": 91.0},
        },
        "roi_summary": {
            "total_esg_capex": 120.5,
            "net_financial_benefit": 24.7,
            "roi_pct": 18.3,
        },
        "investment_quality": {"score": 72.5, "grade": "B+"},
    }


class TestFactExtraction:
    def test_extracts_expected_facts(self):
        facts = extract_facts(_sample_report())
        concepts = {f.concept for f in facts}
        # Headline facts that must always appear when the source data
        # is present. If we ever rename a concept, this test should
        # update deliberately.
        assert "TotalGreenhouseGasEmissions" in concepts
        assert "ScopeOneEmissions" in concepts
        assert "ScopeTwoEmissions" in concepts
        assert "ScopeThreeEmissions" in concepts
        assert "OverallRegulatoryCompliancePercent" in concepts
        assert "ESGInvestmentQualityScore" in concepts
        assert "ESGFinancialReturnPercent" in concepts

    def test_skips_missing_or_NA_values(self):
        report = {"compliance_summary": {"overall": "N/A"}}
        facts = extract_facts(report)
        # No-op input must produce no facts — we never tag absent data
        # as zero, because XBRL consumers treat absent vs. zero very
        # differently.
        assert facts == []

    def test_framework_concept_names_safe(self):
        # Framework names with dashes / spaces shouldn't break concept
        # naming. Output must be PascalCase + alphanumeric.
        facts = extract_facts({
            "compliance_summary": {
                "overall": 90,
                "frameworks": {"SEC-Climate Rule": 75},
            },
        })
        names = [f.concept for f in facts]
        sec_concept = next(n for n in names if n.startswith("Compliance"))
        assert re.fullmatch(r"[A-Za-z0-9]+", sec_concept)
        assert "SEC" in sec_concept and "Climate" in sec_concept


class TestInstanceWellFormedness:
    def test_instance_parses_as_xml(self):
        # The bare minimum guarantee: ``xml.etree`` can parse the output.
        # Without this, a regulator's validator can't even start.
        xml_text = build_xbrl_instance(_sample_report())
        root = ET.fromstring(xml_text)
        # Root tag is in the xbrli namespace
        assert root.tag.endswith("xbrl")

    def test_instance_includes_taxonomy_namespace(self):
        xml_text = build_xbrl_instance(_sample_report())
        # Both the namespace declaration and one tagged fact must appear.
        assert ESG_NS in xml_text
        assert f"{ESG_PREFIX}:TotalGreenhouseGasEmissions" in xml_text

    def test_instance_uses_lei_when_present(self):
        xml_text = build_xbrl_instance(_sample_report())
        assert "5493001KJTIIGC8Y1R12" in xml_text
        assert "iso/17442" in xml_text  # LEI scheme

    def test_instance_falls_back_to_synthetic_identifier(self):
        report = _sample_report()
        report["company"].pop("lei")
        report["company"]["company_name"] = "ACME & Co. !!!"
        xml_text = build_xbrl_instance(report)
        # Identifier sanitised to alphanumeric only — no XML entity
        # leakage from the entity-identifier path.
        assert "ACME" in xml_text
        assert "& Co." not in xml_text


class TestInlineXBRL:
    def test_inline_xbrl_well_formed(self):
        html = build_inline_xbrl(_sample_report())
        # iXBRL is XHTML — must parse cleanly
        ET.fromstring(html)

    def test_inline_xbrl_tags_facts(self):
        html = build_inline_xbrl(_sample_report())
        # Each numeric fact wrapped in an ix:nonFraction element
        assert "ix:nonFraction" in html
        # Concept name appears in the contextRef-style attribute
        assert f"{ESG_PREFIX}:TotalGreenhouseGasEmissions" in html


class TestFactsCSV:
    def test_csv_has_header_and_rows(self):
        csv_text = build_facts_csv(_sample_report())
        lines = csv_text.strip().splitlines()
        # Header + at least one fact line
        assert lines[0].split(",")[0] == "concept"
        assert len(lines) > 1

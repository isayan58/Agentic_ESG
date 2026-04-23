import pytest

from agents.report_generator import ReportGeneratorAgent
from core import hf_client as hf_module
from core.state_manager import state_manager


def test_report_generator_produces_dashboard_templates_and_insights(monkeypatch):
    def fake_generate_text(prompt, max_tokens=300):
        if "Provide one sample Power BI report design" in prompt:
            return (
                "Power BI:\n- Page 1: ESG scorecard with carbon, compliance, and ROI cards.\n"
                "- Page 2: Emissions trend chart and compliance heatmap.\nQuickSight:\n- Dashboard 1: Scope 1/2/3 emissions analysis.\n"
                "- Dashboard 2: Framework compliance tracker."
            )
        return (
            "- Full ESG Executive Report: Ideal for investors with a consolidated view.\n"
            "- Carbon & Environment Brief: Focused on emissions and energy performance.\n"
            "- Compliance Scorecard: Summarizes framework alignment and regulatory gaps.\n"
            "- Stakeholder Narrative Pack: Tailored messaging for board and regulators.\n"
            "- ROI and Value Creation Brief: Highlights financial and strategic benefits.\n"
            "- Prioritized Actions Summary: Recommended next steps from audit and risk findings."
        )

    def fake_subscribe(channel):
        if channel == "carbon_results":
            return {
                "total_emissions_current": 5200,
                "yoy_change_pct": 10,
                "carbon_intensity": 34,
            }
        if channel == "regulatory_results":
            return {
                "overall_compliance": 85,
                "framework_results": {
                    "NGRBC": {
                        "full_name": "NGRBC",
                        "compliance_pct": 88,
                        "covered": 18,
                        "total": 20,
                        "gaps": [],
                    }
                },
            }
        if channel == "audit_results":
            return {
                "readiness_score": {"grade": "B"},
                "audit_recommendations": ["Increase evidence traceability", "Close control gaps in procurement approvals"],
            }
        if channel == "data_collection_results":
            return {
                "datasets_loaded": 5,
                "total_records": 145,
                "overall_completeness": 91,
                "data_quality_summary": ["All core datasets loaded.", "Minor supplier data gaps remain."]
            }
        if channel == "roi_results":
            return {
                "financial_roi": {"roi_pct": 16, "net_financial_benefit": 11},
                "investment_quality_score": {"grade": "B+"},
                "roi_recommendations": ["Expand energy efficiency investments", "Link ESG performance to supplier financing"]
            }
        if channel == "risk_results":
            return {
                "risk_recommendations": ["Hedge climate risk for high-emission assets"]
            }
        if channel == "stakeholder_results":
            return {"distribution_plan": "Use board deck, regulator brief, and employee newsletter."}
        return None

    monkeypatch.setattr(hf_module.hf_client, "generate_text", fake_generate_text)
    monkeypatch.setattr(state_manager, "subscribe", fake_subscribe)

    report_agent = ReportGeneratorAgent()
    results = report_agent.run()

    assert "recommended_reports" in results
    assert "dashboard_templates" in results
    assert "actionable_insights" in results
    assert "data_quality_summary" in results
    assert "regulatory_action_plan" in results
    assert "carbon_insights" in results
    assert "risk_recommendations" in results
    assert "audit_recommendations" in results
    assert "roi_recommendations" in results
    assert "distribution_plan" in results
    assert isinstance(results["recommended_reports"], list)
    assert isinstance(results["dashboard_templates"], dict)
    assert isinstance(results["actionable_insights"], list)
    assert isinstance(results["data_quality_summary"], list)
    assert isinstance(results["regulatory_action_plan"], list)
    assert isinstance(results["carbon_insights"], list)
    assert isinstance(results["risk_recommendations"], list)
    assert isinstance(results["audit_recommendations"], list)
    assert isinstance(results["roi_recommendations"], list)
    assert isinstance(results["distribution_plan"], str)
    assert "power_bi" in results["dashboard_templates"]
    assert "quicksight" in results["dashboard_templates"]

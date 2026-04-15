"""Agent 8: Stakeholder Agent — Audience-tailored ESG communications,
ESG Business Case Generator, and J-Curve expectation setting.

Hypothesis mapping:
  H6 — J-Curve: short-term costs → long-term payback (communication framing)
"""
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.company_config import company_cfg


AUDIENCE_PROFILES = {
    "investors": {
        "label": "Investors & Shareholders",
        "tone": "professional, data-driven, forward-looking",
        "focus": "financial materiality, risk-adjusted returns, ESG rating trajectory",
        "format": "concise with key metrics and outlook",
    },
    "regulators": {
        "label": "Regulators & Compliance Bodies",
        "tone": "formal, precise, evidence-based",
        "focus": "compliance status, framework alignment, data traceability",
        "format": "structured with references to specific requirements",
    },
    "employees": {
        "label": "Employees & Internal Teams",
        "tone": "inspiring, inclusive, transparent",
        "focus": "workplace impact, diversity, safety, community engagement",
        "format": "narrative-driven with personal relevance",
    },
    "public": {
        "label": "General Public & Media",
        "tone": "accessible, honest, impact-focused",
        "focus": "environmental impact, community benefit, sustainability commitments",
        "format": "simple language, key achievements, clear commitments",
    },
}


class StakeholderAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Stakeholder Agent",
            description="Generates audience-tailored ESG communications and engagement content.",
        )

    def execute(self, **kwargs):
        self.log("Generating stakeholder communications")

        # Gather data from other agents
        report_results = state_manager.subscribe("report_results") or {}
        action_results = state_manager.subscribe("action_results") or {}
        carbon_results = state_manager.subscribe("carbon_results") or {}
        risk_results = state_manager.subscribe("risk_results") or {}
        roi_results = state_manager.subscribe("roi_results") or {}

        # Build data context for message generation
        context = self._build_context(
            report_results, action_results, carbon_results, risk_results, roi_results
        )

        # Generate communications for each audience
        communications = {}
        for audience_key, profile in AUDIENCE_PROFILES.items():
            comm = self._generate_communication(audience_key, profile, context)
            tone_check = self.hf.analyze_sentiment(comm["message"])
            comm["tone_analysis"] = tone_check
            communications[audience_key] = comm

        # Performance summary
        perf_summary = self._generate_performance_summary(context)

        # ESG Business Case (board-ready)
        business_case = self._generate_business_case(context, roi_results)

        # J-Curve expectation framing (H6)
        j_curve_framing = self._frame_j_curve(roi_results)

        results = {
            "communications": communications,
            "performance_summary": perf_summary,
            "business_case": business_case,
            "j_curve_framing": j_curve_framing,
            "audiences": list(AUDIENCE_PROFILES.keys()),
            "context_data": context,
        }

        state_manager.publish("stakeholder_results", results, self.name)
        return results

    def _build_context(self, report_results, action_results, carbon_results,
                       risk_results, roi_results=None):
        roi_results = roi_results or {}
        fin_roi = roi_results.get("financial_roi", {})
        iqs = roi_results.get("investment_quality_score", {})

        return {
            "company_name": report_results.get("company", {}).get(
                "company_name", company_cfg.company_name
            ),
            "total_emissions": carbon_results.get("total_emissions_current", "N/A"),
            "yoy_change": carbon_results.get("yoy_change_pct", "N/A"),
            "carbon_intensity": carbon_results.get("carbon_intensity", "N/A"),
            "renewable_pct": carbon_results.get("energy_analysis", {}).get(
                "renewable_pct", "N/A"
            ),
            "compliance_overall": report_results.get("compliance_summary", {}).get(
                "overall", "N/A"
            ),
            "risk_score": risk_results.get("overall_risk_score", "N/A"),
            "esg_rating": risk_results.get("rating_prediction", {}).get(
                "predicted", company_cfg.esg_rating_target or "N/A"
            ),
            "total_actions": action_results.get("summary", {}).get("total_actions", "N/A"),
            "critical_actions": action_results.get("summary", {}).get("critical", "N/A"),
            # ROI context
            "financial_roi_pct": fin_roi.get("roi_pct", "N/A"),
            "cost_savings": fin_roi.get("cost_savings", {}).get("total", "N/A"),
            "esg_capex": fin_roi.get("total_esg_capex", "N/A"),
            "iqs_score": iqs.get("score", "N/A"),
            "iqs_grade": iqs.get("grade", "N/A"),
        }

    def _generate_communication(self, audience_key, profile, context):
        prompt = (
            f"Write an ESG communication for {profile['label']}. "
            f"Tone: {profile['tone']}. Focus: {profile['focus']}. "
            f"Format: {profile['format']}. "
            f"Company: {context['company_name']}. "
            f"Key data — Emissions: {context['total_emissions']} tCO2e "
            f"({context['yoy_change']}% YoY), Renewable energy: {context['renewable_pct']}%, "
            f"Compliance: {context['compliance_overall']}%, "
            f"ESG rating trajectory: {context['esg_rating']}. "
            f"Write 4-5 sentences."
        )
        message = self.hf.generate_text(prompt)

        # Generate subject line
        subject = self._generate_subject(audience_key, context)

        return {
            "audience": profile["label"],
            "audience_key": audience_key,
            "subject": subject,
            "message": message,
            "key_metrics": self._select_metrics_for_audience(audience_key, context),
        }

    def _generate_subject(self, audience_key, context):
        subjects = {
            "investors": f"{context['company_name']} ESG Performance Update — Rating Trajectory: {context['esg_rating']}",
            "regulators": f"{context['company_name']} Regulatory Compliance Report — {context['compliance_overall']}% Alignment",
            "employees": f"Our Sustainability Journey — Progress & Impact Update",
            "public": f"{context['company_name']} Sustainability Report: Building a Greener Future",
        }
        return subjects.get(audience_key, "ESG Performance Update")

    def _select_metrics_for_audience(self, audience_key, context):
        base = [
            {"label": "Total Emissions", "value": f"{context['total_emissions']} tCO2e"},
            {"label": "YoY Change", "value": f"{context['yoy_change']}%"},
        ]

        if audience_key == "investors":
            base.extend([
                {"label": "ESG Rating", "value": context["esg_rating"]},
                {"label": "Carbon Intensity", "value": f"{context['carbon_intensity']} tCO2e/$M"},
                {"label": "Risk Score", "value": f"{context['risk_score']}/100"},
            ])
        elif audience_key == "regulators":
            base.extend([
                {"label": "Compliance", "value": f"{context['compliance_overall']}%"},
                {"label": "Pending Actions", "value": str(context["critical_actions"])},
            ])
        elif audience_key == "employees":
            base.extend([
                {"label": "Renewable Energy", "value": f"{context['renewable_pct']}%"},
            ])
        elif audience_key == "public":
            base.extend([
                {"label": "Renewable Energy", "value": f"{context['renewable_pct']}%"},
                {"label": "ESG Rating", "value": context["esg_rating"]},
            ])

        return base

    def _generate_business_case(self, context, roi_results):
        """Generate a board-ready ESG business case with financial justification."""
        fin_roi = roi_results.get("financial_roi", {})
        strat_roi = roi_results.get("strategic_roi", {})
        iqs = roi_results.get("investment_quality_score", {})

        cost_savings = fin_roi.get("cost_savings", {})
        prompt = (
            f"Write a concise ESG business case for {context['company_name']}'s board. "
            f"ESG Investment Quality Score: {iqs.get('score', 'N/A')}/100 (Grade: {iqs.get('grade', 'N/A')}). "
            f"Financial ROI: {fin_roi.get('roi_pct', 'N/A')}%. "
            f"Total cost savings: INR {cost_savings.get('total', 'N/A')} Cr. "
            f"Revenue uplift: INR {fin_roi.get('esg_revenue_uplift', 'N/A')} Cr. "
            f"Cost of capital reduction: {strat_roi.get('cost_of_capital_reduction_bps', 'N/A')} bps. "
            f"Include: (1) Investment summary, (2) Financial returns, (3) Strategic value, (4) Recommendation. "
            f"Tone: executive, data-driven."
        )
        narrative = self.hf.generate_text(prompt, max_tokens=300)

        return {
            "narrative": narrative,
            "headline": f"ESG Investment Quality: {iqs.get('grade', 'N/A')} — {fin_roi.get('roi_pct', 0)}% Financial ROI",
            "key_financials": {
                "total_invested": f"INR {fin_roi.get('total_esg_capex', 0)} Cr",
                "total_savings": f"INR {cost_savings.get('total', 0)} Cr",
                "revenue_uplift": f"INR {fin_roi.get('esg_revenue_uplift', 0)} Cr",
                "payback_years": fin_roi.get("payback_years"),
                "coc_reduction_bps": strat_roi.get("cost_of_capital_reduction_bps", 0),
            },
            "recommendation": "Increase ESG CapEx allocation" if iqs.get("score", 0) >= 60 else "Maintain current ESG spend, focus on high-ROI initiatives",
        }

    def _frame_j_curve(self, roi_results):
        """H6: Frame the J-Curve for stakeholder expectation setting.

        Explains why ESG investments may show short-term costs before
        long-term payback, and communicates the breakeven timeline.
        """
        j_data = roi_results.get("j_curve", {})
        quarters = j_data.get("quarters", [])
        breakeven = j_data.get("breakeven_quarter")
        total_invested = j_data.get("total_invested", 0)
        total_benefit = j_data.get("total_benefit", 0)
        net = j_data.get("net_position", 0)

        if not quarters:
            return {
                "available": False,
                "message": "Insufficient data for J-Curve analysis.",
            }

        # Identify the trough (maximum negative position)
        trough = min(quarters, key=lambda q: q.get("net_position", 0))

        prompt = (
            f"Explain the ESG J-Curve for {company_cfg.company_name} in 3 sentences. "
            f"Total invested: INR {total_invested} Cr over {len(quarters)} quarters. "
            f"Deepest cost trough: INR {abs(trough['net_position'])} Cr in {trough['period']}. "
            f"{'Breakeven reached in ' + breakeven if breakeven else 'Breakeven not yet reached'}. "
            f"Current net position: INR {net} Cr. "
            f"Frame this positively for investors."
        )
        narrative = self.hf.generate_text(prompt, max_tokens=150)

        return {
            "available": True,
            "narrative": narrative,
            "breakeven_quarter": breakeven,
            "trough_period": trough["period"],
            "trough_amount": trough["net_position"],
            "current_net": net,
            "total_invested": total_invested,
            "total_benefit": total_benefit,
            "status": "Payback achieved" if net >= 0 else "In investment phase",
        }

    def _generate_performance_summary(self, context):
        prompt = (
            f"Write a 3-sentence ESG performance summary for {context['company_name']}. "
            f"Emissions: {context['total_emissions']} tCO2e ({context['yoy_change']}% YoY). "
            f"Renewable energy: {context['renewable_pct']}%. "
            f"Overall compliance: {context['compliance_overall']}%. "
            f"ESG rating: {context['esg_rating']}."
        )
        return self.hf.generate_text(prompt, max_tokens=150)

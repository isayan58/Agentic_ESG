"""Agent 8: Stakeholder Agent — Audience-tailored ESG communications."""
from core.base_agent import BaseAgent
from core.state_manager import state_manager


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

        # Build data context for message generation
        context = self._build_context(
            report_results, action_results, carbon_results, risk_results
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

        results = {
            "communications": communications,
            "performance_summary": perf_summary,
            "audiences": list(AUDIENCE_PROFILES.keys()),
            "context_data": context,
        }

        state_manager.publish("stakeholder_results", results, self.name)
        return results

    def _build_context(self, report_results, action_results, carbon_results, risk_results):
        return {
            "company_name": report_results.get("company", {}).get(
                "company_name", "GreenTech Solutions"
            ),
            "total_emissions": carbon_results.get("total_emissions_current", "38,500"),
            "yoy_change": carbon_results.get("yoy_change_pct", "-14.8"),
            "carbon_intensity": carbon_results.get("carbon_intensity", "83.3"),
            "renewable_pct": carbon_results.get("energy_analysis", {}).get(
                "renewable_pct", 45
            ),
            "compliance_overall": report_results.get("compliance_summary", {}).get(
                "overall", 82
            ),
            "risk_score": risk_results.get("overall_risk_score", 42),
            "esg_rating": risk_results.get("rating_prediction", {}).get(
                "predicted", "A-"
            ),
            "total_actions": action_results.get("summary", {}).get("total_actions", 12),
            "critical_actions": action_results.get("summary", {}).get("critical", 3),
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

    def _generate_performance_summary(self, context):
        prompt = (
            f"Write a 3-sentence ESG performance summary for {context['company_name']}. "
            f"Emissions: {context['total_emissions']} tCO2e ({context['yoy_change']}% YoY). "
            f"Renewable energy: {context['renewable_pct']}%. "
            f"Overall compliance: {context['compliance_overall']}%. "
            f"ESG rating: {context['esg_rating']}."
        )
        return self.hf.generate_text(prompt, max_tokens=150)

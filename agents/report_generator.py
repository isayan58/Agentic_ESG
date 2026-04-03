"""Agent 4: Report Generator — Multi-framework audit-ready report generation."""
from datetime import datetime
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from utils.data_processing import load_company_profile, load_esg_metrics


class ReportGeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Report Generator",
            description="Generates multi-framework, audit-ready ESG reports with AI narratives.",
        )

    def execute(self, **kwargs):
        self.log("Compiling report data from all agents")
        company = load_company_profile()
        metrics_df = load_esg_metrics()

        # Gather data from other agents via state manager
        carbon_results = state_manager.subscribe("carbon_results") or {}
        regulatory_results = state_manager.subscribe("regulatory_results") or {}
        audit_results = state_manager.subscribe("audit_results") or {}
        data_results = state_manager.subscribe("data_collection_results") or {}

        # Generate executive summary
        exec_summary = self._generate_executive_summary(
            company, carbon_results, regulatory_results
        )

        # Generate section narratives
        env_narrative = self._generate_section_narrative("environmental", carbon_results, metrics_df)
        social_narrative = self._generate_section_narrative("social", {}, metrics_df)
        gov_narrative = self._generate_section_narrative("governance", {}, metrics_df)

        # Compile metrics tables
        metrics_tables = self._compile_metrics_tables(metrics_df)

        # Framework-specific sections
        framework_sections = self._compile_framework_sections(regulatory_results)

        # Audit trail
        audit_trail = self._compile_audit_trail(data_results, audit_results)

        results = {
            "report_title": f"{company.get('company_name', 'Company')} ESG Report FY2024",
            "generated_at": datetime.now().isoformat(),
            "company": company,
            "executive_summary": exec_summary,
            "sections": {
                "environmental": {
                    "title": "Environmental Performance",
                    "narrative": env_narrative,
                    "metrics": metrics_tables.get("Environmental", []),
                },
                "social": {
                    "title": "Social Performance",
                    "narrative": social_narrative,
                    "metrics": metrics_tables.get("Social", []),
                },
                "governance": {
                    "title": "Governance Performance",
                    "narrative": gov_narrative,
                    "metrics": metrics_tables.get("Governance", []),
                },
            },
            "framework_sections": framework_sections,
            "carbon_highlights": {
                "total_emissions": carbon_results.get("total_emissions_current", "N/A"),
                "yoy_change": carbon_results.get("yoy_change_pct", "N/A"),
                "carbon_intensity": carbon_results.get("carbon_intensity", "N/A"),
            },
            "compliance_summary": {
                "overall": regulatory_results.get("overall_compliance", "N/A"),
                "frameworks": {
                    k: v.get("compliance_pct", 0)
                    for k, v in regulatory_results.get("framework_results", {}).items()
                },
            },
            "audit_trail": audit_trail,
        }

        state_manager.publish("report_results", results, self.name)
        return results

    def _generate_executive_summary(self, company, carbon_results, regulatory_results):
        company_name = company.get("company_name", "The company")
        total_emissions = carbon_results.get("total_emissions_current", "N/A")
        yoy = carbon_results.get("yoy_change_pct", "N/A")
        compliance = regulatory_results.get("overall_compliance", "N/A")

        prompt = (
            f"Write a 3-4 sentence executive summary for an ESG annual report. "
            f"Company: {company_name}, sector: {company.get('sector', 'IT')}. "
            f"Total emissions: {total_emissions} tCO2e (YoY change: {yoy}%). "
            f"Overall regulatory compliance: {compliance}%. "
            f"Key commitments: Net Zero by 2040, 100% renewable by 2030. "
            f"Tone: professional, forward-looking."
        )
        return self.hf.generate_text(prompt)

    def _generate_section_narrative(self, section, section_data, metrics_df):
        pillar_map = {
            "environmental": "Environmental",
            "social": "Social",
            "governance": "Governance",
        }
        pillar = pillar_map.get(section, "")
        pillar_metrics = metrics_df[metrics_df["pillar"] == pillar] if not metrics_df.empty else None

        context_parts = [f"Generate a brief narrative for the {section} section of an ESG report."]
        if pillar_metrics is not None and not pillar_metrics.empty:
            met = (pillar_metrics["status"] == "Met").sum()
            total = len(pillar_metrics)
            context_parts.append(f"{met}/{total} targets met.")
            top_metrics = pillar_metrics.head(3)
            for _, row in top_metrics.iterrows():
                context_parts.append(
                    f"{row['metric_name']}: {row['value_2024']} {row['unit']} "
                    f"(target: {row['target_2024']})."
                )

        return self.hf.generate_text(" ".join(context_parts))

    def _compile_metrics_tables(self, metrics_df):
        tables = {}
        if metrics_df.empty:
            return tables
        for pillar in ["Environmental", "Social", "Governance"]:
            pdf = metrics_df[metrics_df["pillar"] == pillar]
            tables[pillar] = pdf[
                ["metric_id", "metric_name", "unit", "value_2023", "value_2024", "target_2024", "status"]
            ].to_dict("records")
        return tables

    def _compile_framework_sections(self, regulatory_results):
        sections = {}
        for fw_name, fw_result in regulatory_results.get("framework_results", {}).items():
            sections[fw_name] = {
                "name": fw_result.get("full_name", fw_name),
                "compliance_pct": fw_result.get("compliance_pct", 0),
                "covered": fw_result.get("covered", 0),
                "total": fw_result.get("total", 0),
                "gaps_count": len(fw_result.get("gaps", [])),
            }
        return sections

    def _compile_audit_trail(self, data_results, audit_results):
        trail = []
        trail.append({
            "step": "Data Collection",
            "timestamp": datetime.now().isoformat(),
            "details": f"Loaded {data_results.get('datasets_loaded', 0)} datasets, "
                       f"{data_results.get('total_records', 0)} records",
            "status": "completed",
        })
        trail.append({
            "step": "Data Validation",
            "timestamp": datetime.now().isoformat(),
            "details": f"Overall completeness: {data_results.get('overall_completeness', 'N/A')}%",
            "status": "completed",
        })
        trail.append({
            "step": "Report Generation",
            "timestamp": datetime.now().isoformat(),
            "details": "AI-assisted narrative generation and metrics compilation",
            "status": "completed",
        })
        return trail

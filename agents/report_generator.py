"""Agent 4: Report Generator — Multi-framework audit-ready report generation
with Value Creation Channels framework.

Hypothesis mapping:
  H1 — ESG → Revenue growth (Growth channel)
  H7 — India-specific regulatory context
"""
from datetime import datetime
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.company_config import company_cfg
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
        roi_results = state_manager.subscribe("roi_results") or {}

        fy_label = f"FY{company_cfg.current_fy}" if company_cfg.current_fy else "Current FY"

        # Generate executive summary
        exec_summary = self._generate_executive_summary(
            company, carbon_results, regulatory_results
        )

        # Generate section narratives
        env_narrative = self._generate_section_narrative("environmental", carbon_results, metrics_df)
        social_narrative = self._generate_section_narrative("social", {}, metrics_df)
        gov_narrative = self._generate_section_narrative("governance", {}, metrics_df)

        # Value Creation Channels section (replaces traditional ESG-only view)
        value_channels = self._compile_value_channels(roi_results)

        # Compile metrics tables
        metrics_tables = self._compile_metrics_tables(metrics_df)

        # Framework-specific sections
        framework_sections = self._compile_framework_sections(regulatory_results)

        # Audit trail
        audit_trail = self._compile_audit_trail(data_results, audit_results)

        results = {
            "report_title": f"{company_cfg.company_name} ESG Report {fy_label}",
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
            "value_channels": value_channels,
            "investment_quality": roi_results.get("investment_quality_score", {}),
            "audit_trail": audit_trail,
        }

        state_manager.publish("report_results", results, self.name)
        return results

    def _generate_executive_summary(self, company, carbon_results, regulatory_results):
        company_name = company_cfg.company_name
        total_emissions = carbon_results.get("total_emissions_current", "N/A")
        yoy = carbon_results.get("yoy_change_pct", "N/A")
        compliance = regulatory_results.get("overall_compliance", "N/A")
        commitments = company_cfg.commitments_text()

        prompt = (
            f"Write a 3-4 sentence executive summary for an ESG annual report. "
            f"Company: {company_name}, sector: {company_cfg.sector}. "
            f"Total emissions: {total_emissions} tCO2e (YoY change: {yoy}%). "
            f"Overall regulatory compliance: {compliance}%. "
            f"Key commitments: {commitments}. "
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

        current_val_col = f"value_{company_cfg.current_fy}" if company_cfg.current_fy else "value_2024"
        target_col = f"target_{company_cfg.current_fy}" if company_cfg.current_fy else "target_2024"

        context_parts = [f"Generate a brief narrative for the {section} section of an ESG report."]
        if pillar_metrics is not None and not pillar_metrics.empty:
            met = (pillar_metrics["status"] == "Met").sum()
            total = len(pillar_metrics)
            context_parts.append(f"{met}/{total} targets met.")
            top_metrics = pillar_metrics.head(3)
            for _, row in top_metrics.iterrows():
                val = row.get(current_val_col, row.get("value_2024", "N/A"))
                target = row.get(target_col, row.get("target_2024", "N/A"))
                context_parts.append(
                    f"{row['metric_name']}: {val} {row['unit']} (target: {target})."
                )

        return self.hf.generate_text(" ".join(context_parts))

    def _compile_metrics_tables(self, metrics_df):
        tables = {}
        if metrics_df.empty:
            return tables

        current_val_col = f"value_{company_cfg.current_fy}" if company_cfg.current_fy else "value_2024"
        prev_val_col = f"value_{company_cfg.previous_fy}" if company_cfg.previous_fy else "value_2023"
        target_col = f"target_{company_cfg.current_fy}" if company_cfg.current_fy else "target_2024"

        # Use the columns that actually exist in the dataframe
        desired_cols = ["metric_id", "metric_name", "unit", prev_val_col, current_val_col, target_col, "status"]
        available_cols = [c for c in desired_cols if c in metrics_df.columns]

        for pillar in ["Environmental", "Social", "Governance"]:
            pdf = metrics_df[metrics_df["pillar"] == pillar]
            tables[pillar] = pdf[available_cols].to_dict("records")
        return tables

    def _compile_value_channels(self, roi_results):
        """Build Value Creation Channels section from ROI Agent output.

        Presents ESG performance through 5 business-value lenses:
        Growth, Cost, Risk, Human Capital, Capital Efficiency.
        """
        kpi_data = roi_results.get("kpi_engine", {})
        channels = kpi_data.get("value_channels", [])
        fin_roi = roi_results.get("financial_roi", {})
        strat_roi = roi_results.get("strategic_roi", {})

        if not channels:
            return {"available": False, "channels": []}

        channel_sections = []
        for ch in channels:
            channel_sections.append({
                "name": ch.get("channel", ""),
                "score": ch.get("score", 0),
                "trend": ch.get("trend", "stable"),
                "financial_impact": ch.get("financial_impact", ""),
                "metrics": ch.get("metrics", []),
            })

        return {
            "available": True,
            "channels": channel_sections,
            "composite_score": kpi_data.get("composite_esg_financial_score", 0),
            "financial_roi_pct": fin_roi.get("roi_pct", 0),
            "total_esg_capex": fin_roi.get("total_esg_capex", 0),
            "net_benefit": fin_roi.get("net_financial_benefit", 0),
            "channel_scores": strat_roi.get("channel_scores", {}),
        }

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

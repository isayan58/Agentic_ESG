"""ESG CoPilot — Gradio Interface with tabs for all 8 agents."""
import os

# ── Fix jinja2 LRUCache bug (unhashable dict key in starlette templates) ──
# Must run BEFORE importing gradio, which triggers jinja2 + starlette imports.
import jinja2.utils

_OrigLRUCache = jinja2.utils.LRUCache


class _SafeLRUCache(_OrigLRUCache):
    """LRUCache that gracefully handles unhashable keys (e.g. dicts)."""

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except TypeError:
            raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self[key]
        except (KeyError, TypeError):
            return default

    def __setitem__(self, key, value):
        try:
            super().__setitem__(key, value)
        except TypeError:
            pass

    def __contains__(self, key):
        try:
            return super().__contains__(key)
        except TypeError:
            return False


jinja2.utils.LRUCache = _SafeLRUCache
# ── End jinja2 fix ──

import gradio as gr
import pandas as pd
import json
from agents.data_collector import DataCollectorAgent
from agents.regulatory_tracker import RegulatoryTrackerAgent
from agents.carbon_accountant import CarbonAccountantAgent
from agents.report_generator import ReportGeneratorAgent
from agents.risk_predictor import RiskPredictorAgent
from agents.audit_agent import AuditAgent
from agents.action_agent import ActionAgent
from agents.stakeholder_agent import StakeholderAgent
from core.orchestrator import Orchestrator

# Initialize agents
orchestrator = Orchestrator()


def format_dict(d, indent=0):
    """Format a dict for display."""
    lines = []
    for k, v in d.items():
        prefix = "  " * indent
        if isinstance(v, dict):
            lines.append(f"{prefix}**{k}:**")
            lines.append(format_dict(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}**{k}:** {len(v)} items")
        else:
            lines.append(f"{prefix}**{k}:** {v}")
    return "\n".join(lines)


# --- Agent functions ---

def run_data_collector():
    agent = orchestrator.get_agent("data_collector")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", ""

    summary = (
        f"## Data Collection Results\n\n"
        f"- **Datasets Loaded:** {results.get('datasets_loaded', 0)}\n"
        f"- **Total Records:** {results.get('total_records', 0):,}\n"
        f"- **Overall Completeness:** {results.get('overall_completeness', 0)}%\n"
        f"- **Avg Confidence:** {results.get('overall_confidence', 0)}%\n\n"
        f"### Quality Scores\n\n"
    )
    for name, q in results.get("quality_scores", {}).items():
        summary += f"- **{name}:** {q['completeness']}% complete, {q['total_records']} records\n"

    issues = results.get("quality_issues", [])
    issues_text = ""
    if issues:
        issues_text = "### Quality Issues\n\n"
        for issue in issues:
            issues_text += f"- **{issue['dataset']}:** {issue['issue']} ({issue['severity']})\n"
    else:
        issues_text = "### No quality issues detected"

    return summary, issues_text


def run_regulatory_tracker():
    agent = orchestrator.get_agent("regulatory_tracker")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", ""

    summary = f"## Regulatory Compliance: {results.get('overall_compliance', 0)}%\n\n"
    gaps_text = "## Gap Analysis\n\n"

    for fw, data in results.get("framework_results", {}).items():
        summary += (
            f"### {fw} ({data.get('full_name', '')})\n"
            f"- Compliance: {data['compliance_pct']}%\n"
            f"- Covered: {data['covered']}/{data['total']}\n"
            f"- Gaps: {data['missing'] + data['partial']}\n\n"
        )
        for gap in data.get("gaps", [])[:5]:
            gaps_text += f"- **[{gap['requirement_id']}]** {gap['requirement']} — {gap['status']} ({gap['priority']})\n"

    narrative = results.get("gap_narrative", "")
    return summary, gaps_text, narrative


def run_carbon_accountant():
    agent = orchestrator.get_agent("carbon_accountant")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", ""

    summary = (
        f"## Carbon Accounting Results\n\n"
        f"- **Total Emissions (2024):** {results.get('total_emissions_current', 0):,.0f} tCO2e\n"
        f"- **YoY Change:** {results.get('yoy_change_pct', 0)}%\n"
        f"- **Carbon Intensity:** {results.get('carbon_intensity', 0)} tCO2e/$M\n\n"
        f"### Scope Breakdown\n\n"
    )
    for scope, value in results.get("scope_totals_current", {}).items():
        summary += f"- **{scope}:** {value:,.0f} tCO2e\n"

    hotspots = "## Supply Chain Hotspots\n\n"
    for h in results.get("hotspots", []):
        hotspots += f"- **{h['supplier']}** ({h['country']}): {h['emissions']:,.0f} tCO2e — {h['risk_factors']}\n"

    narrative = results.get("narrative", "")
    return summary, hotspots, narrative


def run_risk_predictor():
    agent = orchestrator.get_agent("risk_predictor")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", ""

    climate = results.get("climate_risks", {})
    rating = results.get("rating_prediction", {})

    summary = (
        f"## Risk Analysis\n\n"
        f"- **Overall Risk Score:** {climate.get('overall_score', 0):.0f}/100 ({climate.get('overall_level', 'N/A')})\n"
        f"- **Physical Risk:** {climate.get('physical_risk', 0)}\n"
        f"- **Transition Risk:** {climate.get('transition_risk', 0)}\n\n"
        f"### ESG Rating\n"
        f"- Current: {rating.get('current', 'N/A')} → Predicted: {rating.get('predicted', 'N/A')}\n"
    )

    scenarios = "## Scenario Analysis\n\n"
    for key, s in results.get("scenarios", {}).items():
        scenarios += (
            f"### {s['name']}\n"
            f"- Emission Reduction: {s['emission_reduction_pct']}%\n"
            f"- Projected Rating: {s['projected_rating']}\n"
            f"- Timeline: {s['timeline']}\n\n"
        )

    narrative = results.get("narrative", "")
    return summary, scenarios, narrative


def run_audit_agent():
    agent = orchestrator.get_agent("audit_agent")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", ""

    readiness = results.get("readiness_score", {})
    summary = (
        f"## Audit Results\n\n"
        f"- **Readiness Score:** {readiness.get('overall', 0):.0f}% (Grade: {readiness.get('grade', 'N/A')})\n"
        f"- **Completeness:** {readiness.get('completeness', 0):.0f}%\n"
        f"- **Compliance:** {readiness.get('compliance', 0):.0f}%\n"
        f"- **Evidence:** {readiness.get('evidence', 0):.0f}%\n"
        f"- **Issues Found:** {results.get('issues_count', 0)}\n"
    )

    findings = results.get("findings_summary", "No findings summary available.")
    return summary, findings


def run_action_agent():
    agent = orchestrator.get_agent("action_agent")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", ""

    summary_data = results.get("summary", {})
    summary = (
        f"## Action Recommendations\n\n"
        f"- **Total Actions:** {summary_data.get('total_actions', 0)}\n"
        f"- **Critical:** {summary_data.get('critical', 0)} | "
        f"**High:** {summary_data.get('high', 0)} | "
        f"**Medium:** {summary_data.get('medium', 0)}\n"
        f"- **Est. Investment:** INR {summary_data.get('total_investment', 0)} lakhs\n\n"
        f"### Top Actions\n\n"
    )
    for action in results.get("actions", [])[:5]:
        summary += f"- **[{action['id']}]** {action['action']} ({action['priority']})\n"

    narrative = results.get("roadmap_narrative", "")
    return summary, narrative


def run_stakeholder_agent():
    agent = orchestrator.get_agent("stakeholder_agent")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", "", ""

    comms = results.get("communications", {})
    investor_msg = comms.get("investors", {}).get("message", "N/A")
    regulator_msg = comms.get("regulators", {}).get("message", "N/A")
    employee_msg = comms.get("employees", {}).get("message", "N/A")
    public_msg = comms.get("public", {}).get("message", "N/A")

    return investor_msg, regulator_msg, employee_msg, public_msg


def run_full_pipeline():
    results = orchestrator.run_full_pipeline()

    summary = "## Full Pipeline Results\n\n"
    for agent_key, agent_results in results.items():
        status = "✅" if "error" not in agent_results else "❌"
        summary += f"- {status} **{agent_key.replace('_', ' ').title()}**\n"

    carbon = results.get("carbon_accountant", {})
    risk = results.get("risk_predictor", {})
    audit = results.get("audit_agent", {})

    summary += (
        f"\n### Key Metrics\n"
        f"- Total Emissions: {carbon.get('total_emissions_current', 'N/A')} tCO2e\n"
        f"- Risk Score: {risk.get('overall_risk_score', 'N/A')}/100\n"
        f"- Audit Readiness: {audit.get('readiness_score', {}).get('overall', 'N/A')}%\n"
    )
    return summary


# --- Build Gradio Interface ---

with gr.Blocks(title="ESG CoPilot", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌍 ESG CoPilot — Autonomous ESG Intelligence")
    gr.Markdown("*8 specialized AI agents powered by HuggingFace*")

    with gr.Tab("🎛️ Mission Control"):
        gr.Markdown("Run the full 8-agent pipeline in dependency order.")
        run_btn = gr.Button("🚀 Run Full Pipeline", variant="primary")
        output = gr.Markdown()
        run_btn.click(run_full_pipeline, outputs=output)

    with gr.Tab("📊 Data Collector"):
        gr.Markdown("Auto-discovers and validates ESG data.")
        btn = gr.Button("Run Data Collection", variant="primary")
        out1 = gr.Markdown(label="Results")
        out2 = gr.Markdown(label="Issues")
        btn.click(run_data_collector, outputs=[out1, out2])

    with gr.Tab("📋 Regulatory Tracker"):
        gr.Markdown("Monitors BRSR, CSRD, GRI, SASB compliance.")
        btn = gr.Button("Run Compliance Analysis", variant="primary")
        out1 = gr.Markdown(label="Compliance")
        out2 = gr.Markdown(label="Gaps")
        out3 = gr.Markdown(label="AI Narrative")
        btn.click(run_regulatory_tracker, outputs=[out1, out2, out3])

    with gr.Tab("🌱 Carbon Accountant"):
        gr.Markdown("Tracks Scope 1/2/3 emissions.")
        btn = gr.Button("Run Carbon Analysis", variant="primary")
        out1 = gr.Markdown(label="Summary")
        out2 = gr.Markdown(label="Hotspots")
        out3 = gr.Markdown(label="AI Narrative")
        btn.click(run_carbon_accountant, outputs=[out1, out2, out3])

    with gr.Tab("⚠️ Risk Predictor"):
        gr.Markdown("Climate risk and ESG rating forecasting.")
        btn = gr.Button("Run Risk Analysis", variant="primary")
        out1 = gr.Markdown(label="Risk Summary")
        out2 = gr.Markdown(label="Scenarios")
        out3 = gr.Markdown(label="AI Narrative")
        btn.click(run_risk_predictor, outputs=[out1, out2, out3])

    with gr.Tab("🔍 Audit Agent"):
        gr.Markdown("Compliance verification and audit trails.")
        btn = gr.Button("Run Audit", variant="primary")
        out1 = gr.Markdown(label="Audit Results")
        out2 = gr.Markdown(label="Findings")
        btn.click(run_audit_agent, outputs=[out1, out2])

    with gr.Tab("🎯 Action Agent"):
        gr.Markdown("Prioritized ESG recommendations.")
        btn = gr.Button("Generate Recommendations", variant="primary")
        out1 = gr.Markdown(label="Actions")
        out2 = gr.Markdown(label="Roadmap")
        btn.click(run_action_agent, outputs=[out1, out2])

    with gr.Tab("👥 Stakeholder Agent"):
        gr.Markdown("Audience-tailored ESG communications.")
        btn = gr.Button("Generate Communications", variant="primary")
        out1 = gr.Markdown(label="💼 Investors")
        out2 = gr.Markdown(label="🏛️ Regulators")
        out3 = gr.Markdown(label="👩‍💻 Employees")
        out4 = gr.Markdown(label="🌍 Public")
        btn.click(run_stakeholder_agent, outputs=[out1, out2, out3, out4])

    with gr.Tab("📄 Report Generator"):
        gr.Markdown("Generate comprehensive ESG report. Run other agents first for best results.")
        btn = gr.Button("Generate Report", variant="primary")
        output = gr.Markdown()

        def run_report():
            agent = orchestrator.get_agent("report_generator")
            results = agent.run()
            if "error" in results:
                return f"Error: {results['error']}"
            text = f"# {results.get('report_title', 'ESG Report')}\n\n"
            text += f"## Executive Summary\n{results.get('executive_summary', '')}\n\n"
            for key, section in results.get("sections", {}).items():
                text += f"## {section['title']}\n{section.get('narrative', '')}\n\n"
            return text

        btn.click(run_report, outputs=output)

    with gr.Tab("🔌 Enterprise Connectors"):
        gr.Markdown("Connect to ERP, HR, IoT, Supplier Portal, SQL, and API data sources.")
        btn = gr.Button("Fetch from All Connectors", variant="primary")
        out_connectors = gr.Markdown()

        def run_connectors():
            from utils.connectors import fetch_all_external_data
            data, statuses = fetch_all_external_data()
            text = "## Enterprise Connector Status\n\n"
            for key, status in statuses.items():
                icon = {"synced": "✅", "streaming": "📡", "error": "❌"}.get(status.get("status", ""), "⚪")
                text += (f"- {icon} **{status['name']}** ({status['type']}) — "
                         f"Status: {status['status']} | Records: {status.get('records', 0)}\n")
            text += f"\n**Total data sources connected:** {len(data)}\n"
            text += f"**Total records fetched:** {sum(len(df) for df in data.values()):,}\n"
            return text

        btn.click(run_connectors, outputs=out_connectors)

    with gr.Tab("📡 24/7 Monitoring"):
        gr.Markdown("Always-on ESG monitoring with real-time alerts.")
        btn = gr.Button("Check Monitoring Status", variant="primary")
        out_monitor = gr.Markdown()

        def run_monitoring():
            from utils.monitoring import monitoring_engine, regulatory_updater
            mon = monitoring_engine.get_dashboard_data()
            reg = regulatory_updater.check_for_updates()

            health_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(mon["health"], "⚪")
            text = (
                f"## 24/7 Monitoring Dashboard\n\n"
                f"- **Health:** {health_icon} {mon['health'].capitalize()}\n"
                f"- **Uptime:** {mon['uptime_days']} days\n"
                f"- **Events Processed:** {mon['events_processed']:,}\n"
                f"- **Active Streams:** {mon['active_streams']}/{mon['total_streams']}\n"
                f"- **Critical Alerts:** {mon['critical_alerts']}\n\n"
                f"### Active Alerts\n\n"
            )
            for alert in mon.get("alerts", []):
                sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert["severity"], "⚪")
                text += f"- {sev_icon} **[{alert['type'].upper()}]** {alert['message']}\n"

            text += f"\n### Regulatory Auto-Updates\n\n"
            text += f"- **All within 24h:** {'✅ Yes' if reg['within_24h'] else '❌ No'}\n"
            text += f"- **Avg response:** {reg['avg_response_hours']} hours\n\n"
            for upd in reg.get("updates", []):
                text += f"- **{upd['framework']}** ({upd['update_type']}): {upd['description'][:80]} — {upd['status']}\n"
            return text

        btn.click(run_monitoring, outputs=out_monitor)

    with gr.Tab("⚡ Spark Analytics"):
        gr.Markdown("Distributed ESG processing with PySpark.")
        btn = gr.Button("Run Spark Analysis", variant="primary")
        out_spark = gr.Markdown()

        def run_spark():
            from utils.spark_processing import spark_processor, PYSPARK_AVAILABLE
            if PYSPARK_AVAILABLE:
                results = spark_processor.run_full_analysis()
            else:
                from utils.data_processing import (
                    load_emissions, compute_scope_totals, compute_data_quality,
                )
                emissions = load_emissions()
                results = {
                    "scope_totals_2024": compute_scope_totals(emissions, 2024),
                    "scope_totals_2023": compute_scope_totals(emissions, 2023),
                    "engine": "Pandas (PySpark not installed)",
                }

            text = f"## Spark Analysis Results\n\n**Engine:** {results.get('engine', 'N/A')}\n\n"
            text += "### Scope Totals 2024\n"
            for scope, total in results.get("scope_totals_2024", {}).items():
                text += f"- **{scope}:** {total:,.1f} tCO2e\n"
            text += "\n### Scope Totals 2023\n"
            for scope, total in results.get("scope_totals_2023", {}).items():
                text += f"- **{scope}:** {total:,.1f} tCO2e\n"
            return text

        btn.click(run_spark, outputs=out_spark)

if __name__ == "__main__":
    # HuggingFace Spaces (Docker SDK) or local
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )

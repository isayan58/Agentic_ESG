"""Streamlit page for the Report Generator — with embedded charts and HTML export."""
import streamlit as st
import pandas as pd
from agents.report_generator import ReportGeneratorAgent
from utils.charts import emissions_donut, compliance_radar, chart_unavailable_message
from core.channels import Channel
from core.state_manager import state_manager
from utils.streamlit_compat import safe_dataframe
from utils.auth import current_user, require_login, sidebar_auth_widget
from utils.feedback_store import save_feedback
from utils.ui import inject_global_css, page_agent_header_live, pwc_header
from utils.pipeline_refresh import data_freshness_caption

st.set_page_config(page_title="Report Generator | ESG Intelligence Hub", page_icon="📄", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Report Generator agent.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="report_generator",
    agent_icon="📄",
)

st.title("📄 Report Generator Agent")
st.markdown("*Multi-framework audit-ready reports with AI narratives and embedded visual charts*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "report_agent" not in st.session_state:
    st.session_state.report_agent = ReportGeneratorAgent()
    st.session_state.report_results = None

agent = st.session_state.report_agent


def render_chart(fig):
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)

st.info("For best results, run Data Collector, Regulatory Tracker, Carbon Accountant, and Audit Agent first.")

if st.button("📝 Generate ESG Report", type="primary"):
    with st.spinner("Generating comprehensive ESG report with embedded charts..."):
        results = agent.run()
        st.session_state.report_results = results
    st.success("Report generated!")

results = st.session_state.report_results
if results and "error" not in results:
    st.markdown("---")
    st.markdown(f"## {results.get('report_title', 'ESG Report')}")
    st.caption(f"Generated: {results.get('generated_at', '')[:19]}")

    # Executive summary
    st.markdown("### Executive Summary")
    st.markdown(results.get("executive_summary", ""))

    st.markdown("---")

    # Carbon highlights with embedded chart
    st.markdown("### Carbon Performance")
    carbon = results.get("carbon_highlights", {})
    k1, k2, k3 = st.columns(3)
    with k1:
        em = carbon.get("total_emissions", "N/A")
        st.metric("Total Emissions", f"{em} tCO2e" if em != "N/A" else "N/A")
    with k2:
        st.metric("YoY Change", f"{carbon.get('yoy_change', 'N/A')}%")
    with k3:
        st.metric("Carbon Intensity", f"{carbon.get('carbon_intensity', 'N/A')} tCO2e/$M")

    # Embedded emissions chart
    carbon_data = state_manager.subscribe(Channel.CARBON)
    if carbon_data and "scope_totals_current" in carbon_data:
        fig = emissions_donut(carbon_data["scope_totals_current"])
        render_chart(fig)

    st.markdown("---")

    # Recommended report pack and insights
    recommended_reports = results.get("recommended_reports", [])
    if recommended_reports:
        st.markdown("### Recommended Report Pack")
        for item in recommended_reports:
            st.markdown(f"- {item}")

    actionable_insights = results.get("actionable_insights", [])
    if actionable_insights:
        st.markdown("### Key Insights")
        for insight in actionable_insights:
            st.markdown(f"- {insight}")

    data_quality_summary = results.get("data_quality_summary", [])
    if data_quality_summary:
        st.markdown("### Data Quality Summary")
        for item in data_quality_summary[:5]:
            st.markdown(f"- {item}")

    regulatory_action_plan = results.get("regulatory_action_plan", [])
    if regulatory_action_plan:
        st.markdown("### Regulatory Action Plan")
        for item in regulatory_action_plan[:5]:
            st.markdown(f"- {item}")

    carbon_insights = results.get("carbon_insights", [])
    if carbon_insights:
        st.markdown("### Carbon Insights")
        for item in carbon_insights[:5]:
            st.markdown(f"- {item}")

    risk_recommendations = results.get("risk_recommendations", [])
    if risk_recommendations:
        st.markdown("### Risk Recommendations")
        for item in risk_recommendations[:5]:
            st.markdown(f"- {item}")

    audit_recommendations = results.get("audit_recommendations", [])
    if audit_recommendations:
        st.markdown("### Audit Recommendations")
        for item in audit_recommendations[:5]:
            st.markdown(f"- {item}")

    roi_recommendations = results.get("roi_recommendations", [])
    if roi_recommendations:
        st.markdown("### ROI Recommendations")
        for item in roi_recommendations[:5]:
            st.markdown(f"- {item}")

    distribution_plan = results.get("distribution_plan", "")
    if distribution_plan:
        st.markdown("### Stakeholder Distribution Plan")
        st.markdown(distribution_plan)

    dashboard_templates = results.get("dashboard_templates", {})
    if dashboard_templates:
        st.markdown("### Sample BI / Dashboard Templates")
        st.markdown(dashboard_templates.get("summary", ""))
        with st.expander("Power BI Template"):
            st.markdown(dashboard_templates.get("power_bi", ""))
        with st.expander("QuickSight Template"):
            st.markdown(dashboard_templates.get("quicksight", ""))

    st.markdown("---")

    # Framework compliance with embedded radar
    st.markdown("### Framework Compliance Summary")
    fw_sections = results.get("framework_sections", {})
    compliance_data = results.get("compliance_summary", {})
    fw_scores = compliance_data.get("frameworks", {})
    if fw_scores:
        col1, col2 = st.columns([1, 1])
        with col1:
            fig = compliance_radar(fw_scores)
            render_chart(fig)
        with col2:
            for fw, pct in fw_scores.items():
                st.metric(fw, f"{pct}%")

    st.markdown("---")

    # ESG sections
    sections = results.get("sections", {})
    for section_key, section_data in sections.items():
        with st.expander(f"📑 {section_data['title']}", expanded=(section_key == "environmental")):
            st.markdown(section_data.get("narrative", ""))
            metrics = section_data.get("metrics", [])
            if metrics:
                df = pd.DataFrame(metrics)
                safe_dataframe(df, use_container_width=True, hide_index=True)

    # Comprehensive audit trail
    with st.expander("🔍 Comprehensive Audit Trail"):
        trail = results.get("audit_trail", [])
        for entry in trail:
            st.markdown(
                f"- **{entry['step']}**: {entry['details']} *(Status: {entry['status']})*"
            )

    # Downloads
    st.markdown("---")
    st.markdown("### Export Report")
    col1, col2 = st.columns(2)

    # Markdown download
    report_md = f"# {results.get('report_title', 'ESG Report')}\n\n"
    report_md += f"## Executive Summary\n{results.get('executive_summary', '')}\n\n"
    for section_key, section_data in sections.items():
        report_md += f"## {section_data['title']}\n{section_data.get('narrative', '')}\n\n"
    with col1:
        st.download_button("📥 Download Markdown", report_md, "esg_report_2024.md", "text/markdown")

    # HTML download with embedded styling
    report_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{results.get('report_title', 'ESG Report')}</title>
<style>
body {{ font-family: Calibri, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; color: #333; }}
h1 {{ color: #1E2761; border-bottom: 3px solid #E8453C; padding-bottom: 10px; }}
h2 {{ color: #1E2761; margin-top: 30px; }}
.metric {{ display: inline-block; background: #f8f9fa; border-left: 4px solid #1E2761; padding: 15px; margin: 5px; border-radius: 5px; }}
.metric .value {{ font-size: 24px; font-weight: bold; color: #1E2761; }}
.metric .label {{ font-size: 12px; color: #666; }}
table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
th {{ background: #1E2761; color: white; }}
tr:nth-child(even) {{ background: #f8f9fa; }}
.footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #888; font-size: 12px; }}
</style></head><body>
<h1>{results.get('report_title', 'ESG Report')}</h1>
<p><em>Generated: {results.get('generated_at', '')[:19]}</em></p>
<div>
<div class="metric"><div class="value">{carbon.get('total_emissions', 'N/A')} tCO2e</div><div class="label">Total Emissions</div></div>
<div class="metric"><div class="value">{carbon.get('yoy_change', 'N/A')}%</div><div class="label">YoY Change</div></div>
<div class="metric"><div class="value">{compliance_data.get('overall', 'N/A')}%</div><div class="label">Compliance</div></div>
</div>
<h2>Executive Summary</h2><p>{results.get('executive_summary', '')}</p>
"""
    for section_key, section_data in sections.items():
        report_html += f"<h2>{section_data['title']}</h2><p>{section_data.get('narrative', '')}</p>\n"
        metrics = section_data.get("metrics", [])
        if metrics:
            report_html += "<table><tr>" + "".join(f"<th>{k}</th>" for k in metrics[0].keys()) + "</tr>"
            for row in metrics:
                report_html += "<tr>" + "".join(f"<td>{v}</td>" for v in row.values()) + "</tr>"
            report_html += "</table>"

    report_html += '<div class="footer">Generated by ESG Intelligence Hub — Command Your ESG Strategy Platform</div></body></html>'

    with col2:
        st.download_button("📥 Download HTML Report", report_html, "esg_report_2024.html", "text/html")

    st.markdown("---")
    st.markdown("### Help the tool learn")
    st.markdown(
        "Your feedback is saved to the feedback store and used to improve future report generation prompts."
    )

    rating = st.radio(
        "How useful was this report?",
        ["Excellent", "Good", "Average", "Poor"],
        index=1,
        horizontal=True,
        key="report_feedback_rating",
    )
    comment = st.text_area(
        "What should improve?",
        key="report_feedback_comment",
        height=120,
    )

    if st.button("Submit feedback", key="report_feedback_submit"):
        user = current_user()
        username = user.get("username") if user else "anonymous"
        save_feedback(
            {
                "report_title": results.get("report_title"),
                "company": results.get("company", {}).get("company_name"),
                "rating": rating,
                "comment": comment,
                "report_type": "Streamlit Report Generator",
                "executive_summary": results.get("executive_summary", ""),
                "recommended_reports": results.get("recommended_reports", []),
                "actionable_insights": results.get("actionable_insights", []),
                "dashboard_templates": results.get("dashboard_templates", {}),
            },
            username=username,
        )
        st.success("Thanks — your feedback has been recorded.")

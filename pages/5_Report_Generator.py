"""Streamlit page for the Report Generator — with embedded charts and HTML export."""
import streamlit as st
import pandas as pd
from agents.report_generator import ReportGeneratorAgent
from utils.charts import emissions_donut, compliance_radar, chart_unavailable_message
from core.state_manager import state_manager
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget

st.set_page_config(page_title="Report Generator | ESG CoPilot", page_icon="📄", layout="wide")
sidebar_auth_widget()
require_login("Sign in to access the Report Generator agent.")
st.title("📄 Report Generator Agent")
st.markdown("*Multi-framework audit-ready reports with AI narratives and embedded visual charts*")
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
    carbon_data = state_manager.subscribe("carbon_results")
    if carbon_data and "scope_totals_current" in carbon_data:
        fig = emissions_donut(carbon_data["scope_totals_current"])
        render_chart(fig)

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

    report_html += '<div class="footer">Generated by ESG CoPilot — Autonomous ESG Intelligence Platform</div></body></html>'

    with col2:
        st.download_button("📥 Download HTML Report", report_html, "esg_report_2024.html", "text/html")

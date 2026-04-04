"""Streamlit page for the Report Generator Agent."""
import streamlit as st
import pandas as pd
from agents.report_generator import ReportGeneratorAgent

st.set_page_config(page_title="Report Generator | ESG CoPilot", page_icon="📄", layout="wide")
st.title("📄 Report Generator Agent")
st.markdown("*Generates multi-framework, audit-ready ESG reports with AI narratives*")
st.markdown("---")

if "report_agent" not in st.session_state:
    st.session_state.report_agent = ReportGeneratorAgent()
    st.session_state.report_results = None

agent = st.session_state.report_agent

st.info("For best results, run Data Collector, Regulatory Tracker, Carbon Accountant, and Audit Agent first.")

if st.button("📝 Generate ESG Report", type="primary"):
    with st.spinner("Generating comprehensive ESG report..."):
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

    # Carbon highlights
    carbon = results.get("carbon_highlights", {})
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Total Emissions", f"{carbon.get('total_emissions', 'N/A')} tCO2e")
    with k2:
        st.metric("YoY Change", f"{carbon.get('yoy_change', 'N/A')}%")
    with k3:
        st.metric("Carbon Intensity", f"{carbon.get('carbon_intensity', 'N/A')} tCO2e/$M")

    st.markdown("---")

    # ESG sections
    sections = results.get("sections", {})
    for section_key, section_data in sections.items():
        with st.expander(f"📑 {section_data['title']}", expanded=(section_key == "environmental")):
            st.markdown(section_data.get("narrative", ""))
            metrics = section_data.get("metrics", [])
            if metrics:
                df = pd.DataFrame(metrics)
                st.dataframe(df, use_container_width=True, hide_index=True)

    # Framework compliance
    st.markdown("### Framework Compliance Summary")
    fw_sections = results.get("framework_sections", {})
    if fw_sections:
        cols = st.columns(len(fw_sections))
        for i, (fw, data) in enumerate(fw_sections.items()):
            with cols[i]:
                st.metric(fw, f"{data['compliance_pct']}%")
                st.caption(f"{data['covered']}/{data['total']} requirements met")

    # Audit trail
    with st.expander("🔍 Audit Trail"):
        trail = results.get("audit_trail", [])
        for entry in trail:
            st.markdown(f"- **{entry['step']}**: {entry['details']} *(Status: {entry['status']})*")

    # Download
    st.markdown("---")
    report_text = f"# {results.get('report_title', 'ESG Report')}\n\n"
    report_text += f"## Executive Summary\n{results.get('executive_summary', '')}\n\n"
    for section_key, section_data in sections.items():
        report_text += f"## {section_data['title']}\n{section_data.get('narrative', '')}\n\n"
    st.download_button(
        "📥 Download Report (Markdown)",
        report_text,
        file_name="esg_report_2024.md",
        mime="text/markdown",
    )

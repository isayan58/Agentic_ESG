"""Streamlit page for the Regulatory Tracker Agent."""
import streamlit as st
import pandas as pd
from agents.regulatory_tracker import RegulatoryTrackerAgent
from utils.charts import compliance_radar

st.set_page_config(page_title="Regulatory Tracker | ESG CoPilot", page_icon="📋", layout="wide")
st.title("📋 Regulatory Tracker Agent")
st.markdown("*Monitors global ESG frameworks and performs compliance gap analysis*")
st.markdown("---")

if "reg_tracker" not in st.session_state:
    st.session_state.reg_tracker = RegulatoryTrackerAgent()
    st.session_state.reg_tracker_results = None

agent = st.session_state.reg_tracker

# Framework selection
frameworks_display = st.multiselect(
    "Frameworks to analyze",
    ["BRSR", "CSRD", "GRI", "SASB"],
    default=["BRSR", "CSRD", "GRI", "SASB"],
)

if st.button("🔄 Run Compliance Analysis", type="primary"):
    with st.spinner("Analyzing regulatory compliance..."):
        results = agent.run()
        st.session_state.reg_tracker_results = results
    st.success("Compliance analysis complete!")

results = st.session_state.reg_tracker_results
if results and "error" not in results:
    st.markdown("---")

    # Overall compliance KPI
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Overall Compliance", f"{results.get('overall_compliance', 0)}%")
    with k2:
        st.metric("Frameworks Analyzed", results.get("frameworks_analyzed", 0))
    with k3:
        total_gaps = sum(
            len(fr.get("gaps", []))
            for fr in results.get("framework_results", {}).values()
        )
        st.metric("Total Gaps", total_gaps)

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Compliance Radar", "Gap Analysis", "AI Narrative"])

    with tab1:
        fw_results = results.get("framework_results", {})
        scores = {fw: data["compliance_pct"] for fw, data in fw_results.items() if fw in frameworks_display}
        if scores:
            fig = compliance_radar(scores)
            st.plotly_chart(fig, use_container_width=True)

        # Framework details table
        rows = []
        for fw, data in fw_results.items():
            if fw in frameworks_display:
                rows.append({
                    "Framework": fw,
                    "Full Name": data.get("full_name", ""),
                    "Mandatory": "Yes" if data.get("mandatory") else "No",
                    "Compliance": f"{data['compliance_pct']}%",
                    "Covered": data["covered"],
                    "Partial": data["partial"],
                    "Missing": data["missing"],
                    "Total": data["total"],
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab2:
        for fw, data in fw_results.items():
            if fw not in frameworks_display:
                continue
            gaps = data.get("gaps", [])
            if gaps:
                st.markdown(f"#### {fw} Gaps ({len(gaps)})")
                gap_rows = []
                for gap in gaps:
                    priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(gap["priority"], "⚪")
                    gap_rows.append({
                        "ID": gap["requirement_id"],
                        "Requirement": gap["requirement"],
                        "Status": gap["status"].capitalize(),
                        "Priority": f"{priority_icon} {gap['priority'].capitalize()}",
                        "Reason": gap["reason"],
                    })
                st.dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)

    with tab3:
        narrative = results.get("gap_narrative", "")
        if narrative:
            st.markdown("#### AI-Generated Gap Analysis")
            st.markdown(narrative)

"""Streamlit page for the Regulatory Tracker Agent — with 24h auto-updates and Compliance Radar."""
import streamlit as st
import pandas as pd
from agents.regulatory_tracker import RegulatoryTrackerAgent
from utils.charts import compliance_radar, chart_unavailable_message
from utils.monitoring import regulatory_updater
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, pwc_header

st.set_page_config(page_title="Regulatory Tracker | ESG CoPilot", page_icon="📋", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Regulatory Tracker agent.")
st.title("📋 Regulatory Tracker Agent")
st.markdown("*Monitors global ESG frameworks — auto-updates within 24 hours of any mandate shift*")
st.markdown("---")

if "reg_tracker" not in st.session_state:
    st.session_state.reg_tracker = RegulatoryTrackerAgent()
    st.session_state.reg_tracker_results = None

agent = st.session_state.reg_tracker


def render_chart(fig):
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)

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
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Overall Compliance", f"{results.get('overall_compliance', 0)}%")
    with k2:
        st.metric("Frameworks Analyzed", results.get("frameworks_analyzed", 0))
    with k3:
        total_gaps = sum(len(fr.get("gaps", [])) for fr in results.get("framework_results", {}).values())
        st.metric("Total Gaps", total_gaps)
    with k4:
        updates = regulatory_updater.check_for_updates()
        st.metric("Pending Updates", updates.get("pending", 0))

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Compliance Radar", "Gap Analysis", "24h Auto-Updates", "AI Narrative"
    ])

    with tab1:
        fw_results = results.get("framework_results", {})
        scores = {fw: data["compliance_pct"] for fw, data in fw_results.items() if fw in frameworks_display}
        if scores:
            fig = compliance_radar(scores)
            render_chart(fig)

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
            safe_dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

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
                safe_dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)

    with tab3:
        update_data = regulatory_updater.check_for_updates()
        st.markdown("#### Regulatory Auto-Update Engine")
        st.markdown(f"**All updates detected within 24 hours:** {'✅ Yes' if update_data['within_24h'] else '❌ No'}")
        st.markdown(f"**Average response time:** {update_data['avg_response_hours']} hours")

        for update in update_data.get("updates", []):
            status_icon = {"integrated": "✅", "analyzing": "🔄", "pending": "⏳"}.get(update["status"], "⚪")
            impact_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(update["impact"], "⚪")
            with st.expander(f"{status_icon} {update['framework']} — {update['update_type']}: {update['description'][:80]}"):
                st.markdown(f"**Detected at:** {update['detected_at'][:19]}")
                st.markdown(f"**Response time:** {update['response_time_hours']} hours")
                st.markdown(f"**Impact:** {impact_icon} {update['impact'].capitalize()}")
                st.markdown(f"**Status:** {update['status'].capitalize()}")
                st.markdown("**Changes:**")
                for change in update.get("changes", []):
                    st.markdown(f"  - {change}")

    with tab4:
        narrative = results.get("gap_narrative", "")
        if narrative:
            st.markdown("#### AI-Generated Gap Analysis")
            st.markdown(narrative)

"""Streamlit page for the Audit Agent."""
import streamlit as st
import pandas as pd
from agents.audit_agent import AuditAgent
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, pwc_header

st.set_page_config(page_title="Audit Agent | ESG CoPilot", page_icon="🔍", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Audit Agent.")
st.title("🔍 Audit Agent")
st.markdown("*Compliance verification, data auditing, and audit trail management*")
st.markdown("---")

if "audit_agent" not in st.session_state:
    st.session_state.audit_agent = AuditAgent()
    st.session_state.audit_results = None

agent = st.session_state.audit_agent

st.info("For best results, run Data Collector, Regulatory Tracker, and Carbon Accountant first.")

if st.button("🔄 Run Audit Verification", type="primary"):
    with st.spinner("Running compliance audit..."):
        results = agent.run()
        st.session_state.audit_results = results
    st.success("Audit complete!")

results = st.session_state.audit_results
if results and "error" not in results:
    st.markdown("---")

    readiness = results.get("readiness_score", {})
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Audit Readiness", f"{readiness.get('overall', 0):.0f}%")
    with k2:
        st.metric("Grade", readiness.get("grade", "N/A"))
    with k3:
        st.metric("Issues Found", results.get("issues_count", 0))
    with k4:
        st.metric("Evidence Score", f"{readiness.get('evidence', 0):.0f}%")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Readiness Breakdown", "Compliance Checklist", "Data Completeness", "Audit Trail"
    ])

    with tab1:
        st.markdown("#### Readiness Score Components")
        components = {
            "Data Completeness": readiness.get("completeness", 0),
            "Compliance Score": readiness.get("compliance", 0),
            "Evidence Verifiability": readiness.get("evidence", 0),
        }
        for comp_name, score in components.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(min(score / 100, 1.0), text=f"{comp_name}: {score:.0f}%")
            with col2:
                status = "✅" if score >= 80 else ("⚠️" if score >= 60 else "❌")
                st.markdown(f"### {status}")

    with tab2:
        checklist = results.get("compliance_checklist", [])
        if checklist:
            status_icon = {"Pass": "✅", "Warning": "⚠️", "Fail": "❌"}
            rows = []
            for item in checklist:
                rows.append({
                    "Status": status_icon.get(item["status"], "⚪"),
                    "Framework": item.get("framework", "General"),
                    "Requirement": item.get("requirement", ""),
                    "Score": f"{item.get('score', 'N/A')}%",
                    "Result": item["status"],
                })
            df = pd.DataFrame(rows)
            safe_dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        completeness = results.get("completeness_audit", [])
        if completeness:
            for item in completeness:
                status_icon = {"Pass": "✅", "Warning": "⚠️", "Fail": "❌", "Missing": "🚫"}.get(item["status"], "⚪")
                priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(item["priority"], "⚪")
                st.markdown(
                    f"{status_icon} **{item['dataset']}** — "
                    f"Completeness: {item['completeness']}% | "
                    f"Records: {item['records']} | "
                    f"Priority: {priority_icon} {item['priority'].capitalize()}"
                )

    with tab4:
        trail = results.get("audit_trail", [])
        if trail:
            for entry in trail:
                st.markdown(
                    f"- `{entry['timestamp'][:19]}` — **{entry['event']}** "
                    f"(by {entry['agent']}) — {entry['status']}"
                )
        else:
            st.info("No audit trail entries yet. Run the full pipeline to populate.")

    # Findings summary
    st.markdown("---")
    st.markdown("#### AI Findings Summary")
    st.markdown(results.get("findings_summary", ""))

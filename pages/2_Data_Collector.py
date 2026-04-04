"""Streamlit page for the Data Collector Agent — with Enterprise Connectors & Auto-Discovery."""
import streamlit as st
import pandas as pd
from agents.data_collector import DataCollectorAgent
from utils.charts import quality_bar, connector_status_chart

st.set_page_config(page_title="Data Collector | ESG CoPilot", page_icon="📊", layout="wide")
st.title("📊 Data Collector Agent")
st.markdown("*Auto-discovers and ingests ESG data from enterprise systems with quality scoring*")
st.markdown("---")

if "data_collector" not in st.session_state:
    st.session_state.data_collector = DataCollectorAgent()
    st.session_state.data_collector_results = None

agent = st.session_state.data_collector

# ── Data Sources & Connectors ──
st.markdown("### Enterprise Data Sources")
col1, col2 = st.columns([2, 1])
with col1:
    uploaded_files = st.file_uploader(
        "Upload additional ESG data files (CSV/JSON)",
        accept_multiple_files=True,
        type=["csv", "json"],
    )
with col2:
    use_connectors = st.checkbox("Enable Enterprise Connectors", value=True,
                                  help="Connect to ERP, HR, IoT, Supplier Portal, Database, and API sources")
    st.caption("Connectors: SAP ERP, Workday HR, IoT/BMS, EcoVadis, PostgreSQL, CDP/MSCI")

# Run agent
if st.button("🔄 Run Auto-Discovery & Collection", type="primary", use_container_width=True):
    file_dict = {}
    if uploaded_files:
        for f in uploaded_files:
            file_dict[f.name] = f

    with st.spinner("Auto-discovering and collecting from all sources..."):
        results = agent.run(uploaded_files=file_dict if file_dict else None, use_connectors=use_connectors)
        st.session_state.data_collector_results = results
    st.success("Data collection complete!")

# ── Display Results ──
results = st.session_state.data_collector_results
if results and "error" not in results:
    st.markdown("---")

    # KPIs
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Datasets Loaded", results.get("datasets_loaded", 0))
    with k2:
        st.metric("Total Records", f"{results.get('total_records', 0):,}")
    with k3:
        st.metric("Completeness", f"{results.get('overall_completeness', 0)}%")
    with k4:
        st.metric("Avg Confidence", f"{results.get('overall_confidence', 0)}%")
    with k5:
        active = sum(1 for s in results.get("connector_statuses", {}).values() if s.get("status") in ("synced", "streaming"))
        st.metric("Active Connectors", f"{active}/6")

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Quality Scores", "Enterprise Connectors", "Missing Data Alerts",
        "Verifiable Trust", "Audit Trail",
    ])

    with tab1:
        quality = results.get("quality_scores", {})
        if quality:
            scores = {name: q["completeness"] for name, q in quality.items()}
            fig = quality_bar(scores)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Detailed Quality Metrics")
            rows = []
            for name, q in quality.items():
                rows.append({
                    "Dataset": name,
                    "Records": q["total_records"],
                    "Fields": q["total_fields"],
                    "Completeness": f"{q['completeness']}%",
                    "Null Values": q["null_count"],
                    "Confidence": f"{q['avg_confidence']}%" if q["avg_confidence"] > 0 else "N/A",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab2:
        conn_statuses = results.get("connector_statuses", {})
        if conn_statuses:
            fig = connector_status_chart(conn_statuses)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Connector Details")
            for key, status in conn_statuses.items():
                icon = {"synced": "✅", "streaming": "📡", "connected": "🔗", "error": "❌", "disconnected": "⚪"}.get(status.get("status", ""), "⚪")
                st.markdown(f"{icon} **{status['name']}** ({status['type']}) — "
                            f"Status: {status['status']} | Records: {status.get('records', 0)} | "
                            f"Last sync: {(status.get('last_sync', 'Never') or 'Never')[:19]}")
        else:
            st.info("Enable Enterprise Connectors and run collection to see connector status.")

    with tab3:
        alerts = results.get("missing_data_alerts", [])
        if alerts:
            for alert in alerts:
                icon = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(alert["severity"], "⚪")
                st.markdown(f"{icon} **{alert['severity'].upper()}** — {alert['message']}")
                st.caption(f"   Recommended action: {alert['action']}")
        else:
            st.success("No missing data gaps detected — all required datasets present!")

    with tab4:
        conf = results.get("confidence_scores", {})
        if conf:
            st.markdown("#### Verifiable Trust — Confidence Scoring per Dataset")
            st.caption("Each dataset is scored on completeness, source reliability, and freshness for audit readiness.")
            for name, score_data in conf.items():
                level_icon = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(score_data["level"], "⚪")
                audit_icon = "✅" if score_data["audit_ready"] else "❌"
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.progress(min(score_data["score"] / 100, 1.0),
                                text=f"{level_icon} **{name}** — {score_data['score']}% ({score_data['level']})")
                with col2:
                    st.markdown(f"Audit Ready: {audit_icon}")

    with tab5:
        if agent.audit_trail:
            for entry in agent.audit_trail:
                st.text(f"[{entry['timestamp'][:19]}] {entry['message']}")
        issues = results.get("quality_issues", [])
        if issues:
            st.markdown("#### AI Quality Classification")
            for issue in issues:
                severity_color = {"critical issue": "🔴", "moderate concern": "🟡", "minor issue": "🟢"}
                icon = severity_color.get(issue["severity"], "⚪")
                st.markdown(f"{icon} **{issue['dataset']}**: {issue['issue']} — *{issue['severity']}*")

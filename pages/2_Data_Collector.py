"""Streamlit page for the Data Collector Agent."""
import streamlit as st
import pandas as pd
from agents.data_collector import DataCollectorAgent
from utils.charts import quality_bar

st.set_page_config(page_title="Data Collector | ESG CoPilot", page_icon="📊", layout="wide")
st.title("📊 Data Collector Agent")
st.markdown("*Auto-discovers, ingests, and validates ESG data with quality scoring*")
st.markdown("---")

if "data_collector" not in st.session_state:
    st.session_state.data_collector = DataCollectorAgent()
    st.session_state.data_collector_results = None

agent = st.session_state.data_collector

# File upload section
st.markdown("### Data Sources")
col1, col2 = st.columns([2, 1])
with col1:
    uploaded_files = st.file_uploader(
        "Upload additional ESG data files (CSV/JSON)",
        accept_multiple_files=True,
        type=["csv", "json"],
    )
with col2:
    st.info("Sample data for GreenTech Solutions is loaded by default.")

# Run agent
if st.button("🔄 Run Data Collection", type="primary"):
    file_dict = {}
    if uploaded_files:
        for f in uploaded_files:
            file_dict[f.name] = f

    with st.spinner("Collecting and validating data..."):
        results = agent.run(uploaded_files=file_dict if file_dict else None)
        st.session_state.data_collector_results = results
    st.success("Data collection complete!")

# Display results
results = st.session_state.data_collector_results
if results and "error" not in results:
    st.markdown("---")

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Datasets Loaded", results.get("datasets_loaded", 0))
    with k2:
        st.metric("Total Records", f"{results.get('total_records', 0):,}")
    with k3:
        st.metric("Completeness", f"{results.get('overall_completeness', 0)}%")
    with k4:
        st.metric("Avg Confidence", f"{results.get('overall_confidence', 0)}%")

    st.markdown("---")

    # Quality scores chart
    tab1, tab2, tab3 = st.tabs(["Quality Scores", "Quality Issues", "Audit Trail"])

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
        issues = results.get("quality_issues", [])
        if issues:
            for issue in issues:
                severity_color = {"critical issue": "🔴", "moderate concern": "🟡", "minor issue": "🟢"}
                icon = severity_color.get(issue["severity"], "⚪")
                st.markdown(f"{icon} **{issue['dataset']}**: {issue['issue']} — *{issue['severity']}*")
        else:
            st.success("No quality issues detected!")

    with tab3:
        if agent.audit_trail:
            for entry in agent.audit_trail:
                st.text(f"[{entry['timestamp'][:19]}] {entry['message']}")

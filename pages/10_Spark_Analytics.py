"""Spark Analytics — Distributed computing dashboard for ESG data at scale."""
import streamlit as st
import pandas as pd
from utils.spark_processing import spark_processor, PYSPARK_AVAILABLE

st.set_page_config(page_title="Spark Analytics | ESG CoPilot", page_icon="⚡", layout="wide")
st.title("⚡ Spark Analytics Engine")
st.markdown("*Distributed ESG data processing powered by Apache PySpark*")
st.markdown("---")

# Status
if PYSPARK_AVAILABLE:
    st.success("PySpark is installed and available for distributed processing.")
else:
    st.warning("PySpark is not installed. Install with `pip install pyspark>=3.5.0`. "
               "Showing what the Spark layer computes — results use pandas fallback.")

st.markdown("### Processing Engine")
engine_col1, engine_col2 = st.columns(2)
with engine_col1:
    st.markdown(f"""
    | Property | Value |
    |----------|-------|
    | **Engine** | {'PySpark (Distributed)' if PYSPARK_AVAILABLE else 'Pandas (Local Fallback)'} |
    | **Mode** | {'local[*] (all cores)' if PYSPARK_AVAILABLE else 'Single-threaded'} |
    | **Shuffle Partitions** | {'4' if PYSPARK_AVAILABLE else 'N/A'} |
    | **Driver Memory** | {'2 GB' if PYSPARK_AVAILABLE else 'System default'} |
    """)
with engine_col2:
    st.markdown("""
    **Spark Advantages for ESG:**
    - Process millions of IoT sensor readings in parallel
    - Distributed supplier risk aggregation across 1000s of suppliers
    - Scalable emission calculations for global value chains
    - In-memory caching for repeated analytics queries
    """)

st.markdown("---")

# Run analysis
if st.button("⚡ Run Spark Analysis", type="primary"):
    with st.spinner("Running distributed analysis..." if PYSPARK_AVAILABLE else "Running analysis (pandas fallback)..."):
        if PYSPARK_AVAILABLE:
            analysis = spark_processor.run_full_analysis()
        else:
            # Fallback to pandas-based computation
            from utils.data_processing import (
                load_emissions, load_esg_metrics, load_supply_chain,
                compute_scope_totals, compute_quarterly_trends,
                compute_data_quality, compute_esg_summary,
            )
            emissions = load_emissions()
            metrics = load_esg_metrics()
            supply_chain = load_supply_chain()

            analysis = {
                "scope_totals_2024": compute_scope_totals(emissions, 2024),
                "scope_totals_2023": compute_scope_totals(emissions, 2023),
                "quarterly_trends": compute_quarterly_trends(emissions).to_dict("records"),
                "emissions_quality": compute_data_quality(emissions),
                "metrics_quality": compute_data_quality(metrics),
                "supplier_risk": (
                    supply_chain.groupby("risk_rating")
                    .agg(count=("supplier_id", "count"),
                         avg_esg=("esg_score", "mean"),
                         total_emissions=("emission_contribution_tco2e", "sum"))
                    .to_dict("index") if not supply_chain.empty else {}
                ),
                "pillar_scores": compute_esg_summary(metrics),
                "engine": "Pandas (local fallback)",
            }
        st.session_state.spark_analysis = analysis
    st.success(f"Analysis complete using {analysis.get('engine', 'unknown')} engine!")

if "spark_analysis" in st.session_state:
    analysis = st.session_state.spark_analysis
    st.markdown("---")

    st.markdown(f"### Results (Engine: `{analysis.get('engine', 'N/A')}`)")

    tab1, tab2, tab3, tab4 = st.tabs(["Scope Totals", "Data Quality", "Supplier Risk", "Pillar Scores"])

    with tab1:
        st.markdown("#### Emission Scope Totals (Spark Aggregation)")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**2024:**")
            for scope, total in analysis.get("scope_totals_2024", {}).items():
                st.metric(scope, f"{total:,.1f} tCO2e")
        with col2:
            st.markdown("**2023:**")
            for scope, total in analysis.get("scope_totals_2023", {}).items():
                st.metric(scope, f"{total:,.1f} tCO2e")

    with tab2:
        st.markdown("#### Data Quality Metrics (Spark Null Analysis)")
        for dataset_name, key in [("Emissions", "emissions_quality"), ("ESG Metrics", "metrics_quality")]:
            q = analysis.get(key, {})
            if q:
                st.markdown(f"**{dataset_name}:** {q.get('total_records', 0)} records, "
                            f"{q.get('completeness', 0)}% complete, "
                            f"{q.get('null_count', 0)} nulls, "
                            f"Confidence: {q.get('avg_confidence', 0)}%")

    with tab3:
        st.markdown("#### Supplier Risk Summary (Spark GroupBy)")
        risk_data = analysis.get("supplier_risk", {})
        if risk_data:
            rows = []
            for rating, data in risk_data.items():
                if isinstance(data, dict):
                    rows.append({"Risk Rating": rating, **data})
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab4:
        st.markdown("#### ESG Pillar Scores (Spark Aggregation)")
        pillar_data = analysis.get("pillar_scores", {})
        if pillar_data:
            for pillar, scores in pillar_data.items():
                if isinstance(scores, dict):
                    score = scores.get("score", 0)
                    st.progress(score / 100, text=f"{pillar}: {score}%")

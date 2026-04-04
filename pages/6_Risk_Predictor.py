"""Streamlit page for the Risk Predictor Agent."""
import streamlit as st
import pandas as pd
from agents.risk_predictor import RiskPredictorAgent
from utils.charts import risk_gauge

st.set_page_config(page_title="Risk Predictor | ESG CoPilot", page_icon="⚠️", layout="wide")
st.title("⚠️ Risk Predictor Agent")
st.markdown("*Climate risk forecasting, ESG rating prediction, and scenario analysis*")
st.markdown("---")

if "risk_agent" not in st.session_state:
    st.session_state.risk_agent = RiskPredictorAgent()
    st.session_state.risk_results = None

agent = st.session_state.risk_agent

if st.button("🔄 Run Risk Analysis", type="primary"):
    with st.spinner("Running risk analysis..."):
        results = agent.run()
        st.session_state.risk_results = results
    st.success("Risk analysis complete!")

results = st.session_state.risk_results
if results and "error" not in results:
    st.markdown("---")

    # Overall risk score
    climate_risks = results.get("climate_risks", {})
    rating = results.get("rating_prediction", {})

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Overall Risk Score", f"{climate_risks.get('overall_score', 0):.0f}/100")
    with k2:
        st.metric("Risk Level", climate_risks.get("overall_level", "N/A"))
    with k3:
        st.metric("Current ESG Rating", rating.get("current", "N/A"))
    with k4:
        st.metric("Predicted Rating", rating.get("predicted", "N/A"), help=f"Confidence: {rating.get('confidence', 0)}%")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Risk Dashboard", "ESG Rating", "Supplier Risks", "Scenario Analysis"
    ])

    with tab1:
        st.markdown("#### Climate Risk Breakdown")
        cols = st.columns(3)
        with cols[0]:
            fig = risk_gauge(climate_risks.get("physical_risk", 0), "Physical Risk")
            st.plotly_chart(fig, use_container_width=True)
        with cols[1]:
            fig = risk_gauge(climate_risks.get("transition_risk", 0), "Transition Risk")
            st.plotly_chart(fig, use_container_width=True)
        with cols[2]:
            fig = risk_gauge(climate_risks.get("emission_risk", 0), "Emission Trajectory")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("#### Risk Items")
        for item in climate_risks.get("risk_items", []):
            level_color = {"Low": "🟢", "Medium": "🟡", "High": "🔴"}.get(item["level"], "⚪")
            st.markdown(f"{level_color} **{item['category']}** (Score: {item['score']}/100) — {item['details']}")

    with tab2:
        st.markdown("#### ESG Rating Prediction")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Current Rating:** {rating.get('current', 'N/A')}")
            st.markdown(f"**Predicted Rating:** {rating.get('predicted', 'N/A')}")
            st.markdown(f"**Confidence:** {rating.get('confidence', 0)}%")
            st.markdown(f"**Targets Met:** {rating.get('metrics_met_pct', 0)}%")

        with col2:
            pillar_scores = rating.get("pillar_scores", {})
            if pillar_scores:
                for pillar, score in pillar_scores.items():
                    st.progress(score / 100, text=f"{pillar}: {score}%")

        # Improvement areas
        areas = rating.get("improvement_areas", [])
        if areas:
            st.markdown("#### Areas Needing Improvement")
            df = pd.DataFrame(areas)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        supplier_risks = results.get("supplier_risks", {})
        k1, k2, k3 = st.columns(3)
        with k1:
            st.metric("High-Risk Suppliers", supplier_risks.get("high_risk_count", 0))
        with k2:
            st.metric("Overdue Audits", supplier_risks.get("overdue_audits", 0))
        with k3:
            st.metric("Avg ESG Score", supplier_risks.get("avg_esg_score", 0))

        suppliers = supplier_risks.get("suppliers", [])
        if suppliers:
            df = pd.DataFrame(suppliers)
            st.dataframe(df, use_container_width=True, hide_index=True)

    with tab4:
        scenarios = results.get("scenarios", {})
        if scenarios:
            cols = st.columns(3)
            for i, (key, scenario) in enumerate(scenarios.items()):
                with cols[i]:
                    color = {"best_case": "🟢", "base_case": "🟡", "worst_case": "🔴"}.get(key, "⚪")
                    st.markdown(f"### {color} {scenario['name']}")
                    st.markdown(f"*{scenario['description']}*")
                    st.metric("Emission Reduction", f"{scenario['emission_reduction_pct']}%")
                    st.metric("Projected Emissions", f"{scenario['projected_emissions']:,.0f} tCO2e")
                    st.markdown(f"**Projected Rating:** {scenario['projected_rating']}")
                    st.markdown(f"**Investment:** {scenario['investment_required']}")
                    st.markdown(f"**Timeline:** {scenario['timeline']}")

    # Narrative
    st.markdown("---")
    st.markdown("#### AI Risk Narrative")
    st.markdown(results.get("narrative", ""))

"""Streamlit page for the Risk Predictor Agent — with interactive scenario sliders and deep-tier risk."""
import streamlit as st
import pandas as pd
from agents.risk_predictor import RiskPredictorAgent
from utils.charts import risk_gauge, charts_available, chart_unavailable_message
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, page_agent_header_live, pwc_header
from utils.pipeline_refresh import data_freshness_caption

st.set_page_config(page_title="Risk Predictor | ESG Intelligence Hub", page_icon="⚠️", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Risk Predictor agent.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="risk_predictor",
    agent_icon="⚠️",
)

st.title("⚠️ Risk Predictor Agent")
st.markdown("*Advanced climate risk forecasting, ESG rating prediction, and dynamic scenario analysis*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "risk_agent" not in st.session_state:
    st.session_state.risk_agent = RiskPredictorAgent()
    st.session_state.risk_results = None

agent = st.session_state.risk_agent


def render_chart(fig):
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)

if st.button("🔄 Run Risk Analysis", type="primary"):
    with st.spinner("Running risk analysis..."):
        results = agent.run()
        st.session_state.risk_results = results
    st.success("Risk analysis complete!")

results = st.session_state.risk_results
if results and "error" not in results:
    st.markdown("---")

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
        st.metric("Predicted Rating", rating.get("predicted", "N/A"),
                   help=f"Confidence: {rating.get('confidence', 0)}%")

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Risk Dashboard", "ESG Rating", "Deep-Tier Supplier Risk",
        "Dynamic Scenario Analysis", "AI Narrative"
    ])

    with tab1:
        st.markdown("#### Climate Risk Breakdown")
        cols = st.columns(3)
        with cols[0]:
            fig = risk_gauge(climate_risks.get("physical_risk", 0), "Physical Risk")
            render_chart(fig)
        with cols[1]:
            fig = risk_gauge(climate_risks.get("transition_risk", 0), "Transition Risk")
            render_chart(fig)
        with cols[2]:
            fig = risk_gauge(climate_risks.get("emission_risk", 0), "Emission Trajectory")
            render_chart(fig)

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

        areas = rating.get("improvement_areas", [])
        if areas:
            st.markdown("#### Areas Needing Improvement")
            safe_dataframe(pd.DataFrame(areas), use_container_width=True, hide_index=True)

    with tab3:
        st.markdown("#### Deep-Tier Supplier Risk Identification")
        st.caption("Risk analysis across Tier 1, Tier 2, and Tier 3 suppliers")
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
            safe_dataframe(df, use_container_width=True, hide_index=True)

        # Deep-tier visualization
        st.markdown("#### Supply Chain Tier Risk Distribution")
        from utils.data_processing import load_supply_chain
        sc_df = load_supply_chain()
        if not sc_df.empty:
            tier_risk = sc_df.groupby(["tier", "risk_rating"]).size().reset_index(name="count")
            if charts_available():
                import plotly.graph_objects as go
                fig = go.Figure()
                for risk in ["High", "Medium", "Low"]:
                    rdf = tier_risk[tier_risk["risk_rating"] == risk]
                    fig.add_trace(go.Bar(
                        x=rdf["tier"], y=rdf["count"], name=f"{risk} Risk",
                        marker_color={"High": "#F44336", "Medium": "#FF9800", "Low": "#4CAF50"}[risk],
                    ))
                fig.update_layout(title="Risk by Supply Chain Tier", barmode="stack", height=350)
                render_chart(fig)
            else:
                st.info(chart_unavailable_message())

    with tab4:
        st.markdown("#### Dynamic Scenario Analysis")
        st.caption("Adjust parameters to see projected outcomes in real-time")

        col1, col2 = st.columns(2)
        with col1:
            renewable_target = st.slider("Renewable Energy Target (%)", 30, 100, 60, 5)
            supplier_engagement = st.slider("Supplier Engagement Level (%)", 20, 100, 50, 5)
        with col2:
            investment_level = st.slider("ESG Investment (INR Lakhs)", 100, 1000, 400, 50)
            timeline_months = st.slider("Implementation Timeline (months)", 6, 36, 18, 3)

        # Compute dynamic scenario based on sliders
        base_emissions = results.get("scenarios", {}).get("base_case", {}).get("projected_emissions", 32000)
        renewable_impact = (renewable_target - 45) * 0.3
        supplier_impact = (supplier_engagement - 30) * 0.25
        investment_impact = (investment_level - 200) * 0.02
        total_reduction = min(55, max(5, renewable_impact + supplier_impact + investment_impact))
        projected = base_emissions * (1 - total_reduction / 100)

        if total_reduction >= 30:
            proj_rating = "A"
        elif total_reduction >= 20:
            proj_rating = "A-"
        elif total_reduction >= 10:
            proj_rating = "BBB+"
        else:
            proj_rating = "BBB"

        st.markdown("---")
        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("Projected Reduction", f"{total_reduction:.1f}%")
        with r2:
            st.metric("Projected Emissions", f"{projected:,.0f} tCO2e")
        with r3:
            st.metric("Projected Rating", proj_rating)

        # Pre-built scenarios comparison
        scenarios = results.get("scenarios", {})
        if scenarios:
            st.markdown("---")
            st.markdown("#### Pre-Built Scenario Comparison")
            cols = st.columns(3)
            for i, (key, scenario) in enumerate(scenarios.items()):
                with cols[i]:
                    color = {"best_case": "🟢", "base_case": "🟡", "worst_case": "🔴"}.get(key, "⚪")
                    st.markdown(f"### {color} {scenario['name']}")
                    st.markdown(f"*{scenario['description']}*")
                    st.metric("Emission Reduction", f"{scenario['emission_reduction_pct']}%")
                    st.metric("Projected Emissions", f"{scenario['projected_emissions']:,.0f} tCO2e")
                    st.markdown(f"**Rating:** {scenario['projected_rating']} | **Timeline:** {scenario['timeline']}")

    with tab5:
        st.markdown("#### AI Risk Narrative")
        st.markdown(results.get("narrative", ""))

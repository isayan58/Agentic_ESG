"""Streamlit page for the Carbon Accountant Agent — with Scope 3 X-Ray Map."""
import streamlit as st
import pandas as pd
from agents.carbon_accountant import CarbonAccountantAgent
from utils.charts import (
    emissions_donut,
    emissions_trend,
    scope3_xray_map,
    charts_available,
    chart_unavailable_message,
)
from utils.data_processing import load_supply_chain
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, page_agent_header_live, pwc_header
from utils.pipeline_refresh import data_freshness_caption

st.set_page_config(page_title="Carbon Accountant | ESG Pilot", page_icon="🌱", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Carbon Accountant agent.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="carbon_accountant",
    agent_icon="🌱",
)

st.title("🌱 Carbon Accountant Agent")
st.markdown("*Tracks Scope 1/2/3 emissions with AI-driven supply chain hotspot detection*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "carbon_agent" not in st.session_state:
    st.session_state.carbon_agent = CarbonAccountantAgent()
    st.session_state.carbon_results = None

agent = st.session_state.carbon_agent


def render_chart(fig):
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)

if st.button("🔄 Run Carbon Analysis", type="primary"):
    with st.spinner("Analyzing carbon emissions..."):
        results = agent.run()
        st.session_state.carbon_results = results
    st.success("Carbon analysis complete!")

results = st.session_state.carbon_results
if results and "error" not in results:
    st.markdown("---")

    # KPIs
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(
            "Total Emissions (2024)",
            f"{results['total_emissions_current']:,.0f} tCO2e",
            f"{results['yoy_change_pct']}% YoY",
        )
    with k2:
        st.metric("Carbon Intensity", f"{results['carbon_intensity']} tCO2e/$M")
    with k3:
        energy = results.get("energy_analysis", {})
        st.metric("Renewable Energy", f"{energy.get('renewable_pct', 0)}%")
    with k4:
        st.metric("Supply Chain Hotspots", len(results.get("hotspots", [])))

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Scope Breakdown", "Emissions Trend", "Scope 3 X-Ray Map", "Energy Mix", "AI Narrative"
    ])

    with tab1:
        col1, col2 = st.columns([1, 1])
        with col1:
            fig = emissions_donut(results["scope_totals_current"])
            render_chart(fig)
        with col2:
            st.markdown("#### Scope Comparison (YoY)")
            for scope in ["Scope 1", "Scope 2", "Scope 3"]:
                current = results["scope_totals_current"].get(scope, 0)
                prev = results["scope_totals_previous"].get(scope, 0)
                change = ((current - prev) / prev * 100) if prev else 0
                st.metric(scope, f"{current:,.0f} tCO2e", f"{change:+.1f}%")

    with tab2:
        trends_data = results.get("quarterly_trends", [])
        if trends_data:
            trends_df = pd.DataFrame(trends_data)
            fig = emissions_trend(trends_df)
            render_chart(fig)

    with tab3:
        st.markdown("#### Scope 3 X-Ray — Global Supply Chain Emission Hotspots")
        st.caption("Bubble size = emission contribution. Color = risk level (Red=High, Yellow=Medium, Green=Low)")
        supply_chain_df = load_supply_chain()
        if not supply_chain_df.empty:
            fig = scope3_xray_map(supply_chain_df)
            render_chart(fig)

        # Hotspot details
        hotspots = results.get("hotspots", [])
        if hotspots:
            st.markdown("#### Top Emission Hotspots")
            for i, h in enumerate(hotspots, 1):
                st.markdown(f"""
                **{i}. {h['supplier']}** ({h['country']} — {h['sector']})
                - Emissions: **{h['emissions']:,.1f} tCO2e** | ESG Score: {h['esg_score']}/100
                - Risk Factors: {h['risk_factors']}
                """)

    with tab4:
        energy_data = results.get("energy_analysis", {})
        if energy_data:
            st.metric("Total Energy", f"{energy_data.get('total_mwh', 0):,.0f} MWh")
            by_source = energy_data.get("by_source", {})
            if by_source:
                if charts_available():
                    import plotly.graph_objects as go
                    fig = go.Figure(go.Pie(
                        labels=list(by_source.keys()),
                        values=list(by_source.values()),
                        hole=0.4,
                        marker=dict(colors=["#F44336", "#4CAF50", "#FF9800", "#2196F3"]),
                    ))
                    fig.update_layout(title="Energy Mix by Source", height=350)
                    render_chart(fig)
                else:
                    st.info(chart_unavailable_message())

        # Category breakdown table
        cat_data = results.get("category_breakdown", [])
        if cat_data:
            st.markdown("#### Emissions by Category (2024)")
            safe_dataframe(pd.DataFrame(cat_data), use_container_width=True, hide_index=True)

    with tab5:
        narrative = results.get("narrative", "")
        if narrative:
            st.markdown("#### AI-Generated Carbon Narrative")
            st.markdown(narrative)

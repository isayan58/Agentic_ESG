"""Streamlit page for the Action Agent."""
import streamlit as st
import pandas as pd
from agents.action_agent import ActionAgent
from utils.charts import action_timeline, chart_unavailable_message
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, pwc_header
from utils.pipeline_refresh import data_freshness_caption

st.set_page_config(page_title="Action Agent | ESG CoPilot", page_icon="🎯", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Action Agent.")
st.title("🎯 Action Agent")
st.markdown("*Generates prioritized, actionable ESG recommendations with timelines*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "action_agent" not in st.session_state:
    st.session_state.action_agent = ActionAgent()
    st.session_state.action_results = None

agent = st.session_state.action_agent


def render_chart(fig):
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)

st.info("For best results, run Risk Predictor, Audit Agent, and Carbon Accountant first.")

if st.button("🔄 Generate Recommendations", type="primary"):
    with st.spinner("Generating action recommendations..."):
        results = agent.run()
        st.session_state.action_results = results
    st.success("Recommendations generated!")

results = st.session_state.action_results
if results and "error" not in results:
    st.markdown("---")

    summary = results.get("summary", {})
    k1, k2, k3, k4, k5 = st.columns(5)
    with k1:
        st.metric("Total Actions", summary.get("total_actions", 0))
    with k2:
        st.metric("Critical", summary.get("critical", 0))
    with k3:
        st.metric("High Priority", summary.get("high", 0))
    with k4:
        st.metric("Medium", summary.get("medium", 0))
    with k5:
        st.metric("Est. Investment", f"INR {summary.get('total_investment', 0)} L")

    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Action Items", "Implementation Roadmap", "AI Narrative"])

    with tab1:
        actions = results.get("actions", [])
        if actions:
            # Filter by priority
            priority_filter = st.multiselect(
                "Filter by priority",
                ["Critical", "High", "Medium", "Low"],
                default=["Critical", "High", "Medium", "Low"],
            )
            filtered = [a for a in actions if a.get("priority") in priority_filter]

            for action in filtered:
                priority_colors = {
                    "Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"
                }
                icon = priority_colors.get(action["priority"], "⚪")
                with st.expander(f"{icon} [{action['id']}] {action['action']} — {action['priority']}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Category:** {action['category']}")
                        st.markdown(f"**Source:** {action['source']}")
                    with col2:
                        st.markdown(f"**Duration:** {action['duration_weeks']} weeks")
                        st.markdown(f"**Cost:** INR {action.get('estimated_cost_lakhs', 0)} lakhs")
                    with col3:
                        st.markdown(f"**Start:** {action.get('start_date', 'TBD')}")
                        st.markdown(f"**End:** {action.get('end_date', 'TBD')}")
                    st.markdown(f"**Impact:** {action['impact']}")
                    st.markdown(f"**KPI:** {action.get('kpi', 'N/A')}")
                    desc = action.get("detailed_description", "")
                    if desc:
                        st.markdown(f"**Details:** {desc}")

    with tab2:
        actions = results.get("actions", [])
        if actions:
            actions_df = pd.DataFrame(actions)
            if "duration_weeks" in actions_df.columns:
                fig = action_timeline(actions_df)
                render_chart(fig)

            # Summary table
            display_cols = ["id", "action", "priority", "category", "duration_weeks", "start_date", "end_date"]
            available_cols = [c for c in display_cols if c in actions_df.columns]
            safe_dataframe(actions_df[available_cols], use_container_width=True, hide_index=True)

    with tab3:
        narrative = results.get("roadmap_narrative", "")
        if narrative:
            st.markdown("#### Strategic Roadmap Overview")
            st.markdown(narrative)

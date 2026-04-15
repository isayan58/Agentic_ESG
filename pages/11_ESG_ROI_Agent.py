"""ESG ROI Agent — dual ROI, value channels, and investment quality."""
import pandas as pd
import streamlit as st

from core.orchestrator import Orchestrator
from utils.streamlit_compat import safe_dataframe


st.set_page_config(page_title="ESG ROI Agent | ESG CoPilot", page_icon="⭐", layout="wide")
st.title("⭐ ESG ROI Agent")
st.markdown("*Quantify ESG-linked financial return, strategic value, and investment quality*")
st.markdown("---")

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()

orch = st.session_state.orchestrator

run_roi = st.button("Run ESG ROI Analysis", type="primary", use_container_width=True)

if run_roi:
    with st.spinner("Running ESG ROI analysis..."):
        results = orch.run_single_agent("roi_agent")
        st.session_state.roi_results = results

results = st.session_state.get("roi_results")

if results:
    if "error" in results:
        st.error(results["error"])
    else:
        fin_roi = results.get("financial_roi", {})
        strat_roi = results.get("strategic_roi", {})
        iqs = results.get("investment_quality_score", {})
        kpi = results.get("kpi_engine", {})

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Financial ROI", f"{fin_roi.get('roi_pct', 0)}%")
        with col2:
            st.metric("Net Benefit", f"INR {fin_roi.get('net_financial_benefit', 0)} Cr")
        with col3:
            st.metric("IQS", f"{iqs.get('score', 0)}/100", f"Grade: {iqs.get('grade', 'N/A')}")
        with col4:
            st.metric("Payback", f"{fin_roi.get('payback_years', 'N/A')} years")

        st.markdown("### Executive Briefing")
        st.write(results.get("narrative", "No narrative available."))

        st.markdown("### Value Creation Channels")
        channels = pd.DataFrame(kpi.get("value_channels", []))
        if not channels.empty:
            safe_dataframe(
                channels[["channel", "score", "trend", "financial_impact"]],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### Investment Quality Components")
        components = iqs.get("components", {})
        if components:
            comp_df = pd.DataFrame(
                [{"component": key.replace("_", " ").title(), "score": value}
                 for key, value in components.items()]
            )
            safe_dataframe(comp_df, use_container_width=True, hide_index=True)

        st.markdown("### Strategic ROI")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Cost of Capital Reduction", f"{strat_roi.get('cost_of_capital_reduction_bps', 0)} bps")
        with col2:
            st.metric("Talent Retention Savings", f"INR {strat_roi.get('talent_retention_savings', 0)}")
        with col3:
            st.metric("Brand Premium Score", strat_roi.get("brand_premium_score", 0))

        st.markdown("### J-Curve")
        j_curve = results.get("j_curve", {})
        quarters = pd.DataFrame(j_curve.get("quarters", []))
        if not quarters.empty:
            safe_dataframe(quarters, use_container_width=True, hide_index=True)
            st.caption(
                f"Breakeven: {j_curve.get('breakeven_quarter', 'Not yet reached')} | "
                f"Current net position: INR {j_curve.get('net_position', 0)} Cr"
            )

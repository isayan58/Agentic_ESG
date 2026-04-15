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
        fin_summary = kpi.get("financial_summary", {})
        cagr = kpi.get("cagr", {})
        volatility = kpi.get("volatility", {})

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Financial ROI", f"{fin_roi.get('roi_pct', 0)}%")
        with col2:
            st.metric("Net Benefit", f"INR {fin_roi.get('net_financial_benefit', 0)} Cr")
        with col3:
            st.metric("IQS", f"{iqs.get('score', 0)}/100", f"Grade: {iqs.get('grade', 'N/A')}")
        with col4:
            st.metric("Payback", f"{fin_roi.get('payback_years', 'N/A')} years")

        st.markdown("### In Plain English")
        st.markdown("""
        - **Top line** means growth: is ESG helping the company grow revenue and brand strength?
        - **Bottom line** means profit: is ESG saving money, improving margins, or avoiding future costs?
        - **Capital efficiency** means return on spend: is ESG capex creating value or just adding expense?
        - **J-curve** means timing: does ESG hurt in the short term but pay back later?
        """)

        st.markdown("### Business Architecture on This Page")
        arch1, arch2, arch3, arch4 = st.columns(4)
        for col, title, body in [
            (arch1, "1. Financial Inputs", "Revenue, margins, cost of capital, and ESG capex come in from the financial dataset."),
            (arch2, "2. KPI Engine", "The engine converts ESG and finance data into five value channels: growth, cost, risk, people, and capital efficiency."),
            (arch3, "3. ROI Logic", "The ROI layer calculates savings, payback, strategic value, and investment quality."),
            (arch4, "4. Decision Signal", "The output tells a leader whether ESG is helping growth, profit, resilience, and long-term value."),
        ]:
            with col:
                st.markdown(f"**{title}**")
                st.caption(body)

        st.markdown("### Top Line and Bottom Line")
        tl1, tl2, tl3, tl4 = st.columns(4)
        with tl1:
            st.metric("Revenue (Top Line)", f"INR {fin_summary.get('revenue_current_fy', 0)} Cr",
                      f"{fin_summary.get('revenue_growth_pct', 0)}% growth")
        with tl2:
            st.metric("EBITDA Margin", f"{fin_summary.get('ebitda_margin_latest', 0)}%")
        with tl3:
            st.metric("ROA / ROE", f"{fin_summary.get('roa_latest', 0)}% / {fin_summary.get('roe_latest', 0)}%")
        with tl4:
            st.metric("Cost of Capital", f"{fin_summary.get('cost_of_capital_latest', 0)}%")

        st.markdown("### Executive Briefing")
        st.write(results.get("narrative", "No narrative available."))

        st.markdown("### Hypotheses Covered on This Page")
        hypotheses_df = pd.DataFrame([
            {
                "Hypothesis": "H1 Growth",
                "Plain English": "ESG can help revenue growth and brand strength.",
                "Current read": f"Revenue growth {fin_summary.get('revenue_growth_pct', 0)}%",
            },
            {
                "Hypothesis": "H2 Profitability",
                "Plain English": "ESG can reduce costs and improve profit quality.",
                "Current read": f"Cost savings INR {fin_roi.get('cost_savings', {}).get('total', 0)} Cr",
            },
            {
                "Hypothesis": "H5 CapEx Quality",
                "Plain English": "ESG investment should create real business value.",
                "Current read": f"IQS {iqs.get('score', 0)}/100 ({iqs.get('grade', 'N/A')})",
            },
            {
                "Hypothesis": "H6 J-Curve",
                "Plain English": "ESG may cost money first and pay back later.",
                "Current read": f"Breakeven {results.get('j_curve', {}).get('breakeven_quarter', 'Not yet reached')}",
            },
        ])
        safe_dataframe(hypotheses_df, use_container_width=True, hide_index=True)

        st.markdown("### Value Creation Channels")
        channels = pd.DataFrame(kpi.get("value_channels", []))
        if not channels.empty:
            safe_dataframe(
                channels[["channel", "score", "trend", "financial_impact"]],
                use_container_width=True,
                hide_index=True,
            )

        st.markdown("### Finance Detail")
        finance_detail = pd.DataFrame([
            {"Metric": "Revenue CAGR", "Value": f"{cagr.get('revenue_cagr', 0)}%"},
            {"Metric": "EBITDA CAGR", "Value": f"{cagr.get('ebitda_cagr', 0)}%"},
            {"Metric": "ESG Capex CAGR", "Value": f"{cagr.get('esg_capex_cagr', 0)}%"},
            {"Metric": "Revenue Volatility", "Value": f"{volatility.get('revenue_volatility', 0)}%"},
            {"Metric": "Margin Volatility", "Value": f"{volatility.get('margin_volatility', 0)}"},
            {"Metric": "Earnings Volatility", "Value": f"{volatility.get('earnings_volatility', 0)}%"},
            {"Metric": "Carbon Tax Exposure", "Value": f"INR {fin_summary.get('carbon_tax_exposure_latest', 0)} L"},
            {"Metric": "Energy Cost", "Value": f"INR {fin_summary.get('energy_cost_latest', 0)} Cr"},
        ])
        safe_dataframe(finance_detail, use_container_width=True, hide_index=True)

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

"""ESG ROI Agent — dual ROI, value channels, and investment quality."""
import pandas as pd
import streamlit as st

from core.orchestrator import Orchestrator
from utils.streamlit_compat import safe_dataframe
from utils.ui import (
    hero, section_header, kpi_card, iqs_gauge, grade_pill, inject_global_css,
)
from utils.auth import require_login, sidebar_auth_widget


st.set_page_config(page_title="ESG ROI Agent | ESG CoPilot", page_icon="⭐", layout="wide")
inject_global_css()
sidebar_auth_widget()
require_login("Sign in to explore the ESG ROI dashboard.")

hero(
    title="ESG ROI Agent",
    emoji="⭐",
    subtitle=(
        "Quantify ESG-linked financial return, strategic value, and investment quality. "
        "The ROI Agent blends cost savings, capital-of-cost reduction, talent retention, "
        "and brand premium into a single board-ready signal."
    ),
    chips=[
        "Dual ROI · Financial + Strategic",
        "5 Value Creation Channels",
        "J-Curve Payback Model",
        "Investment Quality Score",
    ],
)

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

        gauge_col, kpi_col = st.columns([1, 2])
        with gauge_col:
            iqs_gauge(iqs.get("score", 0), iqs.get("grade", "N/A"))
        with kpi_col:
            r1, r2 = st.columns(2)
            with r1:
                kpi_card("Financial ROI", f"{fin_roi.get('roi_pct', 0)}%",
                         "Payback-weighted return", key="roi_page_fin")
            with r2:
                kpi_card("Net Benefit",
                         f"INR {fin_roi.get('net_financial_benefit', 0)} Cr",
                         "After ESG capex and friction", key="roi_page_net")
            r3, r4 = st.columns(2)
            with r3:
                kpi_card("Payback",
                         f"{fin_roi.get('payback_years', 'N/A')} years",
                         "Breakeven horizon", key="roi_page_payback")
            with r4:
                kpi_card("IQS Grade", iqs.get("grade", "N/A"),
                         f"Score {iqs.get('score', 0)}/100", key="roi_page_grade")
            if iqs.get("grade"):
                st.markdown(
                    f"Board-ready signal: {grade_pill(iqs.get('grade', 'N/A'))}",
                    unsafe_allow_html=True,
                )

        section_header("In Plain English",
                       "How each metric on this page translates to business impact.")
        st.markdown("""
        - **Top line** means growth: is ESG helping the company grow revenue and brand strength?
        - **Bottom line** means profit: is ESG saving money, improving margins, or avoiding future costs?
        - **Capital efficiency** means return on spend: is ESG capex creating value or just adding expense?
        - **J-curve** means timing: does ESG hurt in the short term but pay back later?
        """)

        section_header("Business Architecture on This Page",
                       "Four layers: finance inputs → KPI engine → ROI logic → decision signal.")
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

        section_header("Top Line and Bottom Line",
                       "Four primary financial signals after the pipeline run.")
        tl1, tl2, tl3, tl4 = st.columns(4)
        with tl1:
            kpi_card(
                "Revenue (Top Line)",
                f"INR {fin_summary.get('revenue_current_fy', 0)} Cr",
                f"{fin_summary.get('revenue_growth_pct', 0)}% growth",
                key="roi_tl_rev",
            )
        with tl2:
            kpi_card(
                "EBITDA Margin",
                f"{fin_summary.get('ebitda_margin_latest', 0)}%",
                "Operating profit quality",
                key="roi_tl_ebitda",
            )
        with tl3:
            kpi_card(
                "ROA / ROE",
                f"{fin_summary.get('roa_latest', 0)}% / {fin_summary.get('roe_latest', 0)}%",
                "Return on assets and equity",
                key="roi_tl_roa",
            )
        with tl4:
            kpi_card(
                "Cost of Capital",
                f"{fin_summary.get('cost_of_capital_latest', 0)}%",
                "Risk-adjusted funding cost",
                key="roi_tl_coc",
            )

        section_header("Executive Briefing",
                       "Narrative summary generated by the ROI Agent.")
        st.write(results.get("narrative", "No narrative available."))

        section_header("Hypotheses Covered on This Page",
                       "Mapping from business hypotheses to live signals on this run.")
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

        section_header("Value Creation Channels",
                       "Five channels — Growth, Cost, Risk, Human Capital, Capital Efficiency.")
        channels = pd.DataFrame(kpi.get("value_channels", []))
        if not channels.empty:
            safe_dataframe(
                channels[["channel", "score", "trend", "financial_impact"]],
                use_container_width=True,
                hide_index=True,
            )

        section_header("Finance Detail",
                       "CAGR, volatility, and carbon-tax exposure context.")
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

        section_header("Investment Quality Components",
                       "Sub-scores that roll up into the overall IQS.")
        components = iqs.get("components", {})
        if components:
            comp_df = pd.DataFrame(
                [{"component": key.replace("_", " ").title(), "score": value}
                 for key, value in components.items()]
            )
            safe_dataframe(comp_df, use_container_width=True, hide_index=True)

        section_header("Strategic ROI",
                       "Soft-value signals: funding cost, talent, and brand.")
        col1, col2, col3 = st.columns(3)
        with col1:
            kpi_card(
                "Cost of Capital Reduction",
                f"{strat_roi.get('cost_of_capital_reduction_bps', 0)} bps",
                "Lower-cost access to funding",
                key="strat_coc",
            )
        with col2:
            kpi_card(
                "Talent Retention Savings",
                f"INR {strat_roi.get('talent_retention_savings', 0)}",
                "Avoided attrition cost",
                key="strat_talent",
            )
        with col3:
            kpi_card(
                "Brand Premium Score",
                str(strat_roi.get("brand_premium_score", 0)),
                "ESG-linked brand uplift",
                key="strat_brand",
            )

        section_header("J-Curve",
                       "Quarterly cost vs benefit view with breakeven detection.")
        j_curve = results.get("j_curve", {})
        quarters = pd.DataFrame(j_curve.get("quarters", []))
        if not quarters.empty:
            safe_dataframe(quarters, use_container_width=True, hide_index=True)
            st.caption(
                f"Breakeven: {j_curve.get('breakeven_quarter', 'Not yet reached')} | "
                f"Current net position: INR {j_curve.get('net_position', 0)} Cr"
            )

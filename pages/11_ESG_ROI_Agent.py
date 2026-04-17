"""ESG ROI Agent — dual ROI, value channels, investment quality, and peer benchmarking."""
import pandas as pd
import streamlit as st

from core.orchestrator import Orchestrator
from utils.streamlit_compat import safe_dataframe
from utils.ui import (
    hero, section_header, kpi_card, iqs_gauge, grade_pill, inject_global_css,
)
from utils.auth import require_login, sidebar_auth_widget

try:
    import plotly.graph_objects as go
    import plotly.express as px
    _PLOTLY = True
except ImportError:
    _PLOTLY = False


st.set_page_config(page_title="ESG ROI Agent | ESG CoPilot", page_icon="⭐", layout="wide")
inject_global_css()
sidebar_auth_widget()
require_login("Sign in to explore the ESG ROI dashboard.")

hero(
    title="ESG ROI Agent",
    emoji="⭐",
    subtitle=(
        "Quantify ESG-linked financial return, strategic value, and investment quality. "
        "The ROI Agent blends cost savings, cost-of-capital reduction, talent retention, "
        "and brand premium into a single board-ready signal."
    ),
    chips=[
        "Dual ROI · Financial + Strategic",
        "5 Value Creation Channels",
        "J-Curve Payback Model",
        "Investment Quality Score",
        "Peer Benchmarking",
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
        tab_company, tab_peers = st.tabs(["📊 Your Company", "🏢 Peer Benchmarking"])

        # ══════════════════════════════════════════════════════════════════════
        # TAB 1 — YOUR COMPANY  (all existing content, unchanged)
        # ══════════════════════════════════════════════════════════════════════
        with tab_company:
            fin_roi    = results.get("financial_roi", {})
            strat_roi  = results.get("strategic_roi", {})
            iqs        = results.get("investment_quality_score", {})
            kpi        = results.get("kpi_engine", {})
            fin_summary = kpi.get("financial_summary", {})
            cagr       = kpi.get("cagr", {})
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
                {"Metric": "Revenue CAGR",       "Value": f"{cagr.get('revenue_cagr', 0)}%"},
                {"Metric": "EBITDA CAGR",        "Value": f"{cagr.get('ebitda_cagr', 0)}%"},
                {"Metric": "ESG Capex CAGR",     "Value": f"{cagr.get('esg_capex_cagr', 0)}%"},
                {"Metric": "Revenue Volatility", "Value": f"{volatility.get('revenue_volatility', 0)}%"},
                {"Metric": "Margin Volatility",  "Value": f"{volatility.get('margin_volatility', 0)}"},
                {"Metric": "Earnings Volatility","Value": f"{volatility.get('earnings_volatility', 0)}%"},
                {"Metric": "Carbon Tax Exposure","Value": f"INR {fin_summary.get('carbon_tax_exposure_latest', 0)} L"},
                {"Metric": "Energy Cost",        "Value": f"INR {fin_summary.get('energy_cost_latest', 0)} Cr"},
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

        # ══════════════════════════════════════════════════════════════════════
        # TAB 2 — PEER BENCHMARKING
        # ══════════════════════════════════════════════════════════════════════
        with tab_peers:
            peer = results.get("peer_benchmarking", {})

            if not peer.get("available"):
                # ── Teaser / upload prompt ────────────────────────────────
                section_header(
                    "Peer Benchmarking",
                    "Compare your ESG and financial metrics against sector peers.",
                )
                st.info(
                    "**No peer data found.** Upload a sector peer dataset on the "
                    "**Data Collector → Connect Data Sources → File Upload** page to unlock this view.\n\n"
                    "**Supported schemas and what each unlocks:**\n\n"
                    "| Schema | Key columns | What it enables |\n"
                    "|---|---|---|\n"
                    "| `peer_metrics` | `company`, `roa`, `ebitda_margin`, `esg_score`, `esg_capex_pct` | Full metric comparison + percentile ranks |\n"
                    "| `peer_benchmark` | `company`, `roa_avg`, `ebitda_margin_avg`, `esg_score_avg` | 5-year average comparison |\n"
                    "| `peer_esg` | `company`, `esg_score`, `scope1_emissions_tco2e`, `scope2_emissions_tco2e` | ESG score + emissions benchmarking |\n"
                    "| `peer_financials` | `company`, `revenue`, `ebitda`, `net_profit`, `total_assets` | Financial ratio computation |\n\n"
                    "See **SCHEMA.md** for full column specs and example values. "
                    "The reference dataset (`esg_financial_dashboard_15_companies.xlsx`) covers "
                    "15 Indian listed companies across PetroChemical, Power, and Mining sectors."
                )
            else:
                # ── Header strip ──────────────────────────────────────────
                peer_count  = peer.get("peer_count", 0)
                sectors     = peer.get("sectors_covered", [])
                source_label = {
                    "peer_metrics":   "pre-calculated ratios",
                    "peer_benchmark": "5-year averages",
                    "peer_esg":       "raw ESG inputs",
                }.get(peer.get("peer_source", ""), "peer data")

                section_header(
                    "Peer Benchmarking",
                    f"{peer_count} companies · {', '.join(sectors) if sectors else 'All sectors'} · Source: {source_label}",
                )

                benchmarks  = peer.get("benchmarks", {})
                company_name = peer.get("company_name", "Your Company")

                # ── KPI comparison cards ──────────────────────────────────
                if benchmarks:
                    bm_cols = st.columns(len(benchmarks))
                    for col, (mk, b) in zip(bm_cols, benchmarks.items()):
                        with col:
                            cv       = b.get("company_value", 0)
                            median   = b.get("peer_median", 0)
                            gap      = b.get("gap_vs_median", 0)
                            pct      = b.get("percentile")
                            unit     = b.get("unit", "")
                            better   = b.get("higher_is_better", True)

                            # Delta colour: green if above median on "higher-is-better",
                            # green if below median on "lower-is-better"
                            if gap != 0:
                                sign     = "+" if gap > 0 else ""
                                is_good  = (gap > 0 and better) or (gap < 0 and not better)
                                delta_str = f"{sign}{gap}{unit} vs median"
                            else:
                                delta_str = "At sector median"
                                is_good   = True

                            pct_str = f"{pct}th percentile" if pct is not None else ""
                            kpi_card(
                                b["label"],
                                f"{cv}{unit}",
                                f"{delta_str} · {pct_str}",
                                key=f"peer_card_{mk}",
                            )

                st.divider()

                # ── ESG Score bar chart ───────────────────────────────────
                peer_table = peer.get("peer_table", [])

                if peer_table and "esg_score" in benchmarks and _PLOTLY:
                    section_header(
                        "ESG Score vs Peers",
                        f"{company_name} highlighted — sector peer distribution.",
                    )
                    chart_df = pd.DataFrame(peer_table)
                    if "esg_score" in chart_df.columns and "company" in chart_df.columns:
                        chart_df = chart_df.dropna(subset=["esg_score"]).sort_values("esg_score")
                        colors = [
                            "#E8453C" if c == company_name else "#CADCFC"
                            for c in chart_df["company"]
                        ]
                        fig = go.Figure(go.Bar(
                            x=chart_df["esg_score"],
                            y=chart_df["company"],
                            orientation="h",
                            marker_color=colors,
                            text=[f"{v:.1f}" for v in chart_df["esg_score"]],
                            textposition="outside",
                        ))
                        company_score = benchmarks["esg_score"]["company_value"]
                        fig.add_vline(
                            x=benchmarks["esg_score"]["peer_median"],
                            line_dash="dash", line_color="gray",
                            annotation_text="Sector median",
                            annotation_position="top right",
                        )
                        fig.update_layout(
                            xaxis_title="ESG Score (/100)",
                            yaxis_title=None,
                            height=max(350, peer_count * 30),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=40, r=60, t=30, b=40),
                            font=dict(family="Inter, sans-serif", size=12),
                            showlegend=False,
                        )
                        st.plotly_chart(fig, use_container_width=True)

                # ── EBITDA Margin vs ROA scatter ──────────────────────────
                if (peer_table and "ebitda_margin" in benchmarks
                        and "roa" in benchmarks and _PLOTLY):
                    section_header(
                        "Profitability Landscape",
                        "EBITDA Margin vs Return on Assets — each dot is a peer company.",
                    )
                    sdf = pd.DataFrame(peer_table)
                    needed = {"company", "ebitda_margin", "roa"}
                    if needed.issubset(sdf.columns):
                        sdf = sdf.dropna(subset=["ebitda_margin", "roa"])
                        is_company = sdf["company"] == company_name
                        fig2 = go.Figure()
                        # Peer dots
                        peers_only = sdf[~is_company]
                        fig2.add_trace(go.Scatter(
                            x=peers_only["ebitda_margin"],
                            y=peers_only["roa"],
                            mode="markers+text",
                            text=peers_only["company"],
                            textposition="top center",
                            textfont=dict(size=9, color="#555"),
                            marker=dict(size=10, color="#CADCFC",
                                        line=dict(width=1, color="#1E2761")),
                            name="Peers",
                        ))
                        # Company dot (highlighted)
                        co_row = sdf[is_company]
                        if not co_row.empty:
                            fig2.add_trace(go.Scatter(
                                x=co_row["ebitda_margin"],
                                y=co_row["roa"],
                                mode="markers+text",
                                text=co_row["company"],
                                textposition="top center",
                                textfont=dict(size=10, color="#E8453C", family="Inter"),
                                marker=dict(size=16, color="#E8453C",
                                            symbol="star",
                                            line=dict(width=1.5, color="white")),
                                name=company_name,
                            ))
                        # Median crosshairs
                        fig2.add_vline(
                            x=benchmarks["ebitda_margin"]["peer_median"],
                            line_dash="dot", line_color="rgba(0,0,0,0.25)",
                        )
                        fig2.add_hline(
                            y=benchmarks["roa"]["peer_median"],
                            line_dash="dot", line_color="rgba(0,0,0,0.25)",
                        )
                        fig2.update_layout(
                            xaxis_title="EBITDA Margin (%)",
                            yaxis_title="Return on Assets (%)",
                            height=420,
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=50, r=40, t=30, b=50),
                            font=dict(family="Inter, sans-serif", size=12),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02),
                        )
                        st.plotly_chart(fig2, use_container_width=True)

                # ── Scope 1+2 emissions bar ───────────────────────────────
                if (peer_table and "scope1_2_emissions" in benchmarks and _PLOTLY):
                    section_header(
                        "Scope 1+2 Emissions vs Peers",
                        "Lower is better. Values in ktCO₂e.",
                    )
                    edf = pd.DataFrame(peer_table)
                    if "scope1_2_emissions" in edf.columns and "company" in edf.columns:
                        edf = edf.dropna(subset=["scope1_2_emissions"]).sort_values(
                            "scope1_2_emissions", ascending=False
                        )
                        ecolors = [
                            "#E8453C" if c == company_name else "#CADCFC"
                            for c in edf["company"]
                        ]
                        fig3 = go.Figure(go.Bar(
                            x=edf["scope1_2_emissions"],
                            y=edf["company"],
                            orientation="h",
                            marker_color=ecolors,
                            text=[f"{v:,.0f}" for v in edf["scope1_2_emissions"]],
                            textposition="outside",
                        ))
                        fig3.add_vline(
                            x=benchmarks["scope1_2_emissions"]["peer_median"],
                            line_dash="dash", line_color="gray",
                            annotation_text="Sector median",
                            annotation_position="top right",
                        )
                        fig3.update_layout(
                            xaxis_title="Scope 1+2 Emissions (ktCO₂e)",
                            yaxis_title=None,
                            height=max(350, peer_count * 30),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(l=40, r=80, t=30, b=40),
                            font=dict(family="Inter, sans-serif", size=12),
                            showlegend=False,
                        )
                        st.plotly_chart(fig3, use_container_width=True)

                # ── Rankings table ────────────────────────────────────────
                rankings = peer.get("rankings", [])
                if rankings:
                    section_header(
                        "Metric Rankings",
                        "How your company positions on each benchmarked dimension.",
                    )
                    safe_dataframe(
                        pd.DataFrame(rankings),
                        use_container_width=True,
                        hide_index=True,
                    )

                # ── Full peer data table ───────────────────────────────────
                with st.expander("Full peer dataset", expanded=False):
                    if peer_table:
                        safe_dataframe(
                            pd.DataFrame(peer_table),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.caption("No peer data available.")

                if not _PLOTLY:
                    st.caption(
                        "Install `plotly` to enable bar and scatter charts in this tab."
                    )

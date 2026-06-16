"""ESG ROI Agent — dual ROI, value channels, investment quality, and peer benchmarking."""
import pandas as pd
import streamlit as st

from core.orchestrator import Orchestrator
from utils.streamlit_compat import safe_dataframe
from utils.ui import (
    hero, section_header, kpi_card, iqs_gauge, grade_pill, inject_global_css,
    page_agent_header_live,
    pwc_header,
)
from utils.auth import require_login, sidebar_auth_widget
from utils.pipeline_refresh import refresh_real_data, data_freshness_caption
from utils.session import get_session_connection_manager

try:
    import plotly.graph_objects as go
    import plotly.express as px
    _PLOTLY = True
except ImportError:
    _PLOTLY = False


st.set_page_config(page_title="ESG ROI Agent | ESG Intelligence Hub", page_icon="⭐", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to explore the ESG ROI dashboard.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="roi_agent",
    agent_icon="⭐",
)

get_session_connection_manager()

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

# Auto-rehydrate the user's last ROI result so reloading the page
# doesn't show a blank dashboard. Only on the first render of this
# session (guarded) so we don't trample a fresh single-agent rerun.
if (st.session_state.get("roi_results") is None
        and not st.session_state.get("_roi_autoloaded")):
    _autoload_user = ((st.session_state.get("user") or {}).get("username") or "").strip()
    if _autoload_user:
        try:
            from utils.run_store import get_run_store as _get_run_store
            _snap = _get_run_store().latest_run(_autoload_user)
        except Exception:
            _snap = None
        if _snap and isinstance(_snap.get("results"), dict):
            _roi_block = _snap["results"].get("roi_agent")
            if isinstance(_roi_block, dict) and "error" not in _roi_block:
                st.session_state.roi_results = _roi_block
            # Also seed ESG Command Center's bag in case the user navigates
            # there next — keeps both pages consistent.
            st.session_state.pipeline_results = _snap["results"]
    st.session_state["_roi_autoloaded"] = True

run_roi = st.button("Run ESG ROI Analysis", type="primary", use_container_width=True)

# Banner: show registered data sources so the user knows what feeds the analysis
_cm = st.session_state.get("conn_manager")
if _cm and _cm.has_sources():
    _srcs = _cm.list_sources()
    _labels = ", ".join(f"**{s['display_name']}** → `{s['target_schema']}`" for s in _srcs)
    st.success(
        f"📂 **{len(_srcs)} real data source(s) registered** — {_labels}. "
        "These will be ingested before the ROI analysis runs.",
        icon="✅",
    )

data_freshness_caption()

if run_roi:
    with st.spinner("Refreshing data from registered sources..."):
        refresh_real_data()
    with st.spinner("Running ESG ROI analysis..."):
        results = orch.run_single_agent("roi_agent")
        st.session_state.roi_results = results
        # Keep the ESG Command Center's pipeline_results bag in sync so
        # the featured card on that page picks up this single-agent run
        # without a full pipeline rerun. The agent itself publishes to
        # state_manager["roi_results"], which the card reads first; this
        # session_state mirror covers the auto-rehydrate path.
        if isinstance(results, dict) and "error" not in results:
            _pr = st.session_state.get("pipeline_results")
            if not isinstance(_pr, dict):
                _pr = {}
            _pr["roi_agent"] = results
            st.session_state.pipeline_results = _pr

results = st.session_state.get("roi_results")

if results:
    if "error" in results:
        st.error(results["error"])
    else:
        tab_company, tab_peers, tab_whatif, tab_iqs = st.tabs([
            "📊 Your Company",
            "🏢 Peer Benchmarking",
            "🔮 What-if Simulator",
            "📈 Improve IQS",
        ])

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
                # ── Palette constants ─────────────────────────────────────
                _C_YOU     = "#E8453C"             # your company — red
                _C_PEERS   = "#4472C4"             # peer companies — blue
                _C_MEDIAN  = "#F59E0B"             # sector median line — amber
                _C_GRID    = "rgba(0,0,0,0.07)"
                _LAYOUT    = dict(
                    plot_bgcolor  = "rgba(0,0,0,0)",
                    paper_bgcolor = "rgba(0,0,0,0)",
                    font          = dict(family="Inter, sans-serif", size=12),
                )

                # ── Header strip ──────────────────────────────────────────
                peer_count   = peer.get("peer_count", 0)
                sectors      = peer.get("sectors_covered", [])
                source_label = {
                    "peer_metrics":   "pre-calculated ratios",
                    "peer_benchmark": "5-year averages",
                    "peer_esg":       "raw ESG inputs",
                }.get(peer.get("peer_source", ""), "peer data")

                section_header(
                    "Peer Benchmarking",
                    f"{peer_count} companies · "
                    f"{', '.join(sectors) if sectors else 'All sectors'} · "
                    f"Source: {source_label}",
                )

                benchmarks   = peer.get("benchmarks", {})
                company_name = peer.get("company_name", "Your Company")
                peer_table   = peer.get("peer_table", [])

                # ── KPI comparison cards (st.metric for delta colouring) ──
                if benchmarks:
                    bm_cols = st.columns(len(benchmarks))
                    for col, (mk, b) in zip(bm_cols, benchmarks.items()):
                        with col:
                            cv     = b.get("company_value", 0) or 0
                            gap    = b.get("gap_vs_median", 0) or 0
                            pct    = b.get("percentile")
                            unit   = b.get("unit", "")
                            better = b.get("higher_is_better", True)

                            sign      = "+" if gap > 0 else ""
                            delta_str = (
                                f"{sign}{gap:.2f}{unit} vs median"
                                if gap != 0 else "At sector median"
                            )
                            if pct is not None:
                                delta_str += f" · {pct}th pct"

                            # green when the gap is genuinely beneficial
                            delta_color = (
                                "normal"  if better else "inverse"
                            )
                            st.metric(
                                label       = b["label"],
                                value       = f"{cv:g}{unit}",
                                delta       = delta_str,
                                delta_color = delta_color,
                            )

                            # Industry-standard anchor — shown under the
                            # peer-comparison card so users see both the
                            # peer-relative ("am I beating my cohort?")
                            # and absolute ("is my cohort actually good?")
                            # signals in one glance.
                            std = b.get("industry_standard")
                            if std:
                                std_val = std.get("value", 0)
                                std_unit = std.get("unit", unit)
                                st.caption(
                                    f"🎯 Industry standard: **{std_val:g}{std_unit}**  \n"
                                    f"{std.get('position', '')}"
                                )
                                source = std.get("source")
                                if source:
                                    st.caption(f"_Source: {source}_")

                # Industry-standard details expander — keeps the KPI cards
                # uncluttered but surfaces interpretation notes for users
                # who want to understand *why* each benchmark is set where
                # it is.
                _std_rows = [
                    (mk, b) for mk, b in benchmarks.items()
                    if b.get("industry_standard")
                ]
                if _std_rows:
                    with st.expander("📚 Industry standard context"):
                        st.caption(
                            "Industry standards below are fixed benchmarks "
                            "(SBTi pathways, CRISIL medians, etc.) that "
                            "stay constant regardless of which peers you "
                            "uploaded. They complement the peer median by "
                            "anchoring the comparison to absolute targets."
                        )
                        for mk, b in _std_rows:
                            std = b["industry_standard"]
                            st.markdown(
                                f"**{b['label']}** — Standard: "
                                f"{std['value']:g}{std.get('unit','')} "
                                f"· Company: {b['company_value']:g}{b.get('unit','')}"
                            )
                            if std.get("interpretation"):
                                st.caption(std["interpretation"])
                            if std.get("source"):
                                st.caption(f"Source: {std['source']}")
                            st.markdown("")

                st.divider()

                if not _PLOTLY:
                    st.info("Install `plotly` to enable benchmark charts.")
                elif not peer_table:
                    st.caption("No peer data available for charts.")
                else:
                    base_df = pd.DataFrame(peer_table)

                    # ── Helper: build bar-chart DataFrame, inject company ─
                    def _bar_df(metric_col: str, company_val: float,
                                ascending: bool = True):
                        """
                        Return (chart_df, company_display_name).
                        Adds a "(You)" row for the user's company when it is
                        not already present in the uploaded peer data.
                        """
                        if metric_col not in base_df.columns:
                            return pd.DataFrame(), company_name
                        cdf = (base_df[["company", metric_col]]
                               .dropna(subset=[metric_col])
                               .copy())
                        # Normalise company column name
                        if "Company" in cdf.columns and "company" not in cdf.columns:
                            cdf = cdf.rename(columns={"Company": "company"})

                        you_label = f"{company_name} (You)"
                        if company_val and company_name not in cdf["company"].values:
                            cdf = pd.concat(
                                [cdf, pd.DataFrame([{"company": you_label,
                                                     metric_col: company_val}])],
                                ignore_index=True,
                            )
                        else:
                            you_label = company_name

                        cdf = cdf.sort_values(metric_col, ascending=ascending)
                        return cdf, you_label

                    def _bar_colors(companies, you_label):
                        return [_C_YOU if c == you_label else _C_PEERS
                                for c in companies]

                    def _hbar_layout(n_bars: int, x_title: str,
                                     x_max: float) -> dict:
                        return dict(
                            **_LAYOUT,
                            xaxis=dict(
                                title     = x_title,
                                showgrid  = True,
                                gridcolor = _C_GRID,
                                range     = [0, x_max],
                                fixedrange= True,
                            ),
                            yaxis=dict(title=None, automargin=True,
                                       fixedrange=True),
                            height  = max(400, n_bars * 40 + 80),
                            margin  = dict(l=0, r=20, t=20, b=40),
                            bargap  = 0.30,
                            showlegend=False,
                        )

                    # ── CHART 1: ESG Score ────────────────────────────────
                    if "esg_score" in benchmarks and "esg_score" in base_df.columns:
                        section_header(
                            "ESG Score vs Peers",
                            f"Your company highlighted in red · "
                            f"Sector median: {benchmarks['esg_score']['peer_median']:.1f}",
                        )
                        cv1     = benchmarks["esg_score"]["company_value"] or 0
                        cdf1, you1 = _bar_df("esg_score", cv1, ascending=True)
                        if not cdf1.empty:
                            colors1 = _bar_colors(cdf1["company"], you1)
                            x_max1  = cdf1["esg_score"].max() * 1.20
                            fig1 = go.Figure(go.Bar(
                                x            = cdf1["esg_score"],
                                y            = cdf1["company"],
                                orientation  = "h",
                                marker       = dict(color=colors1, line_width=0),
                                text         = [f"{v:.1f}" for v in cdf1["esg_score"]],
                                textposition = "outside",
                                textfont     = dict(size=11),
                                hovertemplate= (
                                    "<b>%{y}</b><br>"
                                    "ESG Score: <b>%{x:.1f}</b> / 100"
                                    "<extra></extra>"
                                ),
                            ))
                            med1 = benchmarks["esg_score"]["peer_median"]
                            fig1.add_vline(
                                x=med1, line_dash="dash",
                                line_color=_C_MEDIAN, line_width=2,
                                annotation_text=f"Median {med1:.1f}",
                                annotation_font=dict(color=_C_MEDIAN, size=11),
                                annotation_position="top right",
                            )
                            fig1.update_layout(
                                **_hbar_layout(len(cdf1), "ESG Score (/ 100)", x_max1)
                            )
                            st.plotly_chart(fig1, use_container_width=True)

                    # ── CHART 2: Profitability scatter ────────────────────
                    if ("ebitda_margin" in benchmarks and "roa" in benchmarks
                            and {"ebitda_margin", "roa"}.issubset(base_df.columns)):
                        section_header(
                            "Profitability Landscape",
                            "EBITDA Margin vs Return on Assets — "
                            "dashed lines show sector medians.",
                        )
                        sdf = base_df.dropna(subset=["ebitda_margin", "roa"]).copy()

                        # Peers: hover-only labels (no always-on text — avoids clutter)
                        peers_s = sdf[sdf["company"] != company_name]
                        fig2    = go.Figure()
                        fig2.add_trace(go.Scatter(
                            x             = peers_s["ebitda_margin"],
                            y             = peers_s["roa"],
                            mode          = "markers",
                            marker        = dict(
                                size   = 12,
                                color  = _C_PEERS,
                                opacity= 0.85,
                                line   = dict(width=1, color="white"),
                            ),
                            name          = "Peers",
                            customdata    = peers_s["company"],
                            hovertemplate = (
                                "<b>%{customdata}</b><br>"
                                "EBITDA Margin: %{x:.1f}%<br>"
                                "ROA: %{y:.1f}%"
                                "<extra></extra>"
                            ),
                        ))

                        # Your company — always from benchmarks so it always shows
                        co_em  = benchmarks["ebitda_margin"]["company_value"] or 0
                        co_roa = benchmarks["roa"]["company_value"] or 0
                        fig2.add_trace(go.Scatter(
                            x             = [co_em],
                            y             = [co_roa],
                            mode          = "markers+text",
                            marker        = dict(
                                size   = 20,
                                color  = _C_YOU,
                                symbol = "star",
                                line   = dict(width=1.5, color="white"),
                            ),
                            text          = [f"  {company_name}"],
                            textposition  = "middle right",
                            textfont      = dict(size=11, color=_C_YOU),
                            name          = company_name,
                            hovertemplate = (
                                f"<b>{company_name}</b><br>"
                                "EBITDA Margin: %{x:.1f}%<br>"
                                "ROA: %{y:.1f}%"
                                "<extra></extra>"
                            ),
                        ))

                        # Median crosshairs
                        med_em  = benchmarks["ebitda_margin"]["peer_median"]
                        med_roa = benchmarks["roa"]["peer_median"]
                        fig2.add_vline(
                            x=med_em, line_dash="dot",
                            line_color="rgba(0,0,0,0.30)", line_width=1.5,
                            annotation_text=f"Median {med_em:.1f}%",
                            annotation_font=dict(size=10, color="#666"),
                            annotation_position="top left",
                        )
                        fig2.add_hline(
                            y=med_roa, line_dash="dot",
                            line_color="rgba(0,0,0,0.30)", line_width=1.5,
                            annotation_text=f"Median {med_roa:.1f}%",
                            annotation_font=dict(size=10, color="#666"),
                            annotation_position="bottom right",
                        )
                        fig2.update_layout(
                            **_LAYOUT,
                            xaxis=dict(
                                title="EBITDA Margin (%)", showgrid=True,
                                gridcolor=_C_GRID, zeroline=False,
                            ),
                            yaxis=dict(
                                title="Return on Assets (%)", showgrid=True,
                                gridcolor=_C_GRID, zeroline=False,
                            ),
                            height=440,
                            margin=dict(l=50, r=120, t=20, b=50),
                            legend=dict(
                                orientation="h", yanchor="bottom",
                                y=1.02, xanchor="right", x=1,
                            ),
                        )
                        st.plotly_chart(fig2, use_container_width=True)

                    # ── CHART 3: Scope 1+2 Emissions ─────────────────────
                    if ("scope1_2_emissions" in benchmarks
                            and "scope1_2_emissions" in base_df.columns):
                        section_header(
                            "Scope 1+2 Emissions vs Peers",
                            "Lower is better · Values in ktCO₂e · "
                            f"Sector median: {benchmarks['scope1_2_emissions']['peer_median']:,.0f}",
                        )
                        cv3     = benchmarks["scope1_2_emissions"]["company_value"] or 0
                        # Sort highest first (worst emitters on top)
                        cdf3, you3 = _bar_df("scope1_2_emissions", cv3, ascending=False)
                        if not cdf3.empty:
                            colors3 = _bar_colors(cdf3["company"], you3)
                            x_max3  = cdf3["scope1_2_emissions"].max() * 1.20
                            fig3 = go.Figure(go.Bar(
                                x            = cdf3["scope1_2_emissions"],
                                y            = cdf3["company"],
                                orientation  = "h",
                                marker       = dict(color=colors3, line_width=0),
                                text         = [f"{v:,.0f}" for v in cdf3["scope1_2_emissions"]],
                                textposition = "outside",
                                textfont     = dict(size=11),
                                hovertemplate= (
                                    "<b>%{y}</b><br>"
                                    "Scope 1+2: <b>%{x:,.0f}</b> ktCO₂e"
                                    "<extra></extra>"
                                ),
                            ))
                            med3 = benchmarks["scope1_2_emissions"]["peer_median"]
                            fig3.add_vline(
                                x=med3, line_dash="dash",
                                line_color=_C_MEDIAN, line_width=2,
                                annotation_text=f"Median {med3:,.0f}",
                                annotation_font=dict(color=_C_MEDIAN, size=11),
                                annotation_position="top right",
                            )
                            fig3.update_layout(
                                **_hbar_layout(len(cdf3),
                                               "Scope 1+2 Emissions (ktCO₂e)", x_max3)
                            )
                            st.plotly_chart(fig3, use_container_width=True)

                # ── Rankings table ────────────────────────────────────────
                rankings = peer.get("rankings", [])
                if rankings:
                    section_header(
                        "Rankings Summary",
                        "Where your company stands on each benchmarked dimension.",
                    )
                    safe_dataframe(
                        pd.DataFrame(rankings),
                        use_container_width=True,
                        hide_index=True,
                    )

                # ── Full peer data table ───────────────────────────────────
                with st.expander("📋 Full peer dataset", expanded=False):
                    if peer_table:
                        safe_dataframe(
                            pd.DataFrame(peer_table),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.caption("No peer data available.")

        # ══════════════════════════════════════════════════════════════════════
        # TAB 3 — WHAT-IF SIMULATOR
        # Pure-functional re-projection: no agent re-runs. Sliders nudge
        # the cached ROI snapshot through ``utils.whatif.simulate`` and
        # we render the deltas next to the live numbers.
        # ══════════════════════════════════════════════════════════════════════
        with tab_whatif:
            from utils.whatif import WhatIfInputs, simulate

            section_header(
                "Scenario sliders",
                "Adjust the inputs and watch the J-curve, IQS, and NPV "
                "recompute live. The baseline run is unchanged.",
            )

            base_iqs = results.get("investment_quality_score", {}) or {}
            base_jc  = results.get("j_curve", {}) or {}
            base_fin = results.get("financial_roi", {}) or {}

            sl_a, sl_b = st.columns(2)
            with sl_a:
                carbon_uplift = st.slider(
                    "Carbon price uplift (%)",
                    min_value=-50, max_value=300, value=0, step=5,
                    help=("Bumps the carbon-tax-avoided line. Useful for "
                          "stress-testing CBAM, India CCTS, or SEC pricing scenarios."),
                )
                capex_uplift = st.slider(
                    "ESG capex change (%)",
                    min_value=-50, max_value=200, value=0, step=5,
                    help="Scales every quarter's ESG-linked capex.",
                )
            with sl_b:
                benefit_uplift = st.slider(
                    "Benefit realisation change (%)",
                    min_value=-50, max_value=200, value=0, step=5,
                    help=("Scales the per-quarter ESG benefit. Negative values "
                          "model 'savings come in slower than projected'."),
                )
                discount_rate = st.slider(
                    "Discount rate / hurdle (%)",
                    min_value=0.0, max_value=25.0,
                    value=float(results.get("kpi_engine", {})
                                .get("financial_summary", {})
                                .get("cost_of_capital_latest", 12) or 12),
                    step=0.5,
                    help="Annualised hurdle rate used for the NPV column.",
                )

            sim = simulate(results, WhatIfInputs(
                carbon_price_uplift_pct=float(carbon_uplift),
                capex_uplift_pct=float(capex_uplift),
                benefit_uplift_pct=float(benefit_uplift),
                discount_rate_pct=float(discount_rate),
            ))

            section_header(
                "Scenario vs baseline",
                "Three side-by-side reads: live IQS, projected IQS, the delta.",
            )
            r1, r2, r3, r4 = st.columns(4)
            with r1:
                kpi_card(
                    "Baseline IQS",
                    f"{base_iqs.get('score', 0)}",
                    f"Grade {base_iqs.get('grade', 'N/A')}",
                    key="whatif_base_iqs",
                )
            with r2:
                kpi_card(
                    "Scenario IQS",
                    f"{sim.iqs.get('score', 0)}",
                    f"Grade {sim.iqs.get('grade', 'N/A')}",
                    key="whatif_sim_iqs",
                )
            with r3:
                delta = sim.delta_iqs
                arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
                kpi_card(
                    "Δ IQS",
                    f"{arrow} {abs(delta)}",
                    "Scenario − Baseline",
                    key="whatif_delta_iqs",
                )
            with r4:
                breakeven_text = sim.j_curve.get("breakeven_quarter") or "Not reached"
                kpi_card(
                    "Scenario breakeven",
                    breakeven_text,
                    (f"Δ {sim.delta_breakeven_quarters:+d} quarters"
                     if sim.delta_breakeven_quarters is not None
                     else "vs baseline"),
                    key="whatif_break",
                )

            r5, r6, r7 = st.columns(3)
            with r5:
                kpi_card(
                    "Scenario savings",
                    f"INR {sim.cost_savings_total} Cr",
                    f"Baseline: INR {base_fin.get('cost_savings', {}).get('total', 0)} Cr",
                    key="whatif_savings",
                )
            with r6:
                kpi_card(
                    "Scenario NPV",
                    f"INR {sim.npv} Cr",
                    f"@ {discount_rate}% discount rate",
                    key="whatif_npv",
                )
            with r7:
                kpi_card(
                    "Scenario net position",
                    f"INR {sim.j_curve.get('net_position', 0)} Cr",
                    f"Baseline: INR {base_jc.get('net_position', 0)} Cr",
                    key="whatif_net",
                )

            section_header(
                "Quarterly trajectory under scenario",
                "Same shape as the baseline J-curve, recomputed under the slider settings.",
            )
            scenario_quarters = pd.DataFrame(sim.j_curve.get("quarters", []))
            if not scenario_quarters.empty:
                if _PLOTLY:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=scenario_quarters["period"],
                        y=scenario_quarters["cumulative_cost"],
                        mode="lines+markers", name="Cumulative cost",
                        line=dict(color="#D04A02", width=3),
                    ))
                    fig.add_trace(go.Scatter(
                        x=scenario_quarters["period"],
                        y=scenario_quarters["cumulative_benefit"],
                        mode="lines+markers", name="Cumulative benefit",
                        line=dict(color="#22C55E", width=3),
                    ))
                    fig.add_trace(go.Scatter(
                        x=scenario_quarters["period"],
                        y=scenario_quarters["net_position"],
                        mode="lines+markers", name="Net position",
                        line=dict(color="#3B82F6", width=2, dash="dot"),
                    ))
                    fig.update_layout(
                        height=380, margin=dict(l=10, r=10, t=20, b=10),
                        legend=dict(orientation="h", yanchor="bottom",
                                    y=1.02, xanchor="right", x=1),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                safe_dataframe(scenario_quarters,
                                use_container_width=True, hide_index=True)
            else:
                st.info("No quarterly data in the baseline run — re-run the pipeline first.")

            with st.expander("ℹ️ How the simulator works"):
                st.markdown(
                    """
- The slider values are applied as multipliers / additive lifts on the
  cached ROI run; **no agents are re-executed**.
- The IQS is recomputed using the same weight vector the ROI Agent
  uses, so a slider-driven score is directly comparable to a real run.
- NPV uses a per-quarter discount rate of `rate / 4`. Setting the rate
  to 0 returns the undiscounted sum.
- Breakeven follows the same "must go underwater first" rule as the
  agent — pure-positive trajectories return *Not reached*.
                    """
                )

        # ══════════════════════════════════════════════════════════════════════
        # TAB 4 — IMPROVE IQS
        # Diagnoses each IQS component, ranks improvement opportunities by
        # addressable lift, and surfaces a concrete action plan per component.
        # ══════════════════════════════════════════════════════════════════════
        with tab_iqs:
            improvement = results.get("iqs_improvement", {})

            if not improvement:
                st.info("Re-run the ESG ROI Analysis to generate the IQS improvement plan.")
            else:
                current_score = improvement.get("current_score", 0)
                current_grade = improvement.get("current_grade", "N/A")
                projected_score = improvement.get("projected_score", 0)
                projected_grade = improvement.get("projected_grade", "N/A")
                total_lift = improvement.get("total_addressable_lift", 0)

                # ── Header strip ──────────────────────────────────────────
                section_header(
                    "IQS Improvement Playbook",
                    "Ranked improvement opportunities across all five IQS components.",
                )

                h1, h2, h3, h4 = st.columns(4)
                with h1:
                    kpi_card(
                        "Current IQS",
                        f"{current_score}/100",
                        f"Grade {current_grade}",
                        key="iqs_imp_current",
                    )
                with h2:
                    kpi_card(
                        "Projected IQS",
                        f"{projected_score}/100",
                        f"Grade {projected_grade} (if top actions completed)",
                        key="iqs_imp_projected",
                    )
                with h3:
                    kpi_card(
                        "Total Addressable Lift",
                        f"+{total_lift} pts",
                        "Across all 5 components",
                        key="iqs_imp_lift",
                    )
                with h4:
                    grade_delta = (
                        f"{current_grade} → {projected_grade}"
                        if current_grade != projected_grade
                        else "Grade unchanged"
                    )
                    kpi_card(
                        "Grade Trajectory",
                        grade_delta,
                        "Achievable with focused execution",
                        key="iqs_imp_grade",
                    )

                # ── AI narrative ──────────────────────────────────────────
                narrative_text = improvement.get("narrative", "")
                if narrative_text:
                    st.markdown(f"> {narrative_text}")

                st.divider()

                # ── Component plans ───────────────────────────────────────
                section_header(
                    "Component-by-Component Action Plan",
                    "Sorted by maximum IQS lift — tackle the top of the list first.",
                )

                component_plans = improvement.get("component_plans", [])

                # Summary table — one row per component
                if component_plans:
                    summary_rows = []
                    for p in component_plans:
                        status_icon = (
                            "🟢" if p["status"] == "Strong"
                            else ("🟡" if p["status"] == "Moderate" else "🔴")
                        )
                        summary_rows.append({
                            "Component": p["component"],
                            "Score": f"{p['current_score']}/100",
                            "Status": f"{status_icon} {p['status']}",
                            "Gap to 100": p["gap_to_100"],
                            "Max IQS Lift": f"+{p['max_iqs_lift']} pts",
                            "Top Action": p["top_action"],
                        })
                    safe_dataframe(
                        pd.DataFrame(summary_rows),
                        use_container_width=True,
                        hide_index=True,
                    )

                st.divider()

                # ── Detailed expandable cards per component ───────────────
                section_header(
                    "Detailed Action Cards",
                    "Expand each component to see the full action list with effort and expected lift.",
                )

                for plan in component_plans:
                    status_icon = (
                        "🟢" if plan["status"] == "Strong"
                        else ("🟡" if plan["status"] == "Moderate" else "🔴")
                    )
                    label = (
                        f"{status_icon} **{plan['component']}** — "
                        f"Score {plan['current_score']}/100 · "
                        f"Max lift +{plan['max_iqs_lift']} pts"
                    )
                    with st.expander(label, expanded=(plan == component_plans[0])):
                        sc1, sc2, sc3 = st.columns(3)
                        with sc1:
                            st.metric("Current Score", f"{plan['current_score']}/100")
                        with sc2:
                            st.metric("Gap to Perfect", f"{plan['gap_to_100']} pts")
                        with sc3:
                            st.metric("Max IQS Lift", f"+{plan['max_iqs_lift']} pts")

                        st.markdown("**Actions to improve this component:**")
                        for i, action in enumerate(plan.get("actions", []), 1):
                            effort_color = (
                                "🟢" if action["effort"] == "Low"
                                else ("🟡" if action["effort"] == "Medium" else "🔴")
                            )
                            st.markdown(
                                f"**{i}. {action['action']}**  \n"
                                f"Effort: {effort_color} {action['effort']} · "
                                f"Expected lift: `{action['expected_lift']}` · "
                                f"Owner: *{action['owner']}*"
                            )

                # ── Weight breakdown reminder ─────────────────────────────
                with st.expander("ℹ️ How IQS is calculated"):
                    st.markdown(
                        """
The Investment Quality Score (0–100) is a weighted composite of five components:

| Component | Weight | What drives it |
|---|---|---|
| Financial ROI | 25% | ROI % on ESG capex, emission savings, energy cost reduction |
| Channel Performance | 25% | Average score across Growth, Cost, Risk, Human Capital, Capital Efficiency channels |
| Strategic Value | 20% | Cost of capital reduction + brand premium score |
| ESG Momentum | 15% | ESG CapEx CAGR + Revenue CAGR |
| Risk Reduction | 15% | Risk channel score from KPI engine |

**Grade thresholds:** A+ (90+) · A (80+) · B+ (70+) · B (60+) · C (50+) · D (<50)

The "Max IQS Lift" per component = gap-to-100 × component weight.
Realistically, expect to capture ~60% of the addressable lift — the projected score uses this factor.
                        """
                    )

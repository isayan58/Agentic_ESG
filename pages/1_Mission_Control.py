"""Mission Control — Full pipeline overview with business impact, pipeline visualization, and transformation view."""
import pandas as pd
import streamlit as st
from core.orchestrator import Orchestrator
from config import AGENT_CONFIG
from utils.charts import (
    pipeline_flow_diagram, business_impact_gauges,
    before_after_comparison, enterprise_stack_layers, tier_comparison_chart,
    chart_unavailable_message,
)
from utils.streamlit_compat import safe_dataframe
from utils.monitoring import monitoring_engine
from utils.ui import (
    hero, section_header, kpi_card, agent_card, pipeline_chips,
    badge, grade_pill, inject_global_css, pwc_header,
)
from utils.auth import require_login, sidebar_auth_widget
from utils.pipeline_refresh import stamp_refresh_from_pipeline
from utils.session import get_session_connection_manager

st.set_page_config(page_title="Mission Control | ESG CoPilot", page_icon="🎛️", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to run the 9-agent pipeline and view Mission Control.")
# Hydrate (or rebuild) this user's persistent ConnectionManager as early
# as possible so the Run buttons below see sources the user registered
# in a previous session.
get_session_connection_manager()

hero(
    title="Mission Control",
    emoji="🎛️",
    subtitle=(
        "Orchestrate all 9 agents — the command center for autonomous ESG intelligence. "
        "Run the full pipeline, monitor agent health in real time, and drill into the "
        "business lens behind every metric."
    ),
    chips=[
        "9 Agents · Orchestrated",
        "Shared-state pub/sub",
        "BRSR · CSRD · GRI · SASB",
        "Always-on monitoring",
    ],
)

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()
if "pipeline_results" not in st.session_state:
    st.session_state.pipeline_results = None

orch = st.session_state.orchestrator


def render_chart(fig):
    """Render Plotly charts when available, otherwise show a fallback note."""
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)


def signal_label(value, good_threshold, watch_threshold=None):
    """Return a simple status label for layman-friendly hypothesis tables."""
    if value is None:
        return "Not available"
    if watch_threshold is None:
        watch_threshold = good_threshold * 0.7
    if value >= good_threshold:
        return "Positive signal"
    if value >= watch_threshold:
        return "Mixed signal"
    return "Needs attention"


section_header("How to Read This Page",
               "Plain-English guide to the business lens, ROI, and hypothesis tracking.")
intro1, intro2, intro3 = st.columns(3)
with intro1:
    st.info("**Top line** means growth: revenue, brand strength, and market momentum.")
with intro2:
    st.info("**Bottom line** means profit impact: margins, savings, payback, and ROI.")
with intro3:
    st.info("**Hypotheses** mean business ideas being tested, like whether ESG reduces risk or improves returns.")

# ── Business Impact KPIs (Slide 12) ──
section_header("Proven Business Impact",
               "Slide-12 gauges rendered from live agent outputs.")
fig = business_impact_gauges()
render_chart(fig)

# ── Agent Fleet Status ──
section_header("Agent Fleet Status",
               "Every agent in the orchestrated pipeline with its most recent run.")
statuses = orch.get_agent_statuses()
pipeline_chips(statuses, AGENT_CONFIG)

cols = st.columns(4)
for i, (key, config) in enumerate(AGENT_CONFIG.items()):
    agent_status = statuses.get(key, {})
    last_run = agent_status.get("last_run") or "Never"
    with cols[i % 4]:
        agent_card(
            name=config["name"],
            icon=config["icon"],
            status=agent_status.get("status", "idle"),
            last_run=last_run,
            color=config["color"],
        )

# ── Real-data status banner ──
_cm = st.session_state.get("conn_manager")
if _cm and _cm.has_sources():
    _srcs = _cm.list_sources()
    _labels = ", ".join(f"**{s['display_name']}** → `{s['target_schema']}`" for s in _srcs)
    st.success(
        f"📂 **{len(_srcs)} real data source(s) registered** — {_labels}. "
        f"The pipeline will use your data instead of sample data.",
        icon="✅",
    )
else:
    st.info(
        "ℹ️ No real data sources registered. The pipeline will run on built-in sample data. "
        "Upload your own data on the **Data Collector** page first.",
        icon="💡",
    )

# ── Run Pipeline ──
goal = st.text_input(
    "Mission Goal",
    value="Prepare for a CSRD filing in Q3 by assessing ESG readiness, gap closure, and ROI.",
    help=(
        "Describe the business objective for this pipeline run. "
        "The planner will decide which agents to execute and when to stop."
    ),
    max_chars=240,
)
col1, col2 = st.columns([1, 3])
with col1:
    run_pipeline = st.button("🚀 Run Full Pipeline", type="primary", use_container_width=True)
with col2:
    st.caption("An LLM plans the next agent(s) to execute based on your goal and the available ESG intelligence modules.")

if run_pipeline:
    progress_bar = st.progress(0)
    status_text = st.empty()

    def progress_callback(agent_key, status, step, total):
        progress_bar.progress(step / total)
        config = AGENT_CONFIG.get(agent_key, {})
        name = config.get("name", agent_key)
        icon = config.get("icon", "🤖")
        if status == "running":
            status_text.info(f"{icon} Running {name}... ({step}/{total})")
        elif status == "completed":
            status_text.success(f"{icon} {name} completed ({step}/{total})")
        elif status == "error":
            status_text.error(f"{icon} {name} failed or was skipped ({step}/{total})")

    with st.spinner("Running full ESG pipeline..."):
        # Forward any real data sources the user registered on the Data
        # Collector page so uploaded files/connections flow into the pipeline.
        conn_mgr = st.session_state.get("conn_manager")
        dc_kwargs = (
            {"connection_manager": conn_mgr}
            if conn_mgr and conn_mgr.has_sources()
            else {}
        )
        results = orch.run_full_pipeline(
            progress_callback=progress_callback,
            data_collector_kwargs=dc_kwargs or None,
            user_goal=goal,
        )
        st.session_state.pipeline_results = results

        # Keep every agent page's "data freshness" caption in sync — the
        # full pipeline just re-ingested the registered sources via the
        # Data Collector, so stamp the refresh timestamp here.
        if conn_mgr and conn_mgr.has_sources():
            dc_res = results.get("data_collector", {}) if isinstance(results, dict) else {}
            stamp_refresh_from_pipeline(
                sources=len(conn_mgr.list_sources()),
                records=int(dc_res.get("total_records", 0)) if isinstance(dc_res, dict) else 0,
                errors=conn_mgr.source_errors() if hasattr(conn_mgr, "source_errors") else {},
            )

    progress_bar.progress(1.0)
    errored = [key for key, value in results.items() if isinstance(value, dict) and "error" in value]
    if errored:
        status_text.warning(f"⚠️ Pipeline completed with issues in: {', '.join(errored)}")
    else:
        status_text.success("✅ Full pipeline completed successfully!")

# ── Pipeline Results ──
if st.session_state.pipeline_results:
    results = st.session_state.pipeline_results
    st.markdown("---")

    tab_results, tab_business, tab_hypotheses, tab_pipeline, tab_transform, tab_stack, tab_tiers, tab_monitor = st.tabs([
        "Results Summary", "Business Lens", "Hypothesis Tracker", "Pipeline Flow",
        "Transformation", "Enterprise Stack", "Tier Config", "24/7 Monitoring",
    ])

    data_res = results.get("data_collector", {})
    carbon_res = results.get("carbon_accountant", {})
    risk_res = results.get("risk_predictor", {})
    audit_res = results.get("audit_agent", {})
    roi_res = results.get("roi_agent", {})
    reg_res = results.get("regulatory_tracker", {})
    action_res = results.get("action_agent", {})
    report_res = results.get("report_generator", {})
    kpi_res = roi_res.get("kpi_engine", {})
    fin_summary = kpi_res.get("financial_summary", {})
    cagr = kpi_res.get("cagr", {})
    volatility = kpi_res.get("volatility", {})

    with tab_results:
        section_header("Pipeline Results",
                       "Headline metrics from the latest full-pipeline run.")

        planning_steps = results.get("planning", [])
        if planning_steps:
            with st.expander("LLM Planning Audit Trail", expanded=False):
                for idx, step in enumerate(planning_steps, start=1):
                    agent_text = step.get("agent", "planner")
                    reason = step.get("reason", "No reason provided.")
                    st.markdown(f"**{idx}.** {agent_text} — {reason}")

        readiness = audit_res.get("readiness_score", {})
        iqs_card = roi_res.get("investment_quality_score", {})

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            kpi_card(
                "Total Records",
                f"{data_res.get('total_records', 0):,}",
                "Rows ingested and validated",
                key="kpi_records",
            )
        with k2:
            kpi_card(
                "Total Emissions",
                f"{carbon_res.get('total_emissions_current', 0):,.0f} tCO2e",
                f"{carbon_res.get('yoy_change_pct', 0)}% YoY",
                key="kpi_emissions",
            )
        with k3:
            kpi_card(
                "Risk Score",
                f"{risk_res.get('overall_risk_score', 0):.0f}/100",
                "Composite ESG risk",
                key="kpi_risk",
            )
        with k4:
            kpi_card(
                "Audit Readiness",
                f"{readiness.get('overall', 0):.0f}%",
                f"Grade: {readiness.get('grade', 'N/A')}",
                key="kpi_audit",
            )
        with k5:
            kpi_card(
                "Investment Quality",
                f"{iqs_card.get('score', 0):.0f}/100",
                f"Grade: {iqs_card.get('grade', 'N/A')}",
                key="kpi_iqs",
            )

        if iqs_card.get("grade"):
            st.markdown(
                f"Headline investment signal: {grade_pill(iqs_card.get('grade', 'N/A'))}",
                unsafe_allow_html=True,
            )

        # Carbon + Compliance charts
        col1, col2 = st.columns(2)
        with col1:
            if carbon_res and "scope_totals_current" in carbon_res:
                from utils.charts import emissions_donut
                fig = emissions_donut(carbon_res["scope_totals_current"])
                render_chart(fig)
        with col2:
            if reg_res and "framework_results" in reg_res:
                from utils.charts import compliance_radar
                scores = {fw: d["compliance_pct"] for fw, d in reg_res["framework_results"].items()}
                fig = compliance_radar(scores)
                render_chart(fig)

        # Actions summary
        if action_res and "actions" in action_res:
            st.markdown("### Top Action Items")
            actions_df = pd.DataFrame(action_res["actions"])
            cols = ["id", "action", "category", "priority", "duration_weeks", "impact"]
            available = [c for c in cols if c in actions_df.columns]
            if available:
                safe_dataframe(actions_df[available].head(5), use_container_width=True, hide_index=True)

        if roi_res and "financial_roi" in roi_res:
            section_header("ESG ROI Snapshot",
                           "Dual ROI and investment-quality signal from the ROI Agent.")
            fin_roi = roi_res.get("financial_roi", {})
            iqs = roi_res.get("investment_quality_score", {})
            col1, col2, col3 = st.columns(3)
            with col1:
                kpi_card("Financial ROI", f"{fin_roi.get('roi_pct', 0)}%",
                         "Payback-weighted return", key="roi_fin")
            with col2:
                kpi_card("Net Financial Benefit",
                         f"INR {fin_roi.get('net_financial_benefit', 0)} Cr",
                         "After ESG capex and friction", key="roi_net")
            with col3:
                kpi_card("IQS Grade", iqs.get("grade", "N/A"),
                         f"Score {iqs.get('score', 0)}/100", key="roi_grade")

    with tab_business:
        st.markdown("### Top Line vs Bottom Line")
        st.caption("This tab translates ESG into plain business language for revenue, profit, capital efficiency, and risk.")

        top1, top2, top3, top4 = st.columns(4)
        with top1:
            st.metric("Revenue (Top Line)", f"INR {fin_summary.get('revenue_current_fy', 0)} Cr",
                      f"{fin_summary.get('revenue_growth_pct', 0)}% growth")
            st.caption("Money coming in from the business.")
        with top2:
            st.metric("EBITDA Margin", f"{fin_summary.get('ebitda_margin_latest', 0)}%")
            st.caption("How much operating profit is left after running costs.")
        with top3:
            st.metric("Net ESG Benefit", f"INR {roi_res.get('financial_roi', {}).get('net_financial_benefit', 0)} Cr")
            st.caption("Estimated financial upside linked to ESG action.")
        with top4:
            st.metric("Cost of Capital", f"{fin_summary.get('cost_of_capital_latest', 0)}%")
            st.caption("How expensive it is for the company to raise money.")

        st.markdown("### In Plain English")
        st.markdown("""
        - If the **top line** improves, ESG may be helping the company win customers, pricing power, or brand trust.
        - If the **bottom line** improves, ESG may be reducing waste, energy spend, tax exposure, or operating friction.
        - If **cost of capital** falls and downside protection rises, ESG may be making the business safer and more investable.
        """)

        finance_rows = pd.DataFrame([
            {
                "Business lens": "Top line",
                "What it means": "Growth and demand",
                "Metric": "Revenue growth",
                "Current signal": f"{fin_summary.get('revenue_growth_pct', 0)}%",
            },
            {
                "Business lens": "Bottom line",
                "What it means": "Profit after costs",
                "Metric": "EBITDA margin",
                "Current signal": f"{fin_summary.get('ebitda_margin_latest', 0)}%",
            },
            {
                "Business lens": "Capital efficiency",
                "What it means": "Return on invested money",
                "Metric": "ROA / ROE",
                "Current signal": f"{fin_summary.get('roa_latest', 0)}% / {fin_summary.get('roe_latest', 0)}%",
            },
            {
                "Business lens": "Funding & risk",
                "What it means": "How safe and attractive the business looks",
                "Metric": "Cost of capital / downside protection",
                "Current signal": (
                    f"{fin_summary.get('cost_of_capital_latest', 0)}% / "
                    f"{risk_res.get('downside_protection', {}).get('score', 0)}/100"
                ),
            },
        ])
        safe_dataframe(finance_rows, use_container_width=True, hide_index=True)

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

    with tab_hypotheses:
        st.markdown("### Hypothesis Tracker")
        st.caption("This shows the business ideas the platform is testing, translated into simple language.")

        market_regime = risk_res.get("market_regime", {})
        downside = risk_res.get("downside_protection", {})
        j_curve = roi_res.get("j_curve", {})
        reporter_profile = reg_res.get("reporter_profile", {})
        iqs = roi_res.get("investment_quality_score", {})
        cost_savings = roi_res.get("financial_roi", {}).get("cost_savings", {}).get("total", 0)

        hypothesis_rows = pd.DataFrame([
            {
                "Hypothesis": "H1 Growth",
                "Plain English": "Better ESG can help the company grow sales and brand strength.",
                "Where to see it": "ROI Agent + Report Generator",
                "Current signal": signal_label(kpi_res.get("composite_esg_financial_score"), 65),
                "Evidence now": f"Revenue growth {fin_summary.get('revenue_growth_pct', 0)}%, growth channel {next((c.get('score', 0) for c in kpi_res.get('value_channels', []) if c.get('channel') == 'Growth'), 0)}/100",
            },
            {
                "Hypothesis": "H2 Profitability",
                "Plain English": "Cutting emissions and energy waste can improve profit.",
                "Where to see it": "Carbon Accountant + ROI Agent",
                "Current signal": signal_label(cost_savings, 1),
                "Evidence now": f"ESG-linked cost savings INR {cost_savings} Cr",
            },
            {
                "Hypothesis": "H3 Cyclical",
                "Plain English": "ESG may perform differently in stable, transition, or stress markets.",
                "Where to see it": "Risk Predictor",
                "Current signal": "Observed" if market_regime else "Not available",
                "Evidence now": f"Market regime: {market_regime.get('regime', 'N/A')}",
            },
            {
                "Hypothesis": "H4 Downside",
                "Plain English": "Stronger ESG can protect the business during shocks or downturns.",
                "Where to see it": "Risk Predictor",
                "Current signal": signal_label(downside.get('score'), 70, 55),
                "Evidence now": f"Downside protection score: {downside.get('score', 0)}/100",
            },
            {
                "Hypothesis": "H5 CapEx Quality",
                "Plain English": "ESG spending should create returns, not just cost.",
                "Where to see it": "ROI Agent + Action Agent",
                "Current signal": signal_label(iqs.get('score'), 70, 55),
                "Evidence now": f"Investment quality: {iqs.get('score', 0)}/100 ({iqs.get('grade', 'N/A')})",
            },
            {
                "Hypothesis": "H6 J-Curve",
                "Plain English": "ESG can hurt in the short term but pay back over time.",
                "Where to see it": "ROI Agent + Stakeholder Agent",
                "Current signal": "Breakeven reached" if j_curve.get("breakeven_quarter") else "Still in payback phase",
                "Evidence now": f"Breakeven: {j_curve.get('breakeven_quarter', 'Not yet reached')}",
            },
            {
                "Hypothesis": "H7 India Nuance",
                "Plain English": "Indian reporting context changes what matters, especially BRSR readiness.",
                "Where to see it": "Regulatory Tracker + Report Generator",
                "Current signal": "Context active" if reporter_profile else "Not available",
                "Evidence now": f"Reporter profile: {reporter_profile.get('classification', 'N/A')}",
            },
        ])
        safe_dataframe(hypothesis_rows, use_container_width=True, hide_index=True)

    with tab_pipeline:
        st.markdown("### Agent Pipeline — Data Flow Visualization")
        st.caption("Sankey diagram showing how data flows between all orchestrated agents")
        fig = pipeline_flow_diagram()
        render_chart(fig)
        st.markdown("""
        **Architecture in plain English**
        - The first layer collects and cleans data.
        - The middle layer turns that data into business signals like growth, profit, and risk.
        - The final layer turns those signals into reports, decisions, and stakeholder communication.
        """)

    with tab_transform:
        st.markdown("### Real-World Transformation — From Months to Weeks")
        fig = before_after_comparison()
        render_chart(fig)
        st.markdown("""
        **Key Outcomes:**
        - Reporting cycle slashed from **5 months** to **3 weeks**
        - Scope 3 coverage expanded from **60%** to **90%**
        - Data accuracy improved to **95%** through AI-driven validation
        - ESG rating trajectory: **BBB → A-** (measurable improvement)
        - Audit readiness score: **92%** (up from 55%)
        """)

    with tab_stack:
        st.markdown("### Enterprise Stack Architecture")
        st.caption("7-layer architecture designed for seamless tech stack integration and massive scale")
        fig = enterprise_stack_layers()
        render_chart(fig)
        st.markdown("""
        | Layer | Component | Technology |
        |-------|-----------|------------|
        | 7 | Command Center UI | Streamlit + Gradio dashboards |
        | 6 | 9 Orchestrated Agents | Python agent classes with HF AI |
        | 5 | Foundational AI Models | HuggingFace Inference API (Mistral, BART) |
        | 4 | Integration & Connectors | ERP, HR, IoT, API, SQL connectors |
        | 3 | Data Lake | Pandas/PySpark unified data layer |
        | 2 | Governance & Security | Audit trails, confidence scoring, access control |
        | 1 | Cloud Foundation | Scalable infrastructure |
        """)

    with tab_tiers:
        st.markdown("### Tailored for Every Enterprise")
        fig = tier_comparison_chart()
        render_chart(fig)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            #### Starter Tier
            *For emerging compliance needs*
            - 3 agents (Data, Carbon, Report)
            - 1 framework (BRSR)
            - 2 data sources
            - Monthly refresh
            """)
        with col2:
            st.markdown("""
            #### Professional Tier
            *For comprehensive corporate reporting*
            - 6 agents (+ Regulatory, Risk, Audit)
            - 3 frameworks (BRSR, GRI, SASB)
            - 4 data sources + connectors
            - Weekly refresh
            """)
        with col3:
            st.markdown("""
            #### Enterprise Tier
            *For fully autonomous global ESG intelligence*
            - All 9 agents
            - All 4+ frameworks (BRSR, CSRD, GRI, SASB)
            - 6+ sources + full connector suite
            - Real-time / 24/7 monitoring
            """)

        st.markdown("#### Pre-Configured Industry Solutions")
        industries = ["Manufacturing", "Finance", "Pharma", "Retail", "IT", "Government"]
        cols = st.columns(len(industries))
        for i, ind in enumerate(industries):
            with cols[i]:
                st.button(ind, disabled=True, use_container_width=True)

    with tab_monitor:
        st.markdown("### 24/7 Always-On Monitoring")
        monitor_data = monitoring_engine.get_dashboard_data()

        health_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(monitor_data["health"], "⚪")
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric("Status", f"{health_icon} {monitor_data['health'].capitalize()}")
        with k2:
            st.metric("Uptime", f"{monitor_data['uptime_days']} days")
        with k3:
            st.metric("Events Processed", f"{monitor_data['events_processed']:,}")
        with k4:
            st.metric("Active Streams", f"{monitor_data['active_streams']}/{monitor_data['total_streams']}")
        with k5:
            st.metric("Critical Alerts", monitor_data["critical_alerts"])

        # Alert timeline
        from utils.charts import monitoring_timeline
        fig = monitoring_timeline(monitor_data.get("alerts", []))
        render_chart(fig)

        # Active alerts
        st.markdown("#### Active Alerts")
        for alert in monitor_data.get("alerts", []):
            sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert["severity"], "⚪")
            ack = "✅" if alert.get("acknowledged") else "⬜"
            st.markdown(f"{sev_icon} `{alert['timestamp'][:16]}` **[{alert['type'].upper()}]** "
                        f"{alert['message']} {ack}")

        # Data streams
        st.markdown("#### Data Streams")
        for name, stream in monitor_data.get("streams", {}).items():
            s_icon = {"active": "🟢", "warning": "🟡"}.get(stream["status"], "⚪")
            st.markdown(f"{s_icon} **{name}** — {stream['frequency']} | Last: {(stream.get('last_reading') or 'N/A')[:16]}")

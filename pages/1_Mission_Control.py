"""Mission Control — Full pipeline overview with business impact, pipeline visualization, and transformation view."""
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

st.set_page_config(page_title="Mission Control | ESG CoPilot", page_icon="🎛️", layout="wide")
st.title("🎛️ Mission Control")
st.markdown("*Orchestrate all 9 agents — the command center for autonomous ESG intelligence*")
st.markdown("---")

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

# ── Business Impact KPIs (Slide 12) ──
st.markdown("### Proven Business Impact")
fig = business_impact_gauges()
render_chart(fig)

st.markdown("---")

# ── Agent Fleet Status ──
st.markdown("### Agent Fleet Status")
statuses = orch.get_agent_statuses()
cols = st.columns(4)
for i, (key, config) in enumerate(AGENT_CONFIG.items()):
    agent_status = statuses.get(key, {})
    status = agent_status.get("status", "idle")
    status_emoji = {"idle": "⚪", "running": "🔄", "completed": "✅", "error": "❌"}.get(status, "⚪")
    with cols[i % 4]:
        st.markdown(f"""
        <div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;
        padding:1rem;margin:0.5rem 0;border-left:4px solid {config['color']};">
            <strong>{config['icon']} {config['name']}</strong><br>
            <span>{status_emoji} {status.capitalize()}</span><br>
            <small>Last run: {agent_status.get('last_run', 'Never')[:16] if agent_status.get('last_run') else 'Never'}</small>
        </div>
        """, unsafe_allow_html=True)

st.markdown("---")

# ── Run Pipeline ──
col1, col2 = st.columns([1, 3])
with col1:
    run_pipeline = st.button("🚀 Run Full Pipeline", type="primary", use_container_width=True)
with col2:
    st.caption("Executes all agents in dependency order with shared state and dependency checks.")

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
        results = orch.run_full_pipeline(progress_callback=progress_callback)
        st.session_state.pipeline_results = results

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

    tab_results, tab_pipeline, tab_transform, tab_stack, tab_tiers, tab_monitor = st.tabs([
        "Results Summary", "Pipeline Flow", "Transformation",
        "Enterprise Stack", "Tier Config", "24/7 Monitoring",
    ])

    with tab_results:
        st.markdown("### Pipeline Results")
        data_res = results.get("data_collector", {})
        carbon_res = results.get("carbon_accountant", {})
        risk_res = results.get("risk_predictor", {})
        audit_res = results.get("audit_agent", {})
        roi_res = results.get("roi_agent", {})

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric("Total Records", f"{data_res.get('total_records', 0):,}")
        with k2:
            st.metric("Total Emissions", f"{carbon_res.get('total_emissions_current', 0):,.0f} tCO2e",
                       f"{carbon_res.get('yoy_change_pct', 0)}% YoY")
        with k3:
            st.metric("Risk Score", f"{risk_res.get('overall_risk_score', 0):.0f}/100")
        with k4:
            readiness = audit_res.get("readiness_score", {})
            st.metric("Audit Readiness", f"{readiness.get('overall', 0):.0f}%",
                       f"Grade: {readiness.get('grade', 'N/A')}")
        with k5:
            iqs = roi_res.get("investment_quality_score", {})
            st.metric("Investment Quality", f"{iqs.get('score', 0):.0f}/100",
                      f"Grade: {iqs.get('grade', 'N/A')}")

        # Carbon + Compliance charts
        col1, col2 = st.columns(2)
        with col1:
            if carbon_res and "scope_totals_current" in carbon_res:
                from utils.charts import emissions_donut
                fig = emissions_donut(carbon_res["scope_totals_current"])
                render_chart(fig)
        with col2:
            reg_res = results.get("regulatory_tracker", {})
            if reg_res and "framework_results" in reg_res:
                from utils.charts import compliance_radar
                scores = {fw: d["compliance_pct"] for fw, d in reg_res["framework_results"].items()}
                fig = compliance_radar(scores)
                render_chart(fig)

        # Actions summary
        action_res = results.get("action_agent", {})
        if action_res and "actions" in action_res:
            st.markdown("### Top Action Items")
            import pandas as pd
            actions_df = pd.DataFrame(action_res["actions"])
            cols = ["id", "action", "category", "priority", "duration_weeks", "impact"]
            available = [c for c in cols if c in actions_df.columns]
            if available:
                safe_dataframe(actions_df[available].head(5), use_container_width=True, hide_index=True)

        if roi_res and "financial_roi" in roi_res:
            st.markdown("### ESG ROI Snapshot")
            fin_roi = roi_res.get("financial_roi", {})
            iqs = roi_res.get("investment_quality_score", {})
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Financial ROI", f"{fin_roi.get('roi_pct', 0)}%")
            with col2:
                st.metric("Net Financial Benefit", f"INR {fin_roi.get('net_financial_benefit', 0)} Cr")
            with col3:
                st.metric("IQS Grade", iqs.get("grade", "N/A"))

    with tab_pipeline:
        st.markdown("### Agent Pipeline — Data Flow Visualization")
        st.caption("Sankey diagram showing how data flows between all orchestrated agents")
        fig = pipeline_flow_diagram()
        render_chart(fig)

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

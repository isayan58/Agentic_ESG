"""Mission Control — Full pipeline overview and execution."""
import streamlit as st
from core.orchestrator import Orchestrator
from config import AGENT_CONFIG

st.set_page_config(page_title="Mission Control | ESG CoPilot", page_icon="🎛️", layout="wide")
st.title("🎛️ Mission Control")
st.markdown("*Orchestrate all 8 agents from a single dashboard*")
st.markdown("---")

# Initialize orchestrator in session state
if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()
if "pipeline_results" not in st.session_state:
    st.session_state.pipeline_results = None

orch = st.session_state.orchestrator

# Agent status grid
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

# Run pipeline
col1, col2 = st.columns([1, 3])
with col1:
    run_pipeline = st.button("🚀 Run Full Pipeline", type="primary", use_container_width=True)
with col2:
    st.caption("Executes all 8 agents in dependency order. Takes a few seconds.")

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

    with st.spinner("Running full ESG pipeline..."):
        results = orch.run_full_pipeline(progress_callback=progress_callback)
        st.session_state.pipeline_results = results

    progress_bar.progress(1.0)
    status_text.success("✅ Full pipeline completed successfully!")

# Display results if available
if st.session_state.pipeline_results:
    results = st.session_state.pipeline_results
    st.markdown("---")
    st.markdown("### Pipeline Results Summary")

    # KPI row
    data_res = results.get("data_collector", {})
    carbon_res = results.get("carbon_accountant", {})
    risk_res = results.get("risk_predictor", {})
    audit_res = results.get("audit_agent", {})

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric(
            "Total Records Processed",
            f"{data_res.get('total_records', 0):,}",
            help="Records across all datasets",
        )
    with k2:
        st.metric(
            "Total Emissions",
            f"{carbon_res.get('total_emissions_current', 0):,.0f} tCO2e",
            f"{carbon_res.get('yoy_change_pct', 0)}% YoY",
        )
    with k3:
        risk_score = risk_res.get("overall_risk_score", 0)
        st.metric("Risk Score", f"{risk_score:.0f}/100")
    with k4:
        readiness = audit_res.get("readiness_score", {})
        st.metric(
            "Audit Readiness",
            f"{readiness.get('overall', 0):.0f}%",
            f"Grade: {readiness.get('grade', 'N/A')}",
        )

    # Detailed results in tabs
    tab1, tab2, tab3 = st.tabs(["Carbon Overview", "Compliance", "Actions"])

    with tab1:
        if carbon_res and "scope_totals_current" in carbon_res:
            from utils.charts import emissions_donut
            fig = emissions_donut(carbon_res["scope_totals_current"])
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"**AI Narrative:** {carbon_res.get('narrative', 'N/A')}")

    with tab2:
        reg_res = results.get("regulatory_tracker", {})
        if reg_res and "framework_results" in reg_res:
            from utils.charts import compliance_radar
            scores = {
                fw: data["compliance_pct"]
                for fw, data in reg_res["framework_results"].items()
            }
            fig = compliance_radar(scores)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f"**Gap Analysis:** {reg_res.get('gap_narrative', 'N/A')}")

    with tab3:
        action_res = results.get("action_agent", {})
        if action_res and "actions" in action_res:
            import pandas as pd
            actions_df = pd.DataFrame(action_res["actions"])
            display_cols = ["id", "action", "category", "priority", "duration_weeks", "impact"]
            available_cols = [c for c in display_cols if c in actions_df.columns]
            if available_cols:
                st.dataframe(actions_df[available_cols], use_container_width=True, hide_index=True)
            st.markdown(f"**Roadmap:** {action_res.get('roadmap_narrative', 'N/A')}")

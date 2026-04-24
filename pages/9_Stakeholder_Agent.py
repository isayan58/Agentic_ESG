"""Streamlit page for the Stakeholder Agent."""
import streamlit as st
from agents.stakeholder_agent import StakeholderAgent
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, page_agent_header_live, pwc_header
from utils.pipeline_refresh import data_freshness_caption

st.set_page_config(page_title="Stakeholder Agent | ESG Intelligence Hub", page_icon="👥", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Stakeholder Agent.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="stakeholder_agent",
    agent_icon="👥",
)

st.title("👥 Stakeholder Agent")
st.markdown("*Generates audience-tailored ESG communications*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "stakeholder_agent" not in st.session_state:
    st.session_state.stakeholder_agent = StakeholderAgent()
    st.session_state.stakeholder_results = None

agent = st.session_state.stakeholder_agent

st.info("For best results, run the full pipeline first to provide context from all agents.")

if st.button("🔄 Generate Communications", type="primary"):
    with st.spinner("Generating stakeholder communications..."):
        results = agent.run()
        st.session_state.stakeholder_results = results
    st.success("Communications generated!")

results = st.session_state.stakeholder_results
if results and "error" not in results:
    st.markdown("---")

    # Performance summary
    st.markdown("### ESG Performance Summary")
    st.markdown(results.get("performance_summary", ""))

    st.markdown("---")
    st.markdown("### Audience-Tailored Communications")

    communications = results.get("communications", {})

    # Audience selector
    audiences = list(communications.keys())
    audience_labels = {
        "investors": "💼 Investors & Shareholders",
        "regulators": "🏛️ Regulators & Compliance Bodies",
        "employees": "👩‍💻 Employees & Internal Teams",
        "public": "🌍 General Public & Media",
    }

    tabs = st.tabs([audience_labels.get(a, a) for a in audiences])

    for i, audience_key in enumerate(audiences):
        comm = communications[audience_key]
        with tabs[i]:
            # Subject line
            st.markdown(f"**Subject:** {comm.get('subject', '')}")
            st.markdown("---")

            # Message
            st.markdown("#### Message")
            st.markdown(comm.get("message", ""))

            # Key metrics for this audience
            st.markdown("---")
            st.markdown("#### Key Metrics")
            metrics = comm.get("key_metrics", [])
            if metrics:
                cols = st.columns(min(len(metrics), 4))
                for j, metric in enumerate(metrics):
                    with cols[j % len(cols)]:
                        st.metric(metric["label"], metric["value"])

            # Tone analysis
            st.markdown("---")
            tone = comm.get("tone_analysis", {})
            if tone:
                label = tone.get("label", "NEUTRAL")
                score = tone.get("score", 0.5)
                tone_colors = {"POSITIVE": "🟢", "NEGATIVE": "🔴", "NEUTRAL": "🟡"}
                st.markdown(
                    f"**Tone Analysis:** {tone_colors.get(label, '⚪')} "
                    f"{label} (confidence: {score:.0%})"
                )

            # Copy button
            full_text = f"Subject: {comm.get('subject', '')}\n\n{comm.get('message', '')}"
            st.download_button(
                f"📥 Download {audience_labels.get(audience_key, audience_key)} Message",
                full_text,
                file_name=f"esg_communication_{audience_key}.txt",
                mime="text/plain",
                key=f"download_{audience_key}",
            )

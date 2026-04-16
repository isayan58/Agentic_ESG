"""ESG CoPilot — public landing page.

This page is visible to *all* visitors (signed-in or not). It showcases the
platform's value proposition, the 9-agent fleet and the architectural layers,
and routes users to the Sign In page for gated functionality (Mission Control,
agents, ROI dashboards).
"""
import streamlit as st

from utils.auth import current_user, sidebar_auth_widget
from utils.ui import (
    badge,
    hero,
    inject_global_css,
    kpi_card,
    section_header,
)

st.set_page_config(
    page_title="ESG CoPilot",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()

# ---------------------------------------------------------------------------
# Sidebar — minimal, brand-forward, auth-aware
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🌍 ESG CoPilot")
    st.markdown("*Autonomous ESG Intelligence*")
    st.markdown("---")
    st.markdown("### Optional AI acceleration")
    hf_token = st.text_input(
        "HuggingFace API token",
        type="password",
        key="hf_token_input",
        help="Not required. Enables AI-augmented analysis inside the agents.",
    )
    if hf_token:
        import os
        os.environ["HF_API_TOKEN"] = hf_token
        st.success("Token set for this session.")
    else:
        st.caption("Running in fallback mode — no AI token needed.")

    st.markdown("---")
    st.markdown("**GreenTech Solutions Pvt. Ltd.**")
    st.caption("Sample company for demonstration")

# Render the auth widget (sign-in / out) below the sidebar content
sidebar_auth_widget()

# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
user = current_user()
if user:
    welcome_subtitle = (
        f"Welcome back, {user.get('full_name') or user.get('username')}. "
        "Jump into Mission Control to orchestrate the 9-agent pipeline — "
        "or explore the overview below."
    )
else:
    welcome_subtitle = (
        "9 autonomous agents convert raw ESG data into board-ready business intelligence. "
        "From BRSR, CSRD, GRI and SASB compliance to carbon, risk and ROI — one orchestrated pipeline."
    )

hero(
    title="ESG CoPilot",
    emoji="🌍",
    subtitle=welcome_subtitle,
    chips=[
        "9 Orchestrated Agents",
        "BRSR · CSRD · GRI · SASB",
        "Top-line · Bottom-line · Risk",
        "HuggingFace-native",
    ],
)

# Primary call-to-action row
cta_cols = st.columns([1, 1, 1, 1])
with cta_cols[0]:
    if user:
        if st.button("🎛️ Open Mission Control", type="primary", use_container_width=True):
            try:
                st.switch_page("pages/1_Mission_Control.py")
            except Exception:
                st.info("Open Mission Control from the sidebar.")
    else:
        if st.button("🔐 Sign in to run pipeline", type="primary", use_container_width=True):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                st.info("Open Sign In from the sidebar.")
with cta_cols[1]:
    if st.button("⭐ ESG ROI Agent", use_container_width=True):
        try:
            target = "pages/11_ESG_ROI_Agent.py" if user else "pages/0_Sign_In.py"
            st.switch_page(target)
        except Exception:
            pass
with cta_cols[2]:
    if st.button("📋 Regulatory Tracker", use_container_width=True):
        try:
            target = "pages/3_Regulatory_Tracker.py" if user else "pages/0_Sign_In.py"
            st.switch_page(target)
        except Exception:
            pass
with cta_cols[3]:
    if user is None:
        if st.button("Create free account", use_container_width=True):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                pass
    else:
        badge("You’re signed in", variant="success")

# ---------------------------------------------------------------------------
# Platform stats
# ---------------------------------------------------------------------------
section_header(
    "Platform at a glance",
    "Agents, frameworks, data sources, and AI models powering the pipeline.",
)

stat_cols = st.columns(4)
with stat_cols[0]:
    kpi_card("AI Agents", "9", description="Specialized ESG agents", key="kpi-agents")
with stat_cols[1]:
    kpi_card("Frameworks", "4", description="BRSR · CSRD · GRI · SASB", key="kpi-frameworks")
with stat_cols[2]:
    kpi_card("Data Sources", "7", description="Sample connectors loaded", key="kpi-sources")
with stat_cols[3]:
    kpi_card("AI Models", "4", description="HuggingFace-powered", key="kpi-models")

# ---------------------------------------------------------------------------
# Plain-English guide
# ---------------------------------------------------------------------------
section_header(
    "Read the business lens in plain English",
    "Three simple framings used throughout every agent dashboard.",
)

plain_col1, plain_col2, plain_col3 = st.columns(3)
with plain_col1:
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem; border:1px solid #e2e8f0; border-radius:14px;
            background:#f6f8fb; height:100%;">
            <div style="font-size:1.5rem;">📈</div>
            <h4 style="margin:0.25rem 0 0.4rem 0;">Top Line</h4>
            <p style="font-size:0.9rem;color:#3f4a5e; margin:0;">
                <strong>Money coming in</strong> — revenue growth, brand lift, customer momentum.
                ESG CoPilot shows whether sustainability is helping the company grow faster.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with plain_col2:
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem; border:1px solid #e2e8f0; border-radius:14px;
            background:#f6f8fb; height:100%;">
            <div style="font-size:1.5rem;">💰</div>
            <h4 style="margin:0.25rem 0 0.4rem 0;">Bottom Line</h4>
            <p style="font-size:0.9rem;color:#3f4a5e; margin:0;">
                <strong>Money left after costs</strong> — margins, savings, avoided carbon costs.
                ESG CoPilot shows whether ESG improves profitability, not just reporting.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with plain_col3:
    st.markdown(
        """
        <div style="
            padding:1rem 1.1rem; border:1px solid #e2e8f0; border-radius:14px;
            background:#f6f8fb; height:100%;">
            <div style="font-size:1.5rem;">🧪</div>
            <h4 style="margin:0.25rem 0 0.4rem 0;">Hypotheses</h4>
            <p style="font-size:0.9rem;color:#3f4a5e; margin:0;">
                <strong>Business ideas being tested</strong> — does ESG improve growth, lower risk,
                or create short-term cost for long-term payoff?
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Architecture
# ---------------------------------------------------------------------------
section_header(
    "Architecture at a glance",
    "From raw data to board-ready decisions in four orchestrated layers.",
)

arch_cols = st.columns(4)
arch_items = [
    ("🗄️", "1. Data Foundation",
     "Data Collector standardizes ESG + financial data so the rest of the system works from one trusted base."),
    ("⚙️", "2. Business Engine",
     "Carbon, Risk, Audit, and ROI agents convert ESG information into top-line, bottom-line, and risk signals."),
    ("🧪", "3. Hypothesis Layer",
     "The platform tests whether ESG is actually improving growth, profitability, downside protection, and payback."),
    ("🎯", "4. Decision Layer",
     "Report, Action, and Stakeholder agents turn analysis into board-ready outputs and clear next steps."),
]
for col, (icon, title, body) in zip(arch_cols, arch_items):
    with col:
        st.markdown(
            f"""
            <div style="
                padding:1rem 1.1rem; border:1px solid #e2e8f0; border-radius:14px;
                background:#ffffff; height:100%;
                box-shadow:0 2px 6px rgba(15,23,42,0.04);">
                <div style="font-size:1.4rem;">{icon}</div>
                <h4 style="margin:0.25rem 0 0.4rem 0;">{title}</h4>
                <p style="font-size:0.88rem;color:#3f4a5e; margin:0;">{body}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Agent fleet
# ---------------------------------------------------------------------------
section_header(
    "The 9-agent fleet",
    "Each agent ships with its own dashboard — sign in to explore them.",
)

agents_info = [
    ("📊", "Data Collector", "Auto-discovers and validates ESG data with quality scoring"),
    ("📋", "Regulatory Tracker", "Monitors BRSR, CSRD, GRI, SASB compliance"),
    ("🌱", "Carbon Accountant", "Tracks Scope 1/2/3 emissions and supply chain hotspots"),
    ("📄", "Report Generator", "Creates multi-framework audit-ready reports"),
    ("⚠️", "Risk Predictor", "Forecasts climate risks and predicts ESG ratings"),
    ("🔍", "Audit Agent", "Verifies compliance and manages audit trails"),
    ("⭐", "ESG ROI Agent", "Quantifies ESG-linked financial and strategic return"),
    ("🎯", "Action Agent", "Generates prioritized recommendations"),
    ("👥", "Stakeholder Agent", "Tailors communications for each audience"),
]

cols = st.columns(3)
for i, (icon, name, desc) in enumerate(agents_info):
    with cols[i % 3]:
        st.markdown(
            f"""
            <div style="
                padding:0.9rem 1rem; border:1px solid #e2e8f0; border-radius:12px;
                background:#ffffff; margin-bottom:0.75rem;">
                <div style="font-weight:600; color:#1a202c;">
                    <span style="font-size:1.15rem;">{icon}</span> {name}
                </div>
                <div style="color:#64748b; font-size:0.85rem; margin-top:0.25rem;">{desc}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------------------
# Getting started
# ---------------------------------------------------------------------------
section_header("Getting started", "Three steps to run the full pipeline.")

st.markdown(
    """
1. **Sign in or create a free account** — required for Mission Control and the agent dashboards.
2. **Open Mission Control** to run the full 9-agent pipeline in one click.
3. **Drill into the ESG ROI Agent** for the clearest finance view in plain English.

> *Optional:* set a HuggingFace API token in the sidebar to unlock AI-augmented analysis inside each agent.
    """
)

# Bottom CTA row (only shown to guests)
if user is None:
    st.markdown("---")
    section_header("Ready to see it in action?", "Sign in or create a free account to unlock the dashboards.")
    cta_a, cta_b, _ = st.columns([1, 1, 2])
    with cta_a:
        if st.button("Create free account", type="primary", use_container_width=True, key="bottom_cta_signup"):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                st.info("Open Sign In from the sidebar.")
    with cta_b:
        if st.button("I already have an account", use_container_width=True, key="bottom_cta_signin"):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                pass

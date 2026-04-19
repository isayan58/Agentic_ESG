"""ESG CoPilot — product landing / Home page.

This is the entry point shown as "Home" in the Streamlit sidebar. It is
visible to *all* visitors (signed-in or not). The signed-in experience
adds a personal greeting and a direct CTA to Mission Control; guests
see product marketing and a sign-up CTA.
"""
from __future__ import annotations

import streamlit as st

from utils.auth import current_user, sidebar_auth_widget
from utils.ui import hero, inject_global_css, pwc_header, section_header

st.set_page_config(
    page_title="ESG CoPilot — Autonomous ESG Intelligence",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()
pwc_header()

# ---------------------------------------------------------------------------
# Page-local CSS — product-grade polish on top of the global design system
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        /* ---- Stat band (trust strip under hero) --------------------- */
        .home-stat-band {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            background: #ffffff;
            overflow: hidden;
            margin: 1rem 0 2.25rem 0;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03);
        }
        .home-stat {
            padding: 1.1rem 1.25rem;
            border-right: 1px solid #eef2f7;
        }
        .home-stat:last-child { border-right: none; }
        .home-stat-value {
            font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            font-weight: 800;
            font-size: 1.9rem;
            color: #0f172a;
            letter-spacing: -0.02em;
            line-height: 1;
        }
        .home-stat-label {
            color: #64748b;
            font-size: 0.82rem;
            font-weight: 500;
            margin-top: 0.35rem;
            letter-spacing: 0.01em;
        }
        @media (max-width: 900px) {
            .home-stat-band { grid-template-columns: repeat(2, 1fr); }
            .home-stat:nth-child(2) { border-right: none; }
            .home-stat:nth-child(1), .home-stat:nth-child(2) {
                border-bottom: 1px solid #eef2f7;
            }
        }

        /* ---- Feature grid ------------------------------------------ */
        .home-feature {
            position: relative;
            padding: 1.35rem 1.4rem;
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            background: #ffffff;
            height: 100%;
            transition: transform 140ms ease, box-shadow 140ms ease, border-color 140ms ease;
            margin-bottom: 0.85rem;
        }
        .home-feature:hover {
            transform: translateY(-2px);
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.08);
            border-color: #cfe4d8;
        }
        .home-feature .feature-icon {
            display: inline-flex; align-items: center; justify-content: center;
            width: 42px; height: 42px; border-radius: 10px;
            background: linear-gradient(135deg, rgba(15, 157, 88, 0.12), rgba(31, 111, 235, 0.12));
            font-size: 1.25rem;
            margin-bottom: 0.8rem;
        }
        .home-feature h4 {
            margin: 0 0 0.35rem 0;
            font-size: 1.02rem;
            color: #0f172a;
        }
        .home-feature p {
            margin: 0;
            color: #475569;
            font-size: 0.9rem;
            line-height: 1.55;
        }

        /* ---- Layer architecture card -------------------------------- */
        .home-layer {
            padding: 1.1rem 1.2rem;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            background: #ffffff;
            height: 100%;
            position: relative;
            overflow: hidden;
            margin-bottom: 0.8rem;
        }
        .home-layer::before {
            content: "";
            position: absolute;
            left: 0; top: 0; bottom: 0; width: 4px;
            background: linear-gradient(180deg, #0f9d58, #1f6feb);
        }
        .home-layer .layer-step {
            font-family: 'JetBrains Mono', monospace;
            font-weight: 500;
            font-size: 0.72rem;
            color: #0b7a43;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .home-layer h4 {
            margin: 0.2rem 0 0.35rem 0;
            font-size: 1.02rem;
            color: #0f172a;
        }
        .home-layer p {
            margin: 0;
            color: #475569;
            font-size: 0.88rem;
            line-height: 1.55;
        }

        /* ---- Agent tile grid --------------------------------------- */
        .home-agent {
            display: flex; gap: 0.85rem; align-items: flex-start;
            padding: 0.85rem 1rem;
            border: 1px solid #eef2f7;
            border-radius: 12px;
            background: #ffffff;
            transition: border-color 120ms ease, background 120ms ease;
            margin-bottom: 0.7rem;
        }
        .home-agent:hover {
            background: #f8fafc;
            border-color: #cfe4d8;
        }
        .home-agent .agent-icon {
            flex-shrink: 0;
            width: 38px; height: 38px; border-radius: 9px;
            background: linear-gradient(135deg, #0f9d58 0%, #0b7a43 100%);
            color: white;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 1.1rem;
            box-shadow: 0 4px 10px rgba(15, 157, 88, 0.22);
        }
        .home-agent .agent-body .agent-name {
            font-weight: 600;
            color: #0f172a;
            font-size: 0.96rem;
        }
        .home-agent .agent-body .agent-desc {
            color: #64748b;
            font-size: 0.84rem;
            margin-top: 0.18rem;
            line-height: 1.45;
        }

        /* ---- Quote / social proof card ------------------------------ */
        .home-quote {
            border: 1px solid #e5e7eb;
            border-radius: 18px;
            padding: 1.75rem 2rem;
            background:
                linear-gradient(135deg, rgba(15, 157, 88, 0.06), rgba(31, 111, 235, 0.06)),
                #ffffff;
            margin: 0.5rem 0 1.5rem 0;
        }
        .home-quote .quote-mark {
            font-family: 'Plus Jakarta Sans', serif;
            font-size: 2.6rem;
            color: #0f9d58;
            line-height: 0.7;
            margin-bottom: 0.4rem;
        }
        .home-quote blockquote {
            margin: 0 0 0.9rem 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 1.22rem;
            font-weight: 600;
            color: #0f172a;
            line-height: 1.45;
            letter-spacing: -0.01em;
        }
        .home-quote .quote-author {
            color: #475569;
            font-size: 0.92rem;
        }
        .home-quote .quote-author strong { color: #0f172a; }

        /* ---- Trust & security strip --------------------------------- */
        .home-trust {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 0.85rem;
            margin: 0.5rem 0 1.5rem 0;
        }
        .home-trust-item {
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 0.9rem 1.05rem;
            background: #ffffff;
        }
        .home-trust-item .trust-title {
            font-weight: 600;
            color: #0f172a;
            font-size: 0.92rem;
        }
        .home-trust-item .trust-desc {
            color: #64748b;
            font-size: 0.82rem;
            margin-top: 0.2rem;
        }

        /* ---- Footer ------------------------------------------------ */
        .home-footer {
            margin-top: 3rem;
            padding: 1.4rem 0 0.2rem 0;
            border-top: 1px solid #e5e7eb;
            color: #64748b;
            font-size: 0.85rem;
            display: flex; justify-content: space-between; flex-wrap: wrap;
            gap: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Sidebar — brand + optional HF token + auth widget
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="padding: 0.25rem 0 0.5rem 0;">
            <div style="font-family:'Plus Jakarta Sans', sans-serif;
                        font-weight:800; font-size:1.25rem; color:#0f172a;
                        letter-spacing:-0.02em;">
                🌍 ESG CoPilot
            </div>
            <div style="color:#64748b; font-size:0.85rem; margin-top:0.15rem;">
                Autonomous ESG intelligence
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("---")

    with st.expander("AI acceleration (optional)", expanded=False):
        hf_token = st.text_input(
            "HuggingFace API token",
            type="password",
            key="hf_token_input",
            help="Not required. Enables AI-augmented analysis inside each agent.",
        )
        if hf_token:
            import os
            os.environ["HF_API_TOKEN"] = hf_token
            st.success("Token set for this session.")
        else:
            st.caption("Running in fallback mode — no AI token needed.")

    st.markdown("---")
    st.caption("**Demo tenant:** GreenTech Solutions Pvt. Ltd.")

sidebar_auth_widget()


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
user = current_user()
if user:
    name = user.get("full_name") or user.get("username", "there")
    eyebrow = f"Signed in · {name}"
    subtitle = (
        "Your ESG command center is ready. Jump into Mission Control to orchestrate "
        "the 9-agent pipeline — or drill into the ROI dashboard for the board-ready view."
    )
else:
    eyebrow = "Enterprise ESG intelligence · Powered by 9 autonomous agents"
    subtitle = (
        "From raw ESG data to board-ready decisions — in one orchestrated pipeline. "
        "Nine specialized agents handle compliance, carbon accounting, risk, audit, "
        "reporting, and ROI so your team can focus on outcomes, not spreadsheets."
    )

hero(
    title="The autonomous platform for enterprise ESG.",
    eyebrow=eyebrow,
    subtitle=subtitle,
    chips=[
        "BRSR · CSRD · GRI · SASB",
        "Top-line · Bottom-line · Risk",
        "HuggingFace-native AI",
        "SOC-2-ready architecture",
    ],
)


# ---------------------------------------------------------------------------
# Primary CTA row
# ---------------------------------------------------------------------------
cta_cols = st.columns([1.1, 1, 1, 1])
with cta_cols[0]:
    if user:
        if st.button("🎛️  Open Mission Control", type="primary", use_container_width=True):
            try:
                st.switch_page("pages/1_Mission_Control.py")
            except Exception:
                st.info("Open Mission Control from the sidebar.")
    else:
        if st.button("🔐  Sign in to continue", type="primary", use_container_width=True):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                st.info("Open Sign In from the sidebar.")
with cta_cols[1]:
    if st.button("⭐  ESG ROI Agent", use_container_width=True, key="cta_roi"):
        target = "pages/11_ESG_ROI_Agent.py" if user else "pages/0_Sign_In.py"
        try:
            st.switch_page(target)
        except Exception:
            pass
with cta_cols[2]:
    if st.button("📋  Regulatory Tracker", use_container_width=True, key="cta_reg"):
        target = "pages/3_Regulatory_Tracker.py" if user else "pages/0_Sign_In.py"
        try:
            st.switch_page(target)
        except Exception:
            pass
with cta_cols[3]:
    if user is None:
        if st.button("Create a free account", use_container_width=True, key="cta_signup"):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                pass
    else:
        if st.button("🌱  Carbon Accountant", use_container_width=True, key="cta_carbon"):
            try:
                st.switch_page("pages/4_Carbon_Accountant.py")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Trust / stat band
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="home-stat-band">
        <div class="home-stat">
            <div class="home-stat-value">9</div>
            <div class="home-stat-label">Autonomous agents</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-value">4</div>
            <div class="home-stat-label">Global frameworks</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-value">Scope 1 · 2 · 3</div>
            <div class="home-stat-label">Full carbon coverage</div>
        </div>
        <div class="home-stat">
            <div class="home-stat-value">&lt; 60s</div>
            <div class="home-stat-label">Full pipeline run</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Product pillars — what you can do
# ---------------------------------------------------------------------------
section_header(
    "Built for the sustainability leaders of modern enterprise.",
    "Six capabilities that replace months of manual work.",
)

features = [
    ("🔗", "Unified ESG data fabric",
     "Connect cloud storage, warehouses, and enterprise systems. Auto-detect schemas, "
     "map columns, and land everything on one trusted base."),
    ("📜", "Regulation-aware compliance",
     "Always-on monitoring for BRSR, CSRD, GRI, SASB. Surface mandate shifts within "
     "24 hours and keep disclosures audit-ready."),
    ("🌱", "Scope 1-2-3 carbon accounting",
     "Track direct, indirect, and supply-chain emissions. AI-assisted hotspot "
     "detection across the tier network."),
    ("⚠️", "Forward-looking risk",
     "Forecast climate risks, predict ESG ratings, and run scenario sliders without "
     "writing a line of code."),
    ("⭐", "Dual ROI you can defend",
     "Quantify ESG-linked financial return and strategic value side-by-side. "
     "Turn sustainability into a CFO-approved investment thesis."),
    ("🗣️", "Audience-tailored narratives",
     "Generate board, investor, regulator, and employee communications from the same "
     "source of truth — zero re-keying."),
]

# First row of 3
row1 = st.columns(3)
for col, (icon, title, body) in zip(row1, features[:3]):
    with col:
        st.markdown(
            f"""
            <div class="home-feature">
                <div class="feature-icon">{icon}</div>
                <h4>{title}</h4>
                <p>{body}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
# Second row of 3
row2 = st.columns(3)
for col, (icon, title, body) in zip(row2, features[3:]):
    with col:
        st.markdown(
            f"""
            <div class="home-feature">
                <div class="feature-icon">{icon}</div>
                <h4>{title}</h4>
                <p>{body}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Architecture — 4 layers
# ---------------------------------------------------------------------------
section_header(
    "From raw data to board-ready decisions in four orchestrated layers.",
    "No black boxes. Every signal traces back to a source of truth.",
)

arch_cols = st.columns(4)
arch_items = [
    ("01 · Data foundation", "Data Foundation",
     "Data Collector standardizes ESG and financial data so the rest of the system "
     "works from one validated base."),
    ("02 · Business engine", "Business Engine",
     "Carbon, Risk, Audit, and ROI agents convert ESG information into top-line, "
     "bottom-line, and risk signals."),
    ("03 · Hypothesis layer", "Hypothesis Layer",
     "Test whether ESG is actually improving growth, profitability, downside "
     "protection, and long-term payback."),
    ("04 · Decision layer", "Decision Layer",
     "Report, Action, and Stakeholder agents turn analysis into board-ready outputs "
     "and clear next steps."),
]
for col, (step, title, body) in zip(arch_cols, arch_items):
    with col:
        st.markdown(
            f"""
            <div class="home-layer">
                <div class="layer-step">{step}</div>
                <h4>{title}</h4>
                <p>{body}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Agent fleet
# ---------------------------------------------------------------------------
section_header(
    "A fleet of nine agents, one operator.",
    "Each agent ships with its own dashboard — sign in to explore them.",
)

agents_info = [
    ("📊", "Data Collector", "Auto-discovers and validates ESG data with quality scoring"),
    ("📋", "Regulatory Tracker", "Monitors BRSR, CSRD, GRI, SASB compliance in real time"),
    ("🌱", "Carbon Accountant", "Tracks Scope 1/2/3 emissions with supply-chain hotspots"),
    ("📄", "Report Generator", "Creates multi-framework audit-ready reports"),
    ("⚠️", "Risk Predictor", "Forecasts climate risks and predicts ESG ratings"),
    ("🔍", "Audit Agent", "Verifies compliance and maintains an immutable audit trail"),
    ("⭐", "ESG ROI Agent", "Quantifies ESG-linked financial and strategic return"),
    ("🎯", "Action Agent", "Generates prioritized, timeline-aware recommendations"),
    ("👥", "Stakeholder Agent", "Tailors communications for every audience"),
]

# Render 3 rows of 3 agents
for row_start in (0, 3, 6):
    row_cols = st.columns(3)
    for col, (icon, name, desc) in zip(row_cols, agents_info[row_start:row_start + 3]):
        with col:
            st.markdown(
                f"""
                <div class="home-agent">
                    <div class="agent-icon">{icon}</div>
                    <div class="agent-body">
                        <div class="agent-name">{name}</div>
                        <div class="agent-desc">{desc}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Social proof / quote
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="home-quote">
        <div class="quote-mark">&#8220;</div>
        <blockquote>
            ESG reporting used to take our team three weeks of spreadsheet wrangling.
            ESG CoPilot collapses that into a 60-second pipeline — and the numbers are
            defensible because every signal traces back to a source of truth.
        </blockquote>
        <div class="quote-author">
            <strong>Sustainability Lead</strong> · GreenTech Solutions Pvt. Ltd. (demo tenant)
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Trust & security strip — visually self-explanatory; no header needed
# ---------------------------------------------------------------------------
st.write("")
st.markdown(
    """
    <div class="home-trust">
        <div class="home-trust-item">
            <div class="trust-title">🔐 bcrypt-hashed credentials</div>
            <div class="trust-desc">Passwords stored with 12-round bcrypt. We never see plaintext.</div>
        </div>
        <div class="home-trust-item">
            <div class="trust-title">🎫 Signed session cookies</div>
            <div class="trust-desc">itsdangerous URLSafeTimedSerializer · 14-day TTL · tamper-evident.</div>
        </div>
        <div class="home-trust-item">
            <div class="trust-title">🧾 Audit-ready by design</div>
            <div class="trust-desc">Every agent output is logged, versioned, and attributable.</div>
        </div>
        <div class="home-trust-item">
            <div class="trust-title">🌐 Deploys anywhere</div>
            <div class="trust-desc">Docker-first. Runs on HuggingFace Spaces, AWS, Azure, GCP, or on-prem.</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Closing CTA — different shape for guests vs. signed-in users
# ---------------------------------------------------------------------------
if user is None:
    bottom_a, bottom_b, _ = st.columns([1, 1, 2])
    with bottom_a:
        if st.button("Create free account", type="primary", use_container_width=True, key="bottom_signup"):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                pass
    with bottom_b:
        if st.button("I already have an account", use_container_width=True, key="bottom_signin"):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="home-footer">
        <div>
            <strong style="color:#0f172a;">ESG CoPilot</strong> · Autonomous ESG intelligence ·
            © 2026 · Built for the sustainability leaders of modern enterprise.
        </div>
        <div>
            v1.0 · <span style="color:#0f9d58; font-weight:600;">● operational</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

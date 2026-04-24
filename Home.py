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
            position: relative;
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0;
            border: 1px solid rgba(208, 74, 2, 0.18);
            border-radius: 20px;
            background:
                linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            overflow: hidden;
            margin: 1rem 0 2.5rem 0;
            box-shadow:
                0 1px 2px rgba(15, 23, 42, 0.04),
                0 18px 40px rgba(208, 74, 2, 0.08);
        }
        .home-stat-band::before {
            content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px;
            background: linear-gradient(90deg, #D04A02 0%, #E0301E 50%, #FFB600 100%);
        }
        .home-stat {
            position: relative;
            padding: 1.35rem 1.35rem 1.25rem;
            border-right: 1px solid rgba(241, 217, 196, 0.6);
            transition: background 160ms ease;
        }
        .home-stat:hover { background: rgba(255, 250, 244, 0.6); }
        .home-stat:last-child { border-right: none; }
        .home-stat-value {
            font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            font-weight: 800;
            font-size: 2.2rem;
            background: linear-gradient(135deg, #A23A02 0%, #D04A02 45%, #E0301E 75%, #FFB600 120%);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.028em;
            line-height: 1;
        }
        .home-stat-label {
            color: #5b6473;
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 0.5rem;
            text-transform: uppercase;
            letter-spacing: 0.07em;
        }
        @media (max-width: 900px) {
            .home-stat-band { grid-template-columns: repeat(2, 1fr); }
            .home-stat:nth-child(2) { border-right: none; }
            .home-stat:nth-child(1), .home-stat:nth-child(2) {
                border-bottom: 1px solid rgba(241, 217, 196, 0.6);
            }
        }

        /* ---- Feature grid ------------------------------------------ */
        .home-feature {
            position: relative;
            padding: 1.5rem 1.5rem 1.4rem;
            border: 1px solid #f1d9c4;
            border-radius: 18px;
            background: linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            height: 100%;
            transition: transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
                        box-shadow 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
                        border-color 200ms ease;
            margin-bottom: 0.85rem;
            overflow: hidden;
        }
        .home-feature::before {
            content: ""; position: absolute; inset: 0; pointer-events: none;
            border-radius: inherit;
            padding: 1px;
            background: linear-gradient(135deg, rgba(208, 74, 2, 0.0), rgba(255, 182, 0, 0.0));
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor; mask-composite: exclude;
            transition: background 260ms ease;
        }
        .home-feature:hover {
            transform: translateY(-4px);
            box-shadow:
                0 20px 40px rgba(208, 74, 2, 0.14),
                0 2px 6px rgba(15, 23, 42, 0.05);
            border-color: transparent;
        }
        .home-feature:hover::before {
            background: linear-gradient(135deg, rgba(208, 74, 2, 0.55), rgba(255, 182, 0, 0.55));
        }
        .home-feature .feature-icon {
            position: relative;
            display: inline-flex; align-items: center; justify-content: center;
            width: 52px; height: 52px; border-radius: 14px;
            background: linear-gradient(135deg, #D04A02 0%, #E0301E 55%, #FFB600 130%);
            color: #fff;
            font-size: 1.45rem;
            margin-bottom: 1rem;
            box-shadow:
                0 10px 24px rgba(208, 74, 2, 0.32),
                inset 0 1px 0 rgba(255, 255, 255, 0.35);
        }
        .home-feature .feature-icon::after {
            content: ""; position: absolute; inset: 0; border-radius: inherit;
            background: radial-gradient(60% 80% at 30% 20%, rgba(255, 255, 255, 0.5), transparent 60%);
            pointer-events: none;
        }
        .home-feature h4 {
            margin: 0 0 0.4rem 0;
            font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            font-size: 1.08rem;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: -0.015em;
        }
        .home-feature p {
            margin: 0;
            color: #475569;
            font-size: 0.92rem;
            line-height: 1.6;
        }

        /* ---- Layer architecture card -------------------------------- */
        .home-layer {
            padding: 1.25rem 1.3rem 1.15rem;
            border: 1px solid #f1d9c4;
            border-radius: 16px;
            background: linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            height: 100%;
            position: relative;
            overflow: hidden;
            margin-bottom: 0.8rem;
            transition: transform 200ms cubic-bezier(0.2, 0.8, 0.2, 1),
                        box-shadow 200ms cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        .home-layer:hover {
            transform: translateY(-3px);
            box-shadow: 0 16px 34px rgba(208, 74, 2, 0.12);
        }
        .home-layer::before {
            content: "";
            position: absolute;
            left: 0; top: 0; bottom: 0; width: 5px;
            background: linear-gradient(180deg, #D04A02 0%, #E0301E 55%, #FFB600 100%);
            box-shadow: 2px 0 12px rgba(208, 74, 2, 0.35);
        }
        .home-layer .layer-step {
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 0.7rem;
            color: #A23A02;
            background: rgba(208, 74, 2, 0.08);
            border: 1px solid rgba(208, 74, 2, 0.20);
            padding: 2px 0.6rem;
            border-radius: 999px;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }
        .home-layer h4 {
            margin: 0.55rem 0 0.35rem 0;
            font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            font-size: 1.05rem;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: -0.015em;
        }
        .home-layer p {
            margin: 0;
            color: #475569;
            font-size: 0.9rem;
            line-height: 1.6;
        }

        /* ---- Agent tile grid --------------------------------------- */
        .home-agent {
            display: flex; gap: 0.95rem; align-items: flex-start;
            padding: 0.95rem 1.1rem;
            border: 1px solid #f1d9c4;
            border-radius: 14px;
            background: #ffffff;
            transition: transform 180ms cubic-bezier(0.2, 0.8, 0.2, 1),
                        border-color 180ms ease,
                        box-shadow 180ms ease,
                        background 180ms ease;
            margin-bottom: 0.7rem;
        }
        .home-agent:hover {
            background: linear-gradient(180deg, #ffffff 0%, #fff6ef 100%);
            border-color: rgba(208, 74, 2, 0.35);
            transform: translateX(2px);
            box-shadow: 0 10px 22px rgba(208, 74, 2, 0.10);
        }
        .home-agent .agent-icon {
            flex-shrink: 0;
            position: relative;
            width: 44px; height: 44px; border-radius: 12px;
            background: linear-gradient(135deg, #D04A02 0%, #E0301E 60%, #FFB600 130%);
            color: white;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
            box-shadow:
                0 8px 16px rgba(208, 74, 2, 0.28),
                inset 0 1px 0 rgba(255, 255, 255, 0.3);
        }
        .home-agent .agent-icon::after {
            content: ""; position: absolute; inset: 0; border-radius: inherit;
            background: radial-gradient(60% 80% at 30% 20%, rgba(255, 255, 255, 0.5), transparent 60%);
            pointer-events: none;
        }
        .home-agent .agent-body .agent-name {
            font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            font-weight: 700;
            color: #0f172a;
            font-size: 0.98rem;
            letter-spacing: -0.01em;
        }
        .home-agent .agent-body .agent-desc {
            color: #5b6473;
            font-size: 0.86rem;
            margin-top: 0.22rem;
            line-height: 1.5;
        }

        /* ---- Quote / social proof card ------------------------------ */
        .home-quote {
            position: relative;
            border: 1px solid rgba(208, 74, 2, 0.22);
            border-radius: 22px;
            padding: 2rem 2.25rem;
            background:
                radial-gradient(600px 240px at 0% 0%, rgba(208, 74, 2, 0.12), transparent 65%),
                radial-gradient(600px 240px at 100% 100%, rgba(255, 182, 0, 0.14), transparent 65%),
                linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            margin: 0.5rem 0 1.5rem 0;
            overflow: hidden;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.7),
                0 18px 44px rgba(208, 74, 2, 0.10);
        }
        .home-quote::before {
            content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
            background: linear-gradient(180deg, #D04A02 0%, #E0301E 50%, #FFB600 100%);
        }
        .home-quote .quote-mark {
            font-family: 'Plus Jakarta Sans', serif;
            font-size: 3.2rem;
            background: linear-gradient(135deg, #D04A02 0%, #FFB600 100%);
            -webkit-background-clip: text; background-clip: text;
            -webkit-text-fill-color: transparent;
            line-height: 0.7;
            margin-bottom: 0.4rem;
            font-weight: 800;
        }
        .home-quote blockquote {
            margin: 0 0 1rem 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
            font-size: 1.3rem;
            font-weight: 600;
            color: #0f172a;
            line-height: 1.45;
            letter-spacing: -0.015em;
        }
        .home-quote .quote-author {
            color: #475569;
            font-size: 0.92rem;
        }
        .home-quote .quote-author strong { color: #0f172a; }

        /* ---- Trust & security strip --------------------------------- */
        .home-trust {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 0.9rem;
            margin: 0.5rem 0 1.5rem 0;
        }
        .home-trust-item {
            position: relative;
            border: 1px solid #f1d9c4;
            border-radius: 14px;
            padding: 1rem 1.1rem;
            background: linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease;
            overflow: hidden;
        }
        .home-trust-item::before {
            content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
            background: linear-gradient(180deg, #D04A02, #FFB600);
            opacity: 0.8;
        }
        .home-trust-item:hover {
            transform: translateY(-2px);
            border-color: rgba(208, 74, 2, 0.35);
            box-shadow: 0 12px 26px rgba(208, 74, 2, 0.10);
        }
        .home-trust-item .trust-title {
            font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            font-weight: 700;
            color: #0f172a;
            font-size: 0.95rem;
            letter-spacing: -0.01em;
        }
        .home-trust-item .trust-desc {
            color: #5b6473;
            font-size: 0.84rem;
            margin-top: 0.25rem;
            line-height: 1.5;
        }

        /* ---- Footer ------------------------------------------------ */
        .home-footer {
            margin-top: 3rem;
            padding: 1.5rem 0 0.2rem 0;
            border-top: 1px solid rgba(208, 74, 2, 0.18);
            color: #64748b;
            font-size: 0.85rem;
            display: flex; justify-content: space-between; flex-wrap: wrap;
            gap: 1rem;
        }
        .home-footer .pulse-dot {
            display: inline-block; width: 8px; height: 8px; border-radius: 50%;
            background: #2E8540; margin-right: 6px; vertical-align: middle;
            box-shadow: 0 0 0 3px rgba(46, 133, 64, 0.22);
            animation: footer-pulse 2s ease-in-out infinite;
        }
        @keyframes footer-pulse {
            0%, 100% { box-shadow: 0 0 0 3px rgba(46, 133, 64, 0.22); }
            50%      { box-shadow: 0 0 0 6px rgba(46, 133, 64, 0.0); }
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

"""ESG Pilot — product landing / Home page.

This is the entry point shown as "Home" in the Streamlit sidebar. It is
visible to *all* visitors (signed-in or not). The signed-in experience
adds a personal greeting and a direct CTA to ESG Command Center; guests
see product marketing and a sign-up CTA.
"""
from __future__ import annotations

import streamlit as st

from utils.auth import current_user, sidebar_auth_widget
from utils.ui import (
    esg_roi_featured_card,
    hero,
    inject_global_css,
    pwc_header,
    section_header,
    statusbar,
)

st.set_page_config(
    page_title="ESG Intelligence Hub — Command Your ESG Strategy",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()
pwc_header()


# ---------------------------------------------------------------------------
# Live system state — read the real orchestrator if one exists in the session.
# The statusbar is wrapped in an st.fragment that auto-reruns every 2s *only*
# while agents are actively running. When idle, we skip the tick to avoid
# burning CPU/rerenders. This keeps the pill honest AND truly live.
# ---------------------------------------------------------------------------
def _read_live_statuses() -> dict | None:
    orch = st.session_state.get("orchestrator")
    if orch is None:
        return None
    try:
        return orch.get_agent_statuses()
    except Exception:
        return None


def _any_running(statuses: dict | None) -> bool:
    if not statuses:
        return False
    return any(
        ((v or {}).get("status") or "").lower() == "running"
        for v in statuses.values()
    )


def _avatar_letter() -> str:
    current = st.session_state.get("current_user") or {}
    if isinstance(current, dict):
        name = (current.get("full_name") or current.get("username") or "").strip()
        if name:
            return name[:1].upper()
    return "S"


# Capture an initial snapshot up here so the rest of the page (hero copy,
# footer operational dot) can read the same truth and stay consistent.
_live_statuses = _read_live_statuses()

# Fragment auto-reruns every 2s when a pipeline is in flight; otherwise renders
# once per page load. Works on Streamlit ≥1.32; falls back to a single render
# if the installed version lacks ``run_every``.
_refresh_interval = 2 if _any_running(_live_statuses) else None
try:
    @st.fragment(run_every=_refresh_interval)
    def _render_statusbar() -> None:
        live = _read_live_statuses()
        statusbar(
            search_placeholder="Search anything across 9 agents…",
            statuses=live,                  # drives pill tone + copy live
            notifications=0,                # wire to real notif store when available
            avatar_initial=_avatar_letter(),
        )
    _render_statusbar()
except TypeError:
    # Older Streamlit: no run_every support → one-shot render.
    statusbar(
        search_placeholder="Search anything across 9 agents…",
        statuses=_live_statuses,
        notifications=0,
        avatar_initial=_avatar_letter(),
    )

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
            border: 1px solid rgba(253, 81, 8, 0.18);
            border-radius: 20px;
            background:
                linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            overflow: hidden;
            margin: 1rem 0 2.5rem 0;
            box-shadow:
                0 1px 2px rgba(15, 23, 42, 0.04),
                0 18px 40px rgba(253, 81, 8, 0.08);
        }
        .home-stat-band::before {
            content: ""; position: absolute; left: 0; right: 0; top: 0; height: 3px;
            background: linear-gradient(90deg, #FD5108 0%, #E0301E 50%, #FFB600 100%);
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
            background: linear-gradient(135deg, #C23A00 0%, #FD5108 45%, #E0301E 75%, #FFB600 120%);
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
            background: linear-gradient(135deg, rgba(253, 81, 8, 0.0), rgba(255, 182, 0, 0.0));
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor; mask-composite: exclude;
            transition: background 260ms ease;
        }
        .home-feature:hover {
            transform: translateY(-4px);
            box-shadow:
                0 20px 40px rgba(253, 81, 8, 0.14),
                0 2px 6px rgba(15, 23, 42, 0.05);
            border-color: transparent;
        }
        .home-feature:hover::before {
            background: linear-gradient(135deg, rgba(253, 81, 8, 0.55), rgba(255, 182, 0, 0.55));
        }
        .home-feature .feature-icon {
            position: relative;
            display: inline-flex; align-items: center; justify-content: center;
            width: 52px; height: 52px; border-radius: 14px;
            background: linear-gradient(135deg, #FD5108 0%, #E0301E 55%, #FFB600 130%);
            color: #fff;
            font-size: 1.45rem;
            margin-bottom: 1rem;
            box-shadow:
                0 10px 24px rgba(253, 81, 8, 0.32),
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
            box-shadow: 0 16px 34px rgba(253, 81, 8, 0.12);
        }
        .home-layer::before {
            content: "";
            position: absolute;
            left: 0; top: 0; bottom: 0; width: 5px;
            background: linear-gradient(180deg, #FD5108 0%, #E0301E 55%, #FFB600 100%);
            box-shadow: 2px 0 12px rgba(253, 81, 8, 0.35);
        }
        .home-layer .layer-step {
            display: inline-block;
            font-family: 'JetBrains Mono', monospace;
            font-weight: 600;
            font-size: 0.7rem;
            color: #C23A00;
            background: rgba(253, 81, 8, 0.08);
            border: 1px solid rgba(253, 81, 8, 0.20);
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
            border-color: rgba(253, 81, 8, 0.35);
            transform: translateX(2px);
            box-shadow: 0 10px 22px rgba(253, 81, 8, 0.10);
        }
        .home-agent .agent-icon {
            flex-shrink: 0;
            position: relative;
            width: 44px; height: 44px; border-radius: 12px;
            background: linear-gradient(135deg, #FD5108 0%, #E0301E 60%, #FFB600 130%);
            color: white;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 1.2rem;
            box-shadow:
                0 8px 16px rgba(253, 81, 8, 0.28),
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

        /* ---- Dashboard-style agent tile (mockup-inspired) ----------- */
        .home-agent-tile {
            position: relative;
            display: flex; flex-direction: column; gap: 0.6rem;
            padding: 1rem 1.1rem;
            border: 1px solid #f1d9c4;
            border-radius: 14px;
            background: linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            height: 100%; min-height: 168px;
            transition: transform 220ms cubic-bezier(0.2, 0.8, 0.2, 1),
                        box-shadow 220ms cubic-bezier(0.2, 0.8, 0.2, 1),
                        border-color 220ms ease;
            overflow: hidden;
            margin-bottom: 0.85rem;
        }
        .home-agent-tile::before {
            content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 3px;
            background: linear-gradient(180deg, #FD5108 0%, #FFB600 100%);
            opacity: 0.45;
            transition: opacity 200ms ease, width 200ms ease;
        }
        .home-agent-tile:hover {
            transform: translateY(-3px);
            border-color: rgba(253, 81, 8, 0.40);
            box-shadow:
                0 18px 38px rgba(253, 81, 8, 0.16),
                0 2px 6px rgba(15, 23, 42, 0.05);
        }
        .home-agent-tile:hover::before { opacity: 1; width: 5px; }
        .home-agent-tile:active {
            transform: translateY(-1px);
            box-shadow: 0 8px 18px rgba(253, 81, 8, 0.14),
                        inset 0 2px 4px rgba(194, 58, 0, 0.10);
        }
        .home-agent-tile.status-running {
            background:
                linear-gradient(180deg, rgba(253, 81, 8, 0.04), #ffffff 60%);
            border-color: rgba(253, 81, 8, 0.30);
        }
        .home-agent-tile.status-error {
            background:
                linear-gradient(180deg, rgba(200, 16, 46, 0.04), #ffffff 60%);
            border-color: rgba(200, 16, 46, 0.25);
        }
        .home-agent-tile .tile-head {
            display: flex; align-items: center; justify-content: space-between;
            gap: 0.75rem;
        }
        .home-agent-tile .tile-title {
            display: flex; align-items: center; gap: 0.7rem;
            min-width: 0; flex: 1;
            font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
            font-weight: 700;
            color: #0f172a;
            font-size: 0.98rem;
            letter-spacing: -0.012em;
        }
        .home-agent-tile .tile-title > span:last-child {
            min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
        }
        .home-agent-tile .tile-pill { flex-shrink: 0; }
        .home-agent-tile .tile-icon {
            flex-shrink: 0;
            width: 34px; height: 34px; border-radius: 10px;
            display: inline-flex; align-items: center; justify-content: center;
            font-size: 1.05rem;
            background: linear-gradient(135deg, rgba(253, 81, 8, 0.14), rgba(255, 182, 0, 0.22));
            color: #C23A00;
            border: 1px solid rgba(253, 81, 8, 0.20);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.6);
            transition: transform 200ms ease, background 200ms ease;
        }
        .home-agent-tile:hover .tile-icon {
            background: linear-gradient(135deg, #FD5108 0%, #E0301E 55%, #FFB600 130%);
            color: #fff;
            transform: scale(1.05) rotate(-3deg);
            box-shadow: 0 6px 14px rgba(253, 81, 8, 0.35);
        }
        .home-agent-tile .tile-pill {
            display: inline-flex; align-items: center; gap: 5px;
            font-family: 'Inter', sans-serif;
            font-size: 0.64rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            padding: 3px 9px;
            border-radius: 999px;
            border: 1px solid;
            text-transform: uppercase;
        }
        .home-agent-tile .tile-pill-dot {
            display: inline-block;
            width: 6px; height: 6px; border-radius: 50%;
        }
        .home-agent-tile .tile-pill-dot.running {
            animation: tile-pulse 1.4s ease-out infinite;
        }
        @keyframes tile-pulse {
            0%   { box-shadow: 0 0 0 0 rgba(253, 81, 8, 0.55); }
            70%  { box-shadow: 0 0 0 6px rgba(253, 81, 8, 0); }
            100% { box-shadow: 0 0 0 0 rgba(253, 81, 8, 0); }
        }
        .home-agent-tile .tile-desc {
            margin: 0;
            color: #475569;
            font-size: 0.82rem;
            line-height: 1.5;
            flex: 1;
        }
        .home-agent-tile .tile-footer {
            display: flex; align-items: center; justify-content: space-between;
            gap: 0.5rem;
            margin-top: auto;
            padding-top: 0.6rem;
            border-top: 1px dashed rgba(241, 217, 196, 0.8);
        }
        .home-agent-tile .tile-meta {
            font-size: 0.72rem; color: #64748b;
            font-family: 'JetBrains Mono', monospace;
        }
        .home-agent-tile .tile-spark {
            width: 94px; height: 26px;
            opacity: 0.85;
            transition: opacity 200ms ease;
        }
        .home-agent-tile:hover .tile-spark { opacity: 1; }
        @media (max-width: 900px) {
            .home-agent-tile { min-height: 140px; }
        }

        /* ---- Quote / social proof card ------------------------------ */
        .home-quote {
            position: relative;
            border: 1px solid rgba(253, 81, 8, 0.22);
            border-radius: 22px;
            padding: 2rem 2.25rem;
            background:
                radial-gradient(600px 240px at 0% 0%, rgba(253, 81, 8, 0.12), transparent 65%),
                radial-gradient(600px 240px at 100% 100%, rgba(255, 182, 0, 0.14), transparent 65%),
                linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
            margin: 0.5rem 0 1.5rem 0;
            overflow: hidden;
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.7),
                0 18px 44px rgba(253, 81, 8, 0.10);
        }
        .home-quote::before {
            content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
            background: linear-gradient(180deg, #FD5108 0%, #E0301E 50%, #FFB600 100%);
        }
        .home-quote .quote-mark {
            font-family: 'Plus Jakarta Sans', serif;
            font-size: 3.2rem;
            background: linear-gradient(135deg, #FD5108 0%, #FFB600 100%);
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
            background: linear-gradient(180deg, #FD5108, #FFB600);
            opacity: 0.8;
        }
        .home-trust-item:hover {
            transform: translateY(-2px);
            border-color: rgba(253, 81, 8, 0.35);
            box-shadow: 0 12px 26px rgba(253, 81, 8, 0.10);
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
            border-top: 1px solid rgba(253, 81, 8, 0.18);
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
# Sidebar — pwc_header() now owns the brand block at the top of the navbar,
# so we only add the optional HF token + tenant caption below it.
# ---------------------------------------------------------------------------
with st.sidebar:
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
        "Your ESG command center is ready. Jump into ESG Command Center to orchestrate "
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
        "BRSR · CSRD · GRI · SASB · SOX · SEC",
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
        if st.button("🎛️  Open ESG Command Center", type="primary", use_container_width=True):
            try:
                st.switch_page("pages/1_ESG_Command_Center.py")
            except Exception:
                st.info("Open ESG Command Center from the sidebar.")
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
            <div class="home-stat-value">6</div>
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
     "Always-on monitoring for BRSR, CSRD, GRI, SASB, SOX, and the SEC Climate Rule. "
     "Surface mandate shifts within 24 hours and keep disclosures audit-ready."),
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
# Agent fleet — ESG ROI Agent is a featured hero, others are a dashboard grid
# ---------------------------------------------------------------------------
section_header(
    "A fleet of nine agents, one operator.",
    "Each agent ships with its own dashboard — sign in to explore them.",
)

# --- Featured ESG ROI Agent card (React-iframe rich component) ---
# Modes:
#   teaser → guest (not signed in). Sample numbers, clearly watermarked.
#   empty  → signed-in but ROI agent has not produced results yet.
#   live   → signed-in with real ROIAgent.results on the session orchestrator.
# The card derives its own mode when passed ``results=`` + ``user_name=``.
_roi_results = None
try:
    _orch_obj = st.session_state.get("orchestrator")
    if _orch_obj is not None:
        _roi_agent_obj = getattr(_orch_obj, "agents", {}).get("roi_agent")
        if _roi_agent_obj is not None:
            _r = getattr(_roi_agent_obj, "results", None)
            if _r:
                _roi_results = _r
except Exception:
    _roi_results = None

_user_display_name = None
if user:
    _user_display_name = (user.get("full_name") or user.get("username") or "").strip() or None

esg_roi_featured_card(
    results=_roi_results,
    mode="auto",                   # auto → live / empty / teaser
    user_name=_user_display_name,
    height=440,                     # fits the IQS ring + label + sparkline
)

# Streamlit button sits outside the iframe so navigation stays clean.
roi_cta_cols = st.columns([1.2, 1, 3])
with roi_cta_cols[0]:
    if st.button(
        "⭐  Open ROI Dashboard  →",
        type="primary",
        use_container_width=True,
        key="featured_roi_open",
    ):
        target = "pages/11_ESG_ROI_Agent.py" if user else "pages/0_Sign_In.py"
        try:
            st.switch_page(target)
        except Exception:
            st.info("Open ESG ROI Agent from the sidebar.")
with roi_cta_cols[1]:
    st.markdown(
        '<div style="font-size:0.82rem;color:#5b6473;padding:10px 4px;">'
        'Board-ready in one click. No spreadsheets.</div>',
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:0.8rem;'></div>", unsafe_allow_html=True)

# --- Remaining 8 agents — compact dashboard tiles with live "Active" pill ---
# Icon, title, Active pill, description, and a sparkline signal — one glance.
other_agents = [
    ("📊", "data_collector",      "Data Collector",      "Auto-discovers and validates ESG data with quality scoring.",   [12, 18, 15, 22, 28, 26, 32, 35]),
    ("📋", "regulatory_tracker",  "Regulatory Tracker",  "Monitors BRSR, CSRD, GRI, SASB, SOX & SEC in real time.",        [22, 25, 23, 28, 31, 34, 30, 36]),
    ("🌱", "carbon_accountant",   "Carbon Accountant",   "Tracks Scope 1/2/3 emissions with supply-chain hotspots.",      [42, 40, 38, 36, 33, 31, 28, 26]),
    ("📄", "report_generator",    "Report Generator",    "Creates multi-framework audit-ready reports.",                   [ 6, 12, 18, 24, 30, 36, 42, 48]),
    ("⚠️",  "risk_predictor",      "Risk Predictor",      "Forecasts climate risks and predicts ESG ratings.",              [48, 44, 46, 42, 38, 40, 36, 34]),
    ("🔍", "audit_agent",         "Audit Agent",         "Verifies compliance and maintains an immutable audit trail.",    [20, 22, 24, 23, 26, 28, 27, 30]),
    ("🎯", "action_agent",        "Action Agent",        "Generates prioritized, timeline-aware recommendations.",         [14, 18, 16, 22, 28, 32, 36, 40]),
    ("👥", "stakeholder_agent",   "Stakeholder Agent",   "Tailors communications for every audience.",                     [10, 14, 18, 22, 20, 24, 28, 32]),
]


def _agent_tile_html(icon: str, name: str, desc: str, spark_vals: list[int],
                     status: str, status_label: str, last_run: str) -> str:
    """Build the HTML for one dashboard-style agent tile."""
    # Build sparkline polyline
    if len(spark_vals) < 2:
        spark_vals = [0, 0]
    vmin, vmax = min(spark_vals), max(spark_vals)
    rng = (vmax - vmin) or 1
    step = 100.0 / (len(spark_vals) - 1)
    pts = " ".join(
        f"{i * step:.2f},{(1 - (v - vmin) / rng) * 24 + 4:.2f}"
        for i, v in enumerate(spark_vals)
    )
    # Pill color per status
    pill_bg, pill_fg, pill_bd = {
        "running":   ("rgba(253, 81, 8, 0.10)",  "#C23A00", "rgba(253, 81, 8, 0.35)"),
        "error":     ("rgba(200, 16, 46, 0.08)", "#C8102E", "rgba(200, 16, 46, 0.35)"),
        "warning":   ("rgba(255, 182, 0, 0.10)", "#8a5b00", "rgba(255, 182, 0, 0.40)"),
        "completed": ("rgba(46, 133, 64, 0.10)", "#2E8540", "rgba(46, 133, 64, 0.30)"),
        "idle":      ("rgba(46, 133, 64, 0.10)", "#2E8540", "rgba(46, 133, 64, 0.30)"),
    }.get(status, ("rgba(46, 133, 64, 0.10)", "#2E8540", "rgba(46, 133, 64, 0.30)"))

    spark_stroke = "#FD5108" if status in ("running", "completed", "idle") else "#C8102E"
    dot_cls = "running" if status == "running" else ""

    return (
        f'<div class="home-agent-tile status-{status}">'
        f'  <div class="tile-head">'
        f'    <div class="tile-title">'
        f'      <span class="tile-icon">{icon}</span>'
        f'      <span>{name}</span>'
        f'    </div>'
        f'    <span class="tile-pill" style="background:{pill_bg};color:{pill_fg};border-color:{pill_bd};">'
        f'      <span class="tile-pill-dot {dot_cls}" style="background:{pill_fg};"></span>{status_label}'
        f'    </span>'
        f'  </div>'
        f'  <p class="tile-desc">{desc}</p>'
        f'  <div class="tile-footer">'
        f'    <span class="tile-meta">🕒 {last_run}</span>'
        f'    <svg class="tile-spark" viewBox="0 0 100 32" preserveAspectRatio="none" aria-hidden="true">'
        f'      <polyline points="{pts}" fill="none" stroke="{spark_stroke}" stroke-width="2"'
        f'               stroke-linecap="round" stroke-linejoin="round"/>'
        f'    </svg>'
        f'  </div>'
        f'</div>'
    )


# Render 2 rows × 4 columns, each card wired to live status when the
# orchestrator is present, otherwise "Ready" with a neutral Active pill.
def _live_agent_status(agent_key: str) -> tuple[str, str, str]:
    """Return (status, label, relative-time) from the orchestrator when
    available — falls back to a safe default that never over-claims."""
    if _live_statuses and agent_key in _live_statuses:
        meta = _live_statuses[agent_key] or {}
        status = (meta.get("status") or "idle").lower()
        last = meta.get("last_run") or "Never"
        # Human-friendly pill labels
        label = {
            "running":   "RUNNING",
            "error":     "ERROR",
            "warning":   "WARNING",
            "completed": "READY",
            "idle":      "READY",
        }.get(status, "READY")
        # Compress the ISO last_run to a relative time
        try:
            from utils.ui import format_relative_time
            last_rel = format_relative_time(last)
        except Exception:
            last_rel = str(last)[:16]
        return status, label, last_rel
    return "idle", "READY", "Standby"


for row_start in (0, 4):
    row_cols = st.columns(4)
    for col, (icon, key, name, desc, spark_vals) in zip(row_cols, other_agents[row_start:row_start + 4]):
        status, label, last = _live_agent_status(key)
        with col:
            st.markdown(
                _agent_tile_html(icon, name, desc, spark_vals, status, label, last),
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
            ESG Intelligence Hub collapses that into a 60-second pipeline — and the numbers are
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
# Footer — live operational state (reads the same orchestrator snapshot)
# ---------------------------------------------------------------------------
_errored = 0
_running = 0
if _live_statuses:
    for _v in _live_statuses.values():
        _s = ((_v or {}).get("status") or "").lower()
        if _s == "error":
            _errored += 1
        elif _s == "running":
            _running += 1

if _errored:
    _foot_color, _foot_label = "#C8102E", f"{_errored} error(s)"
elif _running:
    _foot_color, _foot_label = "#E0301E", f"{_running} agent(s) running"
else:
    _foot_color, _foot_label = "#2E8540", "operational"

st.markdown(
    f"""
    <div class="home-footer">
        <div>
            <strong style="color:#0f172a;">ESG Intelligence Hub</strong> · Command your ESG strategy with real-time intelligence and action ·
            © 2026 · Built for the sustainability leaders of modern enterprise.
        </div>
        <div>
            v1.0 · <span style="color:{_foot_color}; font-weight:700;">
                <span class="pulse-dot" style="background:{_foot_color};
                     box-shadow:0 0 0 3px {_foot_color}22;"></span>{_foot_label}
            </span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

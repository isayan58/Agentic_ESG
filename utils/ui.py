"""React-backed UI helpers for ESG CoPilot Streamlit pages.

This module wraps community React component libraries (shadcn, elements,
extras) behind a stable, minimal API so pages don't have to know which
library rendered a component. Every helper degrades gracefully to native
Streamlit primitives when the React library is missing, so the app keeps
running in constrained environments.

Design principles
-----------------
* Pages import *only* from ``utils.ui``; they never touch the underlying
  libraries. That keeps us free to swap shadcn for another component
  library later without rewriting every page.
* Every helper is idempotent on re-run and safe to call inside columns,
  tabs, and expanders.
* CSS is injected exactly once per Streamlit session via ``inject_global_css``.
"""
from __future__ import annotations

import html
from typing import Optional, Sequence

import streamlit as st

# ---------------------------------------------------------------------------
# Optional React-backed libraries
# ---------------------------------------------------------------------------
try:  # shadcn cards, metric cards, badges, hover cards
    import streamlit_shadcn_ui as sui  # type: ignore

    _HAS_SHADCN = True
except Exception:  # pragma: no cover - fallback path
    sui = None  # type: ignore
    _HAS_SHADCN = False

try:  # streamlit-extras animated counters, grids, metric-card styling
    from streamlit_extras.metric_cards import style_metric_cards  # type: ignore

    _HAS_EXTRAS = True
except Exception:  # pragma: no cover - fallback path
    style_metric_cards = None  # type: ignore
    _HAS_EXTRAS = False


# ---------------------------------------------------------------------------
# Design tokens — kept in Python so they appear in both CSS and Python code
# ---------------------------------------------------------------------------
TOKENS = {
    "brand_primary": "#0f9d58",   # sustainability green
    "brand_accent": "#1f6feb",    # trust blue
    "brand_warn": "#f59e0b",
    "brand_danger": "#dc2626",
    "brand_success": "#10b981",
    "surface": "#ffffff",
    "surface_muted": "#f6f8fb",
    "surface_raised": "#ffffff",
    "border": "#e5e7eb",
    "text": "#1a202c",
    "text_muted": "#6b7280",
}

_STATUS_COLORS = {
    "idle": "#94a3b8",
    "running": TOKENS["brand_accent"],
    "completed": TOKENS["brand_success"],
    "error": TOKENS["brand_danger"],
    "skipped": TOKENS["brand_warn"],
}

_GRADE_COLORS = {
    "A+": "#059669", "A": "#059669", "A-": "#10b981",
    "B+": "#22c55e", "B": "#84cc16", "B-": "#a3e635",
    "C+": "#eab308", "C": "#f59e0b", "C-": "#f97316",
    "D": "#dc2626", "F": "#991b1b",
}


# ---------------------------------------------------------------------------
# Global CSS injection (the design-system layer)
# ---------------------------------------------------------------------------
_FONT_LINK = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
"""

_GLOBAL_CSS = f"""
<style>
    /* ---- Product typography system ---------------------------------- */
    :root {{
        --font-body: 'Inter', -apple-system, 'SF Pro Text', 'Segoe UI',
                     Roboto, 'Helvetica Neue', Arial, sans-serif;
        --font-display: 'Plus Jakarta Sans', 'Inter', -apple-system,
                        'SF Pro Display', 'Segoe UI', Roboto, sans-serif;
        --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', Consolas, monospace;
    }}

    html, body, [class*="st-"], .stApp, .stMarkdown, .stText,
    .stCaption, .stButton > button {{
        font-family: var(--font-body);
        -webkit-font-smoothing: antialiased;
        -moz-osx-font-smoothing: grayscale;
        font-feature-settings: 'cv11', 'ss01', 'ss03', 'cv03';
    }}
    h1, h2, h3, h4, h5 {{
        font-family: var(--font-display);
        letter-spacing: -0.018em;
        color: {TOKENS['text']};
    }}
    h1 {{ font-weight: 800; line-height: 1.05; }}
    h2 {{ font-weight: 700; line-height: 1.15; }}
    h3 {{ font-weight: 700; line-height: 1.2; }}
    h4 {{ font-weight: 600; line-height: 1.25; }}
    code, pre, kbd {{ font-family: var(--font-mono); }}

    p, li, .stMarkdown p {{
        color: #374151;
        line-height: 1.62;
    }}

    /* ---- Layout container ------------------------------------------- */
    section.main > div.block-container {{
        padding-top: 1.75rem;
        padding-bottom: 4rem;
        max-width: 1380px;
    }}
    @media (min-width: 1500px) {{
        section.main > div.block-container {{ max-width: 1440px; }}
    }}

    /* Native st.metric refinement */
    [data-testid="stMetric"] {{
        background: {TOKENS['surface_raised']};
        border: 1px solid {TOKENS['border']};
        border-radius: 12px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
        transition: box-shadow 120ms ease, transform 120ms ease;
    }}
    [data-testid="stMetric"]:hover {{
        box-shadow: 0 6px 16px rgba(16, 24, 40, 0.08);
        transform: translateY(-1px);
    }}
    [data-testid="stMetricLabel"] {{
        font-weight: 600;
        color: {TOKENS['text_muted']};
        text-transform: uppercase;
        font-size: 0.72rem;
        letter-spacing: 0.04em;
    }}
    [data-testid="stMetricValue"] {{
        font-weight: 700;
        color: {TOKENS['text']};
        font-size: 1.6rem;
    }}

    /* Primary button — brand gradient */
    div.stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {TOKENS['brand_primary']} 0%,
                                              {TOKENS['brand_accent']} 100%);
        border: none;
        color: white;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(31, 111, 235, 0.25);
        transition: transform 120ms ease, box-shadow 120ms ease;
    }}
    div.stButton > button[kind="primary"]:hover {{
        transform: translateY(-1px);
        box-shadow: 0 6px 18px rgba(31, 111, 235, 0.35);
    }}

    /* Tab styling — shadcn-like pill tabs */
    div[data-baseweb="tab-list"] {{
        gap: 4px;
        border-bottom: 1px solid {TOKENS['border']};
    }}
    button[data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0 !important;
        padding: 0.6rem 1rem !important;
        font-weight: 500;
    }}
    button[data-baseweb="tab"][aria-selected="true"] {{
        background: {TOKENS['surface_muted']} !important;
        color: {TOKENS['brand_primary']} !important;
        font-weight: 600 !important;
    }}

    /* Dataframe border + rounded corners */
    [data-testid="stDataFrame"] {{
        border: 1px solid {TOKENS['border']};
        border-radius: 10px;
        overflow: hidden;
    }}

    /* Custom component classes used by helpers below */
    .esg-hero {{
        position: relative;
        background:
            radial-gradient(1200px 400px at 0% 0%, rgba(15, 157, 88, 0.10), transparent 60%),
            radial-gradient(1000px 380px at 100% 0%, rgba(31, 111, 235, 0.10), transparent 60%),
            linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
        border: 1px solid {TOKENS['border']};
        border-radius: 20px;
        padding: 2.4rem 2.5rem 2.2rem 2.5rem;
        margin-bottom: 1.75rem;
        overflow: hidden;
        box-shadow:
            0 1px 2px rgba(15, 23, 42, 0.04),
            0 12px 32px rgba(15, 23, 42, 0.05);
    }}
    .esg-hero::before {{
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background:
            linear-gradient(to right, rgba(15, 157, 88, 0.0) 92%, rgba(15, 157, 88, 0.06) 100%),
            linear-gradient(to left,  rgba(31, 111, 235, 0.0) 92%, rgba(31, 111, 235, 0.06) 100%);
    }}
    .esg-hero h1 {{
        margin: 0 0 0.5rem 0;
        font-size: 2.35rem;
        background: linear-gradient(135deg, {TOKENS['brand_primary']} 0%, #0b7a43 35%, {TOKENS['brand_accent']} 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    .esg-hero p.esg-subtitle {{
        margin: 0.1rem 0 0 0;
        font-size: 1.08rem;
        color: #475569;
        line-height: 1.6;
        max-width: 920px;
    }}
    .esg-hero .esg-eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.28rem 0.75rem;
        border-radius: 999px;
        background: rgba(15, 157, 88, 0.08);
        border: 1px solid rgba(15, 157, 88, 0.22);
        color: #0b7a43;
        font-size: 0.78rem;
        font-weight: 600;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        margin-bottom: 0.9rem;
    }}
    .esg-hero .esg-eyebrow .esg-eyebrow-dot {{
        width: 6px; height: 6px; border-radius: 50%;
        background: {TOKENS['brand_primary']};
        box-shadow: 0 0 0 3px rgba(15, 157, 88, 0.18);
    }}
    .esg-chip-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
    }}
    .esg-chip {{
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.7rem;
        border-radius: 999px;
        background: {TOKENS['surface']};
        border: 1px solid {TOKENS['border']};
        font-size: 0.82rem;
        font-weight: 500;
        color: {TOKENS['text']};
    }}
    .esg-chip.status-running  {{ border-color: {_STATUS_COLORS['running']};  color: {_STATUS_COLORS['running']}; }}
    .esg-chip.status-completed{{ border-color: {_STATUS_COLORS['completed']};color: {_STATUS_COLORS['completed']}; }}
    .esg-chip.status-error    {{ border-color: {_STATUS_COLORS['error']};    color: {_STATUS_COLORS['error']}; }}
    .esg-chip.status-idle     {{ border-color: {_STATUS_COLORS['idle']};     color: {_STATUS_COLORS['idle']}; }}

    .esg-section {{
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        margin: 2rem 0 0.75rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid {TOKENS['border']};
    }}
    .esg-section .esg-section-title {{
        font-size: 1.15rem;
        font-weight: 650;
        color: {TOKENS['text']};
    }}
    .esg-section .esg-section-caption {{
        font-size: 0.88rem;
        color: {TOKENS['text_muted']};
    }}

    .esg-grade-pill {{
        display: inline-flex;
        align-items: center;
        padding: 0.2rem 0.6rem;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.92rem;
        color: white;
    }}

    .esg-agent-card {{
        background: {TOKENS['surface_raised']};
        border: 1px solid {TOKENS['border']};
        border-left-width: 4px;
        border-radius: 12px;
        padding: 1rem 1.1rem;
        height: 100%;
        transition: box-shadow 140ms ease, transform 140ms ease;
    }}
    .esg-agent-card:hover {{
        box-shadow: 0 8px 24px rgba(16, 24, 40, 0.08);
        transform: translateY(-2px);
    }}
    .esg-agent-card .esg-agent-title {{
        font-weight: 600;
        font-size: 0.95rem;
    }}
    .esg-agent-card .esg-agent-meta {{
        font-size: 0.78rem;
        color: {TOKENS['text_muted']};
        margin-top: 0.3rem;
    }}
</style>
"""


def inject_global_css() -> None:
    """Inject the design-system CSS.

    Note: this re-runs on every Streamlit rerun. We intentionally do *not*
    short-circuit via ``st.session_state`` — Streamlit rebuilds the whole
    DOM on each rerun, so a one-shot guard would only inject the styles
    on the first render and leave subsequent reruns un-styled. The CSS
    payload is small (~6 KB) so re-injecting is cheap.

    The first render also wires up ``style_metric_cards`` (which mutates
    Streamlit-generated DOM) — that side-effect is one-shot per session.
    """
    # Font loader (uses <link> tags; Streamlit's HTML sanitiser tolerates
    # these, but rejects @import directives inside <style> blocks).
    st.markdown(_FONT_LINK, unsafe_allow_html=True)
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)

    if not st.session_state.get("_esg_metric_cards_styled"):
        if _HAS_EXTRAS and style_metric_cards is not None:
            try:
                style_metric_cards(
                    background_color=TOKENS["surface_raised"],
                    border_left_color=TOKENS["brand_primary"],
                    border_color=TOKENS["border"],
                    box_shadow=True,
                )
            except Exception:
                pass
        st.session_state["_esg_metric_cards_styled"] = True


# ---------------------------------------------------------------------------
# Hero block — landing banner for Mission Control / ROI page
# ---------------------------------------------------------------------------
def hero(
    title: str,
    subtitle: Optional[str] = None,
    chips: Optional[Sequence[str]] = None,
    *,
    emoji: str = "",
    eyebrow: Optional[str] = None,
) -> None:
    """Render a polished hero block with optional eyebrow + status chips."""
    inject_global_css()
    safe_title = html.escape(title)
    prefix = f"{emoji} " if emoji else ""
    subtitle_html = (
        f'<p class="esg-subtitle">{html.escape(subtitle)}</p>'
        if subtitle else ""
    )
    chip_html = ""
    if chips:
        chip_items = "".join(
            f'<span class="esg-chip">{html.escape(c)}</span>' for c in chips
        )
        chip_html = f'<div class="esg-chip-row">{chip_items}</div>'
    eyebrow_html = ""
    if eyebrow:
        eyebrow_html = (
            f'<span class="esg-eyebrow">'
            f'<span class="esg-eyebrow-dot"></span>{html.escape(eyebrow)}'
            f'</span>'
        )

    st.markdown(
        f"""
        <div class="esg-hero">
            {eyebrow_html}
            <h1>{prefix}{safe_title}</h1>
            {subtitle_html}
            {chip_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Section header — consistent divider between major sections
# ---------------------------------------------------------------------------
def section_header(title: str, caption: Optional[str] = None) -> None:
    """Render a shadcn-style section header with a muted caption.

    Uses a custom HTML block so the title and caption sit on one line with
    a subtle bottom border — cleaner than the native ``st.subheader`` and
    consistent with the shadcn card styling used elsewhere.
    """
    inject_global_css()
    cap_html = (
        f'<span class="esg-section-caption">{html.escape(caption)}</span>'
        if caption else ""
    )
    st.markdown(
        f"""
        <div class="esg-section">
            <span class="esg-section-title">{html.escape(title)}</span>
            {cap_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# KPI card — shadcn metric card with graceful st.metric fallback
# ---------------------------------------------------------------------------
def kpi_card(
    label: str,
    value: str,
    description: Optional[str] = None,
    *,
    key: Optional[str] = None,
) -> None:
    """Render a shadcn metric card (React) with an st.metric fallback."""
    inject_global_css()
    if _HAS_SHADCN and sui is not None:
        try:
            sui.metric_card(
                title=label,
                content=value,
                description=description or "",
                key=key or f"kpi_{label}",
            )
            return
        except Exception:
            pass
    st.metric(label, value, delta=description if description else None)


# ---------------------------------------------------------------------------
# Agent card — status-aware dashboard tile for pipeline overview
# ---------------------------------------------------------------------------
def agent_card(
    name: str,
    icon: str,
    status: str,
    last_run: str = "Never",
    color: str = TOKENS["brand_primary"],
) -> None:
    """Render a single agent status tile."""
    inject_global_css()
    status_key = (status or "idle").lower()
    status_emoji = {
        "idle": "⚪", "running": "🔄", "completed": "✅",
        "error": "❌", "skipped": "⚠️",
    }.get(status_key, "⚪")
    status_color = _STATUS_COLORS.get(status_key, TOKENS["text_muted"])
    run_label = last_run[:16] if last_run and last_run != "Never" else "Never"
    st.markdown(
        f"""
        <div class="esg-agent-card" style="border-left-color:{color};">
            <div class="esg-agent-title">{html.escape(icon)} {html.escape(name)}</div>
            <div style="margin-top:0.4rem;color:{status_color};
                        font-size:0.85rem;font-weight:500;">
                {status_emoji} {html.escape(status_key.capitalize())}
            </div>
            <div class="esg-agent-meta">Last run: {html.escape(run_label)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Badge primitives (React shadcn when available, HTML pill fallback)
# ---------------------------------------------------------------------------
def badge(label: str, variant: str = "default") -> None:
    """Render a small status badge. Variants: default, success, warn, error, info."""
    inject_global_css()
    if _HAS_SHADCN and sui is not None:
        try:
            sui.badges(
                badge_list=[(label, _map_variant_to_shadcn(variant))],
                class_name="flex gap-2",
                key=f"badge_{label}_{variant}",
            )
            return
        except Exception:
            pass
    color = {
        "success": TOKENS["brand_success"],
        "warn": TOKENS["brand_warn"],
        "error": TOKENS["brand_danger"],
        "info": TOKENS["brand_accent"],
        "default": TOKENS["text_muted"],
    }.get(variant, TOKENS["text_muted"])
    st.markdown(
        f'<span class="esg-chip" style="border-color:{color};color:{color};">'
        f'{html.escape(label)}</span>',
        unsafe_allow_html=True,
    )


def _map_variant_to_shadcn(variant: str) -> str:
    return {
        "success": "default",
        "warn": "outline",
        "error": "destructive",
        "info": "secondary",
        "default": "secondary",
    }.get(variant, "secondary")


# ---------------------------------------------------------------------------
# Grade pill — specifically for IQS / Audit grades
# ---------------------------------------------------------------------------
def grade_pill(grade: str) -> str:
    """Return an HTML pill string coloured by grade. Use with st.markdown."""
    color = _GRADE_COLORS.get(grade, TOKENS["text_muted"])
    return (
        f'<span class="esg-grade-pill" style="background:{color};">'
        f'{html.escape(grade)}</span>'
    )


# ---------------------------------------------------------------------------
# Pipeline chip row — one chip per agent with colour-coded status
# ---------------------------------------------------------------------------
def pipeline_chips(statuses: dict, agent_config: dict) -> None:
    """Render a horizontal chip row showing every agent's current status."""
    inject_global_css()
    chips_html = []
    for key, config in agent_config.items():
        status = (statuses.get(key, {}).get("status") or "idle").lower()
        icon = config.get("icon", "🤖")
        name = config.get("name", key)
        chips_html.append(
            f'<span class="esg-chip status-{html.escape(status)}">'
            f'{html.escape(icon)} {html.escape(name)}</span>'
        )
    st.markdown(
        f'<div class="esg-chip-row">{"".join(chips_html)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# IQS gauge — inline SVG arc, no charting lib required
# ---------------------------------------------------------------------------
def iqs_gauge(score: float, grade: str, *, size: int = 220) -> None:
    """Render an SVG gauge for the Investment Quality Score."""
    inject_global_css()
    score = max(0.0, min(100.0, float(score or 0)))
    # Arc math
    import math
    radius = size * 0.38
    center = size / 2
    start_angle = math.radians(135)
    end_angle = math.radians(45 + 360)  # 270 deg sweep
    sweep = end_angle - start_angle
    progress_angle = start_angle + sweep * (score / 100.0)

    def polar(angle):
        return center + radius * math.cos(angle), center + radius * math.sin(angle)

    sx, sy = polar(start_angle)
    px, py = polar(progress_angle)
    ex, ey = polar(end_angle)
    large_bg = 1 if sweep > math.pi else 0
    large_fg = 1 if (progress_angle - start_angle) > math.pi else 0

    color = _GRADE_COLORS.get(grade, TOKENS["brand_primary"])

    svg = f"""
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}"
         xmlns="http://www.w3.org/2000/svg" style="display:block;margin:0 auto;">
      <path d="M {sx:.2f} {sy:.2f} A {radius:.2f} {radius:.2f} 0 {large_bg} 1 {ex:.2f} {ey:.2f}"
            stroke="{TOKENS['border']}" stroke-width="14" fill="none" stroke-linecap="round"/>
      <path d="M {sx:.2f} {sy:.2f} A {radius:.2f} {radius:.2f} 0 {large_fg} 1 {px:.2f} {py:.2f}"
            stroke="{color}" stroke-width="14" fill="none" stroke-linecap="round"/>
      <text x="{center}" y="{center - 6}" text-anchor="middle"
            font-family="Inter, sans-serif" font-weight="700"
            font-size="{size * 0.22:.0f}" fill="{TOKENS['text']}">{score:.0f}</text>
      <text x="{center}" y="{center + size * 0.12:.0f}" text-anchor="middle"
            font-family="Inter, sans-serif" font-weight="600"
            font-size="{size * 0.08:.0f}" fill="{TOKENS['text_muted']}">IQS · Grade {html.escape(grade or 'N/A')}</text>
    </svg>
    """
    st.markdown(svg, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Switch — shadcn switch when available, checkbox fallback
# ---------------------------------------------------------------------------
def switch(label: str, *, default: bool = False, key: Optional[str] = None) -> bool:
    inject_global_css()
    if _HAS_SHADCN and sui is not None:
        try:
            return bool(sui.switch(default_checked=default, label=label,
                                   key=key or f"switch_{label}"))
        except Exception:
            pass
    return st.checkbox(label, value=default, key=key)


# ---------------------------------------------------------------------------
# Feature info — dependency visibility so pages can tell users which React
# components are active. Not shown by default; useful for debugging.
# ---------------------------------------------------------------------------
def react_feature_status() -> dict:
    """Return a snapshot of which React-backed libraries are active."""
    return {
        "shadcn": _HAS_SHADCN,
        "extras": _HAS_EXTRAS,
    }

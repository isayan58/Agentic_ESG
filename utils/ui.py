"""React-backed UI helpers for ESG Pilot Streamlit pages.

This module is the **single source of truth** for the product's design
system. Every page imports from here and never touches Streamlit theming,
shadcn, or raw CSS directly. That gives us five layers of consistency in
one place:

    L5 — Design system: tokens for spacing, radii, shadows, type, motion.
    L1 — Interaction states: hover, active, focus-visible, disabled,
                              loading (aria-busy), error, success.
    L3 — Responsiveness: laptop / large monitor / small screen breakpoints.
    L4 — Accessibility: WCAG-AA contrast, keyboard focus rings,
                        prefers-reduced-motion, semantic ARIA on every
                        custom HTML helper, skip-link.
    L2 — Operational realism: log_panel(), retry_button(), drilldown(),
                              format_relative_time(), live_badge().

Backward compatibility: the public surface (``hero``, ``section_header``,
``kpi_card``, ``agent_card``, ``badge``, ``grade_pill``, ``pipeline_chips``,
``iqs_gauge``, ``switch``, ``inject_global_css``, ``pwc_header``,
``react_feature_status``) is preserved. New parameters are keyword-only
with sensible defaults, so existing callers don't break.
"""
from __future__ import annotations

import base64
import html
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import streamlit as st

# ---------------------------------------------------------------------------
# Optional React-backed libraries
# ---------------------------------------------------------------------------
try:
    import streamlit_shadcn_ui as sui  # type: ignore

    _HAS_SHADCN = True
except Exception:  # pragma: no cover
    sui = None  # type: ignore
    _HAS_SHADCN = False

try:
    from streamlit_extras.metric_cards import style_metric_cards  # type: ignore

    _HAS_EXTRAS = True
except Exception:  # pragma: no cover
    style_metric_cards = None  # type: ignore
    _HAS_EXTRAS = False


# ---------------------------------------------------------------------------
# L5 — Design tokens (Python copy; mirrored into CSS vars below)
# ---------------------------------------------------------------------------
TOKENS = {
    # Brand palette — PwC orange family
    "brand_primary": "#FD5108",
    "brand_primary_dark": "#C23A00",
    "brand_accent": "#E0301E",
    "brand_warn": "#FFB600",
    "brand_danger": "#C8102E",
    "brand_success": "#2E8540",
    "brand_info": "#2563eb",

    # Surfaces (warm cream → white)
    "surface": "#ffffff",
    "surface_muted": "#fff6ef",
    "surface_raised": "#ffffff",
    "surface_sunken": "#fbf3eb",
    "border": "#f1d9c4",
    "border_strong": "#e3bfa1",

    # Text — meets WCAG-AA on white
    "text": "#0f172a",            # 17.4:1 on white
    "text_secondary": "#334155",  # 9.8:1
    "text_muted": "#5b6473",      # 6.7:1 (was 6b7280 / 4.6:1 — lifted for AA)
    "text_disabled": "#94a3b8",
}

_STATUS_COLORS = {
    "idle": "#64748b",
    "running": TOKENS["brand_accent"],
    "completed": TOKENS["brand_success"],
    "error": TOKENS["brand_danger"],
    "skipped": TOKENS["brand_warn"],
    "warning": TOKENS["brand_warn"],
}

_GRADE_COLORS = {
    "A+": "#047857", "A": "#059669", "A-": "#10b981",
    "B+": "#22c55e", "B": "#84cc16", "B-": "#a3e635",
    "C+": "#eab308", "C": "#f59e0b", "C-": "#f97316",
    "D": "#dc2626", "F": "#991b1b",
}


# ---------------------------------------------------------------------------
# CSS payload — token block (f-string) + static rules (plain string)
# ---------------------------------------------------------------------------
_FONT_LINK = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Sharp:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
"""

_TOKEN_CSS = f"""
<style>
:root {{
    /* Type ----------------------------------------------------------- */
    --font-body: 'Inter', -apple-system, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
    --font-display: 'Plus Jakarta Sans', 'Inter', -apple-system, 'SF Pro Display', sans-serif;
    --font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', Consolas, monospace;
    --text-xs: 0.72rem;
    --text-sm: 0.82rem;
    --text-base: 0.94rem;
    --text-md: 1.02rem;
    --text-lg: 1.18rem;
    --text-xl: 1.45rem;
    --text-2xl: 1.85rem;
    --text-3xl: 2.35rem;
    --lh-tight: 1.15;
    --lh-snug: 1.35;
    --lh-normal: 1.55;
    --lh-relaxed: 1.7;

    /* Spacing (4-pt grid) -------------------------------------------- */
    --space-1: 4px;  --space-2: 8px;  --space-3: 12px; --space-4: 16px;
    --space-5: 20px; --space-6: 24px; --space-7: 32px; --space-8: 40px;
    --space-9: 56px; --space-10: 72px;

    /* Radii ---------------------------------------------------------- */
    --radius-xs: 4px;  --radius-sm: 6px; --radius-md: 10px;
    --radius-lg: 14px; --radius-xl: 20px; --radius-pill: 999px;

    /* Elevation (5 tiers) -------------------------------------------- */
    --shadow-xs: 0 1px 2px rgba(15, 23, 42, 0.04);
    --shadow-sm: 0 1px 3px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
    --shadow-md: 0 4px 12px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04);
    --shadow-lg: 0 12px 28px rgba(15, 23, 42, 0.12), 0 4px 10px rgba(15, 23, 42, 0.06);
    --shadow-xl: 0 24px 48px rgba(15, 23, 42, 0.16), 0 8px 16px rgba(15, 23, 42, 0.08);
    --shadow-brand: 0 8px 22px rgba(253, 81, 8, 0.20);
    --ring-focus: 0 0 0 3px rgba(253, 81, 8, 0.35);
    --ring-focus-info: 0 0 0 3px rgba(37, 99, 235, 0.35);

    /* Motion --------------------------------------------------------- */
    --dur-fast: 120ms;
    --dur-base: 180ms;
    --dur-slow: 280ms;
    --ease-standard: cubic-bezier(0.2, 0.8, 0.2, 1);
    --ease-decel: cubic-bezier(0, 0, 0.2, 1);
    --ease-accel: cubic-bezier(0.4, 0, 1, 1);

    /* Z-index -------------------------------------------------------- */
    --z-base: 1; --z-raised: 10; --z-overlay: 100; --z-popover: 1000;
    --z-modal: 2000; --z-tooltip: 3000;

    /* Brand ---------------------------------------------------------- */
    --pwc-orange: {TOKENS['brand_primary']};
    --pwc-orange-dark: {TOKENS['brand_primary_dark']};
    --pwc-tomato: {TOKENS['brand_accent']};
    --pwc-amber: {TOKENS['brand_warn']};
    --pwc-danger: {TOKENS['brand_danger']};
    --pwc-success: {TOKENS['brand_success']};
    --pwc-info: {TOKENS['brand_info']};

    /* Surfaces / text ------------------------------------------------ */
    --surface: {TOKENS['surface']};
    --surface-muted: {TOKENS['surface_muted']};
    --surface-raised: {TOKENS['surface_raised']};
    --surface-sunken: {TOKENS['surface_sunken']};
    --border: {TOKENS['border']};
    --border-strong: {TOKENS['border_strong']};
    --text: {TOKENS['text']};
    --text-secondary: {TOKENS['text_secondary']};
    --text-muted: {TOKENS['text_muted']};
    --text-disabled: {TOKENS['text_disabled']};

    /* Status --------------------------------------------------------- */
    --status-idle: {_STATUS_COLORS['idle']};
    --status-running: {_STATUS_COLORS['running']};
    --status-completed: {_STATUS_COLORS['completed']};
    --status-error: {_STATUS_COLORS['error']};
    --status-warning: {_STATUS_COLORS['warning']};
}}
</style>
"""

# ---------------------------------------------------------------------------
# Static CSS — references the tokens above via var(--…)
# ---------------------------------------------------------------------------
_STATIC_CSS = """
<style>
/* L4 accessibility: skip link + reduced motion ------------------------ */
.esg-skip-link {
    position: absolute; left: -999px; top: 0;
    background: var(--pwc-orange); color: #fff;
    padding: var(--space-3) var(--space-5);
    border-radius: 0 0 var(--radius-md) 0;
    z-index: var(--z-tooltip);
    font-weight: 600;
    transition: left var(--dur-base) var(--ease-standard);
}
.esg-skip-link:focus { left: 0; outline: none; }

@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
        scroll-behavior: auto !important;
    }
}

/* App shell ----------------------------------------------------------- */
.stApp {
    background:
        radial-gradient(1100px 360px at 12% -4%,   rgba(253, 81, 8, 0.14), transparent 65%),
        radial-gradient(1000px 340px at 88% -4%,   rgba(255, 182, 0, 0.12), transparent 65%),
        radial-gradient(720px 540px at 50% 120%,   rgba(224, 48, 30, 0.07), transparent 70%),
        linear-gradient(180deg, #fffaf4 0%, #ffffff 32%, #ffffff 100%) !important;
    background-attachment: fixed !important;
}
.stApp::before {
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image:
        linear-gradient(to right,  rgba(253, 81, 8, 0.04) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(253, 81, 8, 0.04) 1px, transparent 1px);
    background-size: 56px 56px;
    mask-image: radial-gradient(1200px 600px at 50% 0%, rgba(0,0,0,0.75), transparent 70%);
    -webkit-mask-image: radial-gradient(1200px 600px at 50% 0%, rgba(0,0,0,0.75), transparent 70%);
}
[data-testid="stAppViewContainer"] { background: transparent !important; position: relative; z-index: 1; }
/* Collapse Streamlit's translucent blurred app header — we render our own
   branded top bar at the top of each page, so the default header only
   contributes hazy dead space. Keep the hamburger/menu accessible via the
   toolbar below it. */
[data-testid="stHeader"] {
    background: transparent !important;
    backdrop-filter: none !important;
    height: 0 !important;
    min-height: 0 !important;
    padding: 0 !important;
    border: none !important;
}
[data-testid="stHeader"] > * { display: none !important; }
[data-testid="stToolbar"] { top: 0 !important; right: var(--space-3) !important; }
/* Keep chat_input in the document flow so submitting a question doesn't
   yank the page down to a sticky bottom bar. */
[data-testid="stChatInput"] {
    position: static !important;
    bottom: auto !important;
    max-width: 100% !important;
    margin-top: var(--space-3);
}
[data-testid="stChatInputContainer"] {
    position: static !important;
    bottom: auto !important;
}
/* Branded top bar — first thing in main content on every page. */
.esg-topbar {
    display: flex; align-items: center; justify-content: space-between;
    gap: var(--space-4);
    padding: 12px var(--space-5);
    margin: 0 0 var(--space-5) 0;
    border-radius: var(--radius-lg);
    background:
        radial-gradient(600px 180px at 0% 0%, rgba(253, 81, 8, 0.14), transparent 60%),
        linear-gradient(90deg, #ffffff 0%, #fffaf4 100%);
    border: 1px solid rgba(253, 81, 8, 0.18);
    box-shadow:
        0 1px 2px rgba(15, 23, 42, 0.04),
        0 12px 28px rgba(253, 81, 8, 0.08);
}
.esg-topbar .esg-topbar-brand {
    display: flex; align-items: center; gap: var(--space-3); min-width: 0;
}
.esg-topbar img.esg-topbar-logo { height: 34px; width: auto; display: block; flex-shrink: 0; }
.esg-topbar .esg-topbar-text { display: flex; flex-direction: column; line-height: 1.15; min-width: 0; }
.esg-topbar .esg-topbar-title {
    font-family: var(--font-display);
    font-weight: 800;
    font-size: 1.25rem;
    letter-spacing: -0.02em;
    background: linear-gradient(135deg, #C23A00 0%, #FD5108 45%, #E0301E 80%, #FFB600 130%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.esg-topbar .esg-topbar-tagline {
    font-size: 0.82rem; color: var(--text-secondary);
    font-weight: 500; letter-spacing: -0.005em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.esg-topbar .esg-topbar-accent {
    height: 3px; width: 48px; border-radius: var(--radius-pill); flex-shrink: 0;
    background: linear-gradient(90deg, var(--pwc-orange) 0%, var(--pwc-tomato) 55%, var(--pwc-amber) 100%);
    box-shadow: 0 1px 3px rgba(253, 81, 8, 0.30);
}
@media (max-width: 720px) {
    .esg-topbar .esg-topbar-tagline { display: none; }
}
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #ffffff 0%, var(--surface-muted) 85%) !important;
    border-right: 1px solid var(--border);
    box-shadow: inset -1px 0 0 rgba(253, 81, 8, 0.06);
}

/* Sidebar nav — pill-style page links with orange active state -------- */
[data-testid="stSidebarNav"] ul { padding: var(--space-2) var(--space-2); }
[data-testid="stSidebarNav"] ul li { margin: 2px 0; }
[data-testid="stSidebarNav"] a {
    display: flex; align-items: center; gap: var(--space-3);
    padding: 10px var(--space-3) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-family: var(--font-body) !important;
    letter-spacing: -0.005em;
    border: 1px solid transparent;
    transition:
        background var(--dur-base) var(--ease-standard),
        color var(--dur-base) var(--ease-standard),
        border-color var(--dur-base) var(--ease-standard),
        transform var(--dur-fast) var(--ease-standard),
        box-shadow var(--dur-base) var(--ease-standard);
}
[data-testid="stSidebarNav"] a:hover {
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.08), rgba(255, 182, 0, 0.10)) !important;
    color: var(--pwc-orange-dark) !important;
    border-color: rgba(253, 81, 8, 0.18);
    transform: translateX(2px);
}
[data-testid="stSidebarNav"] a[aria-current="page"],
[data-testid="stSidebarNav"] a[aria-selected="true"],
[data-testid="stSidebarNav"] a.st-emotion-cache-active,
[data-testid="stSidebarNav"] li[aria-current="page"] > a,
[data-testid="stSidebarNav"] li[aria-selected="true"] > a {
    background: linear-gradient(135deg, var(--pwc-orange) 0%, var(--pwc-tomato) 100%) !important;
    color: #fff !important;
    border-color: rgba(194, 58, 0, 0.35);
    box-shadow:
        0 8px 20px rgba(253, 81, 8, 0.30),
        inset 0 1px 0 rgba(255, 255, 255, 0.25);
    font-weight: 600 !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"]:hover,
[data-testid="stSidebarNav"] li[aria-current="page"] > a:hover {
    background: linear-gradient(135deg, var(--pwc-orange-dark) 0%, var(--pwc-tomato) 100%) !important;
    transform: translateX(2px);
}
[data-testid="stSidebarNav"] span, [data-testid="stSidebarNav"] p { font-weight: inherit !important; }

/* Sidebar nav hierarchy — ESG Command Center & ESG ROI Agent are the two
   primary surfaces the product is sold on (overview + headline value
   number); every other page is a supporting agent. Style them
   accordingly so the sidebar reads as "command centre + investment
   thesis · then the agents that feed them" rather than ten equal
   peers. Targeting via href[*=…] survives page reorderings.        */
[data-testid="stSidebarNav"] a[href*="ESG_Command_Center"],
[data-testid="stSidebarNav"] a[href*="ESG_ROI_Agent"] {
    font-size: 1.02rem !important;
    font-weight: 700 !important;
    padding-top: 12px !important;
    padding-bottom: 12px !important;
    letter-spacing: -0.01em;
}
/* Subtle accent rail on the primary items so they read as "main"
   even when not currently active.                                    */
[data-testid="stSidebarNav"] a[href*="ESG_Command_Center"]:not([aria-current="page"]),
[data-testid="stSidebarNav"] a[href*="ESG_ROI_Agent"]:not([aria-current="page"]) {
    border-left: 3px solid var(--pwc-orange) !important;
    padding-left: calc(var(--space-3) - 3px) !important;
}
/* Everything else (the supporting agent pages + Settings) reads as
   secondary: slightly smaller and subdued, but still legible (WCAG AA). */
[data-testid="stSidebarNav"] a:not([href*="ESG_Command_Center"]):not([href*="ESG_ROI_Agent"]) {
    font-size: 0.84rem !important;
    padding-top: 6px !important;
    padding-bottom: 6px !important;
    opacity: 0.88;
    letter-spacing: 0;
}
[data-testid="stSidebarNav"] a:not([href*="ESG_Command_Center"]):not([href*="ESG_ROI_Agent"]) span,
[data-testid="stSidebarNav"] a:not([href*="ESG_Command_Center"]):not([href*="ESG_ROI_Agent"]) p {
    font-size: 0.84rem !important;
    font-weight: 500 !important;
}
[data-testid="stSidebarNav"] a:not([href*="ESG_Command_Center"]):not([href*="ESG_ROI_Agent"]):hover {
    opacity: 1;
}

/* Pin the sidebar — hide the collapse / hamburger toggle so users can't
   accidentally hide the navbar. Streamlit's collapse button has shifted
   data-testids across versions, so we cover the common variants. The
   sidebar itself stays visible by force, even if its aria-expanded
   attribute were flipped externally.                                   */
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"],
button[kind="headerNoPadding"][aria-label*="sidebar" i] {
    display: none !important;
}
[data-testid="stSidebar"][aria-expanded="false"] {
    transform: translateX(0) !important;
    visibility: visible !important;
    margin-left: 0 !important;
}

/* Layout-ratio locks --------------------------------------------------
   Two things were drifting between viewports and making the page look
   inconsistent:
     1. The sidebar would auto-resize on Streamlit's whim, occasionally
        snapping narrower and squashing nav labels.
     2. The ESG Command Center hero card (rendered via components.v1.html
        into an iframe at fixed height=440px) stretched to whatever the
        viewport offered, which on 27"+ monitors made the IQS gauge
        look isolated in a sea of orange.
   Lock the sidebar to a stable width and cap the main content's max
   width so the proportions match the deployed screenshot regardless of
   monitor size.                                                       */
[data-testid="stSidebar"] {
    min-width: 280px !important;
    max-width: 280px !important;
}
.stApp .block-container {
    max-width: 1440px !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

/* Typography ---------------------------------------------------------- */
html, body, .stApp,
.stMarkdown, .stText, .stCaption,
[data-testid="stMarkdownContainer"], [data-testid="stMarkdown"],
.stButton > button,
.stTextInput input, .stTextArea textarea,
.stSelectbox div[data-baseweb="select"] {
    font-family: var(--font-body);
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    font-feature-settings: 'liga' 1, 'cv11' 1, 'ss01' 1, 'ss03' 1, 'cv03' 1;
}

/* Material icons — MUST stay below scope (do not collapse into block above) */
.material-symbols-rounded, .material-symbols-outlined,
.material-symbols-sharp, .material-icons,
[class*="material-symbols"], [class*="material-icons"] {
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24 !important;
    font-feature-settings: 'liga' 1 !important;
    font-variant-ligatures: common-ligatures contextual !important;
    font-style: normal !important; font-weight: normal !important;
    line-height: 1 !important; letter-spacing: normal !important;
    text-transform: none !important; display: inline-block !important;
    white-space: nowrap !important; direction: ltr !important;
    word-spacing: normal !important; -webkit-font-smoothing: antialiased !important;
}
.material-symbols-rounded   { font-family: 'Material Symbols Rounded'  !important; }
.material-symbols-outlined  { font-family: 'Material Symbols Outlined' !important; }
.material-symbols-sharp     { font-family: 'Material Symbols Sharp'    !important; }
.material-icons             { font-family: 'Material Icons'            !important; }

h1, h2, h3, h4, h5 { font-family: var(--font-display); letter-spacing: -0.018em; color: var(--text); }
h1 { font-weight: 800; line-height: var(--lh-tight); }
h2 { font-weight: 700; line-height: var(--lh-snug); }
h3 { font-weight: 700; line-height: var(--lh-snug); }
h4 { font-weight: 600; line-height: var(--lh-snug); }
code, pre, kbd { font-family: var(--font-mono); }
p, li, .stMarkdown p { color: var(--text-secondary); line-height: var(--lh-relaxed); }

/* Layout container — responsive ---------------------------------------- */
section.main > div.block-container,
[data-testid="stMainBlockContainer"] {
    padding-top: var(--space-3) !important;
    padding-bottom: var(--space-10);
    max-width: 1380px;
}
@media (min-width: 1600px) { section.main > div.block-container { max-width: 1520px; } }
@media (max-width: 1024px) {
    section.main > div.block-container {
        padding-left: var(--space-4); padding-right: var(--space-4);
    }
}
@media (max-width: 768px) {
    section.main > div.block-container { padding-top: var(--space-4); }
    h1 { font-size: var(--text-2xl); }
}

/* L1: Universal focus ring (keyboard accessibility) ------------------- */
button:focus-visible,
[role="button"]:focus-visible,
a:focus-visible,
input:focus-visible, textarea:focus-visible, select:focus-visible,
.esg-agent-card:focus-visible, .esg-chip:focus-visible {
    outline: none;
    box-shadow: var(--ring-focus) !important;
    border-radius: var(--radius-md);
}

/* st.metric refinement ------------------------------------------------ */
[data-testid="stMetric"] {
    background: var(--surface-raised);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: var(--space-4) var(--space-5);
    box-shadow: var(--shadow-xs);
    transition: box-shadow var(--dur-base) var(--ease-standard),
                transform var(--dur-base) var(--ease-standard);
}
[data-testid="stMetric"]:hover {
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}
[data-testid="stMetricLabel"] {
    font-weight: 600; color: var(--text-muted);
    text-transform: uppercase; font-size: var(--text-xs); letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] {
    font-weight: 700; color: var(--text); font-size: var(--text-xl);
    font-family: var(--font-display);
}

/* Buttons ------------------------------------------------------------- */
div.stButton > button {
    transition: transform var(--dur-fast) var(--ease-standard),
                box-shadow var(--dur-fast) var(--ease-standard),
                background var(--dur-fast) var(--ease-standard);
    border-radius: var(--radius-md);
    font-weight: 600;
}
div.stButton > button[kind="primary"] {
    position: relative;
    background: linear-gradient(135deg, var(--pwc-orange) 0%, var(--pwc-tomato) 55%, var(--pwc-amber) 120%);
    background-size: 180% 180%;
    background-position: 0% 0%;
    border: none; color: #fff;
    box-shadow: var(--shadow-brand), inset 0 1px 0 rgba(255, 255, 255, 0.25);
    overflow: hidden;
    transition: transform var(--dur-fast) var(--ease-standard),
                box-shadow var(--dur-fast) var(--ease-standard),
                background-position 600ms var(--ease-standard);
}
div.stButton > button[kind="primary"]::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(120deg, transparent 25%, rgba(255,255,255,0.52) 50%, transparent 75%);
    transform: translateX(-130%);
    transition: transform 550ms var(--ease-standard);
    pointer-events: none;
}
div.stButton > button[kind="primary"]:hover:not(:disabled) {
    transform: translateY(-2px) scale(1.012);
    background-position: 100% 0%;
    box-shadow:
        0 20px 48px rgba(253, 81, 8, 0.55),
        0  6px 16px rgba(253, 81, 8, 0.30),
        inset 0 1px 0 rgba(255, 255, 255, 0.38);
}
div.stButton > button[kind="primary"]:hover:not(:disabled)::after {
    transform: translateX(130%);
}
div.stButton > button[kind="primary"]:active:not(:disabled) {
    transform: translateY(0);
    background: linear-gradient(135deg, var(--pwc-orange-dark) 0%, #7c2d00 100%);
    box-shadow: 0 4px 10px rgba(194, 58, 0, 0.45), inset 0 2px 4px rgba(0, 0, 0, 0.15);
}
div.stButton > button[kind="secondary"] {
    transition:
        transform var(--dur-fast) var(--ease-standard),
        background var(--dur-base) var(--ease-standard),
        border-color var(--dur-base) var(--ease-standard),
        color var(--dur-base) var(--ease-standard),
        box-shadow var(--dur-base) var(--ease-standard);
}
div.stButton > button[kind="secondary"]:hover:not(:disabled) {
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.08), rgba(255, 182, 0, 0.10)) !important;
    border-color: var(--pwc-orange) !important;
    color: var(--pwc-orange-dark) !important;
    transform: translateY(-1px);
    box-shadow: 0 8px 18px rgba(253, 81, 8, 0.14);
}
div.stButton > button[kind="secondary"]:active:not(:disabled) {
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.18), rgba(255, 182, 0, 0.20)) !important;
    transform: translateY(0);
    box-shadow: inset 0 2px 4px rgba(194, 58, 0, 0.15);
}
div.stButton > button[kind="primary"]:active:not(:disabled) {
    transform: translateY(0); box-shadow: var(--shadow-sm);
}
div.stButton > button[kind="secondary"] {
    background: var(--surface); border: 1px solid var(--border-strong); color: var(--text);
}
div.stButton > button[kind="secondary"]:hover:not(:disabled) {
    background: var(--surface-muted); border-color: var(--pwc-orange);
}
div.stButton > button:disabled,
div.stButton > button[disabled] {
    opacity: 0.55; cursor: not-allowed;
    box-shadow: none !important; transform: none !important;
    filter: grayscale(0.4);
}
div.stButton > button[aria-busy="true"] {
    cursor: progress; opacity: 0.85;
}

/* Inputs -------------------------------------------------------------- */
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    border-radius: var(--radius-md) !important;
    border: 1px solid var(--border) !important;
    transition: border-color var(--dur-fast) var(--ease-standard),
                box-shadow var(--dur-fast) var(--ease-standard);
}
.stTextInput input:hover, .stTextArea textarea:hover { border-color: var(--border-strong) !important; }
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
    border-color: var(--pwc-orange) !important;
    box-shadow: var(--ring-focus) !important;
}

/* Tabs (shadcn-pill) -------------------------------------------------- */
div[data-baseweb="tab-list"] { gap: var(--space-1); border-bottom: 1px solid var(--border); }
button[data-baseweb="tab"] {
    border-radius: var(--radius-md) var(--radius-md) 0 0 !important;
    padding: var(--space-3) var(--space-4) !important;
    font-weight: 500;
    transition: background var(--dur-fast) var(--ease-standard);
}
button[data-baseweb="tab"]:hover { background: var(--surface-muted) !important; }
button[data-baseweb="tab"][aria-selected="true"] {
    background: var(--surface-muted) !important;
    color: var(--pwc-orange) !important;
    font-weight: 600 !important;
    box-shadow: inset 0 -2px 0 var(--pwc-orange);
}

/* Dataframe ----------------------------------------------------------- */
[data-testid="stDataFrame"] {
    border: 1px solid var(--border); border-radius: var(--radius-md); overflow: hidden;
    box-shadow: var(--shadow-xs);
}

/* Hero (esg-hero) ----------------------------------------------------- */
.esg-hero {
    position: relative;
    background:
        radial-gradient(1400px 440px at 0% 0%,   rgba(253, 81, 8, 0.22), transparent 60%),
        radial-gradient(1200px 400px at 100% 0%, rgba(255, 182, 0, 0.20), transparent 60%),
        radial-gradient( 900px 340px at 50% 120%, rgba(224, 48, 30, 0.13), transparent 70%),
        linear-gradient(180deg, #fffaf4 0%, #ffffff 100%);
    border: 1px solid rgba(253, 81, 8, 0.18);
    border-radius: var(--radius-xl);
    padding: calc(var(--space-8) + 12px) var(--space-8) var(--space-8);
    margin-bottom: var(--space-6);
    overflow: hidden;
    box-shadow:
        inset 0 1px 0 rgba(255, 255, 255, 0.9),
        0 1px 2px rgba(15, 23, 42, 0.04),
        0 32px 80px rgba(253, 81, 8, 0.18),
        0 0 0 1px rgba(253, 81, 8, 0.06);
}
.esg-hero::before {
    content: ""; position: absolute; inset: -40% -10% auto -10%; height: 80%;
    pointer-events: none; z-index: 0;
    background:
        radial-gradient(360px 220px at 18% 40%, rgba(253, 81, 8, 0.22), transparent 70%),
        radial-gradient(380px 220px at 82% 30%, rgba(255, 182, 0, 0.22), transparent 70%),
        radial-gradient(320px 200px at 52% 80%, rgba(224, 48, 30, 0.18), transparent 70%);
    filter: blur(10px);
    animation: esg-aurora 14s ease-in-out infinite alternate;
}
.esg-hero::after {
    content: ""; position: absolute; inset: 0; pointer-events: none; z-index: 0;
    background-image:
        linear-gradient(to right,  rgba(253, 81, 8, 0.05) 1px, transparent 1px),
        linear-gradient(to bottom, rgba(253, 81, 8, 0.05) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(700px 320px at 50% 40%, rgba(0,0,0,0.35), transparent 75%);
    -webkit-mask-image: radial-gradient(700px 320px at 50% 40%, rgba(0,0,0,0.35), transparent 75%);
    opacity: 0.7;
}
.esg-hero > * { position: relative; z-index: 1; }
@keyframes esg-aurora {
    0%   { transform: translate3d(0, 0, 0) scale(1); }
    50%  { transform: translate3d(-2%, 1%, 0) scale(1.04); }
    100% { transform: translate3d(2%, -1%, 0) scale(1.06); }
}
.esg-hero h1 {
    margin: 0 0 var(--space-3) 0;
    font-size: calc(var(--text-3xl) + 0.35rem);
    line-height: 1.08;
    letter-spacing: -0.028em;
    background: linear-gradient(100deg,
        var(--pwc-orange-dark) 0%,
        var(--pwc-orange) 35%,
        var(--pwc-tomato) 55%,
        var(--pwc-amber) 95%);
    background-size: 200% 100%;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: esg-hero-shine 8s ease-in-out infinite;
}
@keyframes esg-hero-shine {
    0%, 100% { background-position: 0% 50%; }
    50%      { background-position: 100% 50%; }
}
.esg-hero p.esg-subtitle {
    margin: 2px 0 0 0; font-size: calc(var(--text-md) + 0.04rem);
    color: var(--text-secondary); line-height: var(--lh-relaxed); max-width: 920px;
}
.esg-hero .esg-eyebrow {
    display: inline-flex; align-items: center; gap: var(--space-2);
    padding: 6px var(--space-4); border-radius: var(--radius-pill);
    background: rgba(255, 255, 255, 0.72);
    backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(253, 81, 8, 0.30);
    color: var(--pwc-orange-dark);
    font-size: var(--text-xs); font-weight: 700; letter-spacing: 0.06em;
    text-transform: uppercase; margin-bottom: var(--space-4);
    box-shadow: 0 4px 14px rgba(253, 81, 8, 0.14);
}
.esg-hero .esg-eyebrow-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--pwc-orange);
    box-shadow: 0 0 0 3px rgba(253, 81, 8, 0.22);
    animation: esg-pulse 2.4s var(--ease-standard) infinite;
}
.esg-hero .esg-chip {
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(6px); -webkit-backdrop-filter: blur(6px);
    border-color: rgba(253, 81, 8, 0.22);
    font-weight: 600;
}
.esg-hero .esg-chip:hover {
    border-color: rgba(253, 81, 8, 0.45);
    box-shadow: 0 6px 18px rgba(253, 81, 8, 0.14);
}
@media (max-width: 768px) {
    .esg-hero { padding: var(--space-6) var(--space-5); border-radius: var(--radius-lg); }
    .esg-hero h1 { font-size: var(--text-2xl); }
}

/* Stat strip — animated count-up numbers row inside hero -------------- */
.esg-stat-strip {
    display: inline-flex; align-items: stretch;
    margin: var(--space-4) 0 var(--space-3) 0;
    background: rgba(255, 255, 255, 0.76);
    backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(253, 81, 8, 0.20);
    border-radius: var(--radius-pill);
    box-shadow: 0 4px 18px rgba(253, 81, 8, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.95);
    overflow: hidden;
}
.esg-stat-item {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    padding: var(--space-3) var(--space-6); gap: 1px;
    position: relative;
}
.esg-stat-item:not(:last-child)::after {
    content: ""; position: absolute; right: 0; top: 20%; bottom: 20%;
    width: 1px; background: rgba(253, 81, 8, 0.16);
}
.esg-stat-num {
    font-family: var(--font-display);
    font-size: var(--text-2xl); font-weight: 800; line-height: 1;
    letter-spacing: -0.03em;
    background: linear-gradient(135deg, var(--pwc-orange-dark) 0%, var(--pwc-orange) 40%, var(--pwc-amber) 100%);
    background-size: 200% 100%;
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: esg-hero-shine 6s ease-in-out infinite;
}
/* Slot-machine digit reel for count-up animation */
.esg-stat-reel-wrap {
    overflow: hidden;
    height: 1.05em;
    display: inline-flex;
    align-items: flex-start;
}
.esg-stat-reel {
    display: flex; flex-direction: column; align-items: center;
    animation: esg-reel var(--reel-dur, 1.4s) cubic-bezier(0.22, 1, 0.36, 1) var(--reel-delay, 0s) both;
}
@keyframes esg-reel {
    from { transform: translateY(0); }
    to   { transform: translateY(var(--reel-to, 0)); }
}
/* Pop-in for non-numeric stats */
@keyframes esg-stat-pop {
    from { opacity: 0; transform: translateY(6px) scale(0.78); }
    to   { opacity: 1; transform: none; }
}
.esg-stat-pop {
    animation: esg-stat-pop 0.55s cubic-bezier(0.22, 1, 0.36, 1) var(--pop-delay, 0s) both;
}
.esg-stat-label {
    font-size: var(--text-xs); font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.07em;
    color: var(--text-muted);
}

/* PwC header bar ------------------------------------------------------ */
.pwc-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: var(--space-2) 0 var(--space-3) 0;
    margin-bottom: var(--space-2);
    border-bottom: 1px solid rgba(253, 81, 8, 0.18);
}
.pwc-header .pwc-header-brand { display: flex; align-items: center; gap: var(--space-3); }
.pwc-header img.pwc-logo { height: 44px; width: auto; display: block; }
.pwc-header .pwc-header-text { display: flex; flex-direction: column; line-height: 1.1; }
.pwc-header .pwc-header-title {
    font-family: var(--font-display); font-weight: 700;
    font-size: var(--text-base); color: var(--text); letter-spacing: -0.01em;
}
.pwc-header .pwc-header-sub {
    font-size: var(--text-xs); color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.06em; margin-top: 2px;
}
.pwc-header .pwc-accent-bar {
    height: 4px; width: 64px; border-radius: var(--radius-pill);
    background: linear-gradient(90deg, var(--pwc-orange) 0%, var(--pwc-tomato) 55%, var(--pwc-amber) 100%);
    box-shadow: 0 1px 4px rgba(253, 81, 8, 0.30);
}

/* PwC brand header — sidebar variant (navbar top) --------------------- */
/* We render pwc_header() into st.sidebar; Streamlit's default layout     */
/* puts user content BELOW the auto-generated page-nav. To get the brand  */
/* to the true top of the navbar, we flip sibling order with flexbox so   */
/* user content (first child = brand) renders above the nav links.        */
[data-testid="stSidebar"] > div:first-child > div:first-child,
[data-testid="stSidebar"] section[data-testid="stSidebar"] > div:first-child {
    display: flex !important;
    flex-direction: column !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {
    order: 1 !important;                /* brand + HF + auth ABOVE nav   */
    padding-top: 0 !important;
}
[data-testid="stSidebar"] [data-testid="stSidebarNav"] {
    order: 2 !important;                /* page links BELOW brand        */
    padding-top: var(--space-3) !important;
    margin-top: var(--space-3);
}

[data-testid="stSidebar"] .pwc-header-sidebar {
    flex-direction: column; align-items: flex-start;
    padding: var(--space-4) var(--space-3) var(--space-4) var(--space-3);
    margin: 0 calc(var(--space-2) * -1) var(--space-3) calc(var(--space-2) * -1);
    border-bottom: 1px solid rgba(253, 81, 8, 0.22);
    background: linear-gradient(135deg, #ffffff 0%, var(--surface-muted) 100%);
}
[data-testid="stSidebar"] .pwc-header-sidebar .pwc-header-brand {
    width: 100%;
}
[data-testid="stSidebar"] .pwc-header-sidebar img.pwc-logo {
    height: 38px;
}
[data-testid="stSidebar"] .pwc-header-sidebar .pwc-header-title {
    font-family: var(--font-display);
    font-weight: 800;
    font-size: 1.15rem;
    background: linear-gradient(135deg, var(--pwc-orange-dark) 0%, var(--pwc-orange) 45%, var(--pwc-amber) 120%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.025em;
}
/* Tagline in the sidebar: keep the literal string "Powered by PwC India"
   so PwC's brand style (lowercase 'w' in "PwC") is preserved. No
   text-transform or letter-spacing — this is a wordmark, not a label. */
[data-testid="stSidebar"] .pwc-header-sidebar .pwc-header-sub {
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--text-secondary);
    text-transform: none !important;
    letter-spacing: 0;
    margin-top: 3px;
}
[data-testid="stSidebar"] .pwc-header-sidebar .pwc-accent-bar {
    margin-top: var(--space-3);
    width: 48px; height: 3px;
}

/* Chips (status, info) ------------------------------------------------ */
.esg-chip-row { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-3); }
@media (max-width: 640px) {
    .esg-chip-row { flex-wrap: nowrap; overflow-x: auto; -webkit-overflow-scrolling: touch; padding-bottom: 4px; scrollbar-width: none; }
    .esg-chip-row::-webkit-scrollbar { display: none; }
    .esg-chip-row .esg-chip { flex-shrink: 0; }
}
.esg-chip {
    display: inline-flex; align-items: center; gap: var(--space-2);
    padding: 4px var(--space-3); border-radius: var(--radius-pill);
    background: var(--surface); border: 1px solid var(--border);
    font-size: var(--text-sm); font-weight: 500; color: var(--text);
    transition: transform var(--dur-fast) var(--ease-standard),
                box-shadow var(--dur-fast) var(--ease-standard);
}
.esg-chip:hover {
    transform: translateY(-1px);
    border-color: rgba(253, 81, 8, 0.45);
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.06), rgba(255, 182, 0, 0.08));
    color: var(--pwc-orange-dark);
    box-shadow: 0 6px 16px rgba(253, 81, 8, 0.12);
}
.esg-chip:active {
    transform: translateY(0);
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.14), rgba(255, 182, 0, 0.16));
    box-shadow: inset 0 2px 4px rgba(194, 58, 0, 0.12);
}
.esg-chip.status-running   { border-color: var(--status-running);   color: var(--status-running); background: rgba(224, 48, 30, 0.06); }
.esg-chip.status-completed { border-color: var(--status-completed); color: var(--status-completed); background: rgba(46, 133, 64, 0.06); }
.esg-chip.status-error     { border-color: var(--status-error);     color: var(--status-error); background: rgba(200, 16, 46, 0.06); }
.esg-chip.status-warning,
.esg-chip.status-skipped   { border-color: var(--status-warning);   color: #8a5b00; background: rgba(255, 182, 0, 0.10); }
.esg-chip.status-idle      { border-color: var(--status-idle);      color: var(--status-idle); }

/* Section header ------------------------------------------------------ */
.esg-section {
    position: relative;
    display: flex; align-items: baseline; justify-content: space-between;
    gap: var(--space-4);
    margin: var(--space-8) 0 var(--space-4) 0;
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border);
}
.esg-section::after {
    content: ""; position: absolute; left: 0; bottom: -1px;
    width: 72px; height: 3px; border-radius: var(--radius-pill);
    background: linear-gradient(90deg, var(--pwc-orange) 0%, var(--pwc-tomato) 55%, var(--pwc-amber) 100%);
    box-shadow: 0 2px 8px rgba(253, 81, 8, 0.35);
}
.esg-section .esg-section-title {
    font-family: var(--font-display);
    font-size: calc(var(--text-lg) + 0.08rem);
    font-weight: 700; color: var(--text); letter-spacing: -0.018em;
}
.esg-section .esg-section-caption { font-size: var(--text-sm); color: var(--text-muted); }
@media (max-width: 768px) { .esg-section { flex-direction: column; align-items: flex-start; gap: var(--space-1); } }

/* Grade pill ---------------------------------------------------------- */
.esg-grade-pill {
    display: inline-flex; align-items: center;
    padding: 3px var(--space-3); border-radius: var(--radius-sm);
    font-weight: 700; font-size: var(--text-base); color: #fff;
    box-shadow: var(--shadow-xs);
}

/* Status dot — pulses while running ----------------------------------- */
.esg-status-dot {
    width: 9px; height: 9px; border-radius: 50%;
    display: inline-block; vertical-align: middle;
    background: var(--status-idle);
}
.esg-status-dot.status-running {
    background: var(--status-running);
    animation: esg-pulse 1.6s var(--ease-standard) infinite;
}
.esg-status-dot.status-completed { background: var(--status-completed); }
.esg-status-dot.status-error     { background: var(--status-error); }
.esg-status-dot.status-warning,
.esg-status-dot.status-skipped   { background: var(--status-warning); }
@keyframes esg-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(224, 48, 30, 0.55); }
    70%  { box-shadow: 0 0 0 8px rgba(224, 48, 30, 0); }
    100% { box-shadow: 0 0 0 0 rgba(224, 48, 30, 0); }
}

/* Agent card ---------------------------------------------------------- */
.esg-agent-card {
    background: var(--surface-raised);
    border: 1px solid var(--border); border-left-width: 4px;
    border-radius: var(--radius-md);
    padding: var(--space-4) var(--space-4) var(--space-3);
    height: 100%;
    display: flex; flex-direction: column; gap: var(--space-2);
    transition: box-shadow var(--dur-base) var(--ease-standard),
                transform var(--dur-base) var(--ease-standard),
                border-color var(--dur-base) var(--ease-standard);
}
.esg-agent-card:hover {
    box-shadow:
        0 18px 36px rgba(253, 81, 8, 0.14),
        0 2px 6px rgba(15, 23, 42, 0.05);
    transform: translateY(-3px);
    border-color: rgba(253, 81, 8, 0.30);
    border-left-color: var(--pwc-orange) !important;
}
.esg-agent-card:active {
    transform: translateY(-1px);
    box-shadow: 0 8px 18px rgba(253, 81, 8, 0.14), inset 0 2px 4px rgba(194, 58, 0, 0.08);
}
.esg-agent-card.status-running {
    border-color: var(--status-running);
    background: linear-gradient(180deg, rgba(224, 48, 30, 0.05), var(--surface-raised) 60%);
    animation: esg-running-pulse 2.2s ease-in-out infinite;
}
@keyframes esg-running-pulse {
    0%, 100% { box-shadow: 0 0 0 0   rgba(253, 81, 8, 0.10), 0  6px 16px rgba(253, 81, 8, 0.08); }
    50%      { box-shadow: 0 0 0 8px rgba(253, 81, 8, 0.05), 0 18px 36px rgba(253, 81, 8, 0.22); }
}
.esg-agent-card.status-error {
    border-color: var(--status-error);
    background: linear-gradient(180deg, rgba(200, 16, 46, 0.05), var(--surface-raised) 60%);
}
.esg-agent-card.status-completed {
    background: linear-gradient(180deg, rgba(46, 133, 64, 0.04), var(--surface-raised) 60%);
}
/* Shimmer sweep on idle cards */
@keyframes esg-shimmer {
    0%   { background-position: -500px 0; }
    100% { background-position:  500px 0; }
}
.esg-agent-card.status-idle { position: relative; overflow: hidden; }
.esg-agent-card.status-idle::after {
    content: ""; position: absolute; inset: 0;
    background: linear-gradient(
        90deg,
        transparent 20%,
        rgba(253, 81, 8, 0.07) 50%,
        transparent 80%
    );
    background-size: 500px 100%;
    animation: esg-shimmer 2.8s ease-in-out infinite;
    pointer-events: none; border-radius: inherit;
}
.esg-agent-card .esg-agent-head {
    display: flex; align-items: center; justify-content: space-between; gap: var(--space-2);
}
.esg-agent-card .esg-agent-title {
    font-weight: 600; font-size: var(--text-base);
    display: flex; align-items: center; gap: var(--space-2);
    color: var(--text);
}
.esg-agent-card .esg-agent-status {
    font-size: var(--text-xs); font-weight: 600;
    text-transform: uppercase; letter-spacing: 0.05em;
    display: inline-flex; align-items: center; gap: 6px;
}
.esg-agent-card .esg-agent-meta {
    font-size: var(--text-xs); color: var(--text-muted);
    display: flex; flex-wrap: wrap; gap: var(--space-3);
}
.esg-agent-card .esg-agent-meta span { display: inline-flex; align-items: center; gap: 4px; }
.esg-agent-card .esg-agent-error {
    font-size: var(--text-xs); color: var(--status-error);
    background: rgba(200, 16, 46, 0.06);
    border: 1px solid rgba(200, 16, 46, 0.18);
    border-radius: var(--radius-sm);
    padding: 6px var(--space-2);
    font-family: var(--font-mono);
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}

/* KPI delta indicator ------------------------------------------------- */
.esg-kpi-delta {
    display: inline-flex; align-items: center; gap: 4px;
    font-size: var(--text-xs); font-weight: 600;
    padding: 2px var(--space-2); border-radius: var(--radius-sm);
}
.esg-kpi-delta.positive { color: var(--pwc-success); background: rgba(46, 133, 64, 0.10); }
.esg-kpi-delta.negative { color: var(--pwc-danger);  background: rgba(200, 16, 46, 0.10); }
.esg-kpi-delta.neutral  { color: var(--text-muted);  background: rgba(91, 100, 115, 0.10); }

/* Live badge — animated dot for streaming surfaces -------------------- */
.esg-live-badge {
    display: inline-flex; align-items: center; gap: var(--space-2);
    padding: 4px var(--space-3); border-radius: var(--radius-pill);
    background: rgba(46, 133, 64, 0.10); color: var(--pwc-success);
    border: 1px solid rgba(46, 133, 64, 0.30);
    font-size: var(--text-xs); font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;
}
.esg-live-badge .esg-status-dot { background: var(--pwc-success); animation: esg-pulse 1.6s infinite; }

/* Top status strip (like the dashboard mockup's system-status row) ---- */
.esg-statusbar {
    display: flex; align-items: center; justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    margin: 0 0 var(--space-5) 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background:
        linear-gradient(90deg, rgba(255, 250, 244, 0.95) 0%, #ffffff 100%);
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 10px 24px rgba(253, 81, 8, 0.06);
}
.esg-statusbar .esg-statusbar-left {
    display: flex; align-items: center; gap: var(--space-3); flex: 1; min-width: 0;
}
.esg-statusbar .esg-statusbar-right {
    display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap;
}
.esg-statusbar .esg-sb-search {
    display: inline-flex; align-items: center; gap: var(--space-2);
    padding: 8px var(--space-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    background: #ffffff; color: var(--text-muted);
    font-size: var(--text-sm); font-family: var(--font-body);
    min-width: 260px; max-width: 420px; flex: 1;
    transition: border-color var(--dur-base) var(--ease-standard),
                box-shadow var(--dur-base) var(--ease-standard);
}
.esg-statusbar .esg-sb-search:hover {
    border-color: var(--pwc-orange);
    box-shadow: 0 4px 12px rgba(253, 81, 8, 0.10);
}
.esg-statusbar .esg-sb-search kbd {
    margin-left: auto;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: 1px 6px; border-radius: var(--radius-xs);
    border: 1px solid var(--border);
    background: var(--surface-muted);
    color: var(--text-muted);
}
.esg-statusbar .esg-sb-chip {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px var(--space-3); border-radius: var(--radius-pill);
    background: linear-gradient(135deg, rgba(46, 133, 64, 0.08), rgba(46, 133, 64, 0.14));
    border: 1px solid rgba(46, 133, 64, 0.30);
    color: var(--pwc-success);
    font-size: var(--text-xs); font-weight: 700; letter-spacing: 0.04em;
    transition: transform var(--dur-fast) var(--ease-standard),
                box-shadow var(--dur-base) var(--ease-standard);
}
.esg-statusbar .esg-sb-chip:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 14px rgba(46, 133, 64, 0.18);
}
.esg-statusbar .esg-sb-chip .esg-status-dot {
    background: var(--pwc-success); animation: esg-pulse 1.8s infinite;
}
.esg-statusbar .esg-sb-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: var(--radius-md);
    background: #ffffff; border: 1px solid var(--border);
    color: var(--text-secondary); font-size: 1rem;
    transition: background var(--dur-base) var(--ease-standard),
                border-color var(--dur-base) var(--ease-standard),
                transform var(--dur-fast) var(--ease-standard),
                color var(--dur-base) var(--ease-standard);
    cursor: pointer; position: relative;
}
.esg-statusbar .esg-sb-icon:hover {
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.08), rgba(255, 182, 0, 0.10));
    border-color: var(--pwc-orange);
    color: var(--pwc-orange-dark);
    transform: translateY(-1px);
}
.esg-statusbar .esg-sb-icon .esg-sb-badge {
    position: absolute; top: -2px; right: -2px;
    min-width: 14px; height: 14px; padding: 0 4px;
    border-radius: 999px;
    background: linear-gradient(135deg, var(--pwc-orange), var(--pwc-tomato));
    color: #fff; font-size: 9px; font-weight: 700; line-height: 1;
    display: inline-flex; align-items: center; justify-content: center;
    box-shadow: 0 2px 6px rgba(253, 81, 8, 0.40),
                0 0 0 2px #ffffff;
}
.esg-statusbar .esg-sb-avatar {
    width: 36px; height: 36px; border-radius: 50%;
    background: linear-gradient(135deg, var(--pwc-orange) 0%, var(--pwc-tomato) 60%, var(--pwc-amber) 120%);
    color: #fff; font-weight: 700; font-family: var(--font-display);
    display: inline-flex; align-items: center; justify-content: center;
    box-shadow: 0 6px 14px rgba(253, 81, 8, 0.30), inset 0 1px 0 rgba(255,255,255,0.35);
    transition: transform var(--dur-fast) var(--ease-standard),
                box-shadow var(--dur-base) var(--ease-standard);
    cursor: pointer;
}
.esg-statusbar .esg-sb-avatar:hover {
    transform: translateY(-1px) scale(1.03);
    box-shadow: 0 10px 22px rgba(253, 81, 8, 0.42);
}
@media (max-width: 900px) {
    .esg-statusbar { flex-direction: column; align-items: stretch; }
    .esg-statusbar .esg-sb-search { max-width: 100%; }
}

/* Progress bar — gradient + breathing glow ---------------------------- */
@keyframes esg-progress-glow {
    from { box-shadow: 0 0  6px rgba(253, 81, 8, 0.28), 0 2px  8px rgba(253, 81, 8, 0.14); }
    to   { box-shadow: 0 0 20px rgba(253, 81, 8, 0.58), 0 2px 16px rgba(253, 81, 8, 0.32); }
}
[data-testid="stProgress"] div[role="progressbar"],
[data-testid="stProgress"] > div:first-child {
    background: rgba(253, 81, 8, 0.10) !important;
    border-radius: 999px !important;
    height: 8px !important;
    overflow: visible !important;
}
[data-testid="stProgress"] div[role="progressbar"] > div,
[data-testid="stProgress"] > div:first-child > div {
    background: linear-gradient(
        90deg,
        var(--pwc-orange)      0%,
        var(--pwc-tomato)     40%,
        var(--pwc-amber)     100%
    ) !important;
    border-radius: 999px !important;
    height: 100% !important;
    animation: esg-progress-glow 1.6s ease-in-out infinite alternate !important;
    transition: width 0.4s ease-out !important;
    min-width: 8px !important;
}

/* Activity log — terminal-style live ticker --------------------------- */
@keyframes esg-log-entry {
    from { opacity: 0; transform: translateX(-5px); background: rgba(253, 81, 8, 0.06); }
    to   { opacity: 1; transform: translateX(0);    background: transparent; }
}
.esg-log-shell {
    background: linear-gradient(180deg, #fdf8f3 0%, var(--surface-sunken) 100%);
    border: 1px solid rgba(253, 81, 8, 0.18);
    border-left: 3px solid var(--pwc-orange);
    border-radius: var(--radius-md);
    padding: var(--space-3); max-height: 380px; overflow-y: auto;
    font-family: var(--font-mono); font-size: var(--text-xs);
    box-shadow:
        inset 0 1px 3px rgba(253, 81, 8, 0.05),
        0 8px 24px rgba(253, 81, 8, 0.07),
        0 1px 2px rgba(15, 23, 42, 0.04);
}
.esg-log-row {
    display: grid; grid-template-columns: 110px 90px 1fr;
    gap: var(--space-3); padding: 6px var(--space-2);
    border-radius: var(--radius-xs);
    border-bottom: 1px solid rgba(253, 81, 8, 0.07);
    transition: background var(--dur-fast) var(--ease-standard);
}
.esg-log-row:last-child { border-bottom: none; animation: esg-log-entry 0.30s ease-out; }
.esg-log-row:hover { background: rgba(253, 81, 8, 0.04); }
.esg-log-row .esg-log-time { color: var(--text-muted); }
.esg-log-row .esg-log-tag  { font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; }
.esg-log-row .esg-log-tag.info    { color: var(--pwc-info); }
.esg-log-row .esg-log-tag.success { color: var(--pwc-success); }
.esg-log-row .esg-log-tag.warning { color: #8a5b00; }
.esg-log-row .esg-log-tag.error   { color: var(--pwc-danger); }
.esg-log-row .esg-log-msg  { color: var(--text); white-space: pre-wrap; word-break: break-word; }
@media (max-width: 768px) {
    .esg-log-row { grid-template-columns: 1fr; gap: 2px; }
}

/* Sparkline SVG ------------------------------------------------------- */
.esg-sparkline { display: block; width: 100%; height: 36px; }

/* Scrollbar refinement (webkit) --------------------------------------- */
.esg-log-shell::-webkit-scrollbar { width: 8px; height: 8px; }
.esg-log-shell::-webkit-scrollbar-thumb {
    background: var(--border-strong); border-radius: var(--radius-pill);
}
.esg-log-shell::-webkit-scrollbar-track { background: transparent; }
</style>
"""

_GLOBAL_CSS = _TOKEN_CSS + _STATIC_CSS


# ---------------------------------------------------------------------------
# Injection
# ---------------------------------------------------------------------------
def inject_global_css() -> None:
    """Inject font links + token + static CSS. Cheap; safe to call repeatedly."""
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
# PwC header
# ---------------------------------------------------------------------------
_PWC_LOGO_CANDIDATES = ("pwc_logo.png", "assets/pwc_logo.png", "static/pwc_logo.png")


@st.cache_data(show_spinner=False)
def _pwc_logo_data_uri() -> str:
    here = Path(__file__).resolve().parent
    for root in (here.parent, here.parent.parent, Path.cwd()):
        for rel in _PWC_LOGO_CANDIDATES:
            p = root / rel
            if p.is_file():
                try:
                    encoded = base64.b64encode(p.read_bytes()).decode("ascii")
                    return f"data:image/png;base64,{encoded}"
                except Exception:
                    continue
    return ""


PRODUCT_NAME = "ESG Intelligence Hub"
PRODUCT_TAGLINE = "Command your ESG strategy with real-time intelligence and action."


def pwc_header(
    product: str = PRODUCT_NAME,
    tagline: str = PRODUCT_TAGLINE,
    sidebar_tagline: str = "Powered by PwC India",  # kept for API compat; unused
) -> None:
    """Brand header — renders the PwC lock-up + product name + tagline as a
    top banner on every page's main content area.

    The sidebar stays reserved for navigation + auth widgets; the brand
    lives at the top of the page so it's the first thing a user reads.
    """
    inject_global_css()
    skip_link()
    logo_uri = _pwc_logo_data_uri()
    topbar_logo = (
        f'<img class="esg-topbar-logo" src="{logo_uri}" alt="PwC"/>'
        if logo_uri else ""
    )
    st.markdown(
        f'<div class="esg-topbar" role="banner">'
        f'  <div class="esg-topbar-brand">{topbar_logo}'
        f'    <div class="esg-topbar-text">'
        f'      <span class="esg-topbar-title">{html.escape(product)}</span>'
        f'      <span class="esg-topbar-tagline">{html.escape(tagline)}</span>'
        f'    </div>'
        f'  </div>'
        f'  <div class="esg-topbar-accent" aria-hidden="true"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def skip_link(target_id: str = "main") -> None:
    """L4: Render an offscreen 'Skip to main content' link visible on focus."""
    st.markdown(
        f'<a class="esg-skip-link" href="#{html.escape(target_id)}">Skip to main content</a>',
        unsafe_allow_html=True,
    )


def _derive_system_status(statuses: Optional[dict]) -> tuple[str, str, str]:
    """Given a Mission-Control-style statuses dict, return (tone, label, icon).

    tone ∈ {'idle','running','completed','error','warning'} — drives the pill
    color via existing `status-*` classes. Label is the human copy.
    """
    if not statuses:
        return "idle", "All systems ready", "●"
    total = len(statuses)
    running, completed, errored, warning = 0, 0, 0, 0
    for v in statuses.values():
        s = ((v or {}).get("status") or "idle").lower()
        if s == "running":
            running += 1
        elif s == "completed":
            completed += 1
        elif s == "error":
            errored += 1
        elif s in ("warning", "skipped"):
            warning += 1
    if errored:
        return "error", f"{errored} agent{'s' if errored != 1 else ''} errored · {total - errored} healthy", "⚠"
    if running:
        return "running", f"{running}/{total} agent{'s' if total != 1 else ''} running", "●"
    if completed == total and total > 0:
        return "completed", f"All {total} agents completed", "✓"
    if warning:
        return "warning", f"{warning} warning{'s' if warning != 1 else ''} · {total - warning} clean", "●"
    return "idle", "All systems ready", "●"


def statusbar(
    *,
    search_placeholder: str = "Search anything…",
    statuses: Optional[dict] = None,
    system_label: str = "System Status",
    system_value: Optional[str] = None,
    tone: Optional[str] = None,
    notifications: int = 0,
    avatar_initial: str = "S",
) -> None:
    """Render a top status strip — search + LIVE system pill + notif + avatar.

    Pass ``statuses`` (same shape as ESG Command Center's ``orch.get_agent_statuses()``)
    and the pill will automatically reflect live agent state: running counts,
    errors, completions, or a neutral ready state. Animated pulse conveys
    liveness. If ``statuses`` is omitted, ``system_value``/``tone`` can be
    used for a static override.
    """
    inject_global_css()
    if statuses is not None or system_value is None:
        auto_tone, auto_value, _ = _derive_system_status(statuses)
        final_tone = tone or auto_tone
        final_value = system_value or auto_value
    else:
        final_tone = tone or "idle"
        final_value = system_value

    # Pill background + dot color per tone
    tone_bg = {
        "running":   "linear-gradient(135deg, rgba(224, 48, 30, 0.08), rgba(224, 48, 30, 0.16))",
        "completed": "linear-gradient(135deg, rgba(46, 133, 64, 0.08), rgba(46, 133, 64, 0.16))",
        "error":     "linear-gradient(135deg, rgba(200, 16, 46, 0.08), rgba(200, 16, 46, 0.18))",
        "warning":   "linear-gradient(135deg, rgba(255, 182, 0, 0.10), rgba(255, 182, 0, 0.22))",
        "idle":      "linear-gradient(135deg, rgba(46, 133, 64, 0.06), rgba(46, 133, 64, 0.14))",
    }.get(final_tone, "linear-gradient(135deg, rgba(46, 133, 64, 0.06), rgba(46, 133, 64, 0.14))")
    tone_fg = _STATUS_COLORS.get(final_tone, TOKENS["brand_success"])
    tone_border = {
        "running":   "rgba(224, 48, 30, 0.35)",
        "completed": "rgba(46, 133, 64, 0.35)",
        "error":     "rgba(200, 16, 46, 0.40)",
        "warning":   "rgba(255, 182, 0, 0.45)",
        "idle":      "rgba(46, 133, 64, 0.30)",
    }.get(final_tone, "rgba(46, 133, 64, 0.30)")

    badge = (
        f'<span class="esg-sb-badge">{int(notifications)}</span>'
        if notifications and notifications > 0 else ""
    )
    st.markdown(
        f'''
        <div class="esg-statusbar" role="region" aria-label="System chrome">
            <div class="esg-statusbar-left">
                <div class="esg-sb-search" role="search">
                    <span aria-hidden="true">🔍</span>
                    <span>{html.escape(search_placeholder)}</span>
                    <kbd>⌘K</kbd>
                </div>
            </div>
            <div class="esg-statusbar-right">
                <span class="esg-sb-chip status-{html.escape(final_tone)}"
                      role="status" aria-live="polite"
                      style="background:{tone_bg}; color:{tone_fg}; border-color:{tone_border};">
                    <span class="esg-status-dot status-{html.escape(final_tone)}" aria-hidden="true"
                          style="background:{tone_fg};"></span>
                    {html.escape(system_label)} · {html.escape(final_value)}
                </span>
                <span class="esg-sb-icon" role="button" tabindex="0" aria-label="Notifications">
                    🔔{badge}
                </span>
                <span class="esg-sb-avatar" role="img" aria-label="Account">
                    {html.escape(avatar_initial[:1].upper())}
                </span>
            </div>
        </div>
        ''',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Per-page agent status header — user + current agent + live status
# ---------------------------------------------------------------------------
_PAGE_HEADER_CSS = """
<style>
.esg-page-header {
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center; gap: var(--space-5);
    padding: var(--space-3) var(--space-5);
    margin: 0 0 var(--space-5) 0;
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    background:
        linear-gradient(90deg, #ffffff 0%, var(--surface-muted) 100%);
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04),
                0 10px 24px rgba(253, 81, 8, 0.06);
}
.esg-page-header .ph-user {
    display: flex; align-items: center; gap: var(--space-3);
    min-width: 0;
}
.esg-page-header .ph-avatar {
    flex-shrink: 0;
    width: 42px; height: 42px; border-radius: 50%;
    background: linear-gradient(135deg, var(--pwc-orange) 0%, var(--pwc-tomato) 60%, var(--pwc-amber) 130%);
    color: #fff; font-weight: 800; font-family: var(--font-display);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1rem;
    box-shadow: 0 6px 14px rgba(253, 81, 8, 0.32), inset 0 1px 0 rgba(255,255,255,0.35);
}
.esg-page-header .ph-who {
    display: flex; flex-direction: column; line-height: 1.15; min-width: 0;
}
.esg-page-header .ph-greeting {
    font-size: var(--text-xs); color: var(--text-muted);
    letter-spacing: 0.05em; text-transform: uppercase; font-weight: 600;
}
.esg-page-header .ph-name {
    font-family: var(--font-display);
    font-weight: 700; color: var(--text); font-size: var(--text-md);
    letter-spacing: -0.015em;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    max-width: 220px;
}
.esg-page-header .ph-agent {
    display: flex; align-items: center; gap: var(--space-3);
    justify-self: center;
}
.esg-page-header .ph-agent-icon {
    width: 38px; height: 38px; border-radius: var(--radius-md);
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.14), rgba(255, 182, 0, 0.22));
    color: var(--pwc-orange-dark);
    border: 1px solid rgba(253, 81, 8, 0.25);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.15rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}
.esg-page-header .ph-agent-text {
    display: flex; flex-direction: column; line-height: 1.1;
}
.esg-page-header .ph-agent-label {
    font-size: var(--text-xs); color: var(--text-muted);
    letter-spacing: 0.07em; text-transform: uppercase; font-weight: 700;
}
.esg-page-header .ph-agent-name {
    font-family: var(--font-display);
    font-weight: 700; color: var(--text); font-size: var(--text-md);
    letter-spacing: -0.015em;
}
.esg-page-header .ph-status {
    display: flex; align-items: center; gap: var(--space-3);
}
.esg-page-header .ph-chip {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px var(--space-3); border-radius: var(--radius-pill);
    font-size: var(--text-xs); font-weight: 800; letter-spacing: 0.06em;
    text-transform: uppercase;
    border: 1px solid;
    transition: transform var(--dur-fast) var(--ease-standard);
}
.esg-page-header .ph-chip:hover { transform: translateY(-1px); }
.esg-page-header .ph-chip.running {
    background: linear-gradient(135deg, rgba(253, 81, 8, 0.10), rgba(253, 81, 8, 0.20));
    color: var(--pwc-orange-dark); border-color: rgba(253, 81, 8, 0.40);
}
.esg-page-header .ph-chip.completed,
.esg-page-header .ph-chip.idle {
    background: linear-gradient(135deg, rgba(46, 133, 64, 0.08), rgba(46, 133, 64, 0.18));
    color: var(--pwc-success); border-color: rgba(46, 133, 64, 0.35);
}
.esg-page-header .ph-chip.error {
    background: linear-gradient(135deg, rgba(200, 16, 46, 0.10), rgba(200, 16, 46, 0.22));
    color: var(--pwc-danger); border-color: rgba(200, 16, 46, 0.42);
}
.esg-page-header .ph-chip.warning {
    background: linear-gradient(135deg, rgba(255, 182, 0, 0.12), rgba(255, 182, 0, 0.25));
    color: #8a5b00; border-color: rgba(255, 182, 0, 0.45);
}
.esg-page-header .ph-meta {
    display: flex; flex-direction: column; line-height: 1.15; text-align: right;
}
.esg-page-header .ph-meta .m-key {
    font-size: var(--text-xs); color: var(--text-muted);
    letter-spacing: 0.05em; text-transform: uppercase; font-weight: 600;
}
.esg-page-header .ph-meta .m-val {
    font-family: var(--font-mono);
    font-size: var(--text-sm); color: var(--text); font-weight: 600;
}
@media (max-width: 900px) {
    .esg-page-header {
        grid-template-columns: 1fr;
        row-gap: var(--space-3);
    }
    .esg-page-header .ph-agent { justify-self: flex-start; }
    .esg-page-header .ph-meta { text-align: left; }
    .esg-page-header .ph-name { max-width: 100%; }
}
</style>
"""


def _resolve_user_display(user: Optional[dict]) -> tuple[str, str, str]:
    """Return (greeting, display_name, initials) for a current_user() dict."""
    if not user:
        return "Guest session", "Not signed in", "·"
    name = (user.get("full_name") or user.get("username") or "").strip()
    role = (user.get("role") or "").strip() or "Member"
    if not name:
        return "Guest session", "Not signed in", "·"
    display = f"{name} · {role.title()}"
    initials = "".join(part[:1] for part in name.split()[:2]).upper() or name[:1].upper()
    return "Signed in", display, initials


def page_agent_header(
    *,
    agent_key: Optional[str] = None,
    agent_icon: str = "🤖",
    agent_display_name: Optional[str] = None,
    user: Optional[dict] = None,
    statuses: Optional[dict] = None,
) -> None:
    """Top-of-page strip: signed-in user + current agent + live status pill.

    ``agent_key`` matches the orchestrator key ("data_collector", "roi_agent",
    etc.). When ``statuses`` isn't supplied, the helper pulls live status from
    ``st.session_state.orchestrator.get_agent_statuses()`` — so the pill
    reflects the real agent state at this moment.

    Pass ``agent_key=None`` to render the header as a user-greeting only
    (useful on Sign-In / Settings / Home-like pages).
    """
    inject_global_css()
    st.markdown(_PAGE_HEADER_CSS, unsafe_allow_html=True)

    # If the caller didn't hand us a user dict, try to look it up. Keeps
    # page call sites tidy — they only need to pass the agent_key/icon.
    if user is None:
        try:
            from utils.auth import current_user as _cu
            user = _cu()
        except Exception:
            user = None

    greeting, display_name, initials = _resolve_user_display(user)

    # --- Live status lookup ---
    meta: dict = {}
    if agent_key:
        if statuses is None:
            orch = st.session_state.get("orchestrator")
            if orch is not None:
                try:
                    statuses = orch.get_agent_statuses()
                except Exception:
                    statuses = None
        if statuses and agent_key in statuses:
            meta = statuses[agent_key] or {}

    status_raw = str(meta.get("status") or "idle").lower()
    status_label = {
        "running":   "RUNNING",
        "error":     "ERROR",
        "completed": "READY",
        "idle":      "READY",
        "warning":   "WARNING",
    }.get(status_raw, "READY")
    dot_extra = "running" if status_raw == "running" else status_raw

    last_run_rel = format_relative_time(meta.get("last_run") or "Never")
    runtime = format_duration(meta.get("runtime_seconds"))
    run_count = meta.get("run_count") or 0

    # Assemble agent block (only when we're on an agent-specific page)
    agent_html = ""
    if agent_key:
        name = html.escape(agent_display_name or meta.get("name") or agent_key.replace("_", " ").title())
        agent_html = (
            f'<div class="ph-agent">'
            f'  <span class="ph-agent-icon">{html.escape(agent_icon)}</span>'
            f'  <div class="ph-agent-text">'
            f'    <span class="ph-agent-label">Current agent</span>'
            f'    <span class="ph-agent-name">{name}</span>'
            f'  </div>'
            f'</div>'
        )

    # Right-side status + metadata. When there's no agent context we still
    # show a "Ready" session chip so the bar never feels empty.
    right_html = (
        f'<div class="ph-status">'
        f'  <span class="ph-chip {dot_extra}">'
        f'    <span class="esg-status-dot status-{dot_extra}" aria-hidden="true"></span>'
        f'    {status_label}'
        f'  </span>'
        f'  <div class="ph-meta">'
        f'    <span class="m-key">Last run</span>'
        f'    <span class="m-val">{html.escape(last_run_rel)}</span>'
        f'  </div>'
        f'  <div class="ph-meta">'
        f'    <span class="m-key">Runtime</span>'
        f'    <span class="m-val">{html.escape(runtime)}</span>'
        f'  </div>'
        f'  <div class="ph-meta">'
        f'    <span class="m-key">Runs</span>'
        f'    <span class="m-val">{int(run_count)}</span>'
        f'  </div>'
        f'</div>'
    )

    st.markdown(
        f'<div class="esg-page-header" role="region" aria-label="Session and agent status">'
        f'  <div class="ph-user">'
        f'    <span class="ph-avatar">{html.escape(initials)}</span>'
        f'    <div class="ph-who">'
        f'      <span class="ph-greeting">{html.escape(greeting)}</span>'
        f'      <span class="ph-name">{html.escape(display_name)}</span>'
        f'    </div>'
        f'  </div>'
        f'  {agent_html}'
        f'  {right_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def page_agent_header_live(
    *,
    agent_key: Optional[str] = None,
    agent_icon: str = "🤖",
    agent_display_name: Optional[str] = None,
    user: Optional[dict] = None,
) -> None:
    """Fragment-wrapped variant of ``page_agent_header``. Auto-refreshes every
    2 s while the bound agent is actively running; renders once otherwise.
    Drop-in replacement for the static helper on pages that care about
    real-time status during a pipeline run.
    """
    # Decide whether we need ticks by inspecting the current status once.
    interval: Optional[int] = None
    if agent_key is not None:
        try:
            orch = st.session_state.get("orchestrator")
            if orch is not None:
                s = orch.get_agent_statuses() or {}
                if s.get(agent_key, {}).get("status") == "running":
                    interval = 2
        except Exception:
            pass

    try:
        @st.fragment(run_every=interval)
        def _render() -> None:
            page_agent_header(
                agent_key=agent_key,
                agent_icon=agent_icon,
                agent_display_name=agent_display_name,
                user=user,
            )
        _render()
    except TypeError:
        # Fallback for older Streamlit without fragment(run_every=...)
        page_agent_header(
            agent_key=agent_key,
            agent_icon=agent_icon,
            agent_display_name=agent_display_name,
            user=user,
        )


# ---------------------------------------------------------------------------
# Hero
# ---------------------------------------------------------------------------
def hero(
    title: str,
    subtitle: Optional[str] = None,
    chips: Optional[Sequence[str]] = None,
    *,
    emoji: str = "",
    eyebrow: Optional[str] = None,
    stats: Optional[Sequence[tuple]] = None,
) -> None:
    """Render the branded hero banner.

    ``stats`` accepts a list of ``(value, label)`` tuples, e.g.
    ``[("9", "Agents"), ("6", "Frameworks"), ("<60s", "Pipeline")]``.
    Pure-integer values animate with a CSS count-up; others display statically.
    """
    inject_global_css()
    safe_title = html.escape(title)
    prefix = f"{emoji} " if emoji else ""
    subtitle_html = (
        f'<p class="esg-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    chip_html = ""
    if chips:
        chip_items = "".join(f'<span class="esg-chip">{html.escape(c)}</span>' for c in chips)
        chip_html = f'<div class="esg-chip-row" role="list">{chip_items}</div>'
    eyebrow_html = ""
    if eyebrow:
        eyebrow_html = (
            f'<span class="esg-eyebrow" role="status">'
            f'<span class="esg-eyebrow-dot" aria-hidden="true"></span>{html.escape(eyebrow)}'
            f'</span>'
        )

    # Build stat strip — slot-machine reel for integers, pop-in for others
    stat_items_html = ""
    if stats:
        for i, (val, label) in enumerate(stats):
            v_str = str(val).strip()
            delay = f"{0.20 + i * 0.14:.2f}s"
            if v_str.isdigit():
                # Build a vertical digit reel for each character in the number.
                # Each character slot scrolls from "0" down to the target digit.
                digit_reels = ""
                for ch in v_str:
                    d = int(ch)
                    # Stack digits 0→d, clip to one line height, animate translateY
                    # from 0 to -(d * 100)% so the reel stops on the right digit.
                    digits_stack = "".join(f"<span>{k}</span>" for k in range(d + 1))
                    to_pct = f"{-d * 100}%"
                    digit_reels += (
                        f'<span class="esg-stat-reel-wrap">'
                        f'<span class="esg-stat-reel" '
                        f'style="--reel-to:{to_pct};--reel-dur:1.35s;--reel-delay:{delay};">'
                        f'{digits_stack}'
                        f'</span></span>'
                    )
                num_html = (
                    f'<span class="esg-stat-num" aria-label="{v_str}" '
                    f'style="display:inline-flex;align-items:baseline;">'
                    f'{digit_reels}</span>'
                )
            else:
                num_html = (
                    f'<span class="esg-stat-num esg-stat-pop" '
                    f'style="--pop-delay:{delay}" aria-label="{v_str}">'
                    f'{html.escape(v_str)}</span>'
                )
            stat_items_html += (
                f'<div class="esg-stat-item">'
                f'{num_html}'
                f'<span class="esg-stat-label">{html.escape(str(label))}</span>'
                f'</div>'
            )
        stat_strip_html = f'<div class="esg-stat-strip">{stat_items_html}</div>'
    else:
        stat_strip_html = ""

    st.markdown(
        f'<div class="esg-hero" role="region" aria-label="{safe_title}">'
        f'{eyebrow_html}<h1>{prefix}{safe_title}</h1>{subtitle_html}'
        f'{stat_strip_html}{chip_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Section header
# ---------------------------------------------------------------------------
def section_header(title: str, caption: Optional[str] = None) -> None:
    inject_global_css()
    cap = (
        f'<span class="esg-section-caption">{html.escape(caption)}</span>' if caption else ""
    )
    st.markdown(
        f'<div class="esg-section">'
        f'<span class="esg-section-title">{html.escape(title)}</span>{cap}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# KPI card — extended with trend / sparkline / delta_kind
# ---------------------------------------------------------------------------
def _sparkline_svg(values: Sequence[float], color: str) -> str:
    if not values or len(values) < 2:
        return ""
    vmin, vmax = min(values), max(values)
    rng = (vmax - vmin) or 1
    step = 100.0 / (len(values) - 1)
    pts = " ".join(
        f"{i * step:.2f},{(1 - (v - vmin) / rng) * 28 + 4:.2f}"
        for i, v in enumerate(values)
    )
    return (
        f'<svg class="esg-sparkline" viewBox="0 0 100 36" preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" '
        f'stroke-linejoin="round" points="{pts}" />'
        f'</svg>'
    )


def kpi_card(
    label: str,
    value: str,
    description: Optional[str] = None,
    *,
    key: Optional[str] = None,
    delta: Optional[str] = None,
    delta_kind: str = "neutral",
    sparkline: Optional[Sequence[float]] = None,
) -> None:
    """Render a KPI tile. Adds optional ``delta``/``sparkline`` that the
    shadcn metric_card can't show; falls back to st.metric otherwise."""
    inject_global_css()

    # Custom render path when caller supplies delta or sparkline
    if delta is not None or sparkline:
        spark_color = {
            "positive": TOKENS["brand_success"],
            "negative": TOKENS["brand_danger"],
        }.get(delta_kind, TOKENS["brand_primary"])
        spark = _sparkline_svg(sparkline or [], spark_color)
        delta_html = (
            f'<span class="esg-kpi-delta {html.escape(delta_kind)}">{html.escape(delta)}</span>'
            if delta else ""
        )
        desc_html = (
            f'<div style="color:var(--text-muted);font-size:var(--text-xs);margin-top:4px;">'
            f'{html.escape(description)}</div>' if description else ""
        )
        st.markdown(
            f'<div class="esg-agent-card" style="border-left-color:{spark_color};" '
            f'role="group" aria-label="{html.escape(label)}">'
            f'<div style="font-size:var(--text-xs);text-transform:uppercase;letter-spacing:0.05em;'
            f'color:var(--text-muted);font-weight:600;">{html.escape(label)}</div>'
            f'<div style="display:flex;align-items:baseline;gap:var(--space-2);">'
            f'<div style="font-family:var(--font-display);font-weight:700;font-size:var(--text-2xl);'
            f'color:var(--text);">{html.escape(value)}</div>{delta_html}</div>'
            f'{spark}{desc_html}</div>',
            unsafe_allow_html=True,
        )
        return

    if _HAS_SHADCN and sui is not None:
        try:
            sui.metric_card(
                title=label, content=value, description=description or "",
                key=key or f"kpi_{label}",
            )
            return
        except Exception:
            pass
    st.metric(label, value, delta=description if description else None)


# ---------------------------------------------------------------------------
# Agent card — extended with runtime, last_error, description
# ---------------------------------------------------------------------------
def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    if seconds < 1:
        return f"{int(seconds * 1000)} ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"


def format_relative_time(iso: Optional[str]) -> str:
    """Convert an ISO timestamp to '3m ago' / 'just now'. Returns '—' if blank."""
    if not iso or iso == "Never":
        return "Never"
    try:
        if iso.endswith("Z"):
            dt = datetime.fromisoformat(iso[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            now = datetime.now()
        else:
            now = datetime.now(dt.tzinfo)
        delta = (now - dt).total_seconds()
    except Exception:
        return iso[:16]
    if delta < 0:
        return "just now"
    if delta < 10:
        return "just now"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


def agent_card(
    name: str,
    icon: str,
    status: str,
    last_run: str = "Never",
    color: str = TOKENS["brand_primary"],
    *,
    runtime_seconds: Optional[float] = None,
    last_error: Optional[str] = None,
    description: Optional[str] = None,
    run_count: Optional[int] = None,
) -> None:
    """Status-aware agent tile. New keyword args surface operational realism
    (runtime, last error, run count) without breaking older callers."""
    inject_global_css()
    status_key = (status or "idle").lower()
    status_color = _STATUS_COLORS.get(status_key, TOKENS["text_muted"])
    status_label = status_key.capitalize()

    meta_bits = [
        f'<span title="Last run">🕒 {html.escape(format_relative_time(last_run))}</span>'
    ]
    if runtime_seconds is not None:
        meta_bits.append(f'<span title="Runtime">⚡ {format_duration(runtime_seconds)}</span>')
    if run_count:
        meta_bits.append(f'<span title="Run count">🔁 {run_count}×</span>')
    meta_html = " ".join(meta_bits)

    error_html = ""
    if last_error and status_key == "error":
        error_html = (
            f'<div class="esg-agent-error" title="{html.escape(last_error)}">'
            f'⚠ {html.escape(last_error[:140])}{"…" if len(last_error) > 140 else ""}</div>'
        )
    desc_html = (
        f'<div style="font-size:var(--text-xs);color:var(--text-muted);'
        f'line-height:var(--lh-snug);">{html.escape(description)}</div>'
        if description else ""
    )

    st.markdown(
        f'<div class="esg-agent-card status-{html.escape(status_key)}" '
        f'style="border-left-color:{color};" '
        f'role="group" aria-label="{html.escape(name)} agent">'
        f'<div class="esg-agent-head">'
        f'<div class="esg-agent-title">{html.escape(icon)} {html.escape(name)}</div>'
        f'<div class="esg-agent-status" style="color:{status_color};">'
        f'<span class="esg-status-dot status-{html.escape(status_key)}"></span>'
        f'{html.escape(status_label)}</div>'
        f'</div>'
        f'{desc_html}'
        f'<div class="esg-agent-meta">{meta_html}</div>'
        f'{error_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# L2 — Operational realism
# ---------------------------------------------------------------------------
def live_badge(label: str = "Live") -> None:
    inject_global_css()
    st.markdown(
        f'<span class="esg-live-badge" role="status" aria-live="polite">'
        f'<span class="esg-status-dot" aria-hidden="true"></span>{html.escape(label)}'
        f'</span>',
        unsafe_allow_html=True,
    )


def log_panel(
    entries: Iterable[dict],
    *,
    height: int = 380,
    level_filter: Optional[Sequence[str]] = None,
    agent_filter: Optional[Sequence[str]] = None,
    key: str = "log",
    show_filters: bool = True,
    empty_message: str = "No activity yet — run the pipeline to populate logs.",
) -> None:
    """Filterable, monospace activity log. ``entries`` is an iterable of
    dicts with at least ``timestamp`` (ISO), ``message``; optional ``level``
    (info/success/warning/error) and ``agent``.
    """
    inject_global_css()
    rows = list(entries or [])

    if show_filters and rows:
        all_levels = sorted({(r.get("level") or "info").lower() for r in rows})
        all_agents = sorted({r.get("agent") or "—" for r in rows})
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            sel_levels = st.multiselect(
                "Level", all_levels, default=level_filter or all_levels,
                key=f"{key}_levels",
            )
        with c2:
            sel_agents = st.multiselect(
                "Agent", all_agents, default=agent_filter or all_agents,
                key=f"{key}_agents",
            )
        with c3:
            search = st.text_input("Search", key=f"{key}_search", placeholder="Filter…")
        rows = [
            r for r in rows
            if (r.get("level") or "info").lower() in sel_levels
            and (r.get("agent") or "—") in sel_agents
            and (not search or search.lower() in (r.get("message") or "").lower())
        ]

    if not rows:
        st.info(empty_message)
        return

    body_parts = []
    for r in rows[-500:]:  # cap render budget
        ts = r.get("timestamp", "")
        try:
            ts_short = datetime.fromisoformat(ts).strftime("%H:%M:%S")
        except Exception:
            ts_short = ts[:8] if ts else "—"
        level = (r.get("level") or "info").lower()
        agent = r.get("agent") or "—"
        msg = r.get("message") or ""
        body_parts.append(
            f'<div class="esg-log-row">'
            f'<span class="esg-log-time">{html.escape(ts_short)} · {html.escape(agent)}</span>'
            f'<span class="esg-log-tag {html.escape(level)}">{html.escape(level)}</span>'
            f'<span class="esg-log-msg">{html.escape(msg)}</span>'
            f'</div>'
        )
    st.markdown(
        f'<div class="esg-log-shell" role="log" aria-live="polite" '
        f'style="max-height:{int(height)}px;">'
        f'{"".join(body_parts)}</div>',
        unsafe_allow_html=True,
    )


def retry_button(label: str = "Retry", *, key: str, disabled: bool = False) -> bool:
    """Small secondary button styled for the 'try again' affordance."""
    inject_global_css()
    return st.button(
        f"🔁 {label}", key=key, disabled=disabled, type="secondary",
        use_container_width=False,
    )


def drilldown(title: str, *, expanded: bool = False, icon: str = "🔍"):
    """Consistent expander styling for drill-down sections."""
    inject_global_css()
    return st.expander(f"{icon} {title}", expanded=expanded)


# ---------------------------------------------------------------------------
# Badge primitives
# ---------------------------------------------------------------------------
def badge(label: str, variant: str = "default") -> None:
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
        "success": TOKENS["brand_success"], "warn": TOKENS["brand_warn"],
        "error": TOKENS["brand_danger"], "info": TOKENS["brand_accent"],
        "default": TOKENS["text_muted"],
    }.get(variant, TOKENS["text_muted"])
    st.markdown(
        f'<span class="esg-chip" style="border-color:{color};color:{color};">'
        f'{html.escape(label)}</span>',
        unsafe_allow_html=True,
    )


def _map_variant_to_shadcn(variant: str) -> str:
    return {
        "success": "default", "warn": "outline", "error": "destructive",
        "info": "secondary", "default": "secondary",
    }.get(variant, "secondary")


def grade_pill(grade: str) -> str:
    color = _GRADE_COLORS.get(grade, TOKENS["text_muted"])
    return (
        f'<span class="esg-grade-pill" style="background:{color};">'
        f'{html.escape(grade)}</span>'
    )


# ---------------------------------------------------------------------------
# Pipeline chip row
# ---------------------------------------------------------------------------
def pipeline_chips(statuses: dict, agent_config: dict) -> None:
    inject_global_css()
    chips_html = []
    for key, config in agent_config.items():
        status = (statuses.get(key, {}).get("status") or "idle").lower()
        icon = config.get("icon", "🤖")
        name = config.get("name", key)
        chips_html.append(
            f'<span class="esg-chip status-{html.escape(status)}" role="listitem" '
            f'aria-label="{html.escape(name)} status {html.escape(status)}">'
            f'<span class="esg-status-dot status-{html.escape(status)}" aria-hidden="true"></span>'
            f'{html.escape(icon)} {html.escape(name)}</span>'
        )
    st.markdown(
        f'<div class="esg-chip-row" role="list" aria-label="Pipeline status">'
        f'{"".join(chips_html)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# ESG ROI featured card — a React-iframe rich component
# ---------------------------------------------------------------------------
# Rendered via streamlit.components.v1.html so it gets its own isolated DOM.
# That lets us run real JS (count-up, SVG draw-on, pulse animations) without
# polluting Streamlit's CSS scope or fighting its rerun model.
def esg_roi_featured_card(
    *,
    results: Optional[dict] = None,
    mode: str = "auto",
    user_name: Optional[str] = None,
    height: int = 440,
    previous_iqs: Optional[float] = None,
) -> None:
    """Render the ESG ROI agent as a featured dashboard hero card.

    Three modes (``mode``):
      * ``"live"``   — signed-in user, real ``roi_agent.results`` passed.
      * ``"empty"``  — signed-in but no run yet. Card shows "run to populate".
      * ``"teaser"`` — guest (not signed in). Card shows an indicative
                       preview clearly watermarked as sample data.
      * ``"auto"``   — pick based on inputs: live if ``results`` present and
                       has an IQS score, teaser if ``user_name`` is None,
                       else empty.

    ``results`` is the raw dict returned by ``ROIAgent.run()`` — the card
    pulls IQS/grade from ``results['investment_quality_score']`` and ROI
    figures from ``results['financial_roi']`` / ``['strategic_roi']`` so it
    always reflects whatever ESG Command Center most recently produced.
    """
    from streamlit.components.v1 import html as _html

    inject_global_css()

    # --- Resolve mode ----------------------------------------------------
    if mode == "auto":
        if results and isinstance(results.get("investment_quality_score"), dict) \
                and results["investment_quality_score"].get("score") is not None:
            mode = "live"
        elif user_name:
            mode = "empty"
        else:
            mode = "teaser"

    # --- Defaults (teaser uses aspirational sample numbers) --------------
    iqs_score: float = 87.0
    grade: str = "A"
    financial_return: str = "2.47×"
    strategic_return: str = "IQS 87 / 100"
    payback_months: int = 14
    delta_label: str = "+12 vs last run"
    delta_arrow: str = "↑"
    sparkline: Optional[Sequence[float]] = None

    # --- Live mapping from the ROI agent's result schema -----------------
    # ROIAgent.run() returns (see agents/roi_agent.py):
    #   results['investment_quality_score']['score' | 'grade']
    #   results['financial_roi']['roi_pct' | 'payback_years' | 'net_financial_benefit']
    #   results['strategic_roi']['cost_of_capital_reduction_bps' | 'brand_premium_score']
    #   results['j_curve']['quarters'][i]['cumulative_benefit']
    if mode == "live" and results:
        iqs_block = results.get("investment_quality_score") or {}
        iqs_score = float(iqs_block.get("score") or 0)
        grade = str(iqs_block.get("grade") or "—")

        fin = results.get("financial_roi") or {}
        roi_pct = fin.get("roi_pct")
        if isinstance(roi_pct, (int, float)):
            financial_return = f"{1 + float(roi_pct) / 100:.2f}×"
        else:
            financial_return = "—"

        payback_years = fin.get("payback_years")
        if isinstance(payback_years, (int, float)) and payback_years:
            payback_months = max(1, int(round(float(payback_years) * 12)))
        else:
            payback_months = 0

        strat = results.get("strategic_roi") or {}
        coc_bps = strat.get("cost_of_capital_reduction_bps")
        if isinstance(coc_bps, (int, float)) and coc_bps:
            strategic_return = f"{int(coc_bps)} bps · WACC"
        else:
            strategic_return = f"IQS {iqs_score:.0f} / 100"

        j_curve = results.get("j_curve") or {}
        quarters = j_curve.get("quarters") or []
        if quarters:
            try:
                sparkline = [
                    float(q.get("cumulative_benefit") or 0) for q in quarters
                ]
            except Exception:
                sparkline = None

        # Real delta vs previous saved run if the caller looked one up.
        # If we don't have a prior IQS to compare to (very first run, or
        # caller didn't pass it), fall back to a neutral "first run"
        # label rather than the misleading "live · updated now" string,
        # which read like an animated heartbeat instead of an actual
        # delta and confused users into thinking the card was always
        # the latest of *something*.
        if isinstance(previous_iqs, (int, float)) and previous_iqs > 0:
            _diff = float(iqs_score) - float(previous_iqs)
            if abs(_diff) < 0.5:
                delta_label = "no change vs last run"
                delta_arrow = "→"
            elif _diff > 0:
                delta_label = f"+{_diff:.0f} vs last run"
                delta_arrow = "↑"
            else:
                delta_label = f"{_diff:.0f} vs last run"
                delta_arrow = "↓"
        else:
            delta_label = "first computed run"
            delta_arrow = "✦"

    elif mode == "empty":
        iqs_score, grade = 0, "—"
        financial_return = "—"
        strategic_return = "Run pipeline to populate"
        payback_months = 0
        delta_label = "no run yet"
        delta_arrow = "·"

    # --- Sparkline polyline (100×36 viewBox) -----------------------------
    spark: Sequence[float] = list(sparkline) if sparkline else \
        [42, 48, 55, 51, 62, 68, 75, 71, 82, max(1.0, iqs_score or 50)]
    if len(spark) < 2:
        spark = [spark[0] if spark else 0, spark[0] if spark else 0]
    vmin, vmax = min(spark), max(spark)
    rng = (vmax - vmin) or 1
    step = 100.0 / (len(spark) - 1)
    points = " ".join(
        f"{i * step:.2f},{(1 - (v - vmin) / rng) * 28 + 4:.2f}" for i, v in enumerate(spark)
    )

    # --- Mode-specific badge (top-right watermark) -----------------------
    if mode == "teaser":
        mode_badge = (
            '<span class="mode-badge teaser" title="Illustrative numbers — sign in for yours">'
            '◇ SAMPLE PREVIEW · SIGN IN FOR YOUR NUMBERS</span>'
        )
    elif mode == "empty":
        mode_badge = (
            '<span class="mode-badge empty">◯ NO ROI RUN YET · OPEN MISSION CONTROL</span>'
        )
    else:
        mode_badge = (
            '<span class="mode-badge live"><span class="live-dot"></span>'
            '<span class="live-label">LIVE</span></span>'
        )

    # Greeting line
    greet = (
        f'Good to see you, {html.escape(user_name)} — here is your current investment thesis.'
        if mode == "live" and user_name else
        (f'Signed in as {html.escape(user_name)}. Run the ESG Command Center to populate your ROI view.'
         if mode == "empty" and user_name else
         'See what your ROI could look like. Sign in to unlock your live numbers.')
    )
    live_dot = ""  # badge now lives in top-right; left title has no duplicate

    _html(
        f"""
<!doctype html>
<html><head><meta charset="utf-8"><style>
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif; }}
  .roi-wrap {{
    position: relative;
    border-radius: 22px;
    padding: 26px 32px;
    color: #fff;
    background:
      radial-gradient(600px 340px at 0% 0%, rgba(255, 182, 0, 0.40), transparent 60%),
      radial-gradient(700px 380px at 100% 120%, rgba(194, 58, 0, 0.65), transparent 70%),
      linear-gradient(135deg, #FD5108 0%, #E0301E 55%, #8A2A00 120%);
    box-shadow:
      0 24px 60px rgba(253, 81, 8, 0.34),
      inset 0 1px 0 rgba(255, 255, 255, 0.30);
    overflow: hidden;
    min-height: {height - 20}px;
    display: grid; grid-template-columns: 1.3fr 1fr; gap: 28px;
    transition: transform 300ms cubic-bezier(0.2, 0.8, 0.2, 1),
                box-shadow 300ms cubic-bezier(0.2, 0.8, 0.2, 1);
  }}
  .roi-wrap::before {{
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background-image:
      linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px);
    background-size: 44px 44px;
    mask-image: radial-gradient(600px 400px at 20% 0%, rgba(0,0,0,0.7), transparent 75%);
    -webkit-mask-image: radial-gradient(600px 400px at 20% 0%, rgba(0,0,0,0.7), transparent 75%);
    opacity: 0.6;
  }}
  .roi-wrap:hover {{
    transform: translateY(-3px);
    box-shadow:
      0 32px 72px rgba(253, 81, 8, 0.45),
      inset 0 1px 0 rgba(255, 255, 255, 0.40);
  }}
  /* Mode-specific treatments — keep the PwC orange palette in empty /
     teaser states too; the "NO ROI RUN YET" badge already signals state. */
  .roi-wrap.mode-empty {{
    background:
      radial-gradient(600px 340px at 0% 0%, rgba(255, 182, 0, 0.30), transparent 60%),
      radial-gradient(700px 380px at 100% 120%, rgba(194, 58, 0, 0.55), transparent 70%),
      linear-gradient(135deg, #E0301E 0%, #C23A00 55%, #8A2A00 120%);
  }}
  .roi-wrap.mode-teaser {{ filter: saturate(1.05); }}
  .mode-badge {{
    position: absolute; top: 18px; right: 22px; z-index: 5;
    display: inline-flex; align-items: center; gap: 8px;
    font-size: 10px; font-weight: 800; letter-spacing: 0.12em;
    padding: 6px 12px; border-radius: 999px;
    background: rgba(255, 255, 255, 0.18);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.32);
    color: #fffbe6;
    text-transform: uppercase;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.20);
  }}
  .mode-badge.live {{
    background: rgba(74, 222, 128, 0.18);
    border-color: rgba(74, 222, 128, 0.45);
    color: #d1fae5;
  }}
  .mode-badge.empty {{
    background: rgba(255, 182, 0, 0.18);
    border-color: rgba(255, 182, 0, 0.45);
    color: #fff8d7;
  }}
  .mode-badge.teaser {{
    background: rgba(255, 255, 255, 0.16);
    border-color: rgba(255, 255, 255, 0.40);
    color: #fff;
  }}
  .roi-left  {{ position: relative; z-index: 1; display: flex; flex-direction: column; gap: 14px; padding-top: 36px; }}
  .roi-right {{ position: relative; z-index: 1; display: flex; flex-direction: column; justify-content: center; padding-top: 36px; }}
  .eyebrow {{
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 14px; border-radius: 999px;
    background: rgba(255, 255, 255, 0.18);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255, 255, 255, 0.30);
    font-size: 11px; font-weight: 700; letter-spacing: 0.10em; text-transform: uppercase;
    align-self: flex-start;
  }}
  .eyebrow .star {{ font-size: 13px; filter: drop-shadow(0 0 8px rgba(255,255,255,0.5)); }}
  .live-dot {{
    display: inline-block; width: 7px; height: 7px; border-radius: 50%;
    background: #4ade80; box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.6);
    animation: live-pulse 1.4s ease-out infinite;
  }}
  .live-label {{ font-size: 10px; font-weight: 800; letter-spacing: 0.12em; color: #d1fae5; }}
  @keyframes live-pulse {{
    0% {{ box-shadow: 0 0 0 0 rgba(74, 222, 128, 0.7); }}
    70% {{ box-shadow: 0 0 0 7px rgba(74, 222, 128, 0); }}
    100% {{ box-shadow: 0 0 0 0 rgba(74, 222, 128, 0); }}
  }}
  h2.roi-title {{
    margin: 0;
    font-family: 'Plus Jakarta Sans', 'Inter', sans-serif;
    font-weight: 800; font-size: 2rem; letter-spacing: -0.025em;
    line-height: 1.1;
    text-shadow: 0 2px 12px rgba(0, 0, 0, 0.18);
  }}
  .roi-subtitle {{
    margin: 0; color: rgba(255, 255, 255, 0.88);
    font-size: 0.95rem; line-height: 1.55; max-width: 95%;
  }}
  .roi-metric-row {{
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 6px;
  }}
  .roi-metric {{
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.22);
    backdrop-filter: blur(8px);
    border-radius: 14px; padding: 12px 14px;
    transition: background 200ms ease, transform 200ms ease;
  }}
  .roi-metric:hover {{ background: rgba(255, 255, 255, 0.20); transform: translateY(-2px); }}
  .roi-metric .m-label {{
    font-size: 10px; font-weight: 700; letter-spacing: 0.08em;
    color: rgba(255, 255, 255, 0.78); text-transform: uppercase;
  }}
  .roi-metric .m-value {{
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 800; font-size: 1.35rem; letter-spacing: -0.025em;
    margin-top: 4px; line-height: 1.1;
    text-shadow: 0 1px 6px rgba(0, 0, 0, 0.15);
  }}
  /* Right column: large animated score.
     Sized so the full stack (pill + ring + label + delta + sparkline)
     fits comfortably inside the 440px iframe on the shortest reasonable
     viewport without the ring clipping. */
  .iqs-stack {{ display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }}
  .iqs-ring {{
    position: relative; width: 128px; height: 128px; flex-shrink: 0;
    display: flex; align-items: center; justify-content: center;
    border-radius: 50%;
    background:
      conic-gradient(from 210deg,
        #FFB600 0deg,
        #fff 260deg,
        rgba(255, 255, 255, 0.2) 260deg);
    animation: ring-fill 1.6s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  }}
  .iqs-ring::before {{
    content: ""; position: absolute; inset: 9px; border-radius: 50%;
    background: linear-gradient(135deg, #B02800 0%, #7A1C00 100%);
  }}
  @keyframes ring-fill {{
    from {{ background: conic-gradient(from 210deg, rgba(255,255,255,0.2) 0deg, rgba(255,255,255,0.2) 360deg); }}
  }}
  .iqs-num {{
    position: relative; z-index: 1;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 800; font-size: 2.3rem; letter-spacing: -0.035em;
    color: #fff;
    text-shadow: 0 3px 14px rgba(0, 0, 0, 0.30);
  }}
  .iqs-sub {{
    font-size: 11px; font-weight: 700; letter-spacing: 0.10em;
    color: rgba(255, 255, 255, 0.85); text-transform: uppercase;
  }}
  .grade-pill {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 12px; border-radius: 999px;
    background: rgba(255, 255, 255, 0.94); color: #8A2A00;
    font-family: 'Plus Jakarta Sans', sans-serif;
    font-weight: 800; font-size: 12px; letter-spacing: 0.04em;
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.18);
  }}
  .delta-chip {{
    font-size: 11px; font-weight: 700; color: #d1fae5;
    background: rgba(74, 222, 128, 0.20);
    border: 1px solid rgba(74, 222, 128, 0.40);
    padding: 3px 10px; border-radius: 999px;
    letter-spacing: 0.02em;
  }}
  /* Sparkline */
  .spark {{ margin-top: 10px; width: 100%; }}
  .spark polyline {{
    fill: none; stroke: #fff; stroke-width: 2.2;
    stroke-linecap: round; stroke-linejoin: round;
    filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.25));
    stroke-dasharray: 400; stroke-dashoffset: 400;
    animation: draw 1.8s cubic-bezier(0.2, 0.8, 0.2, 1) forwards;
  }}
  .spark-fill {{
    fill: url(#sparkGrad);
    opacity: 0;
    animation: fadeIn 800ms 1.2s forwards;
  }}
  @keyframes draw   {{ to {{ stroke-dashoffset: 0; }} }}
  @keyframes fadeIn {{ to {{ opacity: 0.5; }} }}
  @media (max-width: 820px) {{
    .roi-wrap {{ grid-template-columns: 1fr; }}
    .roi-right {{ align-items: flex-start; }}
    .iqs-stack {{ align-items: flex-start; }}
    h2.roi-title {{ font-size: 1.55rem; }}
  }}
</style></head>
<body>
  <div class="roi-wrap mode-{mode}">
    {mode_badge}
    <div class="roi-left">
      <span class="eyebrow"><span class="star">✦</span> FEATURED AGENT · CFO-READY INTELLIGENCE</span>
      <h2 class="roi-title">ESG ROI Agent — the investment thesis, quantified.</h2>
      <p class="roi-subtitle">{greet}</p>
      <div class="roi-metric-row">
        <div class="roi-metric">
          <div class="m-label">Financial Return</div>
          <div class="m-value">{html.escape(financial_return)}</div>
        </div>
        <div class="roi-metric">
          <div class="m-label">Strategic Return</div>
          <div class="m-value">{html.escape(strategic_return)}</div>
        </div>
        <div class="roi-metric">
          <div class="m-label">Payback Horizon</div>
          <div class="m-value">{payback_months if payback_months else "—"}{" mo" if payback_months else ""}</div>
        </div>
      </div>
    </div>
    <div class="roi-right">
      <div class="iqs-stack">
        <span class="grade-pill">⭐ GRADE {html.escape(grade)}</span>
        <div class="iqs-ring">
          <div class="iqs-num" id="iqs-num" data-target="{iqs_score:.0f}">0</div>
        </div>
        <div class="iqs-sub">IQS · Investment Quality Score</div>
        <span class="delta-chip">{html.escape(delta_arrow)} {html.escape(delta_label)}</span>
        <svg class="spark" viewBox="0 0 100 36" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"  stop-color="#FFB600" stop-opacity="0.8"/>
              <stop offset="100%" stop-color="#FFB600" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <polygon class="spark-fill" points="0,36 {points} 100,36"/>
          <polyline points="{points}"/>
        </svg>
      </div>
    </div>
  </div>
<script>
  (function() {{
    const el = document.getElementById('iqs-num');
    if (!el) return;
    const target = parseFloat(el.dataset.target || '0');
    const duration = 1600;
    let start = null;
    function tick(ts) {{
      if (!start) start = ts;
      const p = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = Math.round(target * eased).toString();
      if (p < 1) requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);
  }})();
</script>
</body></html>
""",
        height=height,
        scrolling=False,
    )


# ---------------------------------------------------------------------------
# IQS gauge (unchanged geometry, modernized typography)
# ---------------------------------------------------------------------------
def iqs_gauge(score: float, grade: str, *, size: int = 220) -> None:
    inject_global_css()
    score = max(0.0, min(100.0, float(score or 0)))
    radius = size * 0.38
    center = size / 2
    start_angle = math.radians(135)
    end_angle = math.radians(45 + 360)
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
         xmlns="http://www.w3.org/2000/svg" role="img"
         aria-label="Investment Quality Score {score:.0f} of 100, grade {html.escape(grade or 'N/A')}"
         style="display:block;margin:0 auto;">
      <path d="M {sx:.2f} {sy:.2f} A {radius:.2f} {radius:.2f} 0 {large_bg} 1 {ex:.2f} {ey:.2f}"
            stroke="{TOKENS['border']}" stroke-width="14" fill="none" stroke-linecap="round"/>
      <path d="M {sx:.2f} {sy:.2f} A {radius:.2f} {radius:.2f} 0 {large_fg} 1 {px:.2f} {py:.2f}"
            stroke="{color}" stroke-width="14" fill="none" stroke-linecap="round"/>
      <text x="{center}" y="{center - 6}" text-anchor="middle"
            font-family="Plus Jakarta Sans, Inter, sans-serif" font-weight="800"
            font-size="{size * 0.22:.0f}" fill="{TOKENS['text']}">{score:.0f}</text>
      <text x="{center}" y="{center + size * 0.12:.0f}" text-anchor="middle"
            font-family="Inter, sans-serif" font-weight="600"
            font-size="{size * 0.08:.0f}" fill="{TOKENS['text_muted']}">IQS · Grade {html.escape(grade or 'N/A')}</text>
    </svg>
    """
    st.markdown(svg, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------
def switch(label: str, *, default: bool = False, key: Optional[str] = None) -> bool:
    inject_global_css()
    if _HAS_SHADCN and sui is not None:
        try:
            return bool(sui.switch(
                default_checked=default, label=label, key=key or f"switch_{label}",
            ))
        except Exception:
            pass
    return st.checkbox(label, value=default, key=key)


# ---------------------------------------------------------------------------
# Feature info
# ---------------------------------------------------------------------------
def react_feature_status() -> dict:
    return {"shadcn": _HAS_SHADCN, "extras": _HAS_EXTRAS}


# ---------------------------------------------------------------------------
# Telemetry helper — derive a flat audit-trail list across all agents
# ---------------------------------------------------------------------------
def collect_audit_trail(agent_objects: dict, *, limit: int = 200) -> list[dict]:
    """Merge each agent's audit_trail into a single time-ordered list."""
    rows: list[dict] = []
    for agent in (agent_objects or {}).values():
        trail = getattr(agent, "audit_trail", None) or []
        rows.extend(trail)
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    return rows[:limit]

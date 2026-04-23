"""React-backed UI helpers for ESG CoPilot Streamlit pages.

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
    "brand_primary": "#D04A02",
    "brand_primary_dark": "#A23A02",
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
    --shadow-brand: 0 8px 22px rgba(208, 74, 2, 0.20);
    --ring-focus: 0 0 0 3px rgba(208, 74, 2, 0.35);
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
        radial-gradient(900px 280px at 0% 0%,    rgba(208, 74, 2, 0.10), transparent 70%),
        radial-gradient(900px 280px at 100% 0%,  rgba(255, 182, 0, 0.08), transparent 70%),
        linear-gradient(180deg, #fffaf4 0%, #ffffff 32%, #ffffff 100%) !important;
    background-attachment: fixed !important;
}
[data-testid="stAppViewContainer"] { background: transparent !important; }
[data-testid="stHeader"] { background: transparent !important; backdrop-filter: blur(8px); }
[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, var(--surface-muted) 0%, #ffffff 80%) !important;
    border-right: 1px solid var(--border);
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
section.main > div.block-container {
    padding-top: var(--space-6);
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
    background: linear-gradient(135deg, var(--pwc-orange) 0%, var(--pwc-tomato) 100%);
    border: none; color: #fff;
    box-shadow: var(--shadow-brand);
}
div.stButton > button[kind="primary"]:hover:not(:disabled) {
    transform: translateY(-1px);
    box-shadow: 0 10px 26px rgba(208, 74, 2, 0.42);
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
        radial-gradient(1200px 380px at 0% 0%, rgba(208, 74, 2, 0.16), transparent 60%),
        radial-gradient(1000px 360px at 100% 0%, rgba(255, 182, 0, 0.14), transparent 60%),
        linear-gradient(180deg, #fffaf4 0%, #ffffff 100%);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: var(--space-8) var(--space-8) var(--space-7);
    margin-bottom: var(--space-6);
    overflow: hidden;
    box-shadow: var(--shadow-xs), 0 12px 32px rgba(208, 74, 2, 0.07);
}
.esg-hero::before {
    content: ""; position: absolute; inset: 0; pointer-events: none;
    background:
        linear-gradient(to right, rgba(208, 74, 2, 0) 90%, rgba(208, 74, 2, 0.08) 100%),
        linear-gradient(to left,  rgba(255, 182, 0, 0) 90%, rgba(255, 182, 0, 0.08) 100%);
}
.esg-hero h1 {
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-3xl);
    background: linear-gradient(135deg, var(--pwc-orange) 0%, var(--pwc-tomato) 55%, var(--pwc-amber) 100%);
    -webkit-background-clip: text; background-clip: text;
    -webkit-text-fill-color: transparent;
}
.esg-hero p.esg-subtitle {
    margin: 2px 0 0 0; font-size: var(--text-md);
    color: var(--text-secondary); line-height: var(--lh-relaxed); max-width: 920px;
}
.esg-hero .esg-eyebrow {
    display: inline-flex; align-items: center; gap: var(--space-2);
    padding: 4px var(--space-3); border-radius: var(--radius-pill);
    background: rgba(208, 74, 2, 0.10);
    border: 1px solid rgba(208, 74, 2, 0.28);
    color: var(--pwc-orange-dark);
    font-size: var(--text-xs); font-weight: 600; letter-spacing: 0.04em;
    text-transform: uppercase; margin-bottom: var(--space-3);
}
.esg-hero .esg-eyebrow-dot {
    width: 6px; height: 6px; border-radius: 50%;
    background: var(--pwc-orange);
    box-shadow: 0 0 0 3px rgba(208, 74, 2, 0.20);
    animation: esg-pulse 2.4s var(--ease-standard) infinite;
}
@media (max-width: 768px) {
    .esg-hero { padding: var(--space-6) var(--space-5); border-radius: var(--radius-lg); }
    .esg-hero h1 { font-size: var(--text-2xl); }
}

/* PwC header bar ------------------------------------------------------ */
.pwc-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: var(--space-2) 0 var(--space-3) 0;
    margin-bottom: var(--space-2);
    border-bottom: 1px solid rgba(208, 74, 2, 0.18);
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
    box-shadow: 0 1px 4px rgba(208, 74, 2, 0.30);
}

/* Chips (status, info) ------------------------------------------------ */
.esg-chip-row { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-3); }
.esg-chip {
    display: inline-flex; align-items: center; gap: var(--space-2);
    padding: 4px var(--space-3); border-radius: var(--radius-pill);
    background: var(--surface); border: 1px solid var(--border);
    font-size: var(--text-sm); font-weight: 500; color: var(--text);
    transition: transform var(--dur-fast) var(--ease-standard),
                box-shadow var(--dur-fast) var(--ease-standard);
}
.esg-chip:hover { transform: translateY(-1px); box-shadow: var(--shadow-xs); }
.esg-chip.status-running   { border-color: var(--status-running);   color: var(--status-running); background: rgba(224, 48, 30, 0.06); }
.esg-chip.status-completed { border-color: var(--status-completed); color: var(--status-completed); background: rgba(46, 133, 64, 0.06); }
.esg-chip.status-error     { border-color: var(--status-error);     color: var(--status-error); background: rgba(200, 16, 46, 0.06); }
.esg-chip.status-warning,
.esg-chip.status-skipped   { border-color: var(--status-warning);   color: #8a5b00; background: rgba(255, 182, 0, 0.10); }
.esg-chip.status-idle      { border-color: var(--status-idle);      color: var(--status-idle); }

/* Section header ------------------------------------------------------ */
.esg-section {
    display: flex; align-items: baseline; justify-content: space-between;
    gap: var(--space-4);
    margin: var(--space-7) 0 var(--space-3) 0;
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border);
}
.esg-section .esg-section-title { font-size: var(--text-lg); font-weight: 700; color: var(--text); letter-spacing: -0.01em; }
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
    box-shadow: var(--shadow-md);
    transform: translateY(-2px);
}
.esg-agent-card.status-running {
    border-color: var(--status-running);
    background: linear-gradient(180deg, rgba(224, 48, 30, 0.04), var(--surface-raised) 60%);
}
.esg-agent-card.status-error {
    border-color: var(--status-error);
    background: linear-gradient(180deg, rgba(200, 16, 46, 0.05), var(--surface-raised) 60%);
}
.esg-agent-card.status-completed {
    background: linear-gradient(180deg, rgba(46, 133, 64, 0.04), var(--surface-raised) 60%);
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

/* Activity log -------------------------------------------------------- */
.esg-log-shell {
    background: var(--surface-sunken);
    border: 1px solid var(--border); border-radius: var(--radius-md);
    padding: var(--space-3); max-height: 380px; overflow-y: auto;
    font-family: var(--font-mono); font-size: var(--text-xs);
    box-shadow: inset 0 1px 3px rgba(15, 23, 42, 0.04);
}
.esg-log-row {
    display: grid; grid-template-columns: 110px 90px 1fr;
    gap: var(--space-3); padding: 6px var(--space-2);
    border-radius: var(--radius-xs);
    border-bottom: 1px solid rgba(241, 217, 196, 0.6);
    transition: background var(--dur-fast) var(--ease-standard);
}
.esg-log-row:last-child { border-bottom: none; }
.esg-log-row:hover { background: rgba(255, 255, 255, 0.6); }
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


def pwc_header(product: str = "ESG CoPilot", tagline: str = "Powered by PwC India") -> None:
    inject_global_css()
    skip_link()
    logo_uri = _pwc_logo_data_uri()
    logo_html = f'<img class="pwc-logo" src="{logo_uri}" alt="PwC"/>' if logo_uri else ""
    st.markdown(
        f'<div class="pwc-header" role="banner">'
        f'<div class="pwc-header-brand">{logo_html}'
        f'<div class="pwc-header-text">'
        f'<span class="pwc-header-title">{html.escape(product)}</span>'
        f'<span class="pwc-header-sub">{html.escape(tagline)}</span>'
        f'</div></div>'
        f'<div class="pwc-accent-bar" aria-hidden="true"></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def skip_link(target_id: str = "main") -> None:
    """L4: Render an offscreen 'Skip to main content' link visible on focus."""
    st.markdown(
        f'<a class="esg-skip-link" href="#{html.escape(target_id)}">Skip to main content</a>',
        unsafe_allow_html=True,
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
) -> None:
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
    st.markdown(
        f'<div class="esg-hero" role="region" aria-label="{safe_title}">'
        f'{eyebrow_html}<h1>{prefix}{safe_title}</h1>{subtitle_html}{chip_html}'
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

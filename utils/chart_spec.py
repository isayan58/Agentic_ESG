"""Shared chart-spec contract — the single source of truth for the
``render_chart`` capability.

This module deliberately depends only on Plotly (never Streamlit), so it can
be imported from three very different places without dragging a UI framework
along:

  * the ``esg-charts`` MCP server, which validates a spec and echoes it back;
  * any UI client (the Streamlit ``chat_drawer``, a future Gradio/Slack bot)
    that turns the validated spec into a live figure;
  * tests.

Before the LangGraph + MCP migration this logic lived inline in
``utils/chat_drawer.py`` (``_RENDER_CHART_TOOL`` + ``_figure_from_tool_input``).
Lifting it here is what lets the chart tool be served over MCP and reused by
any client instead of being hardcoded into one Streamlit file.
"""
from __future__ import annotations

from typing import Any, Optional

try:
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except Exception:  # pragma: no cover - exercised only without plotly
    go = None  # type: ignore
    _HAS_PLOTLY = False


# PwC warm palette — kept identical to the pre-migration chat drawer so the
# inline charts look unchanged after the swap.
PWC_PALETTE = ["#FD5108", "#E0301E", "#FFB600", "#D04A02", "#A23A02", "#7a2e0c"]

CHART_TYPES = ["bar", "horizontal_bar", "line", "pie", "scatter", "area"]


# The JSON-schema for the tool's input. The MCP server advertises this same
# shape; keeping it here means the schema and the renderer can never drift.
RENDER_CHART_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "chart_type": {"type": "string", "enum": CHART_TYPES},
        "x": {
            "type": "array",
            "items": {"type": ["string", "number"]},
            "description": "Category labels (bar/pie) or x-axis values (line/scatter).",
        },
        "y": {
            "type": "array",
            "items": {"type": "number"},
            "description": "Numeric values aligned with x.",
        },
        "x_label": {"type": "string"},
        "y_label": {"type": "string"},
    },
    "required": ["title", "chart_type", "x", "y"],
}

RENDER_CHART_DESCRIPTION = (
    "Render a chart inline in the chat. Use when a chart would communicate "
    "the answer better than prose — for trends over time, category "
    "breakdowns, framework comparisons, IQS components, or distributions. "
    "The chart appears immediately after the surrounding text. Don't "
    "chart trivial single-value answers."
)


def validate_chart_spec(spec: dict) -> dict:
    """Normalise + validate a chart spec. Returns a clean dict ready to be
    serialised back as a tool result. Raises ``ValueError`` on a spec that
    could never render so the model gets a clear tool error instead of a
    silently dropped chart."""
    chart_type = str(spec.get("chart_type") or "bar").lower()
    if chart_type not in CHART_TYPES:
        raise ValueError(
            f"chart_type must be one of {CHART_TYPES}, got {chart_type!r}"
        )
    x = list(spec.get("x") or [])
    y = list(spec.get("y") or [])
    if not x or not y:
        raise ValueError("Both 'x' and 'y' must be non-empty arrays.")
    if len(x) != len(y):
        raise ValueError(
            f"'x' ({len(x)}) and 'y' ({len(y)}) must have equal length."
        )
    return {
        "title": str(spec.get("title") or ""),
        "chart_type": chart_type,
        "x": x,
        "y": y,
        "x_label": str(spec.get("x_label") or ""),
        "y_label": str(spec.get("y_label") or ""),
    }


def figure_from_spec(spec: dict) -> Optional["go.Figure"]:
    """Build a themed Plotly figure from a (validated or raw) chart spec.

    Returns ``None`` when Plotly is unavailable or the spec is unrenderable —
    callers fall back to text-only rendering in that case.
    """
    if not _HAS_PLOTLY:
        return None
    try:
        spec = validate_chart_spec(spec)
    except ValueError:
        return None

    chart_type = spec["chart_type"]
    title = spec["title"]
    x, y = spec["x"], spec["y"]
    x_label, y_label = spec["x_label"], spec["y_label"]

    if chart_type == "bar":
        fig = go.Figure(go.Bar(x=x, y=y, marker_color=PWC_PALETTE[0]))
    elif chart_type == "horizontal_bar":
        fig = go.Figure(go.Bar(x=y, y=x, orientation="h", marker_color=PWC_PALETTE[0]))
        x_label, y_label = y_label, x_label
    elif chart_type == "line":
        fig = go.Figure(go.Scatter(
            x=x, y=y, mode="lines+markers",
            line=dict(color=PWC_PALETTE[0], width=2.5),
            marker=dict(color=PWC_PALETTE[1], size=8),
        ))
    elif chart_type == "area":
        fig = go.Figure(go.Scatter(
            x=x, y=y, mode="lines", fill="tozeroy",
            line=dict(color=PWC_PALETTE[0], width=2),
            fillcolor="rgba(253, 81, 8, 0.18)",
        ))
    elif chart_type == "scatter":
        fig = go.Figure(go.Scatter(
            x=x, y=y, mode="markers",
            marker=dict(color=PWC_PALETTE[0], size=10),
        ))
    elif chart_type == "pie":
        fig = go.Figure(go.Pie(
            labels=x, values=y,
            marker=dict(colors=PWC_PALETTE),
            textinfo="label+percent",
        ))
    else:  # pragma: no cover - guarded by validate_chart_spec
        return None

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#0f172a")),
        xaxis_title=x_label,
        yaxis_title=y_label,
        margin=dict(l=12, r=12, t=44, b=12),
        height=280,
        plot_bgcolor="#ffffff",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#0f172a"),
        showlegend=(chart_type == "pie"),
    )
    fig.update_xaxes(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0")
    fig.update_yaxes(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0")
    return fig


__all__ = [
    "PWC_PALETTE",
    "CHART_TYPES",
    "RENDER_CHART_INPUT_SCHEMA",
    "RENDER_CHART_DESCRIPTION",
    "validate_chart_spec",
    "figure_from_spec",
]

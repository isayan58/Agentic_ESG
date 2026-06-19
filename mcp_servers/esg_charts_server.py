"""``esg-charts`` MCP server — the ``render_chart`` capability, lifted out of
the Streamlit chat file so any client can request a chart.

The server does **not** draw anything (it has no display). It validates the
chart spec and returns it as JSON tagged with ``"_esg_chart": true``. The UI
client (Streamlit ``chat_drawer``, or any future surface) recognises that
marker in the tool result and renders the live figure via
``utils.chart_spec.figure_from_spec``. This keeps the *what to chart* decision
on the server side and the *how to paint it* concern on the client side — the
split that lets the same tool serve a web UI, a notebook, or a Slack card.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from utils.chart_spec import RENDER_CHART_DESCRIPTION, validate_chart_spec

mcp = FastMCP("esg-charts")


@mcp.tool(description=RENDER_CHART_DESCRIPTION)
def render_chart(
    title: str,
    chart_type: str,
    x: list,
    y: list,
    x_label: str = "",
    y_label: str = "",
) -> str:
    """Validate a chart spec and return it for the client to render.

    ``chart_type`` ∈ {bar, horizontal_bar, line, pie, scatter, area}. ``x`` and
    ``y`` must be equal-length arrays. Returns the cleaned spec as JSON; the
    client paints it inline immediately after the surrounding text.
    """
    try:
        spec = validate_chart_spec({
            "title": title,
            "chart_type": chart_type,
            "x": x,
            "y": y,
            "x_label": x_label,
            "y_label": y_label,
        })
    except ValueError as exc:
        return json.dumps({"error": str(exc)})
    spec["_esg_chart"] = True
    return json.dumps(spec, default=str)


if __name__ == "__main__":
    mcp.run()

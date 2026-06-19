"""``esg-data`` MCP server — read-only access to a user's pipeline runs.

Wraps :class:`utils.run_store.RunStore` behind three MCP tools so any client
(the LangGraph Pilot, a future Slack bot, an eval harness) can fetch run data
through one standard interface instead of importing the store directly.

Run standalone for a quick check:

    python -m mcp_servers.esg_data_server          # serves over stdio

It is normally spawned by the Pilot agent (``core/pilot_agent.py``) over stdio.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow ``python mcp_servers/esg_data_server.py`` (script-style spawn by the
# MCP stdio client) to resolve the project package imports below.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from utils.run_store import get_run_store
from utils.run_summary import headline_metrics

mcp = FastMCP("esg-data")


@mcp.tool()
def list_runs(username: str) -> str:
    """List the saved pipeline runs for a user, newest first.

    Returns a JSON array of run summaries (id, label, timestamp, headline
    figures). Use this to discover which runs exist before fetching one.
    """
    runs = get_run_store().list_runs(username)
    return json.dumps(runs, default=str)


@mcp.tool()
def get_headline_metrics(username: str, run_id: str | None = None) -> str:
    """Return the headline-metrics summary for a user's run.

    Defaults to the latest run when ``run_id`` is omitted. This is the same
    compact grounding block the Pilot uses to answer most questions — call it
    first when the user asks about "the run" generally.
    """
    store = get_run_store()
    snap = store.load_run(username, run_id) if run_id else store.latest_run(username)
    results = (snap or {}).get("results") if isinstance(snap, dict) else None
    if not results:
        return "No pipeline run found for this user yet."
    summary = headline_metrics(results)
    return summary or "Run found, but it carries no summarisable headline metrics."


@mcp.tool()
def get_agent_result(username: str, agent_key: str, run_id: str | None = None) -> str:
    """Fetch one domain agent's full result dict from a run, as JSON.

    ``agent_key`` is one of: data_collector, regulatory_tracker,
    carbon_accountant, risk_predictor, audit_agent, roi_agent,
    report_generator, action_agent, stakeholder_agent. Defaults to the latest
    run when ``run_id`` is omitted. Prefer this over dumping the whole run when
    the user asks about a single domain (e.g. just emissions, or just ROI).
    """
    store = get_run_store()
    snap = store.load_run(username, run_id) if run_id else store.latest_run(username)
    results = (snap or {}).get("results") if isinstance(snap, dict) else None
    if not results:
        return "No pipeline run found for this user yet."
    if agent_key not in results:
        available = ", ".join(k for k in results if k != "planning")
        return f"No result for {agent_key!r} in this run. Available: {available}"
    return json.dumps(results[agent_key], default=str)


if __name__ == "__main__":
    mcp.run()

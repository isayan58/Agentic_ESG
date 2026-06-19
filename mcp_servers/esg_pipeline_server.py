"""``esg-pipeline`` MCP server — *live* compute, wrapping the existing
:class:`core.orchestrator.Orchestrator`.

This is the capability the pre-migration chatbot lacked entirely: it could only
read whatever was cached. These two tools let the Pilot trigger a real run and
persist it, so the next ``esg-data`` lookup sees fresh numbers.

Each call constructs a fresh ``Orchestrator`` (one run = one orchestrator, as
the Streamlit pages do) and saves the result to the shared run store under the
user's name, so the result is durable and visible to every other surface.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP

from core.orchestrator import Orchestrator
from utils.run_store import get_run_store
from utils.run_summary import headline_metrics

mcp = FastMCP("esg-pipeline")


def _save(username: str, results: dict, *, goal: str | None, label: str) -> str | None:
    """Persist a run snapshot; return the run id or ``None`` on failure.
    Saving must never sink the tool call — a computed-but-unsaved result is
    still useful to report back."""
    try:
        return get_run_store().save_run(
            username, results=results, goal=goal, label=label,
            saved_by="esg-pipeline-mcp",
        )
    except Exception:
        return None


@mcp.tool()
def run_full_pipeline(username: str, goal: str | None = None) -> str:
    """Run the full 9-agent ESG pipeline live, save it, and summarise.

    Triggers a real, Claude-driven orchestration over all domain agents
    (data collection → emissions → risk → audit → ROI → reporting → actions →
    stakeholders), persists the snapshot under the user, and returns the run id
    plus the headline-metrics block. Use when the user asks to "run the
    pipeline", "refresh the numbers", or analyse newly changed data. This is a
    heavy operation (live LLM + compute) — only call it on an explicit request.
    """
    orch = Orchestrator()
    results = orch.run_full_pipeline(user_goal=goal)
    run_id = _save(username, results, goal=goal, label="Pilot full-pipeline run")
    summary = headline_metrics(results) or "Pipeline ran but produced no headline metrics."
    return json.dumps({"run_id": run_id, "summary": summary}, default=str)


@mcp.tool()
def run_agent(username: str, agent_key: str) -> str:
    """Run a single domain agent live (with its prerequisites) and summarise.

    ``agent_key`` ∈ {data_collector, regulatory_tracker, carbon_accountant,
    risk_predictor, audit_agent, roi_agent, report_generator, action_agent,
    stakeholder_agent}. Prerequisite agents are run first in dependency order on
    the same orchestrator so the target has the upstream data it needs. The
    partial run is saved. Cheaper than a full pipeline when the user only wants,
    say, refreshed emissions or a fresh ROI figure.
    """
    orch = Orchestrator()
    if agent_key not in orch.agents:
        return json.dumps({"error": f"Unknown agent: {agent_key}"})

    # Run the dependency closure in canonical order, stopping after the target.
    # Agents read their upstream inputs off the shared orchestrator instance,
    # so running them in order on `orch` is what wires the chain together.
    results: dict = {}
    for key in orch.agent_order:
        out = orch.agents[key].run(orchestrator=orch)
        results[key] = out
        if key == agent_key:
            break

    _save(username, results, goal=None, label=f"Pilot single-agent: {agent_key}")
    target = results.get(agent_key, {})
    return json.dumps({"agent": agent_key, "result": target}, default=str)


if __name__ == "__main__":
    mcp.run()

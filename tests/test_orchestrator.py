"""Smoke tests for the orchestrator's *non-LLM* surface.

The legacy ``_plan_next_step`` test predates the move to a Claude-driven
agent loop and was wired against an HF-fake that no longer exists.
We've replaced those tests with three behavioural pins that don't need
an Anthropic API key:

  1. Construction wires every agent in ``PIPELINE_ORDER`` with the
     correct telemetry key.
  2. ``run_single_agent`` dispatches by key and returns the agent's
     result dict (or an error dict for unknown agents).
  3. ``get_agent_statuses`` returns a row per agent with the keys the
     Mission Control fleet card consumes.

The real Anthropic loop and the incremental-cache behaviour are tested
in :mod:`test_orchestrator_cache` and exercised via the Mission Control
manual run; we don't want to spend a real API key on each CI run.
"""
from __future__ import annotations

from core.orchestrator import Orchestrator, PIPELINE_ORDER


def test_constructor_wires_every_agent_with_telemetry_key():
    orch = Orchestrator()
    expected_keys = [k for k, _, _ in PIPELINE_ORDER]
    assert list(orch.agents.keys()) == expected_keys
    for key in expected_keys:
        assert orch.agents[key].telemetry_key == key


def test_run_single_agent_dispatches_by_key(monkeypatch):
    orch = Orchestrator()

    captured = {}

    def fake_run(self_unused=None, **kwargs):
        captured["called"] = True
        return {"ok": True, "kwargs": list(kwargs.keys())}

    monkeypatch.setattr(orch.agents["data_collector"], "run", fake_run)

    out = orch.run_single_agent("data_collector", connection_manager=None)
    assert out["ok"] is True
    assert "connection_manager" in out["kwargs"]
    assert captured["called"]


def test_run_single_agent_unknown_key_returns_error_dict():
    orch = Orchestrator()
    out = orch.run_single_agent("not_a_real_agent")
    assert "error" in out
    assert "not_a_real_agent" in out["error"]


def test_get_agent_statuses_includes_required_keys():
    orch = Orchestrator()
    statuses = orch.get_agent_statuses()
    # One row per agent
    assert set(statuses.keys()) == {k for k, _, _ in PIPELINE_ORDER}
    # Each row has the keys Mission Control reads.
    for row in statuses.values():
        assert {"name", "status", "last_run", "runtime_seconds",
                "last_error", "run_count"} <= set(row.keys())

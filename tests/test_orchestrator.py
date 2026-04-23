import pytest

from core.orchestrator import Orchestrator


class FakeHF:
    def __init__(self, response):
        self.response = response

    def generate_text(self, prompt, max_tokens=300):
        return self.response


def test_planner_parses_structured_json(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "hf", FakeHF('{"action":"run_agent","agent":"data_collector","reason":"start with data"}'))

    plan = orch._plan_next_step("Assess CSRD readiness", {})

    assert plan["action"] == "run_agent"
    assert plan["agent"] == "data_collector"
    assert "reason" in plan


def test_planner_fallbacks_to_static_pipeline_when_llm_is_unparseable(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "hf", FakeHF("This is not JSON."))

    plan = orch._plan_next_step("Build an ESG report", {})

    assert plan["action"] == "run_agent"
    assert plan["agent"] == "data_collector"


def test_run_full_pipeline_returns_results_and_planning(monkeypatch):
    orch = Orchestrator()
    monkeypatch.setattr(orch, "hf", FakeHF("This is not JSON."))

    results = orch.run_full_pipeline(user_goal="Validate ESG readiness")

    assert "planning" in results
    assert "data_collector" in results
    assert results["data_collector"].get("datasets_loaded", 0) > 0
    assert results["planning"][0]["action"] == "run_agent"

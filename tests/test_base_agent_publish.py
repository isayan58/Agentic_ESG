"""BaseAgent.run() must auto-publish to ``output_channel`` on success.

This pins down the Step 6 contract: agents declare ``output_channel`` as a
class attribute, ``execute()`` returns a result dict, and the wrapper
publishes for them. Errors must NOT publish so subscribers don't see
``{"error": ...}`` sentinels masquerading as real results.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture
def fresh_state(monkeypatch):
    """Reset state_manager and yield it with a user-switching helper."""
    class _FakeSt:
        def __init__(self):
            self.session_state = {}

    fake_st = _FakeSt()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    from core.state_manager import state_manager
    state_manager.clear_all()

    fake_st.session_state["user"] = {"username": "tester"}
    yield state_manager
    state_manager.clear_all()


@pytest.fixture
def telem_isolated(monkeypatch, tmp_path):
    """Don't pollute the real telemetry file from these tests."""
    from utils import agent_telemetry as t
    monkeypatch.setattr(t, "_TELEMETRY_FILE", tmp_path / "telem.json")
    monkeypatch.setattr(t, "_DATA_DIR", tmp_path)


class TestAutoPublish:
    def test_completed_run_publishes_to_output_channel(self, fresh_state, telem_isolated):
        from core.base_agent import BaseAgent
        from core.channels import Channel

        class FakeAgent(BaseAgent):
            output_channel = Channel.CARBON

            def __init__(self):
                super().__init__("Fake", "fake agent")

            def execute(self, **kwargs):
                return {"scope1": 100}

        agent = FakeAgent()
        result = agent.run()
        assert result == {"scope1": 100}
        assert fresh_state.subscribe(Channel.CARBON) == {"scope1": 100}

    def test_error_run_does_not_publish(self, fresh_state, telem_isolated):
        from core.base_agent import BaseAgent
        from core.channels import Channel

        class BoomAgent(BaseAgent):
            output_channel = Channel.RISK

            def __init__(self):
                super().__init__("Boom", "boom agent")

            def execute(self, **kwargs):
                raise RuntimeError("kaboom")

        agent = BoomAgent()
        result = agent.run()
        assert "error" in result  # BaseAgent's error sentinel
        # Subscribers must not see a stale/error payload on the channel.
        assert fresh_state.subscribe(Channel.RISK) is None

    def test_no_output_channel_means_no_publish(self, fresh_state, telem_isolated):
        from core.base_agent import BaseAgent
        from core.channels import Channel

        class SilentAgent(BaseAgent):
            # output_channel left as the default None
            def __init__(self):
                super().__init__("Silent", "silent agent")

            def execute(self, **kwargs):
                return {"x": 1}

        SilentAgent().run()
        # None of the canonical channels were touched.
        assert fresh_state.subscribe(Channel.AUDIT) is None
        assert fresh_state.subscribe(Channel.ROI) is None

    def test_publish_failure_does_not_break_run(self, fresh_state, telem_isolated, monkeypatch):
        from core.base_agent import BaseAgent
        from core.channels import Channel
        from core import state_manager as sm_module

        class FlakyPublishAgent(BaseAgent):
            output_channel = Channel.AUDIT

            def __init__(self):
                super().__init__("Flaky", "flaky agent")

            def execute(self, **kwargs):
                return {"ok": True}

        def _broken_publish(*a, **kw):
            raise IOError("disk full")

        monkeypatch.setattr(sm_module.state_manager, "publish", _broken_publish)

        # The run should still return cleanly; publish failure is swallowed.
        result = FlakyPublishAgent().run()
        assert result == {"ok": True}

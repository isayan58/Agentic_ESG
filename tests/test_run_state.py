import pytest
from pydantic import ValidationError

from core.channels import Channel
from core.run_state import AgentError, RunState


class TestRunStateConstruction:
    def test_minimal_required_fields(self):
        s = RunState(user_id="alice")
        assert s.user_id == "alice"
        assert s.company_id is None
        assert s.status == "created"
        assert s.outputs == {}
        assert s.errors == []
        # run_id auto-generated
        assert s.run_id and len(s.run_id) >= 32
        assert s.created_at  # ISO timestamp populated

    def test_user_id_required(self):
        with pytest.raises(ValidationError):
            RunState()  # missing user_id

    def test_extra_fields_rejected(self):
        # extra="forbid" guards against typo-d kwargs leaking in.
        with pytest.raises(ValidationError):
            RunState(user_id="alice", random_typo="x")


class TestRunStateLifecycle:
    def test_status_transitions(self):
        s = RunState(user_id="alice")
        assert s.status == "created"

        s.mark_running()
        assert s.status == "running"
        assert s.started_at is not None

        s.mark_completed()
        assert s.status == "completed"
        assert s.finished_at is not None

    def test_error_path(self):
        s = RunState(user_id="alice")
        s.mark_running()
        s.mark_error()
        assert s.status == "error"
        assert s.finished_at is not None

    def test_record_error_appends(self):
        s = RunState(user_id="alice")
        s.record_error("carbon_accountant", "missing emissions data")
        s.record_error("audit_agent", "evidence_map empty")
        assert len(s.errors) == 2
        assert isinstance(s.errors[0], AgentError)
        assert s.errors[0].agent == "carbon_accountant"
        assert s.has_errors()


class TestOutputsByChannel:
    def test_record_with_enum_member(self):
        s = RunState(user_id="alice")
        s.record_output(Channel.CARBON, {"scope1": 100})
        # Stored under the string value, not the enum member, for portability.
        assert s.outputs == {"carbon_results": {"scope1": 100}}

    def test_get_with_enum_member(self):
        s = RunState(user_id="alice")
        s.record_output(Channel.RISK, {"score": 42})
        assert s.get_output(Channel.RISK) == {"score": 42}
        assert s.get_output("risk_results") == {"score": 42}

    def test_default_for_missing_channel(self):
        s = RunState(user_id="alice")
        assert s.get_output(Channel.AUDIT) is None
        assert s.get_output(Channel.AUDIT, default={}) == {}


class TestSerialization:
    def test_round_trip_preserves_state(self):
        s = RunState(user_id="alice", company_id="acme")
        s.mark_running()
        s.record_output(Channel.CARBON, {"scope1": 100})
        s.record_error("audit_agent", "boom")
        s.mark_completed()

        dumped = s.model_dump()
        restored = RunState.model_validate(dumped)
        assert restored.user_id == "alice"
        assert restored.company_id == "acme"
        assert restored.status == "completed"
        assert restored.outputs == {"carbon_results": {"scope1": 100}}
        assert restored.errors[0].agent == "audit_agent"

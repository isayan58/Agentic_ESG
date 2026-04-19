"""Cross-user isolation regression tests for ``core.state_manager``.

These tests pin down the bug surfaced in production: User A's pipeline
results were visible to User B in the same Python process because the
shared singleton's ``_channels`` dict was process-wide. Per-user
partitioning (see ``core/state_manager.py``) fixes this; the assertions
below guarantee we don't regress.
"""
from __future__ import annotations

import sys

import pytest


@pytest.fixture
def fresh_sm(monkeypatch):
    """Yield a freshly cleared ``state_manager`` and a helper to switch
    the "current user" by mutating a fake ``streamlit.session_state``.

    Important: ``state_manager._current_username`` resolves the
    signed-in user from ``streamlit.session_state["user"]["username"]``,
    so we install a fake ``streamlit`` module *into the import system*
    before importing ``state_manager`` again. The fake holds a
    ``session_state`` dict the test can mutate to swap users.
    """
    # Install a minimal fake streamlit so the imports inside
    # ``_current_username`` resolve to our shim.
    class _FakeSt:
        def __init__(self):
            self.session_state = {}

    fake_st = _FakeSt()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    # Reset the singleton — its module is already imported above.
    from core.state_manager import state_manager
    state_manager.clear_all()

    def set_user(username: str | None) -> None:
        if username is None:
            fake_st.session_state.pop("user", None)
        else:
            fake_st.session_state["user"] = {"username": username}

    yield state_manager, set_user

    state_manager.clear_all()


class TestPerUserIsolation:
    def test_publish_by_user_a_is_invisible_to_user_b(self, fresh_sm):
        """Core regression: publishing as one user must not be readable
        by another. Without the fix this assertion fails because both
        users share the same ``_channels`` dict.
        """
        sm, set_user = fresh_sm

        set_user("alice")
        sm.publish("carbon_results", {"scope1": 1234}, agent_name="carbon")

        # Switch to a fresh user — they must see no data on the channel.
        set_user("bob")
        assert sm.subscribe("carbon_results") is None

        # And publishing as Bob doesn't pollute Alice.
        sm.publish("carbon_results", {"scope1": 9999}, agent_name="carbon")
        set_user("alice")
        assert sm.subscribe("carbon_results") == {"scope1": 1234}

    def test_get_all_channels_only_returns_current_user_channels(self, fresh_sm):
        sm, set_user = fresh_sm

        set_user("alice")
        sm.publish("regulatory_results", {"x": 1})
        set_user("bob")
        sm.publish("audit_results", {"y": 2})

        assert "regulatory_results" not in sm.get_all_channels()
        assert "audit_results" in sm.get_all_channels()

        set_user("alice")
        assert "regulatory_results" in sm.get_all_channels()
        assert "audit_results" not in sm.get_all_channels()

    def test_clear_only_clears_current_user(self, fresh_sm):
        sm, set_user = fresh_sm

        set_user("alice")
        sm.publish("carbon_results", {"a": 1})
        set_user("bob")
        sm.publish("carbon_results", {"b": 2})

        # Bob clears his own bucket — Alice's data must survive.
        sm.clear()
        assert sm.subscribe("carbon_results") is None
        set_user("alice")
        assert sm.subscribe("carbon_results") == {"a": 1}

    def test_clear_user_drops_specific_username(self, fresh_sm):
        sm, set_user = fresh_sm

        set_user("alice")
        sm.publish("audit_results", {"a": 1})
        set_user("bob")
        sm.publish("audit_results", {"b": 2})

        # Logging Alice out from elsewhere wipes her bucket without
        # touching Bob's currently-active session.
        sm.clear_user("alice")

        # Bob still sees his data.
        assert sm.subscribe("audit_results") == {"b": 2}
        # Alice sees nothing on her next visit.
        set_user("alice")
        assert sm.subscribe("audit_results") is None

    def test_guest_users_share_anonymous_bucket(self, fresh_sm):
        """Guests (no signed-in user) all route to ``_anonymous`` — this
        is intentional, since there is no per-session identity to key
        on. The follow-up sign-in still gets a clean per-username bucket.
        """
        sm, set_user = fresh_sm

        set_user(None)
        sm.publish("data_collection_results", {"k": 1})
        # Another guest sees the same bucket — that's expected for the
        # demo flow, which has no per-tab identity.
        assert sm.subscribe("data_collection_results") == {"k": 1}

        # As soon as someone signs in, they're isolated.
        set_user("eve")
        assert sm.subscribe("data_collection_results") is None

    def test_internal_channels_property_returns_current_user_bucket(self, fresh_sm):
        """``utils.pipeline_refresh._clear_stale_state_datasets`` mutates
        ``state_manager._channels`` directly; the property must point at
        the *current* user so the pop targets only their data.
        """
        sm, set_user = fresh_sm

        set_user("alice")
        sm.publish("dataset_emissions", {"x": 1})
        set_user("bob")
        sm.publish("dataset_emissions", {"y": 2})

        # Bob's pipeline-refresh path pops from her own bucket only.
        sm._channels.pop("dataset_emissions", None)
        assert sm.subscribe("dataset_emissions") is None
        set_user("alice")
        assert sm.subscribe("dataset_emissions") == {"x": 1}

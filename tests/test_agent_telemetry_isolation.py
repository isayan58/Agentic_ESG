"""Per-user isolation regression tests for ``utils.agent_telemetry``.

Mirrors the structure of ``test_state_manager_isolation``. Two users in
the same Python process must never see each other's runs.
"""
from __future__ import annotations

import json
import sys

import pytest


@pytest.fixture
def telem(monkeypatch, tmp_path):
    """Yield the telemetry module pointed at a tmp file with a swappable user."""
    class _FakeSt:
        def __init__(self):
            self.session_state = {}

    fake_st = _FakeSt()
    monkeypatch.setitem(sys.modules, "streamlit", fake_st)

    # Force the module to flush import state so the local streamlit import
    # inside _current_username sees our fake. The module already uses a
    # local import on every call, so we just point its file path elsewhere.
    from utils import agent_telemetry as t
    monkeypatch.setattr(t, "_TELEMETRY_FILE", tmp_path / "telem.json")
    monkeypatch.setattr(t, "_DATA_DIR", tmp_path)

    def set_user(username):
        if username is None:
            fake_st.session_state.pop("user", None)
        else:
            fake_st.session_state["user"] = {"username": username}

    yield t, set_user


class TestPerUserIsolation:
    def test_record_by_alice_invisible_to_bob(self, telem):
        t, set_user = telem

        set_user("alice")
        t.record("data_collector", {"status": "completed", "runtime_seconds": 1.5})

        set_user("bob")
        assert t.get("data_collector") is None
        assert t.load_all() == {}

    def test_each_user_sees_only_their_own(self, telem):
        t, set_user = telem

        set_user("alice")
        t.record("data_collector", {"status": "completed", "runtime_seconds": 1.0})
        set_user("bob")
        t.record("data_collector", {"status": "error", "last_error": "boom"})

        set_user("alice")
        rec = t.get("data_collector")
        assert rec["status"] == "completed"
        assert rec["runtime_seconds"] == 1.0

        set_user("bob")
        rec = t.get("data_collector")
        assert rec["status"] == "error"

    def test_explicit_user_id_overrides_session(self, telem):
        t, set_user = telem

        set_user("alice")
        t.record("data_collector", {"status": "completed"}, user_id="bob")

        # Recorded under bob, not alice.
        assert t.get("data_collector") is None
        assert t.get("data_collector", user_id="bob")["status"] == "completed"

    def test_history_is_per_user(self, telem):
        t, set_user = telem

        set_user("alice")
        t.record("carbon", {"status": "completed", "runtime_seconds": 1.0,
                            "finished_at": "2026-01-01T00:00:00"})
        t.record("carbon", {"status": "completed", "runtime_seconds": 2.0,
                            "finished_at": "2026-01-02T00:00:00"})

        set_user("bob")
        assert t.history("carbon") == []

        set_user("alice")
        hist = t.history("carbon")
        assert len(hist) == 2
        assert hist[0]["timestamp"] == "2026-01-02T00:00:00"

    def test_reset_only_affects_target_user(self, telem):
        t, set_user = telem

        set_user("alice")
        t.record("data_collector", {"status": "completed"})
        set_user("bob")
        t.record("data_collector", {"status": "completed"})

        set_user("alice")
        t.reset()  # alice only

        set_user("bob")
        assert t.get("data_collector") is not None
        set_user("alice")
        assert t.get("data_collector") is None


class TestLegacyMigration:
    def test_old_flat_shape_is_quarantined_under_legacy(self, telem, tmp_path):
        t, set_user = telem

        # Write an old-shape file: {agent_key: {...}}, no user partitioning.
        old = {
            "data_collector": {
                "status": "completed",
                "last_run": "2026-01-01T00:00:00",
                "history": [{"status": "completed", "runtime_seconds": 1.0}],
            }
        }
        t._TELEMETRY_FILE.write_text(json.dumps(old))

        set_user("alice")
        # Alice should NOT see the legacy data — it belongs to no one yet.
        assert t.get("data_collector") is None

        # But it survives under the _legacy bucket.
        assert t.get("data_collector", user_id="_legacy")["status"] == "completed"

    def test_writing_after_legacy_preserves_legacy_bucket(self, telem):
        t, set_user = telem

        old = {"carbon": {"status": "completed", "history": []}}
        t._TELEMETRY_FILE.write_text(json.dumps(old))

        set_user("alice")
        t.record("data_collector", {"status": "completed"})

        # Both buckets co-exist on disk.
        on_disk = json.loads(t._TELEMETRY_FILE.read_text())
        assert "_legacy" in on_disk
        assert "alice" in on_disk
        assert on_disk["_legacy"]["carbon"]["status"] == "completed"
        assert on_disk["alice"]["data_collector"]["status"] == "completed"


class TestGuestFallback:
    def test_no_signed_in_user_routes_to_anonymous(self, telem):
        t, set_user = telem

        set_user(None)
        t.record("data_collector", {"status": "completed"})
        assert t.get("data_collector")["status"] == "completed"
        assert t.get("data_collector", user_id="_anonymous")["status"] == "completed"

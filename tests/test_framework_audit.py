"""Tests for the regulatory-update audit log + revert flow.

Pins three guarantees:
  1. apply → revert → apply round-trips cleanly. Revert removes the
     requirement that apply added; re-apply re-adds it.
  2. Every apply / revert / dismiss action lands in the audit log
     with the actor and timestamp.
  3. Revert is idempotent — calling it twice is a no-op that still
     records the operator's intent.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils import framework_refresh as fr


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """Redirect framework_refresh's two JSON files to a tmp dir.

    The module reads/writes ``data/regulatory_frameworks.json`` and
    ``data/regulatory_updates.json`` directly — bypass the real files
    so tests don't mutate shipped data.
    """
    fr_path = tmp_path / "regulatory_frameworks.json"
    upd_path = tmp_path / "regulatory_updates.json"

    fr_path.write_text(json.dumps({
        "frameworks": {
            "CSRD": {
                "name": "Corporate Sustainability Reporting Directive",
                "requirements": [
                    {"id": "CSRD-EXISTING", "section": "1", "requirement": "Existing"},
                ],
            },
            "BRSR": {"name": "BRSR", "requirements": []},
        }
    }))

    monkeypatch.setattr(fr, "FRAMEWORKS_PATH", fr_path)
    monkeypatch.setattr(fr, "UPDATES_PATH", upd_path)
    monkeypatch.setattr(fr, "DATA_DIR", tmp_path)
    return tmp_path


def _seed_pending_update(update_id: str = "abc123",
                         requirement_id: str = "CSRD-NEW",
                         framework: str = "CSRD") -> dict:
    return {
        "id": update_id,
        "framework": framework,
        "type": "new_requirement",
        "title": "New disclosure",
        "description": "A new mandatory thing",
        "source_url": "https://example.com/rule",
        "detected_at": "2026-04-25T10:00:00",
        "impact": "high",
        "status": "pending",
        "proposed_requirement": {
            "id": requirement_id,
            "section": "12.3",
            "requirement": "Disclose climate transition plan",
            "data_fields": ["transition_plan", "capex_alignment"],
            "priority": "critical",
        },
    }


class TestApplyAndAudit:
    def test_apply_appends_requirement_and_audit_entry(self, isolated_data_dir):
        store = fr._empty_store()
        store["updates"].append(_seed_pending_update())
        fr.save_updates_store(store)

        result = fr.apply_update("abc123", actor="alice")

        assert result["ok"]
        assert result["requirement_id"] == "CSRD-NEW"

        # Framework file mutated
        fw = fr.load_frameworks()
        ids = [r["id"] for r in fw["frameworks"]["CSRD"]["requirements"]]
        assert "CSRD-NEW" in ids

        # Update marked applied with actor
        s2 = fr.load_updates_store()
        u = s2["updates"][0]
        assert u["status"] == "applied"
        assert u["applied_by"] == "alice"
        assert u["applied_requirement_id"] == "CSRD-NEW"

        # Audit log captured the action
        log = fr.audit_log(s2)
        assert len(log) == 1
        assert log[0]["action"] == "apply"
        assert log[0]["actor"] == "alice"
        assert log[0]["framework"] == "CSRD"

    def test_apply_idempotent_does_not_double_audit(self, isolated_data_dir):
        store = fr._empty_store()
        store["updates"].append(_seed_pending_update())
        fr.save_updates_store(store)

        fr.apply_update("abc123", actor="alice")
        result = fr.apply_update("abc123", actor="alice")

        assert result.get("already") is True
        log = fr.audit_log(fr.load_updates_store())
        # Second apply was a no-op — only one audit entry.
        assert len(log) == 1

    def test_apply_unknown_id_returns_error(self, isolated_data_dir):
        fr.save_updates_store(fr._empty_store())
        result = fr.apply_update("nope", actor="alice")
        assert not result["ok"]
        assert "No update" in result["reason"]


class TestRevert:
    def test_revert_removes_requirement_and_logs(self, isolated_data_dir):
        store = fr._empty_store()
        store["updates"].append(_seed_pending_update())
        fr.save_updates_store(store)

        fr.apply_update("abc123", actor="alice")
        result = fr.revert_update("abc123", actor="bob",
                                  reason="False positive")

        assert result["ok"]
        assert result["requirement_removed"] is True

        # Requirement removed from the framework file
        fw = fr.load_frameworks()
        ids = [r["id"] for r in fw["frameworks"]["CSRD"]["requirements"]]
        assert "CSRD-NEW" not in ids
        # The pre-existing requirement is untouched.
        assert "CSRD-EXISTING" in ids

        # Update flipped back to pending so a human can re-decide
        u = fr.load_updates_store()["updates"][0]
        assert u["status"] == "pending"
        assert u["reverted_by"] == "bob"
        assert u["revert_reason"] == "False positive"
        assert "applied_at" not in u
        assert "applied_requirement_id" not in u

        # Audit log has both the apply and the revert. Order can tie on
        # the same-second timestamp; assert *content*, not order.
        log = fr.audit_log(fr.load_updates_store())
        actions = sorted(e["action"] for e in log)
        assert actions == ["apply", "revert"]
        revert_entry = next(e for e in log if e["action"] == "revert")
        assert revert_entry["actor"] == "bob"
        assert revert_entry["reason"] == "False positive"

    def test_revert_round_trip_reapply_works(self, isolated_data_dir):
        store = fr._empty_store()
        store["updates"].append(_seed_pending_update())
        fr.save_updates_store(store)

        fr.apply_update("abc123", actor="alice")
        fr.revert_update("abc123", actor="bob")
        # Re-apply should re-add the requirement.
        fr.apply_update("abc123", actor="carol")

        fw = fr.load_frameworks()
        ids = [r["id"] for r in fw["frameworks"]["CSRD"]["requirements"]]
        assert ids.count("CSRD-NEW") == 1, "round-trip should not duplicate"

    def test_revert_on_pending_update_is_noop(self, isolated_data_dir):
        store = fr._empty_store()
        store["updates"].append(_seed_pending_update())
        fr.save_updates_store(store)

        result = fr.revert_update("abc123", actor="alice", reason="oops")
        assert not result["ok"]
        assert result.get("already_reverted")

        # Still logged — operator's *intent* matters even when the
        # action was a no-op.
        log = fr.audit_log(fr.load_updates_store())
        assert any(e["action"] == "revert_skipped" for e in log)

    def test_revert_unknown_id_returns_error(self, isolated_data_dir):
        fr.save_updates_store(fr._empty_store())
        result = fr.revert_update("nope")
        assert not result["ok"]


class TestDismiss:
    def test_dismiss_records_actor_and_audit(self, isolated_data_dir):
        store = fr._empty_store()
        store["updates"].append(_seed_pending_update())
        fr.save_updates_store(store)

        fr.dismiss_update("abc123", reason="duplicate", actor="alice")

        u = fr.load_updates_store()["updates"][0]
        assert u["status"] == "dismissed"
        assert u["dismissed_by"] == "alice"
        assert u["dismiss_reason"] == "duplicate"

        log = fr.audit_log(fr.load_updates_store())
        assert log[0]["action"] == "dismiss"
        assert log[0]["actor"] == "alice"


class TestAuditLogFilters:
    def test_filter_by_framework(self, isolated_data_dir):
        store = fr._empty_store()
        store["updates"].append(_seed_pending_update("u1", framework="CSRD",
                                                      requirement_id="CSRD-1"))
        store["updates"].append(_seed_pending_update("u2", framework="BRSR",
                                                      requirement_id="BRSR-1"))
        fr.save_updates_store(store)

        fr.apply_update("u1", actor="alice")
        fr.apply_update("u2", actor="alice")

        csrd_only = fr.audit_log(framework="CSRD")
        assert len(csrd_only) == 1
        assert csrd_only[0]["framework"] == "CSRD"

    def test_limit_truncates_head(self, isolated_data_dir):
        store = fr._empty_store()
        for i in range(5):
            store["updates"].append(_seed_pending_update(
                f"u{i}", framework="CSRD", requirement_id=f"CSRD-{i}",
            ))
        fr.save_updates_store(store)
        for i in range(5):
            fr.apply_update(f"u{i}", actor="alice")

        log = fr.audit_log(limit=3)
        assert len(log) == 3

"""Tests for the persistent pipeline-run snapshot store.

Tests run against the local-JSON backend only — the HF Dataset path
needs network and a real token. The local fallback is what every
unsigned-token deployment hits, so we exercise it end-to-end.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from utils import run_store


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    """Force the local-JSON backend into a tmp dir for each test.

    Returns a fresh ``RunStore`` with the singleton bypassed so each
    test starts clean.
    """
    monkeypatch.setattr(run_store, "LOCAL_FALLBACK_DIR", tmp_path / "runs")
    # Force the local backend by stripping any inherited HF token
    # (the dev's machine may have one set in ~/.cache).
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_API_TOKEN", raising=False)
    monkeypatch.delenv("HUGGING_FACE_HUB_TOKEN", raising=False)
    # Make sure the home-dir token file isn't picked up either.
    monkeypatch.setattr(run_store.Path, "home", classmethod(lambda cls: tmp_path / "_home"))

    store = run_store.RunStore(history_cap=3)
    return store


def _example_results() -> dict:
    return {
        "data_collector": {"total_records": 1234, "datasets": {"x": 1}},
        "audit_agent": {"readiness_score": {"grade": "B", "overall": 76}},
        "roi_agent": {"investment_quality_score": {"grade": "A", "score": 82}},
        "carbon_accountant": {"total_emissions_current": 9876},
    }


class TestSaveAndList:
    def test_save_returns_run_id_and_lists(self, isolated_store):
        rid = isolated_store.save_run(
            "alice",
            results=_example_results(),
            label="Q3 review",
            goal="Q3 CSRD prep",
            saved_by="alice",
        )
        assert rid

        runs = isolated_store.list_runs("alice")
        assert len(runs) == 1
        assert runs[0]["id"] == rid
        assert runs[0]["label"] == "Q3 review"
        assert runs[0]["headline"]["audit_grade"] == "B"
        assert runs[0]["headline"]["iqs_grade"] == "A"

    def test_load_round_trips_results(self, isolated_store):
        rid = isolated_store.save_run(
            "alice", results=_example_results(), label="r1",
        )
        snap = isolated_store.load_run("alice", rid)
        assert snap is not None
        # Top-level metadata
        assert snap["label"] == "r1"
        # Results round-trip exactly (within JSON's typing surface).
        assert snap["results"]["data_collector"]["total_records"] == 1234
        assert snap["results"]["audit_agent"]["readiness_score"]["grade"] == "B"

    def test_users_are_isolated(self, isolated_store):
        isolated_store.save_run("alice", results=_example_results(), label="A")
        isolated_store.save_run("bob",   results=_example_results(), label="B")
        assert len(isolated_store.list_runs("alice")) == 1
        assert len(isolated_store.list_runs("bob")) == 1
        assert isolated_store.list_runs("alice")[0]["label"] == "A"
        assert isolated_store.list_runs("bob")[0]["label"] == "B"

    def test_list_returns_newest_first(self, isolated_store):
        ids = [
            isolated_store.save_run("alice", results=_example_results(), label=f"r{i}")
            for i in range(3)
        ]
        runs = isolated_store.list_runs("alice")
        assert [r["id"] for r in runs] == list(reversed(ids))


class TestDelete:
    def test_delete_removes_from_index_and_disk(self, isolated_store, tmp_path):
        rid = isolated_store.save_run("alice", results=_example_results(),
                                       label="r1")
        snap_path = isolated_store._local_snapshot_path("alice", rid)
        assert snap_path.is_file()

        assert isolated_store.delete_run("alice", rid) is True
        assert isolated_store.list_runs("alice") == []
        assert not snap_path.is_file()

    def test_delete_unknown_returns_false(self, isolated_store):
        assert isolated_store.delete_run("alice", "no-such-id") is False


class TestHistoryCap:
    def test_oldest_runs_pruned_after_cap(self, isolated_store):
        # cap=3 from the fixture
        ids = [
            isolated_store.save_run("alice", results=_example_results(), label=f"r{i}")
            for i in range(5)
        ]
        runs = isolated_store.list_runs("alice")
        assert len(runs) == 3
        # The two oldest should have been pruned.
        kept_ids = [r["id"] for r in runs]
        assert ids[0] not in kept_ids
        assert ids[1] not in kept_ids
        assert ids[-1] in kept_ids

    def test_pruned_snapshots_deleted_from_disk(self, isolated_store):
        ids = [
            isolated_store.save_run("alice", results=_example_results(), label=f"r{i}")
            for i in range(5)
        ]
        # First two were rotated out — their snapshot files should be gone.
        for rotated_id in ids[:2]:
            assert not isolated_store._local_snapshot_path("alice", rotated_id).is_file()


class TestSizeCap:
    def test_oversized_run_raises(self, isolated_store, monkeypatch):
        # Drop the cap to something tiny so the example results blow it.
        monkeypatch.setattr(run_store, "MAX_SNAPSHOT_BYTES", 100)
        with pytest.raises(ValueError, match="cap"):
            isolated_store.save_run("alice", results=_example_results(),
                                     label="big")
        # The index must not have been updated when the save aborted.
        assert isolated_store.list_runs("alice") == []


class TestUsernameSanitisation:
    def test_unsafe_chars_normalised(self, isolated_store):
        # "alice@example.com" must end up as a filesystem-safe key,
        # and lookups must use the same normalised key so save+load
        # round-trip without the caller having to pre-clean the name.
        rid = isolated_store.save_run("alice@example.com",
                                       results=_example_results(), label="r")
        runs = isolated_store.list_runs("alice@example.com")
        assert len(runs) == 1
        assert runs[0]["id"] == rid


class TestDiagnostic:
    def test_reports_local_backend_after_save(self, isolated_store):
        isolated_store.save_run("alice", results=_example_results(), label="r")
        diag = isolated_store.diagnostic()
        assert diag["backend"] == "local_json"
        assert "Local JSON" in diag["label"]

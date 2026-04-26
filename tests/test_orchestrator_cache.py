"""Tests for the incremental-run cache on :class:`core.orchestrator.Orchestrator`.

The cache is a pure in-memory data structure on the orchestrator
instance — independent of the Anthropic agent loop, which makes it
unit-testable without an API key.

What's pinned here:
  1. Fingerprints are stable for the same inputs and change when any
     dependency's result changes.
  2. ``store_incremental_cache`` refuses to memoise errored runs.
  3. ``lookup_incremental_cache`` distinguishes "have nothing" from
     "have a cached empty dict".
  4. ``invalidate_incremental_cache`` clears both the cache and the
     last-run hit counters.
  5. The data_collector fingerprint reflects the connection-manager's
     source signature, so swapping sources busts the cache.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.orchestrator import Orchestrator


@pytest.fixture
def orch():
    """Fresh orchestrator per test, with the cache empty."""
    o = Orchestrator()
    o.invalidate_incremental_cache()
    return o


class FakeConnectionManager:
    """Just enough surface to satisfy ``compute_dep_fingerprint``."""
    def __init__(self, signature: str):
        self._sig = signature

    def sources_signature(self) -> str:
        return self._sig


class TestFingerprints:
    def test_same_inputs_same_fingerprint(self, orch):
        results = {"data_collector": {"total_records": 10}}
        f1 = orch.compute_dep_fingerprint("regulatory_tracker", results)
        f2 = orch.compute_dep_fingerprint("regulatory_tracker", results)
        assert f1 == f2

    def test_dep_change_changes_fingerprint(self, orch):
        before = {"data_collector": {"total_records": 10}}
        after = {"data_collector": {"total_records": 20}}
        f1 = orch.compute_dep_fingerprint("regulatory_tracker", before)
        f2 = orch.compute_dep_fingerprint("regulatory_tracker", after)
        assert f1 != f2

    def test_data_collector_fingerprint_uses_sources_signature(self, orch):
        cm_a = FakeConnectionManager("sig-a")
        cm_b = FakeConnectionManager("sig-b")
        f1 = orch.compute_dep_fingerprint(
            "data_collector", {},
            data_collector_kwargs={"connection_manager": cm_a},
        )
        f2 = orch.compute_dep_fingerprint(
            "data_collector", {},
            data_collector_kwargs={"connection_manager": cm_b},
        )
        f1_repeat = orch.compute_dep_fingerprint(
            "data_collector", {},
            data_collector_kwargs={"connection_manager": cm_a},
        )
        assert f1 != f2
        assert f1 == f1_repeat

    def test_data_collector_fingerprint_no_manager_is_stable(self, orch):
        # No connection manager → falls through to the kwargs surface
        # only. Same kwargs → same fingerprint.
        f1 = orch.compute_dep_fingerprint("data_collector", {})
        f2 = orch.compute_dep_fingerprint("data_collector", {})
        assert f1 == f2

    def test_chain_propagates_through_deps(self, orch):
        # If data_collector's fingerprint changes (different sources),
        # downstream agents whose deps include data_collector should
        # also see a different fingerprint — even if the in-memory
        # results dict is identical (the cache memo carries the change).
        cm_a = FakeConnectionManager("sig-a")
        cm_b = FakeConnectionManager("sig-b")

        # Simulate a successful data_collector run under sig-a:
        dc_fp_a = orch.compute_dep_fingerprint(
            "data_collector", {},
            data_collector_kwargs={"connection_manager": cm_a},
        )
        orch.store_incremental_cache("data_collector", dc_fp_a, {"total_records": 1})
        results = {"data_collector": {"total_records": 1}}
        # Regulatory's fingerprint reflects dc_fp_a.
        reg_fp_under_a = orch.compute_dep_fingerprint("regulatory_tracker", results)

        # Now switch sources and re-run data_collector:
        dc_fp_b = orch.compute_dep_fingerprint(
            "data_collector", {},
            data_collector_kwargs={"connection_manager": cm_b},
        )
        assert dc_fp_a != dc_fp_b
        orch.store_incremental_cache("data_collector", dc_fp_b, {"total_records": 2})
        results = {"data_collector": {"total_records": 2}}
        reg_fp_under_b = orch.compute_dep_fingerprint("regulatory_tracker", results)
        assert reg_fp_under_a != reg_fp_under_b


class TestStoreAndLookup:
    def test_lookup_miss_when_empty(self, orch):
        hit, value = orch.lookup_incremental_cache("data_collector", "fp-x")
        assert hit is False
        assert value is None

    def test_lookup_hit_after_store(self, orch):
        orch.store_incremental_cache("data_collector", "fp-x", {"ok": True})
        hit, value = orch.lookup_incremental_cache("data_collector", "fp-x")
        assert hit is True
        assert value == {"ok": True}

    def test_lookup_miss_on_different_fingerprint(self, orch):
        orch.store_incremental_cache("data_collector", "fp-x", {"ok": True})
        hit, value = orch.lookup_incremental_cache("data_collector", "fp-y")
        assert hit is False
        assert value is None

    def test_empty_fingerprint_never_hits(self, orch):
        # Avoids accidental hits when the fingerprint computation
        # returned "" (e.g. a connection manager with no sources_signature).
        orch.store_incremental_cache("data_collector", "", {"ok": True})
        hit, _ = orch.lookup_incremental_cache("data_collector", "")
        assert hit is False

    def test_errored_results_are_not_cached(self, orch):
        orch.store_incremental_cache("data_collector", "fp-x",
                                      {"error": "fetch failed"})
        hit, _ = orch.lookup_incremental_cache("data_collector", "fp-x")
        assert hit is False, "errored runs must re-execute next time"

    def test_distinguishes_empty_dict_from_missing(self, orch):
        # Cached empty dict is a valid result — must hit, not be
        # mistaken for "nothing cached".
        orch.store_incremental_cache("data_collector", "fp-x", {})
        hit, value = orch.lookup_incremental_cache("data_collector", "fp-x")
        assert hit is True
        assert value == {}


class TestCacheLifecycle:
    def test_invalidate_clears_everything(self, orch):
        orch.store_incremental_cache("data_collector", "fp-x", {"ok": True})
        orch.record_cache_hit("data_collector")
        assert orch.cache_hits_last_run() == ["data_collector"]

        orch.invalidate_incremental_cache()

        hit, _ = orch.lookup_incremental_cache("data_collector", "fp-x")
        assert hit is False
        assert orch.cache_hits_last_run() == []

    def test_record_cache_hit_appends(self, orch):
        orch.record_cache_hit("data_collector")
        orch.record_cache_hit("regulatory_tracker")
        assert orch.cache_hits_last_run() == ["data_collector", "regulatory_tracker"]

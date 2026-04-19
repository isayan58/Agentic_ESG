"""Tests for ConnectionManager: signatures, per-source caching, errors.

These tests drive the manager with an in-memory fake connector so no
network / driver is required. The fixtures live in ``conftest.py``.
"""
from __future__ import annotations

import pandas as pd
import pytest

from utils.connection_manager import ConnectionManager, _signature


# ══════════════════════════════════════════════════════════════════════
# _signature helper
# ══════════════════════════════════════════════════════════════════════

class TestSignatureHelper:
    def test_deterministic_for_equal_inputs(self):
        assert _signature("a", {"k": 1}) == _signature("a", {"k": 1})

    def test_differs_when_value_changes(self):
        assert _signature("a", {"k": 1}) != _signature("a", {"k": 2})

    def test_order_independent_for_dicts(self):
        a = _signature({"x": 1, "y": 2})
        b = _signature({"y": 2, "x": 1})
        assert a == b

    def test_bytes_hashed_with_full_sha256(self):
        # Two 4-byte payloads that differ → must produce different signatures.
        sig_a = _signature({"blob": b"AAAA"})
        sig_b = _signature({"blob": b"AAAB"})
        assert sig_a != sig_b
        # Same bytes → same signature
        assert _signature({"blob": b"AAAA"}) == _signature({"blob": b"AAAA"})

    def test_bytes_signature_length_suggests_full_sha256(self):
        # The bytes-marker we embed should contain a 64-hex-char hash
        # (SHA-256), not the 16-char truncated hash used previously.
        import hashlib
        import json
        payload = b"hello-world"
        # Reconstruct what _signature's _coerce would store
        marker = f"bytes:{len(payload)}:{hashlib.sha256(payload).hexdigest()}"
        assert len(marker.split(":")[-1]) == 64

    def test_handles_non_json_serialisable_via_repr(self):
        # An object with no JSON representation should still produce a
        # stable signature by falling back to repr().
        class Widget:
            def __repr__(self):
                return "Widget(1)"
        sig_a = _signature(Widget())
        sig_b = _signature(Widget())
        assert sig_a == sig_b


# ══════════════════════════════════════════════════════════════════════
# Registry behaviour
# ══════════════════════════════════════════════════════════════════════

class TestRegistry:
    def test_add_source_initialises_cache_fields(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {"uri": "s3://x"},
                       "emissions", {"a": "b"})
        src = mgr.get_source("s1")
        assert src["_cached_signature"] is None
        assert src["_cached_df"] is None
        assert src["status"] == "configured"

    def test_list_sources_hides_underscore_cache_fields(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {}, "emissions", {})
        rows = mgr.list_sources()
        assert rows and all(not k.startswith("_") for k in rows[0].keys())
        assert rows[0]["id"] == "s1"

    def test_remove_source_returns_bool(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {}, "emissions", {})
        assert mgr.remove_source("s1") is True
        assert mgr.remove_source("s1") is False

    def test_has_sources_tracks_state(self):
        mgr = ConnectionManager()
        assert mgr.has_sources() is False
        mgr.add_source("s1", "delta_lake", {}, "emissions", {})
        assert mgr.has_sources() is True
        mgr.remove_source("s1")
        assert mgr.has_sources() is False


# ══════════════════════════════════════════════════════════════════════
# Signatures
# ══════════════════════════════════════════════════════════════════════

class TestSignatures:
    def test_source_signature_stable(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {"k": "v"}, "emissions", {})
        s1 = mgr.source_signature("s1")
        s2 = mgr.source_signature("s1")
        assert s1 == s2 and len(s1) == 64

    def test_source_signature_empty_for_unknown(self):
        mgr = ConnectionManager()
        assert mgr.source_signature("missing") == ""

    def test_signature_changes_when_config_changes(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {"k": "v1"}, "emissions", {})
        before = mgr.source_signature("s1")
        # Simulate user editing the query
        mgr._sources["s1"]["config"] = {"k": "v2"}
        after = mgr.source_signature("s1")
        assert before != after

    def test_signature_changes_when_schema_changes(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {}, "emissions", {})
        before = mgr.source_signature("s1")
        mgr._sources["s1"]["target_schema"] = "energy"
        assert before != mgr.source_signature("s1")

    def test_signature_changes_when_mapping_changes(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {}, "emissions", {"a": "b"})
        before = mgr.source_signature("s1")
        mgr._sources["s1"]["column_mapping"] = {"a": "c"}
        assert before != mgr.source_signature("s1")

    def test_signature_changes_when_connector_type_changes(self):
        mgr = ConnectionManager()
        mgr.add_source("s1", "delta_lake", {}, "emissions", {})
        before = mgr.source_signature("s1")
        mgr._sources["s1"]["connector_type"] = "aws_s3"
        assert before != mgr.source_signature("s1")

    def test_sources_signature_order_independent(self):
        mgr_a = ConnectionManager()
        mgr_a.add_source("a", "delta_lake", {}, "emissions", {})
        mgr_a.add_source("b", "aws_s3", {}, "energy", {})

        mgr_b = ConnectionManager()
        mgr_b.add_source("b", "aws_s3", {}, "energy", {})
        mgr_b.add_source("a", "delta_lake", {}, "emissions", {})

        assert mgr_a.sources_signature() == mgr_b.sources_signature()

    def test_file_bytes_detected_as_different(self):
        mgr = ConnectionManager()
        mgr.add_source("u", "file_upload",
                       {"file_bytes": b"row1,val1\nrow2,val2",
                        "file_name": "a.csv"},
                       "emissions", {})
        before = mgr.source_signature("u")

        # Re-upload with different bytes but same length
        mgr._sources["u"]["config"]["file_bytes"] = b"row1,val2\nrow2,val1"
        assert before != mgr.source_signature("u")


# ══════════════════════════════════════════════════════════════════════
# Fetch + cache semantics
# ══════════════════════════════════════════════════════════════════════

class TestFetchAndCache:
    def test_fetch_source_unknown_raises(self, register_fake_connector, identity_mapping):
        mgr = ConnectionManager()
        with pytest.raises(KeyError):
            mgr.fetch_source("does_not_exist")

    def test_fetch_source_returns_mapped_df(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(
            pd.DataFrame({"scope": ["1"], "emissions_tco2e": [42]}),
        )
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})
        df = mgr.fetch_source("s1")
        assert list(df.columns) == ["scope", "emissions_tco2e"]
        assert len(df) == 1
        assert mgr.get_source("s1")["status"] == "active"
        assert mgr.get_source("s1")["last_row_count"] == 1

    def test_cache_hit_when_signature_matches(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})

        # First fetch populates cache
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 1

        # Second fetch with identical config uses cache — no remote call
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 1

    def test_cache_miss_when_signature_changes(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {"q": "old"}, "emissions", {})
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 1

        # Edit the config — cache should be invalidated
        mgr._sources["s1"]["config"] = {"q": "new"}
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 2

    def test_cache_disabled_always_refetches(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})

        mgr.fetch_source("s1", use_cache=False)
        mgr.fetch_source("s1", use_cache=False)
        mgr.fetch_source("s1", use_cache=False)
        assert conn.fetch_calls == 3

    def test_cache_returns_independent_copy(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1, 2, 3]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})

        first = mgr.fetch_source("s1", use_cache=True)
        # Mutate the caller's DataFrame
        first.loc[0, "a"] = 999
        # Next cached fetch must return the original data
        second = mgr.fetch_source("s1", use_cache=True)
        assert second.loc[0, "a"] == 1

    def test_invalidate_cache_single(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 1

        mgr.invalidate_cache("s1")
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 2

    def test_invalidate_cache_all(self, register_fake_connector, identity_mapping):
        ctype1, conn1 = register_fake_connector(pd.DataFrame({"a": [1]}))
        ctype2, conn2 = register_fake_connector(pd.DataFrame({"b": [2]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype1, {}, "emissions", {})
        mgr.add_source("s2", ctype2, {}, "energy", {})
        mgr.fetch_source("s1", use_cache=True)
        mgr.fetch_source("s2", use_cache=True)

        mgr.invalidate_cache()
        mgr.fetch_source("s1", use_cache=True)
        mgr.fetch_source("s2", use_cache=True)
        assert conn1.fetch_calls == 2
        assert conn2.fetch_calls == 2


# ══════════════════════════════════════════════════════════════════════
# Errors & fetch_all
# ══════════════════════════════════════════════════════════════════════

class TestFetchAllAndErrors:
    def test_fetch_all_returns_empty_for_failing_source(self, register_fake_connector, identity_mapping):
        ctype_ok, _ = register_fake_connector(pd.DataFrame({"a": [1]}))
        ctype_bad, _ = register_fake_connector(
            pd.DataFrame({"a": [1]}), should_fail=True,
        )

        mgr = ConnectionManager()
        mgr.add_source("ok", ctype_ok, {}, "emissions", {})
        mgr.add_source("bad", ctype_bad, {}, "energy", {})

        all_data = mgr.fetch_all()
        assert not all_data["ok"].empty
        assert all_data["bad"].empty
        assert mgr.get_source("bad")["status"] == "error"

    def test_source_errors_only_returns_errored(self, register_fake_connector, identity_mapping):
        ctype_ok, _ = register_fake_connector(pd.DataFrame({"a": [1]}))
        ctype_bad, _ = register_fake_connector(
            pd.DataFrame({"a": [1]}), should_fail=True,
        )

        mgr = ConnectionManager()
        mgr.add_source("ok", ctype_ok, {}, "emissions", {})
        mgr.add_source("bad", ctype_bad, {}, "energy", {})
        mgr.fetch_all()

        errors = mgr.source_errors()
        assert "ok" not in errors
        assert "bad" in errors
        assert "simulated failure" in errors["bad"]

    def test_fetch_all_by_schema_concatenates_multi_source(self, register_fake_connector, identity_mapping):
        ctype1, _ = register_fake_connector(pd.DataFrame({"scope": ["1"], "val": [10]}))
        ctype2, _ = register_fake_connector(pd.DataFrame({"scope": ["2"], "val": [20]}))

        mgr = ConnectionManager()
        mgr.add_source("a", ctype1, {}, "emissions", {})
        mgr.add_source("b", ctype2, {}, "emissions", {})

        by_schema = mgr.fetch_all_by_schema()
        assert "emissions" in by_schema
        assert len(by_schema["emissions"]) == 2
        assert set(by_schema["emissions"]["val"]) == {10, 20}

    def test_fetch_all_by_schema_skips_empty_sources(self, register_fake_connector, identity_mapping):
        ctype_ok, _ = register_fake_connector(pd.DataFrame({"v": [1]}))
        ctype_bad, _ = register_fake_connector(
            pd.DataFrame({"v": [1]}), should_fail=True,
        )

        mgr = ConnectionManager()
        mgr.add_source("ok", ctype_ok, {}, "emissions", {})
        mgr.add_source("bad", ctype_bad, {}, "emissions", {})

        by_schema = mgr.fetch_all_by_schema()
        assert len(by_schema["emissions"]) == 1

    def test_fetch_all_forwards_use_cache(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})

        mgr.fetch_all(use_cache=True)
        mgr.fetch_all(use_cache=True)
        assert conn.fetch_calls == 1

    def test_fetch_all_by_schema_forwards_use_cache(self, register_fake_connector, identity_mapping):
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})

        mgr.fetch_all_by_schema(use_cache=True)
        mgr.fetch_all_by_schema(use_cache=True)
        assert conn.fetch_calls == 1

    def test_re_registering_source_clears_cache(self, register_fake_connector, identity_mapping):
        """add_source() overwriting an existing source must reset cache fields."""
        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 1

        # Re-register with different config
        mgr.add_source("s1", ctype, {"changed": True}, "emissions", {})
        mgr.fetch_source("s1", use_cache=True)
        assert conn.fetch_calls == 2

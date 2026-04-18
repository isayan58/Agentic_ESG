"""Tests for the ``refresh_real_data`` pipeline-refresh helper.

The helper touches three collaborators: the Streamlit session state,
the ``state_manager`` singleton, and the Data Collector agent. We
install a FakeStreamlit via the ``fake_st`` fixture (see conftest),
install a stub DataCollector into ``st.session_state["data_collector"]``
to avoid importing the real agent, and assert on the recorded calls
and state mutations.
"""
from __future__ import annotations

import pandas as pd
import pytest


class StubDataCollector:
    """Minimal stand-in for DataCollectorAgent used by the refresh helper."""

    def __init__(self, records: int = 42,
                 accepts_use_cache: bool = True,
                 raise_type_error_without_kw: bool = False):
        self.records = records
        self.accepts_use_cache = accepts_use_cache
        self.raise_type_error_without_kw = raise_type_error_without_kw
        self.calls: list[dict] = []

    def run(self, **kwargs):
        # Simulate an older agent that doesn't accept use_cache — raise
        # TypeError the way Python would if the kwarg isn't accepted.
        if self.raise_type_error_without_kw and "use_cache" in kwargs:
            raise TypeError("run() got an unexpected keyword argument 'use_cache'")
        self.calls.append(kwargs)
        return {"total_records": self.records, "datasets": {}, "quality_scores": {}}


class StubConnectionManager:
    """Just enough surface for the refresh helper to introspect."""

    def __init__(self, sources=None, errors=None):
        self._sources = sources or []
        self._errors = errors or {}

    def has_sources(self):
        return bool(self._sources)

    def list_sources(self):
        return list(self._sources)

    def sources_signature(self):
        # Deterministic across calls — the helper only compares to itself
        return "sig:" + ",".join(sorted(s["id"] for s in self._sources))

    def source_errors(self):
        return dict(self._errors)


# ══════════════════════════════════════════════════════════════════════
# refresh_real_data
# ══════════════════════════════════════════════════════════════════════

class TestRefreshRealData:
    def test_no_sources_returns_reason_no_sources(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        result = refresh_real_data()
        assert result["refreshed"] is False
        assert result["reason"] == "no_sources"
        assert result["sources"] == 0

    def test_no_conn_mgr_at_all(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        # conn_manager key absent entirely
        result = refresh_real_data()
        assert result["refreshed"] is False
        assert result["reason"] == "no_sources"

    def test_with_sources_re_runs_data_collector(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(sources=[{"id": "s1", "target_schema": "emissions"}])
        dc = StubDataCollector(records=1234)
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        result = refresh_real_data()
        assert result["refreshed"] is True
        assert result["reason"] == "full"
        assert result["sources"] == 1
        assert result["records"] == 1234
        assert result["signature"]  # non-empty
        assert dc.calls and dc.calls[0]["connection_manager"] is cm

    def test_only_changed_propagates_use_cache_true(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(sources=[{"id": "s1"}])
        dc = StubDataCollector()
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        refresh_real_data(only_changed=True)
        assert dc.calls[-1].get("use_cache") is True

    def test_default_is_full_refresh(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(sources=[{"id": "s1"}])
        dc = StubDataCollector()
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        refresh_real_data()
        # Default `only_changed=False` → use_cache forwarded as False
        assert dc.calls[-1].get("use_cache") is False

    def test_older_data_collector_without_use_cache(self, fake_st):
        """If DataCollector.run() doesn't accept use_cache, the helper
        must catch the TypeError and retry without it."""
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(sources=[{"id": "s1"}])
        dc = StubDataCollector(raise_type_error_without_kw=True)
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        result = refresh_real_data(only_changed=True)
        assert result["refreshed"] is True
        # Fallback call must not include use_cache
        fallback = dc.calls[-1]
        assert "use_cache" not in fallback
        assert fallback["connection_manager"] is cm

    def test_writes_session_state_keys(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(sources=[{"id": "s1"}])
        dc = StubDataCollector(records=99)
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        refresh_real_data()
        assert "_last_data_refresh" in fake_st.session_state
        assert fake_st.session_state["_last_data_refresh_records"] == 99
        assert fake_st.session_state["_last_data_refresh_signature"]
        assert fake_st.session_state["_last_data_refresh_errors"] == {}

    def test_surfaces_source_errors_as_warnings(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(
            sources=[{"id": "s1"}, {"id": "s2"}],
            errors={"s2": "Authentication failed"},
        )
        dc = StubDataCollector()
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        result = refresh_real_data()
        assert "s2" in result["errors"]
        assert any("s2" in w["body"] for w in fake_st.warnings)
        assert any("Authentication failed" in w["body"] for w in fake_st.warnings)

    def test_show_errors_false_suppresses_warnings(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(
            sources=[{"id": "s1"}],
            errors={"s1": "boom"},
        )
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = StubDataCollector()

        refresh_real_data(show_errors=False)
        assert fake_st.warnings == []

    def test_show_toast_renders_toast_on_success(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(sources=[{"id": "s1"}])
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = StubDataCollector(records=10)

        refresh_real_data(show_toast=True)
        assert fake_st.toasts and "1 source" in fake_st.toasts[0]["body"]

    def test_clears_stale_state_manager_channels(self, fake_st):
        from utils.pipeline_refresh import refresh_real_data
        from core.state_manager import state_manager

        # Seed stale data the refresh must clear
        state_manager.publish("dataset_emissions", pd.DataFrame({"a": [1]}))
        state_manager.publish("validated_supply_chain", pd.DataFrame({"b": [2]}))
        state_manager.publish("other_channel", {"keep": True})

        cm = StubConnectionManager(sources=[{"id": "s1"}])
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = StubDataCollector()

        refresh_real_data()

        channels = state_manager.get_all_channels()
        assert "dataset_emissions" not in channels
        assert "validated_supply_chain" not in channels
        # Non-dataset channels preserved
        assert "other_channel" in channels

    def test_empty_manager_still_clears_stale_channels(self, fake_st):
        """Regression: if the user removes their last real source, the
        helper must still clear stale ``dataset_*`` channels and re-run
        the Data Collector so sample data repopulates the schema."""
        from utils.pipeline_refresh import refresh_real_data
        from core.state_manager import state_manager

        state_manager.publish("dataset_peer_metrics", pd.DataFrame({"a": [1]}))

        cm = StubConnectionManager(sources=[])  # zero sources, but manager exists
        dc = StubDataCollector()
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        result = refresh_real_data()
        assert result["refreshed"] is True
        assert "dataset_peer_metrics" not in state_manager.get_all_channels()
        # Data Collector was still invoked (so sample data can repopulate)
        assert dc.calls and dc.calls[0]["connection_manager"] is cm

    def test_reuses_existing_data_collector(self, fake_st):
        """Helper must not re-instantiate the DataCollector when one is
        already in session_state — that would lose the audit trail."""
        from utils.pipeline_refresh import refresh_real_data
        cm = StubConnectionManager(sources=[{"id": "s1"}])
        dc = StubDataCollector()
        fake_st.session_state["conn_manager"] = cm
        fake_st.session_state["data_collector"] = dc

        refresh_real_data()
        refresh_real_data()

        # Same instance used twice
        assert fake_st.session_state["data_collector"] is dc
        assert len(dc.calls) == 2


# ══════════════════════════════════════════════════════════════════════
# stamp_refresh_from_pipeline
# ══════════════════════════════════════════════════════════════════════

class TestStampRefreshFromPipeline:
    def test_writes_session_state_keys(self, fake_st):
        from utils.pipeline_refresh import stamp_refresh_from_pipeline
        cm = StubConnectionManager(sources=[{"id": "a"}, {"id": "b"}])
        fake_st.session_state["conn_manager"] = cm

        stamp_refresh_from_pipeline(sources=2, records=77, errors={"a": "x"})

        ss = fake_st.session_state
        assert ss["_last_data_refresh"]
        assert ss["_last_data_refresh_records"] == 77
        assert ss["_last_data_refresh_errors"] == {"a": "x"}
        assert ss["_last_data_refresh_signature"]  # not None when cm has sources

    def test_works_without_conn_manager(self, fake_st):
        from utils.pipeline_refresh import stamp_refresh_from_pipeline
        # Should not raise even when no conn_manager is in session
        stamp_refresh_from_pipeline(sources=0, records=0)
        assert fake_st.session_state["_last_data_refresh_records"] == 0
        assert fake_st.session_state["_last_data_refresh_signature"] is None


# ══════════════════════════════════════════════════════════════════════
# data_freshness_caption
# ══════════════════════════════════════════════════════════════════════

class TestDataFreshnessCaption:
    def test_renders_nothing_when_no_conn_manager(self, fake_st):
        from utils.pipeline_refresh import data_freshness_caption
        data_freshness_caption()
        assert fake_st.captions == []

    def test_renders_nothing_when_no_sources(self, fake_st):
        from utils.pipeline_refresh import data_freshness_caption
        fake_st.session_state["conn_manager"] = StubConnectionManager(sources=[])
        data_freshness_caption()
        assert fake_st.captions == []

    def test_renders_prompt_when_sources_but_never_refreshed(self, fake_st):
        from utils.pipeline_refresh import data_freshness_caption
        fake_st.session_state["conn_manager"] = StubConnectionManager(
            sources=[{"id": "s1"}]
        )
        data_freshness_caption()
        assert fake_st.captions
        assert "will be re-fetched" in fake_st.captions[0]

    def test_renders_ago_when_refreshed(self, fake_st):
        from datetime import datetime
        from utils.pipeline_refresh import data_freshness_caption

        fake_st.session_state["conn_manager"] = StubConnectionManager(
            sources=[{"id": "s1"}]
        )
        fake_st.session_state["_last_data_refresh"] = datetime.now().isoformat()

        data_freshness_caption()
        joined = " ".join(fake_st.captions)
        assert "refreshed" in joined
        assert "sec ago" in joined or "min ago" in joined

    def test_renders_error_line_when_last_refresh_had_errors(self, fake_st):
        from datetime import datetime
        from utils.pipeline_refresh import data_freshness_caption

        fake_st.session_state["conn_manager"] = StubConnectionManager(
            sources=[{"id": "s1"}]
        )
        fake_st.session_state["_last_data_refresh"] = datetime.now().isoformat()
        fake_st.session_state["_last_data_refresh_errors"] = {"s1": "boom"}

        data_freshness_caption()
        # One caption for the "refreshed X ago" line, one for the error line
        assert len(fake_st.captions) == 2
        assert "s1" in fake_st.captions[1]
        assert "sample data" in fake_st.captions[1]

    def test_handles_bad_timestamp_gracefully(self, fake_st):
        from utils.pipeline_refresh import data_freshness_caption
        fake_st.session_state["conn_manager"] = StubConnectionManager(
            sources=[{"id": "s1"}]
        )
        fake_st.session_state["_last_data_refresh"] = "not-an-iso-date"
        data_freshness_caption()
        # Should fall back to "recently" rather than crashing
        assert fake_st.captions
        assert "recently" in fake_st.captions[0]


# ══════════════════════════════════════════════════════════════════════
# _compute_sources_signature fallback
# ══════════════════════════════════════════════════════════════════════

class TestSignatureFallback:
    def test_uses_manager_native_signature_when_available(self, fake_st):
        from utils.pipeline_refresh import _compute_sources_signature
        cm = StubConnectionManager(sources=[{"id": "s1"}])
        assert _compute_sources_signature(cm) == cm.sources_signature()

    def test_falls_back_when_manager_lacks_method(self, fake_st):
        from utils.pipeline_refresh import _compute_sources_signature

        class LegacyManager:
            def list_sources(self):
                return [{
                    "id": "s1",
                    "connector_type": "delta_lake",
                    "target_schema": "emissions",
                    "column_mapping": {},
                    "config": {"k": "v"},
                }]

        sig = _compute_sources_signature(LegacyManager())
        # Full SHA-256 hex digest
        assert len(sig) == 64
        assert all(c in "0123456789abcdef" for c in sig)

    def test_empty_string_when_list_sources_raises(self, fake_st):
        from utils.pipeline_refresh import _compute_sources_signature

        class BrokenManager:
            def list_sources(self):
                raise RuntimeError("boom")

        assert _compute_sources_signature(BrokenManager()) == ""

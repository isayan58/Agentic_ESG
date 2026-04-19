"""Integration tests: refresh helper ↔ ConnectionManager ↔ DataCollector.

These exercise the real ``DataCollectorAgent`` against a real
``ConnectionManager`` (backed by the in-memory fake connector) and
verify that:

1. ``use_cache`` flows all the way through from ``refresh_real_data``
   to the connector so unchanged sources don't re-execute remotely.
2. Real-source data is published to ``state_manager`` under the
   expected ``dataset_{schema}`` channel.
3. Removing a source and re-running drops its published dataset.
4. A failing source is recorded in ``source_errors()`` and surfaced by
   the refresh helper.
"""
from __future__ import annotations

import pandas as pd
import pytest

from utils.connection_manager import ConnectionManager


# ══════════════════════════════════════════════════════════════════════
# End-to-end: refresh_real_data → DataCollector → ConnectionManager
# ══════════════════════════════════════════════════════════════════════

class TestEndToEnd:
    def test_use_cache_prevents_remote_refetch(
        self, fake_st, register_fake_connector, identity_mapping
    ):
        from agents.data_collector import DataCollectorAgent
        from utils.pipeline_refresh import refresh_real_data

        ctype, conn = register_fake_connector(
            pd.DataFrame({"scope": ["1"], "emissions_tco2e": [10]})
        )

        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})

        fake_st.session_state["conn_manager"] = mgr
        fake_st.session_state["data_collector"] = DataCollectorAgent()

        # First refresh — populates cache
        refresh_real_data(only_changed=True)
        assert conn.fetch_calls == 1

        # Second refresh with identical config — cache hit, no remote call
        refresh_real_data(only_changed=True)
        assert conn.fetch_calls == 1

        # Third refresh with `only_changed=False` (default) — must re-fetch
        refresh_real_data()
        assert conn.fetch_calls == 2

    def test_config_edit_invalidates_cache(
        self, fake_st, register_fake_connector, identity_mapping
    ):
        from agents.data_collector import DataCollectorAgent
        from utils.pipeline_refresh import refresh_real_data

        ctype, conn = register_fake_connector(pd.DataFrame({"a": [1]}))
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {"query": "SELECT 1"}, "emissions", {})

        fake_st.session_state["conn_manager"] = mgr
        fake_st.session_state["data_collector"] = DataCollectorAgent()

        refresh_real_data(only_changed=True)
        assert conn.fetch_calls == 1

        # User "edits" the query
        mgr._sources["s1"]["config"] = {"query": "SELECT 2"}
        refresh_real_data(only_changed=True)
        assert conn.fetch_calls == 2

    def test_real_data_published_to_state_manager(
        self, fake_st, register_fake_connector, identity_mapping
    ):
        from agents.data_collector import DataCollectorAgent
        from core.state_manager import state_manager
        from utils.pipeline_refresh import refresh_real_data

        ctype, _ = register_fake_connector(
            pd.DataFrame({"scope": ["1", "2"], "emissions_tco2e": [100, 200]})
        )
        mgr = ConnectionManager()
        mgr.add_source("s1", ctype, {}, "emissions", {})

        fake_st.session_state["conn_manager"] = mgr
        fake_st.session_state["data_collector"] = DataCollectorAgent()

        refresh_real_data()

        # The DataCollector publishes dataset_<schema> channels
        channels = state_manager.get_all_channels()
        dataset_channels = [c for c in channels if c.startswith("dataset_")]
        assert "dataset_emissions" in dataset_channels
        published = state_manager.subscribe("dataset_emissions")
        assert published is not None
        assert len(published) == 2

    def test_removing_real_only_source_drops_its_dataset(
        self, fake_st, register_fake_connector, identity_mapping
    ):
        """``peer_metrics`` has no sample loader, so a real source is the
        only thing that can produce its ``dataset_*`` channel. Removing
        that source must drop the channel entirely — no stale data."""
        from agents.data_collector import DataCollectorAgent
        from core.state_manager import state_manager
        from utils.pipeline_refresh import refresh_real_data

        ctype_peer, _ = register_fake_connector(
            pd.DataFrame({"company": ["ACME"], "esg_score": [72]})
        )
        ctype_energy, _ = register_fake_connector(pd.DataFrame({"v": [2]}))

        mgr = ConnectionManager()
        mgr.add_source("peers", ctype_peer, {}, "peer_metrics", {})
        mgr.add_source("nrg", ctype_energy, {}, "energy", {})

        fake_st.session_state["conn_manager"] = mgr
        fake_st.session_state["data_collector"] = DataCollectorAgent()

        refresh_real_data()
        channels = state_manager.get_all_channels()
        assert "dataset_peer_metrics" in channels
        assert "dataset_energy" in channels

        # Remove the peer_metrics source — it has no sample fallback
        mgr.remove_source("peers")
        refresh_real_data()

        channels = state_manager.get_all_channels()
        assert "dataset_peer_metrics" not in channels, \
            "Real-only schema's channel should have been cleared"
        assert "dataset_energy" in channels, \
            "Still-registered source's dataset should survive"

    def test_removing_source_clears_stale_real_data(
        self, fake_st, register_fake_connector, identity_mapping
    ):
        """After removing the last real source on a schema, the published
        channel must no longer contain that source's sentinel values.

        Historical note: when the app shipped bundled sample CSVs this
        test verified that sample data back-filled the channel after
        removal. Samples have been retired in favour of per-user sources
        (each user configures their own data inputs), so the guarantee
        is narrower now: *stale* real data must not leak. An empty
        channel for an unconfigured schema is the correct steady state.
        """
        from agents.data_collector import DataCollectorAgent
        from core.state_manager import state_manager
        from utils.pipeline_refresh import refresh_real_data

        distinctive = pd.DataFrame({
            "supplier_id": ["__REAL_SENTINEL__"],
            "emissions_tco2e": [999999],
        })
        ctype_sc, _ = register_fake_connector(distinctive)

        mgr = ConnectionManager()
        mgr.add_source("sc", ctype_sc, {}, "supply_chain", {})

        fake_st.session_state["conn_manager"] = mgr
        fake_st.session_state["data_collector"] = DataCollectorAgent()

        refresh_real_data()
        published_before = state_manager.subscribe("dataset_supply_chain")
        flat_before = str(published_before)
        assert "__REAL_SENTINEL__" in flat_before

        # Remove the real source — stale sentinel must be purged.
        mgr.remove_source("sc")
        refresh_real_data()

        published_after = state_manager.subscribe("dataset_supply_chain")
        flat_after = str(published_after)
        assert "__REAL_SENTINEL__" not in flat_after, \
            "Stale real-source data must not leak after removal"

    def test_failed_source_reported_and_warned(
        self, fake_st, register_fake_connector, identity_mapping
    ):
        from agents.data_collector import DataCollectorAgent
        from utils.pipeline_refresh import refresh_real_data

        ctype_ok, _ = register_fake_connector(pd.DataFrame({"a": [1]}))
        ctype_bad, _ = register_fake_connector(
            pd.DataFrame({"a": [1]}), should_fail=True,
        )

        mgr = ConnectionManager()
        mgr.add_source("good", ctype_ok, {}, "emissions", {})
        mgr.add_source("bad", ctype_bad, {}, "energy", {})

        fake_st.session_state["conn_manager"] = mgr
        fake_st.session_state["data_collector"] = DataCollectorAgent()

        result = refresh_real_data()

        # Error recorded on the manager
        assert "bad" in mgr.source_errors()
        # And surfaced on the result
        assert "bad" in result["errors"]
        # And rendered as a warning banner
        assert any("bad" in w["body"] for w in fake_st.warnings)
        # The good source still produced a dataset
        from core.state_manager import state_manager
        assert "dataset_emissions" in state_manager.get_all_channels()

    def test_empty_conn_manager_does_not_publish_real_channels(
        self, fake_st
    ):
        """A refresh with no real sources must not write any ``dataset_*``
        channels (the DataCollector still loads sample data but that
        uses different keys like ``emissions``, not ``dataset_emissions``)."""
        from utils.pipeline_refresh import refresh_real_data
        # No conn_manager at all
        result = refresh_real_data()
        assert result["refreshed"] is False

"""Pipeline refresh helper — re-ingests every registered real data source.

Downstream agents read canonical datasets from ``core.state_manager``,
which is a module-level singleton that keeps whatever the Data Collector
last published.  When a user changes their Snowflake query, edits an S3
object, swaps a Google Sheet, or updates any other configured source
and then clicks "Run" on a single-agent page (Carbon, Regulatory,
Risk, Audit, Report, Action, Stakeholder, ROI), the agent would
otherwise see stale data.

This module provides a single helper — :func:`refresh_real_data` — that
every page's Run button calls before the agent fires.  It transparently
re-fetches every source on :class:`ConnectionManager`, re-publishes
fresh datasets to ``state_manager``, and returns a small status dict
the page can surface as a "data refreshed Xs ago" badge.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st


def refresh_real_data(force: bool = True,
                      show_toast: bool = False) -> dict[str, Any]:
    """Re-run the Data Collector against every registered real source.

    The helper always uses the current ``st.session_state.conn_manager``
    so changes the user made since the last run are picked up.

    Parameters
    ----------
    force : bool
        When ``True`` (default), re-fetch on every call.  When ``False``,
        skip the refresh if the source configuration hasn't changed
        since the previous successful run (tracked via a signature on
        the connection manager).
    show_toast : bool
        When ``True``, surface a small toast/info banner noting how many
        sources were refreshed.  Pages that already render their own
        "Running…" spinner usually leave this off.

    Returns
    -------
    dict
        ``{"refreshed": bool, "reason": str, "sources": int,
           "records": int, "timestamp": str, "signature": str}``
    """
    conn_mgr = st.session_state.get("conn_manager")
    if conn_mgr is None or not conn_mgr.has_sources():
        return {
            "refreshed": False,
            "reason": "no_sources",
            "sources": 0,
            "records": 0,
            "timestamp": st.session_state.get("_last_data_refresh"),
            "signature": None,
        }

    # Change-detection: compute a lightweight signature over the
    # registered source configs.  If it matches the last successful
    # refresh, skip the re-fetch unless the caller forces it.
    signature = _compute_sources_signature(conn_mgr)
    last_sig = st.session_state.get("_last_data_refresh_signature")
    if not force and signature and signature == last_sig:
        return {
            "refreshed": False,
            "reason": "unchanged",
            "sources": len(conn_mgr.list_sources()),
            "records": st.session_state.get("_last_data_refresh_records", 0),
            "timestamp": st.session_state.get("_last_data_refresh"),
            "signature": signature,
        }

    # Reuse the page-scoped DataCollector if it exists (preserves the
    # audit trail across runs), otherwise construct a fresh one.
    agent = st.session_state.get("data_collector")
    if agent is None:
        from agents.data_collector import DataCollectorAgent
        agent = DataCollectorAgent()
        st.session_state["data_collector"] = agent

    result = agent.run(connection_manager=conn_mgr)

    now = datetime.now()
    st.session_state["_last_data_refresh"] = now.isoformat()
    st.session_state["_last_data_refresh_signature"] = signature
    st.session_state["_last_data_refresh_records"] = int(
        result.get("total_records", 0) if isinstance(result, dict) else 0
    )

    status = {
        "refreshed": True,
        "reason": "forced" if force else "changed",
        "sources": len(conn_mgr.list_sources()),
        "records": st.session_state["_last_data_refresh_records"],
        "timestamp": st.session_state["_last_data_refresh"],
        "signature": signature,
    }
    if show_toast:
        try:
            st.toast(
                f"🔄 Refreshed {status['sources']} source(s) "
                f"· {status['records']:,} records",
                icon="✅",
            )
        except Exception:
            pass
    return status


def data_freshness_caption() -> None:
    """Render a subtle "Data refreshed … ago" caption for an agent page.

    Safe to call even when no real sources are configured — in that
    case it renders nothing, so it doesn't clutter the sample-data
    experience.
    """
    conn_mgr = st.session_state.get("conn_manager")
    if conn_mgr is None or not conn_mgr.has_sources():
        return

    last = st.session_state.get("_last_data_refresh")
    sources = len(conn_mgr.list_sources())
    if not last:
        st.caption(
            f"📡 {sources} real source(s) registered — data will be re-fetched "
            "from every source the next time you click **Run**."
        )
        return

    try:
        ts = datetime.fromisoformat(last)
        delta = datetime.now() - ts
        secs = int(delta.total_seconds())
        if secs < 60:
            ago = f"{secs} sec ago"
        elif secs < 3600:
            ago = f"{secs // 60} min ago"
        else:
            ago = f"{secs // 3600} hr ago"
    except Exception:
        ago = "recently"

    st.caption(
        f"📡 Real data refreshed **{ago}** from {sources} registered source(s). "
        "Click **Run** to pull the latest."
    )


def _compute_sources_signature(conn_mgr) -> str:
    """Return a stable hash of the configured sources.

    Captures connector type, target schema, column mapping, and config
    dict for every source.  Binary payloads (file bytes) are reduced
    to their length + a crc-style digest so uploading the same file
    twice doesn't trigger an unnecessary refresh, but uploading a new
    revision does.
    """
    import hashlib
    import json

    def _coerce(value):
        if isinstance(value, (bytes, bytearray)):
            h = hashlib.sha1(bytes(value)).hexdigest()[:16]
            return f"bytes:{len(value)}:{h}"
        if isinstance(value, dict):
            return {k: _coerce(v) for k, v in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [_coerce(v) for v in value]
        try:
            json.dumps(value)
            return value
        except TypeError:
            return repr(value)

    try:
        sources = conn_mgr.list_sources()
    except Exception:
        return ""

    payload = [
        {
            "id": s.get("id"),
            "type": s.get("connector_type"),
            "schema": s.get("target_schema"),
            "mapping": _coerce(s.get("column_mapping", {})),
            "config": _coerce(s.get("config", {})),
        }
        for s in sources
    ]
    try:
        serialised = json.dumps(payload, sort_keys=True, default=str)
    except Exception:
        serialised = repr(payload)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]

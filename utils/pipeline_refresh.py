"""Pipeline refresh helper — re-ingests registered real data sources.

Downstream agents read canonical datasets from ``core.state_manager``,
which is a module-level singleton that keeps whatever the Data Collector
last published. When a user changes their Snowflake query, edits an S3
object, swaps a Google Sheet, re-uploads a file, or updates any other
configured source and then clicks "Run" on a single-agent page (Carbon,
Regulatory, Risk, Audit, Report, Action, Stakeholder, ROI), the agent
would otherwise see stale data.

This module provides a single helper — :func:`refresh_real_data` — that
every page's Run button calls before the agent fires. It:

* re-fetches every registered source via ``ConnectionManager``,
* reuses a per-source cached DataFrame when the source config is
  unchanged (opt-in via ``only_changed=True``) so unchanged Snowflake
  queries don't re-execute on every click,
* clears stale ``dataset_*`` / ``validated_*`` entries from
  ``state_manager`` before the Data Collector republishes, so a
  removed source's old data can't leak into the next run,
* surfaces fetch errors in the Streamlit UI instead of silently
  falling back to sample data,
* returns a small status dict the page can turn into a "refreshed N sec
  ago" badge via :func:`data_freshness_caption`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st


# Channel-name prefixes the Data Collector publishes to state_manager.
# Cleared before every refresh so stale datasets from previously-registered
# sources can't leak into the next pipeline run.
_STATE_DATASET_PREFIXES = ("dataset_", "validated_")


def refresh_real_data(only_changed: bool = False,
                      show_toast: bool = False,
                      show_errors: bool = True) -> dict[str, Any]:
    """Re-run the Data Collector against every registered real source.

    The helper always uses the current ``st.session_state.conn_manager``
    so changes the user made since the last run are picked up.

    Parameters
    ----------
    only_changed : bool
        When ``False`` (default), every registered source is re-fetched
        from its remote system. When ``True``, sources whose config
        signature matches the last successful fetch reuse their cached
        DataFrame — unchanged Snowflake queries don't re-execute.
    show_toast : bool
        When ``True``, surface a small toast noting how many sources
        were refreshed.
    show_errors : bool
        When ``True`` (default), render an ``st.warning()`` for any
        source that failed to fetch so a bad credential doesn't silently
        fall back to sample data.

    Returns
    -------
    dict
        ``{"refreshed": bool, "reason": str, "sources": int,
           "records": int, "timestamp": str, "signature": str,
           "errors": {source_id: message}}``
    """
    conn_mgr = st.session_state.get("conn_manager")
    bootstrapped = False
    if conn_mgr is None:
        # Lazy bootstrap: if a user is signed in and has saved sources
        # in the HF Dataset, hydrate them now so the first page they
        # land on (which might not be Data Collector) still sees them.
        # If hydration fails, fall through to the original contract so
        # guest / offline flows keep behaving identically.
        try:
            from utils.session import get_session_connection_manager
            conn_mgr = get_session_connection_manager()
            bootstrapped = True
        except Exception:
            conn_mgr = None

    # If we had to lazy-bootstrap and the resulting manager has no
    # sources, preserve the original "nothing to refresh" contract so
    # guest flows (and the pipeline_refresh test suite) keep seeing
    # ``refreshed=False``. The non-bootstrap branch below still
    # falls through to the Data Collector when the *user's* manager
    # exists with zero sources (to clear stale channels).
    if conn_mgr is None or (bootstrapped and not conn_mgr.has_sources()):
        return {
            "refreshed": False,
            "reason": "no_sources",
            "sources": 0,
            "records": 0,
            "timestamp": st.session_state.get("_last_data_refresh"),
            "signature": None,
            "errors": {},
        }

    # When the manager exists but has zero sources (e.g. the user just
    # removed their last registered source), we still need to:
    #   (a) clear any stale ``dataset_*`` channels published by a prior
    #       run so removed-source data can't leak, and
    #   (b) re-run the Data Collector so sample data repopulates the
    #       canonical channels for downstream agents.
    # Falling through the normal path accomplishes both — only the
    # "truly nothing to do" case (no manager at all) short-circuits.
    signature = _compute_sources_signature(conn_mgr)

    # Reuse the page-scoped DataCollector if it exists (preserves the
    # audit trail across runs), otherwise construct a fresh one.
    agent = st.session_state.get("data_collector")
    if agent is None:
        from agents.data_collector import DataCollectorAgent
        agent = DataCollectorAgent()
        st.session_state["data_collector"] = agent

    # Clear stale canonical datasets so a removed source's data can't
    # leak through. The Data Collector will republish whatever the
    # current registered sources produce.
    _clear_stale_state_datasets()

    try:
        result = agent.run(
            connection_manager=conn_mgr,
            use_cache=only_changed,
        )
    except TypeError:
        # Older DataCollector signature (no use_cache kwarg) — fall back
        # to the original contract.
        result = agent.run(connection_manager=conn_mgr)

    errors = {}
    try:
        errors = conn_mgr.source_errors()
    except Exception:
        pass

    if show_errors and errors:
        for sid, msg in errors.items():
            st.warning(
                f"⚠️ Source **{sid}** failed to fetch: {msg}. "
                "The pipeline will fall back to sample data for the affected schema.",
                icon="⚠️",
            )

    now = datetime.now()
    st.session_state["_last_data_refresh"] = now.isoformat()
    st.session_state["_last_data_refresh_signature"] = signature
    st.session_state["_last_data_refresh_records"] = int(
        result.get("total_records", 0) if isinstance(result, dict) else 0
    )
    st.session_state["_last_data_refresh_errors"] = errors

    status = {
        "refreshed": True,
        "reason": "only_changed" if only_changed else "full",
        "sources": len(conn_mgr.list_sources()),
        "records": st.session_state["_last_data_refresh_records"],
        "timestamp": st.session_state["_last_data_refresh"],
        "signature": signature,
        "errors": errors,
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


def stamp_refresh_from_pipeline(sources: int, records: int,
                                errors: dict | None = None) -> None:
    """Record that a refresh happened via a non-helper path (e.g. Mission
    Control's full-pipeline run).

    Used to keep the ``data_freshness_caption()`` on every page honest
    when the Data Collector was invoked outside this helper.
    """
    conn_mgr = st.session_state.get("conn_manager")
    sig = _compute_sources_signature(conn_mgr) if conn_mgr else None
    st.session_state["_last_data_refresh"] = datetime.now().isoformat()
    st.session_state["_last_data_refresh_signature"] = sig
    st.session_state["_last_data_refresh_records"] = int(records)
    st.session_state["_last_data_refresh_errors"] = errors or {}


def data_freshness_caption() -> None:
    """Render a subtle "Data refreshed … ago" caption for an agent page.

    Safe to call even when no real sources are configured — in that
    case it renders nothing, so it doesn't clutter the sample-data
    experience. Surfaces a warning line when the last refresh recorded
    any source errors so users aren't silently running on sample data.
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
    errors = st.session_state.get("_last_data_refresh_errors") or {}
    if errors:
        failed = ", ".join(f"`{sid}`" for sid in errors)
        st.caption(f"⚠️ Last refresh had errors on {failed} — sample data used for affected schemas.")


def _clear_stale_state_datasets() -> None:
    """Drop stale ``dataset_*`` / ``validated_*`` entries from state_manager.

    Downstream agents read canonical data from ``state_manager``; if a
    source is later removed, its last-published dataset would otherwise
    hang around forever. Clearing here guarantees the next Data Collector
    run is the sole source of truth.
    """
    try:
        from core.state_manager import state_manager
    except Exception:
        return

    try:
        channels = state_manager.get_all_channels()
    except Exception:
        return

    for ch in list(channels.keys()):
        if ch.startswith(_STATE_DATASET_PREFIXES):
            # StateManager has no public "delete", so we reach into the
            # internal dict. Tolerate absence to stay future-proof.
            try:
                state_manager._channels.pop(ch, None)
            except Exception:
                pass


def _compute_sources_signature(conn_mgr) -> str:
    """Return the connection manager's full-session signature.

    Delegates to :meth:`ConnectionManager.sources_signature` when
    available, with a defensive local fallback for older managers.
    """
    try:
        return conn_mgr.sources_signature()
    except AttributeError:
        pass

    import hashlib
    import json

    def _coerce(value):
        if isinstance(value, (bytes, bytearray)):
            return f"bytes:{len(value)}:{hashlib.sha256(bytes(value)).hexdigest()}"
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
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()

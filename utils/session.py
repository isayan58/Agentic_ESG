"""Session-scoped bootstrap helpers.

The core idea: every Streamlit page that needs ``st.session_state.conn_manager``
should call :func:`get_session_connection_manager()` *once* at the top of
the page. That helper:

* reads the currently signed-in user,
* hydrates a fresh ``ConnectionManager`` from the user's saved sources
  (via :mod:`utils.source_store`) if the manager isn't already in
  session state,
* installs a persistence callback so every subsequent ``add_source`` /
  ``remove_source`` is synced to the store without the page having to
  think about it,
* caches the resulting manager under ``st.session_state.conn_manager``
  (keyed on the signed-in username so switching accounts in the same
  tab rebuilds cleanly).

Guests (no signed-in user) still get a working in-memory manager so the
demo flow keeps working; their sources simply aren't persisted.
"""
from __future__ import annotations

import streamlit as st

from utils.connection_manager import ConnectionManager
from utils.source_store import (
    get_source_store,
    record_to_source,
    source_to_record,
)


_SESSION_KEY = "conn_manager"
_OWNER_KEY = "_conn_manager_owner"


def _current_username() -> str | None:
    """Return the signed-in username, or ``None`` for guests."""
    try:
        user = st.session_state.get("user")
    except Exception:
        user = None
    if not user:
        return None
    return (user.get("username") or "").strip() or None


def _build_on_change(username: str):
    """Return a callback that snapshots a ConnectionManager to the store."""
    store = get_source_store()

    def _callback(mgr: ConnectionManager) -> None:
        records = [
            source_to_record(sid, meta)
            for sid, meta in mgr._sources.items()  # noqa: SLF001
        ]
        store.save(username, records)

    return _callback


def get_session_connection_manager() -> ConnectionManager:
    """Return the per-user ``ConnectionManager`` for the current session.

    Idempotent: calling this N times in one browser session is cheap after
    the first call. Rebuilds when the signed-in user changes so two users
    sharing a browser tab can't cross-contaminate each other's sources.
    """
    username = _current_username()
    existing = st.session_state.get(_SESSION_KEY)
    existing_owner = st.session_state.get(_OWNER_KEY)

    if existing is not None and existing_owner == username:
        return existing

    # Owner mismatch (or first call) — rebuild.
    mgr = ConnectionManager()
    if username:
        try:
            raw = get_source_store().load(username)
            # Round-trip through record_to_source so any base64-encoded
            # bytes in configs get decoded back into real ``bytes`` before
            # the connectors see them.
            hydrated = []
            for r in raw:
                sid, meta = record_to_source(r)
                hydrated.append({"id": sid, **meta})
            mgr.hydrate_sources(hydrated)
        except Exception:
            # Store unavailable — start with an empty manager. Guests are
            # unaffected because they skip persistence entirely.
            pass
        mgr.set_on_change(_build_on_change(username))

    st.session_state[_SESSION_KEY] = mgr
    st.session_state[_OWNER_KEY] = username
    return mgr


def rebuild_session_connection_manager() -> ConnectionManager:
    """Force a rebuild — useful on logout so the next signed-in user
    doesn't see the previous user's sources before ``current_user()`` has
    a chance to refresh."""
    st.session_state.pop(_SESSION_KEY, None)
    st.session_state.pop(_OWNER_KEY, None)
    return get_session_connection_manager()

"""Session-scoped bootstrap helpers.

The core idea: every Streamlit page that needs per-user state should
call :func:`get_session_connection_manager` and
:func:`get_session_company_config` *once* at the top of the page. Those
helpers:

* read the currently signed-in user,
* hydrate the user's ``ConnectionManager`` (sources) and
  ``CompanyConfig`` (profile) from the persistent store on first access,
* install a write-through persistence callback for sources so every
  subsequent ``add_source`` / ``remove_source`` syncs back to the store,
* bind the user's ``CompanyConfig`` to the current thread so every
  agent that imports ``company_cfg`` automatically sees the right
  per-user values for this rerun,
* cache results under ``st.session_state`` (keyed on the signed-in
  username) so switching accounts in the same tab rebuilds cleanly.

Guests (no signed-in user) still get a working in-memory manager and the
bundled default profile, so the demo flow keeps working; their state
simply isn't persisted.
"""
from __future__ import annotations

import streamlit as st

from core.company_config import (
    CompanyConfig,
    get_default_company_config,
    set_active_company_config,
)
from utils.connection_manager import ConnectionManager
from utils.profile_store import get_profile_store
from utils.source_store import (
    get_source_store,
    record_to_source,
    source_to_record,
)


_SESSION_KEY = "conn_manager"
_OWNER_KEY = "_conn_manager_owner"
_PROFILE_KEY = "company_profile"
_PROFILE_OWNER_KEY = "_company_profile_owner"
_PROFILE_TOKEN_KEY = "_company_profile_token"
_CONFIG_KEY = "_company_cfg"


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
    """Return a callback that snapshots a ConnectionManager to the store.

    Also drops the process-wide source-store cache entry so a second tab
    on the same replica picks up the change on its next rerun instead
    of waiting for the TTL window to elapse.

    Side effect: invalidates the orchestrator's incremental cache. The
    fingerprint chain *should* propagate a source change all the way
    through to every downstream agent's dep_fp, but the chain depends
    on data_collector's result actually changing in a fingerprint-
    detectable way — and data_collector's result is mostly aggregate
    metadata (record counts, completeness scores). If a user replaces
    a CSV with the same number of rows but different *values*, the
    metadata can hash identically even though every downstream
    calculation should change. Clearing the cache here guarantees a
    fresh end-to-end run on the next click, regardless of how the
    user mutated the source.
    """
    store = get_source_store()

    def _callback(mgr: ConnectionManager) -> None:
        records = [
            source_to_record(sid, meta)
            for sid, meta in mgr._sources.items()  # noqa: SLF001
        ]
        store.save(username, records)
        store.clear_cache(username)
        try:
            orch = st.session_state.get("orchestrator")
            if orch is not None and hasattr(orch, "invalidate_incremental_cache"):
                orch.invalidate_incremental_cache()
        except Exception:
            pass

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


# ---------------------------------------------------------------------------
# Per-user company profile / CompanyConfig
# ---------------------------------------------------------------------------
def get_session_company_profile() -> dict:
    """Return the signed-in user's profile dict (mutable copy).

    Loads from the per-user profile store on first access this session,
    falls back to the bundled default profile for guests. Always returns
    a fresh deep copy so the caller can mutate without affecting other
    sessions.

    Side effect: records the load token under ``_PROFILE_TOKEN_KEY`` in
    session_state. :func:`save_session_company_profile` reads this token
    back out to give optimistic-concurrency protection — two tabs of
    the same user editing simultaneously will no longer silently clobber
    each other.
    """
    username = _current_username()
    existing = st.session_state.get(_PROFILE_KEY)
    existing_owner = st.session_state.get(_PROFILE_OWNER_KEY)

    if existing is not None and existing_owner == username:
        # Return a copy so mutations in the page don't leak through the
        # cached reference (which the Settings page edits in-place).
        import json as _json
        return _json.loads(_json.dumps(existing))

    store = get_profile_store()
    token: str | None = None
    if username:
        try:
            profile, token = store.load_with_token(username)
        except Exception:
            profile = store.default_profile()
            token = None
    else:
        profile = store.default_profile()

    st.session_state[_PROFILE_KEY] = profile
    st.session_state[_PROFILE_OWNER_KEY] = username
    st.session_state[_PROFILE_TOKEN_KEY] = token
    # Force the company-config helper to rebuild on next call.
    st.session_state.pop(_CONFIG_KEY, None)

    import json as _json
    return _json.loads(_json.dumps(profile))


def save_session_company_profile(profile: dict, *, force: bool = False) -> None:
    """Persist ``profile`` for the signed-in user and refresh the cache.

    No-op for guests (they have nowhere durable to save to).

    Concurrency
    -----------
    By default we enforce optimistic concurrency using the token captured
    at :func:`get_session_company_profile` time. If the stored profile
    has changed since load (another tab / replica), the underlying store
    raises :class:`utils.profile_store.ProfileConflict` and the caller
    is expected to surface a "reload or overwrite?" prompt to the user.

    Pass ``force=True`` to bypass the check and clobber the other
    writer — used when the user explicitly chooses "Save anyway" after
    being shown the conflict.

    After the durable write succeeds we clear the *process-wide* profile
    cache for this user so any other browser tab on the same replica
    sees the new profile on its next rerun rather than waiting out the
    TTL.
    """
    username = _current_username()
    if not username:
        return
    store = get_profile_store()
    expected_token = (
        None if force else st.session_state.get(_PROFILE_TOKEN_KEY)
    )
    if force or expected_token is None:
        # Legacy / forced path — no concurrency check.
        new_token = store.save(username, profile)
    else:
        new_token = store.save(username, profile, expected_token=expected_token)
    store.clear_cache(username)
    # Update the in-session cache so the page sees its own write back
    # immediately (don't wait for the TTL to expire on the next load).
    st.session_state[_PROFILE_KEY] = profile
    st.session_state[_PROFILE_OWNER_KEY] = username
    st.session_state[_PROFILE_TOKEN_KEY] = new_token
    st.session_state.pop(_CONFIG_KEY, None)


def get_session_company_config() -> CompanyConfig:
    """Return (and bind) the per-user :class:`CompanyConfig` for this rerun.

    Side effect: also calls :func:`set_active_company_config` so every
    ``from core.company_config import company_cfg`` reference in the
    rest of the page (and inside agents) resolves to this user's config
    for the duration of this thread's work.

    Idempotent — safe to call at the top of every page.
    """
    username = _current_username()
    cached = st.session_state.get(_CONFIG_KEY)
    cached_owner = st.session_state.get(_PROFILE_OWNER_KEY)

    if cached is not None and cached_owner == username:
        set_active_company_config(cached)
        return cached

    if username:
        profile = get_session_company_profile()
        cfg, build_error = _build_company_config_safely(profile)
    else:
        cfg = get_default_company_config()
        build_error = None

    st.session_state[_CONFIG_KEY] = cfg
    # Stash the last build error so pages / banners can surface it
    # without re-running the construction. Cleared on successful build.
    st.session_state["_company_cfg_build_error"] = build_error
    set_active_company_config(cfg)
    return cfg


def _build_company_config_safely(profile: dict) -> tuple[CompanyConfig, str | None]:
    """Construct a :class:`CompanyConfig` from ``profile``, never raising.

    Returns ``(cfg, error_message)``. ``error_message`` is ``None`` on
    success, or a human-readable string on failure (profile was invalid
    and we fell back to the bundled default). The Settings page reads
    this so the user sees *why* their edits didn't apply instead of
    silently running on defaults.
    """
    # Cheap structural check first — surfaces malformed profiles with
    # field-level errors rather than a bare exception.
    from utils.profile_validator import validate_profile
    issues = validate_profile(profile)
    if issues:
        return get_default_company_config(), (
            "Profile failed validation: "
            + "; ".join(issues[:3])
            + ("…" if len(issues) > 3 else "")
        )
    try:
        return CompanyConfig(profile_data=profile), None
    except Exception as exc:  # noqa: BLE001 — last-resort guard
        return get_default_company_config(), (
            f"Could not build CompanyConfig from profile: "
            f"{type(exc).__name__}: {exc}"
        )


def rebuild_session_company_config() -> CompanyConfig:
    """Force a rebuild — call on logout so the next signed-in user's
    profile loads fresh on the next interaction."""
    st.session_state.pop(_PROFILE_KEY, None)
    st.session_state.pop(_PROFILE_OWNER_KEY, None)
    st.session_state.pop(_PROFILE_TOKEN_KEY, None)
    st.session_state.pop(_CONFIG_KEY, None)
    set_active_company_config(None)
    return get_session_company_config()

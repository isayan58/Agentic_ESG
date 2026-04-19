"""Shared state manager for inter-agent communication.

The pipeline runs as a tree of agents that talk to each other through a
publish/subscribe channel store. Historically that store was a single
process-wide dict — fine for a single-user demo, **catastrophic** the
moment multiple users hit the same Streamlit process: User B's
``publish("carbon_results", …)`` would silently overwrite User A's, and
on User A's next page-view the Audit / Report / Risk / Action /
Stakeholder / ROI agents would happily ``subscribe()`` and render
User B's numbers on User A's screen.

This module fixes that by partitioning the channel store *per-user*.
Every ``publish`` / ``subscribe`` / ``get_all_channels`` / ``clear``
call resolves the current Streamlit session's signed-in username (with
a stable ``"_anonymous"`` fallback for guest / non-Streamlit / test
contexts) and routes the operation into that user's private bucket.

The public API is unchanged so existing call sites keep working:

* ``state_manager.publish(channel, data)``      — current user's bucket
* ``state_manager.subscribe(channel)``          — current user's bucket
* ``state_manager.get_all_channels()``          — current user's bucket
* ``state_manager.clear()``                     — current user's bucket

For explicit cross-user cleanup (e.g. on logout) callers can use the
new ``state_manager.clear_user(username)`` helper.

We also preserve a ``state_manager._channels`` *property* that returns
the current user's bucket, so the one direct-mutation site in
:mod:`utils.pipeline_refresh` (``_channels.pop(ch, None)``) keeps
working without a code change.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any


_GUEST_KEY = "_anonymous"


def _current_username() -> str:
    """Return the signed-in username for routing, or the guest sentinel.

    Resolved at every call so the same singleton can serve many users
    in the same Python process. Falls back to a stable ``"_anonymous"``
    bucket when:

    * Streamlit isn't importable (tests, scripts, CLI)
    * No user is signed in (the public landing pages)
    * Streamlit's session state is not initialised yet (very early in
      page bootstrap, before ``require_login`` runs)
    """
    try:
        import streamlit as st  # local import — avoids hard dep at import time
    except Exception:
        return _GUEST_KEY
    try:
        user = st.session_state.get("user")
    except Exception:
        return _GUEST_KEY
    if not user:
        return _GUEST_KEY
    name = (user.get("username") or "").strip()
    return name or _GUEST_KEY


class StateManager:
    """Per-user pub/sub state manager for passing data between agents.

    All public mutating / reading operations are scoped to the
    *currently signed-in user*. Two users sharing the same Python
    process never see each other's published channels.
    """

    def __init__(self) -> None:
        # username → {channel_name: {"data", "published_by", "timestamp"}}
        self._user_channels: dict[str, dict[str, dict[str, Any]]] = {}
        # username → list of audit-trail entries
        self._user_history: dict[str, list[dict[str, Any]]] = {}

    # ── Internal helpers ────────────────────────────────────────────────
    def _bucket(self, username: str | None = None) -> dict[str, dict[str, Any]]:
        """Return the channel-bucket for ``username`` (creating it lazily).

        ``None`` resolves to the current Streamlit session's user.
        """
        key = username or _current_username()
        return self._user_channels.setdefault(key, {})

    def _history_bucket(self, username: str | None = None) -> list[dict[str, Any]]:
        key = username or _current_username()
        return self._user_history.setdefault(key, [])

    # ── Public pub/sub API ──────────────────────────────────────────────
    def publish(self, channel: str, data: Any, agent_name: str = "system") -> None:
        bucket = self._bucket()
        bucket[channel] = {
            "data": data,
            "published_by": agent_name,
            "timestamp": datetime.now().isoformat(),
        }
        self._history_bucket().append({
            "action": "publish",
            "channel": channel,
            "agent": agent_name,
            "timestamp": datetime.now().isoformat(),
        })

    def subscribe(self, channel: str) -> Any:
        entry = self._bucket().get(channel)
        if entry:
            return entry["data"]
        return None

    def get_all_channels(self) -> dict[str, dict[str, Any]]:
        return {
            ch: {
                "published_by": info["published_by"],
                "timestamp": info["timestamp"],
                "has_data": info["data"] is not None,
            }
            for ch, info in self._bucket().items()
        }

    def clear(self) -> None:
        """Clear the **current user's** bucket only."""
        self._bucket().clear()
        self._history_bucket().clear()

    def clear_user(self, username: str) -> None:
        """Drop a specific user's bucket entirely. Safe to call on logout."""
        if not username:
            return
        self._user_channels.pop(username, None)
        self._user_history.pop(username, None)

    def clear_all(self) -> None:
        """Drop every user's bucket. Useful in tests / process shutdown."""
        self._user_channels.clear()
        self._user_history.clear()

    # ── Backward-compat shim ────────────────────────────────────────────
    # ``utils.pipeline_refresh._clear_stale_state_datasets`` reaches in
    # via ``state_manager._channels.pop(ch, None)``. Exposing a property
    # that returns the current user's bucket keeps that call site
    # working *and* per-user safe — popping from the property mutates
    # the underlying bucket because dicts are reference types.
    @property
    def _channels(self) -> dict[str, dict[str, Any]]:
        return self._bucket()

    @property
    def _history(self) -> list[dict[str, Any]]:
        return self._history_bucket()


# Singleton — module-global on purpose. Per-user partitioning lives
# inside the instance, not the import surface.
state_manager = StateManager()

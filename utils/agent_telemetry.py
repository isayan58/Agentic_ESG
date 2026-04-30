"""Persistent agent telemetry store, partitioned per user.

Every agent run (success or error) produces a telemetry record — who ran,
when, how long, success/error, recent audit tail. ``BaseAgent.run()`` calls
``record()`` before/after ``execute()`` so we capture state even on crashes.

Why a file and not a DB?
------------------------
This is the simplest persistence layer that survives process restarts: a
single JSON blob at ``data/agent_telemetry.json``, written atomically via
tempfile + rename under a process-wide lock. When we outgrow single-file,
swap the ``_read_file`` / ``_write_file`` implementations for a real DB —
every public function (``record``, ``load_all``, ``get``, ``history``) keeps
its signature, so call sites don't change.

User partitioning
-----------------
The on-disk JSON is keyed first by ``user_id`` and then by ``agent_key``::

    {
      "alice":    { "data_collector": { ... }, "carbon_accountant": { ... } },
      "bob":      { "data_collector": { ... } },
      "_legacy":  { ... }   # pre-partitioning records, migrated on first read
    }

Public functions accept an optional ``user_id``; when omitted, the current
Streamlit session's signed-in user is resolved via the same helper used by
``core.state_manager`` (falling back to ``"_anonymous"`` for tests/scripts).
This keeps two users in the same Python process from seeing each other's
runs.

Per-agent record shape (unchanged)
----------------------------------
::

    {
      "name":            "Data Collector",
      "status":          "completed" | "running" | "error" | "idle",
      "last_run":        "2026-04-24T10:32:15+00:00",   # finished_at
      "started_at":      "2026-04-24T10:32:11+00:00",
      "finished_at":     "2026-04-24T10:32:15+00:00",
      "runtime_seconds": 3.92,
      "last_error":      null | "traceback string",
      "run_count":       42,
      "updated_at":      "2026-04-24T10:32:15+00:00",
      "history": [           # capped; newest first
        {"timestamp": ..., "status": ..., "runtime_seconds": ..., "error": ...},
        ...
      ]
    }
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# File layout
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _REPO_ROOT / "data"
_TELEMETRY_FILE = _DATA_DIR / "agent_telemetry.json"

# Cap how many prior runs we keep per agent. Plenty for a UI "last 20 runs"
# view; if you need full history, stream into a real DB at that point.
_HISTORY_CAP = 50

# Process-wide lock. Streamlit reruns the script per request — within a
# single Python process, this lock keeps concurrent saves consistent.
_LOCK = threading.Lock()

# Reserved bucket for telemetry written before per-user partitioning landed.
# We migrate the old flat-shape JSON into this bucket on first read.
_LEGACY_USER = "_legacy"
_GUEST_USER = "_anonymous"


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------
_slug_re = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Lowercase snake_case slug derived from an agent name.

    ``"Data Collector"`` → ``"data_collector"``. Used as a fallback when an
    orchestrator-assigned ``telemetry_key`` is absent.
    """
    return _slug_re.sub("_", (value or "").lower()).strip("_") or "agent"


def _current_username() -> str:
    """Mirror of ``core.state_manager._current_username``.

    Resolved at every call so the same module can serve many users in the
    same Python process. Falls back to ``"_anonymous"`` when streamlit is
    unavailable, no user is signed in, or session state is uninitialised.
    """
    try:
        import streamlit as st  # local import — avoid hard dep
    except Exception:
        return _GUEST_USER
    try:
        user = st.session_state.get("user")
    except Exception:
        return _GUEST_USER
    if not user:
        return _GUEST_USER
    name = (user.get("username") or "").strip()
    return name or _GUEST_USER


def _resolve_user(user_id: Optional[str]) -> str:
    return user_id if user_id else _current_username()


def _looks_like_agent_record(value: Any) -> bool:
    """Heuristic for detecting the pre-partitioning flat shape on disk."""
    if not isinstance(value, dict):
        return False
    return any(k in value for k in ("status", "last_run", "history", "run_count"))


def _ensure_partitioned(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return data in the new ``{user: {agent: rec}}`` shape.

    If the file is the old flat ``{agent: rec}`` shape we move it under the
    ``_legacy`` user. Idempotent — safe to call on already-partitioned data.
    """
    if not data:
        return {}
    if any(_looks_like_agent_record(v) for v in data.values()):
        return {_LEGACY_USER: data}
    # Already partitioned. Strip any non-dict values defensively.
    return {k: v for k, v in data.items() if isinstance(v, dict)}


# ---------------------------------------------------------------------------
# Low-level file IO — swap these two to move off JSON without touching the
# public API.
# ---------------------------------------------------------------------------
def _read_file() -> dict[str, dict[str, Any]]:
    if not _TELEMETRY_FILE.exists():
        return {}
    try:
        with _TELEMETRY_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return _ensure_partitioned(data) if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        # Corrupt or unreadable — treat as empty so callers keep working.
        # The next successful ``record()`` will rewrite the file cleanly.
        return {}


def _write_file(data: dict[str, dict[str, Any]]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Atomic write: temp file in same dir, then os.replace onto target.
    # Guarantees readers never see a half-written JSON blob.
    fd, tmp_path = tempfile.mkstemp(
        prefix=".agent_telemetry_", suffix=".json", dir=str(_DATA_DIR)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True, default=str)
        os.replace(tmp_path, _TELEMETRY_FILE)
    except Exception:
        # Best-effort cleanup on failure.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def load_all(user_id: Optional[str] = None) -> dict[str, dict]:
    """Return a copy of the calling user's telemetry snapshot.

    Pass ``user_id`` explicitly for tests/CLI; production callers can omit
    it and the current Streamlit session user is used.
    """
    uid = _resolve_user(user_id)
    with _LOCK:
        return _read_file().get(uid, {})


def get(agent_key: str, user_id: Optional[str] = None) -> Optional[dict]:
    """Return the telemetry record for one agent, or ``None`` if absent."""
    uid = _resolve_user(user_id)
    with _LOCK:
        return _read_file().get(uid, {}).get(agent_key)


def history(agent_key: str, limit: int = 20, user_id: Optional[str] = None) -> list[dict]:
    """Return the last ``limit`` run records for an agent (newest first)."""
    rec = get(agent_key, user_id=user_id) or {}
    return (rec.get("history") or [])[:max(0, int(limit))]


def record(
    agent_key: str,
    snapshot: dict,
    *,
    append_history: bool = True,
    user_id: Optional[str] = None,
) -> None:
    """Merge ``snapshot`` into the user's record for ``agent_key`` and persist.

    Expected snapshot keys (any subset): ``name``, ``status``, ``last_run``,
    ``started_at``, ``finished_at``, ``runtime_seconds``, ``last_error``,
    ``run_count``.

    When ``append_history`` is True and the snapshot's ``status`` is
    ``completed`` or ``error``, a compact history row is prepended. Running/idle
    updates don't pollute history — they just refresh the live fields.
    """
    uid = _resolve_user(user_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        data = _read_file()
        user_bucket = data.setdefault(uid, {})
        existing = user_bucket.get(agent_key) or {}
        merged = {**existing, **{k: v for k, v in snapshot.items() if v is not None}}

        if append_history:
            status = (snapshot.get("status") or "").lower()
            if status in ("completed", "error"):
                row = {
                    "timestamp": snapshot.get("finished_at") or now_iso,
                    "status": status,
                    "runtime_seconds": snapshot.get("runtime_seconds"),
                    "error": snapshot.get("last_error"),
                }
                hist = list(existing.get("history") or [])
                hist.insert(0, row)
                merged["history"] = hist[:_HISTORY_CAP]

        merged["updated_at"] = now_iso
        user_bucket[agent_key] = merged
        _write_file(data)


def reset(agent_key: Optional[str] = None, user_id: Optional[str] = None) -> None:
    """Clear telemetry for one user — either one agent or the whole bucket.

    Pass ``user_id="*"`` to wipe the entire file (admin/test only).
    """
    if user_id == "*":
        with _LOCK:
            _write_file({})
        return

    uid = _resolve_user(user_id)
    with _LOCK:
        data = _read_file()
        bucket = data.get(uid)
        if not bucket:
            return
        if agent_key is None:
            data.pop(uid, None)
        else:
            bucket.pop(agent_key, None)
        _write_file(data)

"""Persistent agent telemetry store.

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

Schema
------
Top-level dict keyed by ``agent_key`` (e.g. ``"data_collector"``, ``"roi_agent"``).
Each entry::

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


# ---------------------------------------------------------------------------
# Low-level file IO — swap these two to move off JSON without touching the
# public API.
# ---------------------------------------------------------------------------
def _read_file() -> dict[str, Any]:
    if not _TELEMETRY_FILE.exists():
        return {}
    try:
        with _TELEMETRY_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        # Corrupt or unreadable — treat as empty so callers keep working.
        # The next successful ``record()`` will rewrite the file cleanly.
        return {}


def _write_file(data: dict[str, Any]) -> None:
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
def load_all() -> dict[str, dict]:
    """Return a copy of the entire telemetry snapshot."""
    with _LOCK:
        return _read_file()


def get(agent_key: str) -> Optional[dict]:
    """Return the telemetry record for one agent, or ``None`` if absent."""
    with _LOCK:
        return _read_file().get(agent_key)


def history(agent_key: str, limit: int = 20) -> list[dict]:
    """Return the last ``limit`` run records for an agent (newest first)."""
    rec = get(agent_key) or {}
    return (rec.get("history") or [])[:max(0, int(limit))]


def record(agent_key: str, snapshot: dict, *, append_history: bool = True) -> None:
    """Merge ``snapshot`` into an agent's record and persist.

    Expected snapshot keys (any subset): ``name``, ``status``, ``last_run``,
    ``started_at``, ``finished_at``, ``runtime_seconds``, ``last_error``,
    ``run_count``.

    When ``append_history`` is True and the snapshot's ``status`` is
    ``completed`` or ``error``, a compact history row is prepended. Running/idle
    updates don't pollute history — they just refresh the live fields.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        data = _read_file()
        existing = data.get(agent_key) or {}
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
        data[agent_key] = merged
        _write_file(data)


def reset(agent_key: Optional[str] = None) -> None:
    """Clear telemetry — either for one agent or (if ``None``) the whole file.

    Mostly a convenience for tests/admin tooling. No production code calls it.
    """
    with _LOCK:
        if agent_key is None:
            _write_file({})
            return
        data = _read_file()
        data.pop(agent_key, None)
        _write_file(data)

"""Persistent feedback logging for ESG Pilot.

Stores explicit user feedback alongside generated report metadata so the
pipeline can learn from real usage signals over time.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK_DIR = Path("data") / "feedback"
_FEEDBACK_LOCK = threading.RLock()


def _safe_username(username: str | None) -> str:
    if not username:
        return "anonymous"
    cleaned = re.sub(r"[^a-zA-Z0-9_.\-]", "_", username.strip())
    return cleaned[:64] or "anonymous"


def _feedback_file(username: str | None = None) -> Path:
    return FEEDBACK_DIR / f"{_safe_username(username)}.json"


def _ensure_feedback_dir() -> None:
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def load_feedback(username: str | None = None) -> list[dict]:
    path = _feedback_file(username)
    if not path.is_file():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def load_all_feedback() -> list[dict]:
    feedback = []
    if not FEEDBACK_DIR.is_dir():
        return feedback
    for path in sorted(FEEDBACK_DIR.glob("*.json")):
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
            items = json.loads(raw)
            if isinstance(items, list):
                feedback.extend(items)
        except Exception:
            continue
    return feedback


def load_recent_feedback(limit: int = 10) -> list[dict]:
    feedback = load_all_feedback()
    def _key(item: dict) -> float:
        value = item.get("timestamp")
        if not isinstance(value, str):
            return 0.0
        try:
            return datetime.fromisoformat(value).timestamp()
        except Exception:
            return 0.0

    feedback.sort(key=_key, reverse=True)
    return feedback[:limit]


def save_feedback(entry: dict, username: str | None = None) -> dict:
    if not isinstance(entry, dict):
        raise ValueError("Feedback entry must be a dict.")
    entry_copy = dict(entry)
    entry_copy["timestamp"] = datetime.now(timezone.utc).isoformat()
    if "username" not in entry_copy:
        entry_copy["username"] = _safe_username(username)
    _ensure_feedback_dir()
    path = _feedback_file(username)
    with _FEEDBACK_LOCK:
        existing = load_feedback(username)
        existing.append(entry_copy)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return entry_copy

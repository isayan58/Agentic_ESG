"""Framework refresh — pulls global regulatory updates via Claude's server-side
web_search tool, diffs them against the local `regulatory_frameworks.json`,
and stores pending changes in an overlay file for human approval.

Design (see conversation):
- Real fetch via Claude + web_search (no hallucinated requirements).
- Pending overlay at data/regulatory_updates.json (status: pending | applied |
  dismissed) with provenance URLs.
- Approved updates merge into the live framework set; dismissed ones are
  retained for audit.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic
import config


# Where the overlay of pending / applied / dismissed updates lives.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UPDATES_PATH = DATA_DIR / "regulatory_updates.json"
FRAMEWORKS_PATH = DATA_DIR / "regulatory_frameworks.json"

# Frameworks in scope for auto-refresh. Keep names aligned with
# regulatory_frameworks.json keys.
TRACKED_FRAMEWORKS = ("BRSR", "CSRD", "GRI", "SASB", "SOX", "SEC")


# ── Storage helpers ─────────────────────────────────────────────────────

def _empty_store() -> dict:
    return {
        "last_checked": None,
        "last_error": None,
        "updates": [],  # each: {id, framework, type, title, description,
                        # source_url, detected_at, impact, status,
                        # proposed_requirement?}
    }


def load_updates_store() -> dict:
    if not UPDATES_PATH.exists():
        return _empty_store()
    try:
        with UPDATES_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Backfill missing keys for older files.
        for k, v in _empty_store().items():
            data.setdefault(k, v)
        return data
    except (OSError, json.JSONDecodeError):
        return _empty_store()


def save_updates_store(store: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = UPDATES_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(store, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, UPDATES_PATH)


def load_frameworks() -> dict:
    with FRAMEWORKS_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def save_frameworks(frameworks: dict) -> None:
    tmp = FRAMEWORKS_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(frameworks, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, FRAMEWORKS_PATH)


# ── Fetch via Claude web_search ─────────────────────────────────────────

_FETCH_PROMPT = """You are an ESG regulatory intelligence analyst. Using web search,
find **only authoritative** updates published in the last 6 months for these
frameworks: {frameworks}.

Sources that count as authoritative:
- BRSR: SEBI circulars & press releases (sebi.gov.in)
- CSRD / ESRS: EFRAG, European Commission, ESMA
- GRI: globalreporting.org / standards
- SASB / ISSB: ifrs.org, sasb.org
- SOX: PCAOB, SEC (sec.gov) rule releases, AS standards
- SEC Climate Rule: sec.gov rule releases and final rule text

For each real update you find, return a JSON object with:
{{
  "framework": "<one of: BRSR, CSRD, GRI, SASB, SOX, SEC>",
  "type": "new_requirement | amendment | deadline_change | guidance | assurance_change | withdrawal",
  "title": "<short title>",
  "description": "<2-3 sentence plain-English summary of what changed>",
  "source_url": "<direct link to the authority's page>",
  "effective_date": "<YYYY-MM-DD or null if not yet set>",
  "impact": "high | medium | low",
  "proposed_requirement": {{
    "id": "<suggested id, e.g. BRSR-E13 or SEC-CLIM-1507>",
    "section": "<official section / item number>",
    "requirement": "<short requirement name>",
    "data_fields": ["<snake_case_field_1>", ...],
    "priority": "critical | high | medium | low"
  }} or null (null when the update is a deadline change or guidance, not a new requirement)
}}

Return ONLY a JSON array of these objects, nothing else. If no real updates
are found for a framework, simply omit it. Do not invent requirements — every
entry must map to a real published change with a working source URL.
"""


def _strip_to_json_array(text: str) -> str:
    """Pull the first top-level JSON array from Claude's response.

    Claude's web-search responses often include prose and citation markup
    around the JSON. We locate the outermost [...] substring that parses.
    """
    fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text


def _update_id(entry: dict) -> str:
    """Stable id so the same published change isn't re-added on every refresh."""
    seed = json.dumps(
        {
            "framework": entry.get("framework"),
            "title": entry.get("title"),
            "source_url": entry.get("source_url"),
        },
        sort_keys=True,
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def fetch_framework_updates(
    frameworks: tuple[str, ...] = TRACKED_FRAMEWORKS,
    *,
    max_searches: int = 8,
    model: str | None = None,
) -> list[dict]:
    """Call Claude with web_search enabled and return parsed update entries.

    Raises RuntimeError if ANTHROPIC_API_KEY is missing or the response can't
    be parsed — callers should catch and surface the error in the UI.
    """
    api_key = config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set — framework refresh requires it."
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = _FETCH_PROMPT.format(frameworks=", ".join(frameworks))
    response = client.messages.create(
        model=model or config.ANTHROPIC_MODEL,
        max_tokens=4096,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": max_searches,
        }],
        messages=[{"role": "user", "content": prompt}],
    )
    # Concatenate text blocks (the tool-use + search results flow through
    # server-side; final JSON lives in the last text block).
    text_chunks = [
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    ]
    body = "\n".join(text_chunks).strip()
    if not body:
        return []
    raw = _strip_to_json_array(body)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Model did not return parseable JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise RuntimeError("Expected a JSON array from the model.")

    cleaned = []
    for entry in parsed:
        if not isinstance(entry, dict):
            continue
        fw = entry.get("framework")
        if fw not in frameworks:
            continue
        if not entry.get("title") or not entry.get("source_url"):
            continue
        entry["id"] = _update_id(entry)
        entry.setdefault("detected_at", datetime.now().isoformat(timespec="seconds"))
        entry.setdefault("status", "pending")
        cleaned.append(entry)
    return cleaned


# ── Diff + merge ────────────────────────────────────────────────────────

def refresh_and_store(
    frameworks: tuple[str, ...] = TRACKED_FRAMEWORKS,
) -> dict:
    """Run a full refresh: fetch, dedupe against the stored overlay, persist.

    Returns the updated store dict. On failure, store.last_error is set and
    the previous updates are preserved.
    """
    store = load_updates_store()
    try:
        fetched = fetch_framework_updates(frameworks)
    except Exception as exc:
        store["last_checked"] = datetime.now().isoformat(timespec="seconds")
        store["last_error"] = str(exc)
        save_updates_store(store)
        return store

    existing_ids = {u.get("id") for u in store.get("updates", [])}
    added = 0
    for entry in fetched:
        if entry["id"] in existing_ids:
            continue
        store["updates"].append(entry)
        existing_ids.add(entry["id"])
        added += 1

    store["last_checked"] = datetime.now().isoformat(timespec="seconds")
    store["last_error"] = None
    store["last_added_count"] = added
    save_updates_store(store)
    return store


# ── Approvals ───────────────────────────────────────────────────────────

def _find_update(store: dict, update_id: str) -> dict | None:
    for u in store.get("updates", []):
        if u.get("id") == update_id:
            return u
    return None


def apply_update(update_id: str) -> dict:
    """Apply a pending update to regulatory_frameworks.json.

    If the update carries a `proposed_requirement`, append it under the
    matching framework's `requirements` list. Marks the update as applied
    with the timestamp. Idempotent — re-applying has no extra effect.
    """
    store = load_updates_store()
    update = _find_update(store, update_id)
    if update is None:
        return {"ok": False, "reason": f"No update with id {update_id}."}
    if update.get("status") == "applied":
        return {"ok": True, "already": True}

    proposed = update.get("proposed_requirement")
    frameworks = load_frameworks()
    fw_name = update.get("framework")

    if proposed and fw_name in frameworks.get("frameworks", {}):
        reqs = frameworks["frameworks"][fw_name].setdefault("requirements", [])
        # Don't duplicate by id or (section, requirement) pair.
        existing_ids = {r.get("id") for r in reqs}
        existing_pairs = {
            (r.get("section"), r.get("requirement")) for r in reqs
        }
        already = (
            proposed.get("id") in existing_ids
            or (proposed.get("section"), proposed.get("requirement")) in existing_pairs
        )
        if not already:
            reqs.append({
                "id": proposed.get("id"),
                "section": proposed.get("section"),
                "requirement": proposed.get("requirement"),
                "data_fields": proposed.get("data_fields") or [],
                "priority": proposed.get("priority") or "medium",
            })
            save_frameworks(frameworks)

    update["status"] = "applied"
    update["applied_at"] = datetime.now().isoformat(timespec="seconds")
    save_updates_store(store)
    return {"ok": True}


def dismiss_update(update_id: str, reason: str = "") -> dict:
    store = load_updates_store()
    update = _find_update(store, update_id)
    if update is None:
        return {"ok": False, "reason": f"No update with id {update_id}."}
    update["status"] = "dismissed"
    update["dismissed_at"] = datetime.now().isoformat(timespec="seconds")
    if reason:
        update["dismiss_reason"] = reason
    save_updates_store(store)
    return {"ok": True}


# ── Convenience filters for the UI ──────────────────────────────────────

def pending_updates(store: dict | None = None) -> list[dict]:
    s = store or load_updates_store()
    return [u for u in s.get("updates", []) if u.get("status") == "pending"]


def applied_updates(store: dict | None = None) -> list[dict]:
    s = store or load_updates_store()
    return [u for u in s.get("updates", []) if u.get("status") == "applied"]


def dismissed_updates(store: dict | None = None) -> list[dict]:
    s = store or load_updates_store()
    return [u for u in s.get("updates", []) if u.get("status") == "dismissed"]


def time_since_last_check(store: dict | None = None) -> str:
    s = store or load_updates_store()
    ts = s.get("last_checked")
    if not ts:
        return "never"
    try:
        then = datetime.fromisoformat(ts)
    except ValueError:
        return ts
    delta = datetime.now() - then
    secs = int(delta.total_seconds())
    if secs < 60:
        return f"{secs}s ago"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


__all__ = [
    "TRACKED_FRAMEWORKS",
    "load_updates_store",
    "save_updates_store",
    "fetch_framework_updates",
    "refresh_and_store",
    "apply_update",
    "dismiss_update",
    "pending_updates",
    "applied_updates",
    "dismissed_updates",
    "time_since_last_check",
]

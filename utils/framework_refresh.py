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
        # Append-only event log for every apply / revert / dismiss action.
        # Lets operators answer "who approved this requirement and when?"
        # and gives revert_update something to read when undoing a change.
        # Each entry: {action, update_id, framework, requirement_id,
        #              timestamp, actor?, snapshot?}
        "audit_log": [],
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
    # ``strict=False`` tolerates raw control characters (literal \n, \t, …)
    # inside string values — LLM output is frequently not RFC-strict, and
    # rejecting the whole payload because of one unescaped newline loses
    # real regulatory updates. If that still fails, strip the remaining
    # disallowed control chars (NULs, etc.) and try once more before
    # giving up with the original error.
    try:
        parsed = json.loads(raw, strict=False)
    except json.JSONDecodeError as exc:
        scrubbed = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
        try:
            parsed = json.loads(scrubbed, strict=False)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"Model did not return parseable JSON: {exc}"
            ) from exc
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

    # Best-effort fan-out to configured notification routes for the
    # signed-in user's org. Failures are absorbed inside ``notify`` so a
    # broken Slack webhook never blocks a successful refresh.
    if added:
        try:
            _notify_pending_updates(store, added)
        except Exception:  # noqa: BLE001 — never break the refresh path
            pass
    return store


def _notify_pending_updates(store: dict, added_count: int) -> None:
    """Dispatch a `regulatory_update_pending` event for newly-detected updates."""
    try:
        from utils.notifications import Event, notify
    except Exception:  # pragma: no cover - notifications optional
        return

    # Find owners we should fan out to. Streamlit context is not
    # guaranteed (this might run from a CLI / job), so we fall back to
    # an env-configured org if no signed-in user is available.
    owner: str | None = None
    actor: str | None = None
    try:
        import streamlit as st
        user = (st.session_state.get("user") or {}) if hasattr(st, "session_state") else {}
        owner = (user.get("org_id") or "").strip() or None
        actor = (user.get("username") or "").strip() or None
    except Exception:
        owner = None
    owner = owner or os.getenv("ESG_DEFAULT_ORG") or None
    if not owner:
        return

    pending = [u for u in store.get("updates", []) if u.get("status") == "pending"]
    headlines = "; ".join(
        f"[{u.get('framework')}] {u.get('title')}" for u in pending[:3]
    )
    summary = (
        f"{added_count} new regulatory update(s) need approval. "
        f"Total pending in queue: {len(pending)}.\n\n{headlines}"
    )
    severity = "warning" if added_count >= 3 else "info"
    notify(
        Event(
            type="regulatory_update_pending",
            title=f"{added_count} new regulatory update(s) pending approval",
            summary=summary,
            severity=severity,
            actor=actor,
            payload={"added": added_count, "pending_total": len(pending)},
        ),
        owner=owner,
    )


# ── Approvals ───────────────────────────────────────────────────────────

def _find_update(store: dict, update_id: str) -> dict | None:
    for u in store.get("updates", []):
        if u.get("id") == update_id:
            return u
    return None


def _append_audit(store: dict, action: str, update: dict, *,
                  actor: str | None = None,
                  requirement_id: str | None = None,
                  extra: dict | None = None) -> None:
    """Append one entry to the audit log.

    Mutates ``store`` in place; callers must :func:`save_updates_store`
    afterwards. Kept tiny on purpose — the audit log is append-only and
    the schema is intentionally permissive so we can grow new action
    types without breaking older entries.
    """
    entry = {
        "action": action,
        "update_id": update.get("id"),
        "framework": update.get("framework"),
        "title": update.get("title"),
        "requirement_id": requirement_id,
        "actor": actor,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        entry.update(extra)
    store.setdefault("audit_log", []).append(entry)


def apply_update(update_id: str, *, actor: str | None = None) -> dict:
    """Apply a pending update to regulatory_frameworks.json.

    If the update carries a `proposed_requirement`, append it under the
    matching framework's `requirements` list. Marks the update as applied
    with the timestamp. Idempotent — re-applying has no extra effect.

    Records an entry in ``store["audit_log"]`` so the action can be
    attributed and reverted later. ``actor`` is the signed-in username
    (when available) so the log answers "who approved this?".
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
    appended_requirement_id: str | None = None

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
            new_req = {
                "id": proposed.get("id"),
                "section": proposed.get("section"),
                "requirement": proposed.get("requirement"),
                "data_fields": proposed.get("data_fields") or [],
                "priority": proposed.get("priority") or "medium",
            }
            reqs.append(new_req)
            save_frameworks(frameworks)
            appended_requirement_id = new_req["id"]

    update["status"] = "applied"
    update["applied_at"] = datetime.now().isoformat(timespec="seconds")
    if actor:
        update["applied_by"] = actor
    # Record on the update itself so a later revert knows what to remove
    # even if the audit log gets truncated.
    if appended_requirement_id:
        update["applied_requirement_id"] = appended_requirement_id
    _append_audit(
        store, "apply", update,
        actor=actor,
        requirement_id=appended_requirement_id,
    )
    save_updates_store(store)
    return {"ok": True, "requirement_id": appended_requirement_id}


def revert_update(update_id: str, *, actor: str | None = None,
                  reason: str = "") -> dict:
    """Undo a previously-applied update.

    Removes the requirement that ``apply_update`` appended (matched on
    ``applied_requirement_id`` first, falling back to the
    ``proposed_requirement.id`` for entries written before the audit log
    landed) and flips the update's status back to ``pending`` so a human
    can re-decide. The original audit-log entry is preserved; a new
    ``revert`` entry is appended.

    Idempotent: reverting an already-reverted update is a no-op that
    still records the attempt in the audit log so the operator's intent
    is captured.
    """
    store = load_updates_store()
    update = _find_update(store, update_id)
    if update is None:
        return {"ok": False, "reason": f"No update with id {update_id}."}
    if update.get("status") != "applied":
        # Record the no-op so "I tried to revert this" is still visible.
        _append_audit(
            store, "revert_skipped", update, actor=actor,
            extra={"reason": reason or f"status was {update.get('status')!r}"},
        )
        save_updates_store(store)
        return {"ok": False, "already_reverted": True,
                "reason": f"Update status is {update.get('status')!r}; nothing to revert."}

    requirement_id = (
        update.get("applied_requirement_id")
        or (update.get("proposed_requirement") or {}).get("id")
    )

    frameworks = load_frameworks()
    fw_name = update.get("framework")
    removed = False
    if requirement_id and fw_name in frameworks.get("frameworks", {}):
        reqs = frameworks["frameworks"][fw_name].get("requirements") or []
        new_reqs = [r for r in reqs if r.get("id") != requirement_id]
        if len(new_reqs) != len(reqs):
            frameworks["frameworks"][fw_name]["requirements"] = new_reqs
            save_frameworks(frameworks)
            removed = True

    update["status"] = "pending"
    update["reverted_at"] = datetime.now().isoformat(timespec="seconds")
    if actor:
        update["reverted_by"] = actor
    if reason:
        update["revert_reason"] = reason
    # Drop the apply markers so a re-apply re-runs cleanly.
    update.pop("applied_at", None)
    update.pop("applied_by", None)
    update.pop("applied_requirement_id", None)
    _append_audit(
        store, "revert", update, actor=actor,
        requirement_id=requirement_id,
        extra={"reason": reason, "requirement_removed": removed},
    )
    save_updates_store(store)
    return {"ok": True, "requirement_id": requirement_id,
            "requirement_removed": removed}


def dismiss_update(update_id: str, reason: str = "",
                   *, actor: str | None = None) -> dict:
    store = load_updates_store()
    update = _find_update(store, update_id)
    if update is None:
        return {"ok": False, "reason": f"No update with id {update_id}."}
    update["status"] = "dismissed"
    update["dismissed_at"] = datetime.now().isoformat(timespec="seconds")
    if actor:
        update["dismissed_by"] = actor
    if reason:
        update["dismiss_reason"] = reason
    _append_audit(store, "dismiss", update, actor=actor,
                  extra={"reason": reason} if reason else None)
    save_updates_store(store)
    return {"ok": True}


def audit_log(store: dict | None = None,
              *, framework: str | None = None,
              limit: int | None = None) -> list[dict]:
    """Return audit-log entries, newest first.

    Filters by framework when supplied (case-sensitive — matches
    ``TRACKED_FRAMEWORKS``). ``limit`` truncates the head of the list.
    """
    s = store or load_updates_store()
    entries = list(s.get("audit_log") or [])
    if framework:
        entries = [e for e in entries if e.get("framework") == framework]
    entries.sort(key=lambda e: e.get("timestamp") or "", reverse=True)
    if limit is not None and limit >= 0:
        entries = entries[:limit]
    return entries


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
    "revert_update",
    "dismiss_update",
    "audit_log",
    "pending_updates",
    "applied_updates",
    "dismissed_updates",
    "time_since_last_check",
]

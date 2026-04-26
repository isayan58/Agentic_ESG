"""Persistent per-user pipeline-run snapshots.

The README flags session-scoped storage as the most-cited UX gap:
refreshing the browser drops all uploaded data and pipeline results.
``utils.profile_store`` and ``utils.source_store`` already solve the
*input* side (profile, configured sources). This module solves the
*output* side — full pipeline ``results`` dicts persisted per user so an
analyst can come back tomorrow, click *Load*, and see the exact run they
saved without re-fetching every connector.

Design mirrors the sibling stores deliberately:
    * same backend resolver — HF Dataset when ``HF_TOKEN`` is set,
      local JSON under ``data/runs/`` otherwise (ephemeral on Spaces);
    * same module-level singleton + per-store lock + TTL cache;
    * structured ``diagnostic()`` for the sidebar indicator.

Storage layout::

    runs/{username}/index.json           # ordered list of run summaries
    runs/{username}/{run_id}.json        # full snapshot (one file per run)

Why one file per run rather than one giant array?
    1. Listing the saved runs (a hot path on Mission Control) doesn't
       need to download every snapshot.
    2. Deleting one run doesn't require rewriting the whole history.
    3. Snapshots can be large (the ROI agent alone produces a few KB
       of nested dicts × 9 agents) — keeping them isolated avoids
       blowing the source-payload cap that ``utils.source_store``
       guards against.

Serialisation
-------------
Pipeline results are dicts of dicts/lists/scalars built by the agents.
We use ``json.dumps(default=str)`` so any stray non-serialisable value
(e.g. a Timestamp) becomes a string instead of crashing the save. This
is lossy for DataFrames if any agent ever returns one inline, but the
current agents only return aggregated scalars/dicts, so the round-trip
is exact in practice.
"""
from __future__ import annotations

import io
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_log = logging.getLogger(__name__)

try:
    from huggingface_hub import HfApi, hf_hub_download
    from huggingface_hub.utils import (
        EntryNotFoundError,
        HfHubHTTPError,
        RepositoryNotFoundError,
    )

    _HAS_HF = True
except Exception:  # pragma: no cover
    HfApi = None  # type: ignore
    hf_hub_download = None  # type: ignore
    _HAS_HF = False


DEFAULT_DATASET = os.getenv("ESG_AUTH_DATASET", "isayan58/esg-copilot-auth")
RUNS_DIR_IN_REPO = "runs"
LOCAL_FALLBACK_DIR = Path("data") / "runs"
CACHE_TTL_SECONDS = 30
MAX_RETRIES = 3

# Bound the list to keep the index file small and the UI tractable.
# Older snapshots are discarded oldest-first as new ones land.
DEFAULT_HISTORY_CAP = 25

# Hard cap on a single snapshot's serialised size. Same headroom logic
# as source_store: 4 MB is plenty for nine agents of aggregate output
# while staying under HF rate-limit-friendly thresholds.
MAX_SNAPSHOT_BYTES = int(os.getenv("ESG_RUN_MAX_BYTES", str(4 * 1024 * 1024)))


def _resolve_token() -> Optional[str]:
    """Same token lookup as the sibling stores."""
    for name in ("HF_TOKEN", "HF_API_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(name)
        if value:
            return value.strip()
    candidate = Path.home() / ".cache" / "huggingface" / "token"
    if candidate.is_file():
        try:
            text = candidate.read_text().strip()
            if text:
                return text
        except OSError:  # pragma: no cover
            pass
    return None


def _safe_username(username: str) -> str:
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9_.\-]", "_", (username or "").strip())
    return cleaned[:64] or "anonymous"


def _new_run_id() -> str:
    """Sortable run id: ``YYYYMMDDTHHMMSS-<rand4>``.

    The timestamp prefix means lexical order matches chronological order
    in any list view, even before the index file loads.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:4]}"


def _summarize(run: dict) -> dict:
    """Pull a small, UI-friendly summary out of a full run snapshot.

    Stored in the index file so listing saved runs doesn't require
    downloading each snapshot. Defensive against missing keys — we want
    listing to keep working even if an agent's schema drifted between
    save and load.
    """
    results = run.get("results") or {}
    data_res = results.get("data_collector") or {}
    audit_res = results.get("audit_agent") or {}
    roi_res = results.get("roi_agent") or {}
    carbon_res = results.get("carbon_accountant") or {}

    return {
        "id": run.get("id"),
        "label": run.get("label") or "Untitled run",
        "saved_at": run.get("saved_at"),
        "saved_by": run.get("saved_by"),
        "goal": run.get("goal"),
        "agent_count": sum(1 for v in results.values() if isinstance(v, dict) and "error" not in v),
        "errored_agents": [k for k, v in results.items()
                           if isinstance(v, dict) and "error" in v],
        "headline": {
            "total_records": data_res.get("total_records") if isinstance(data_res, dict) else None,
            "audit_grade": ((audit_res.get("readiness_score") or {}).get("grade")
                            if isinstance(audit_res, dict) else None),
            "iqs_grade": ((roi_res.get("investment_quality_score") or {}).get("grade")
                          if isinstance(roi_res, dict) else None),
            "emissions_total": (carbon_res.get("total_emissions_current")
                                if isinstance(carbon_res, dict) else None),
        },
    }


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
class RunStore:
    """Per-user pipeline-run registry persisted to HF Dataset (or local)."""

    def __init__(self, dataset_repo: str = DEFAULT_DATASET,
                 history_cap: int = DEFAULT_HISTORY_CAP):
        self._dataset = dataset_repo
        self._token = _resolve_token()
        self._api = HfApi(token=self._token) if (_HAS_HF and self._token) else None
        self._lock = threading.RLock()
        self._history_cap = max(1, int(history_cap))
        # username -> (index_records, loaded_at)
        self._index_cache: dict[str, tuple[list[dict], float]] = {}
        self._resolved_backend: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[str] = None

    # -- Public API --------------------------------------------------------
    @property
    def has_token(self) -> bool:
        return bool(self._token)

    def backend_label(self) -> str:
        if self._resolved_backend == "hf_dataset":
            return f"HuggingFace Dataset ({self._dataset}:{RUNS_DIR_IN_REPO}/)"
        if self._resolved_backend == "local_json":
            return f"Local JSON ({LOCAL_FALLBACK_DIR}) — ephemeral"
        return "Unresolved — will pick backend on first read"

    def diagnostic(self) -> dict:
        return {
            "backend": self._resolved_backend,
            "label": self.backend_label(),
            "has_token": bool(self._token),
            "dataset": self._dataset,
            "last_error": self._last_error,
            "last_error_at": self._last_error_at,
        }

    def save_run(self, username: str, *, results: dict,
                 label: str | None = None,
                 goal: str | None = None,
                 saved_by: str | None = None) -> str:
        """Persist a pipeline-run snapshot. Returns the run id.

        Trims the index to ``history_cap`` newest entries, deleting the
        underlying snapshot files for any rotated-out runs so the
        backend doesn't accumulate orphans.

        Raises ``ValueError`` if the serialised snapshot exceeds
        :data:`MAX_SNAPSHOT_BYTES` — the caller should surface a
        "your run is too big to save" message rather than truncating
        silently.
        """
        username = _safe_username(username)
        run_id = _new_run_id()
        snapshot = {
            "id": run_id,
            "label": (label or "Untitled run").strip()[:120] or "Untitled run",
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "saved_by": saved_by or username,
            "goal": (goal or "")[:240],
            "results": results or {},
        }

        try:
            payload = json.dumps(
                snapshot, ensure_ascii=False, default=str
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Run snapshot is not JSON-serialisable: {exc}") from exc
        if len(payload) > MAX_SNAPSHOT_BYTES:
            raise ValueError(
                f"Run snapshot is {len(payload):,} bytes "
                f"(cap {MAX_SNAPSHOT_BYTES:,}). Trim agent outputs or raise "
                "ESG_RUN_MAX_BYTES if this is genuinely needed."
            )

        with self._lock:
            self._save_snapshot_raw(username, run_id, payload)
            index = self._load_index_raw(username)
            index.insert(0, _summarize(snapshot))
            # Cap-and-prune. Each rotated-out run takes its snapshot
            # file with it so the backend doesn't accumulate ghosts.
            if len(index) > self._history_cap:
                for stale in index[self._history_cap:]:
                    stale_id = stale.get("id")
                    if stale_id:
                        try:
                            self._delete_snapshot_raw(username, stale_id)
                        except Exception:  # noqa: BLE001 — best-effort cleanup
                            pass
                index = index[:self._history_cap]
            self._save_index_raw(username, index)
            self._index_cache[username] = (list(index), time.time())
        return run_id

    def list_runs(self, username: str) -> list[dict]:
        """Return summaries (newest first). Empty list if none."""
        username = _safe_username(username)
        with self._lock:
            cached = self._index_cache.get(username)
            if cached and (time.time() - cached[1]) < CACHE_TTL_SECONDS:
                return [dict(r) for r in cached[0]]
            index = self._load_index_raw(username)
            self._index_cache[username] = (list(index), time.time())
            return [dict(r) for r in index]

    def load_run(self, username: str, run_id: str) -> dict | None:
        """Return the full snapshot for ``run_id``, or ``None`` if absent."""
        username = _safe_username(username)
        with self._lock:
            return self._load_snapshot_raw(username, run_id)

    def delete_run(self, username: str, run_id: str) -> bool:
        """Drop a single saved run. Returns True if it existed."""
        username = _safe_username(username)
        with self._lock:
            removed = self._delete_snapshot_raw(username, run_id)
            index = self._load_index_raw(username)
            new_index = [r for r in index if r.get("id") != run_id]
            if len(new_index) != len(index):
                self._save_index_raw(username, new_index)
                self._index_cache[username] = (list(new_index), time.time())
                removed = True
            return removed

    def clear_cache(self, username: Optional[str] = None) -> None:
        with self._lock:
            if username is None:
                self._index_cache.clear()
            else:
                self._index_cache.pop(_safe_username(username), None)

    # -- Backend internals --------------------------------------------------
    def _index_path_in_repo(self, username: str) -> str:
        return f"{RUNS_DIR_IN_REPO}/{username}/index.json"

    def _snapshot_path_in_repo(self, username: str, run_id: str) -> str:
        return f"{RUNS_DIR_IN_REPO}/{username}/{run_id}.json"

    def _local_index_path(self, username: str) -> Path:
        return LOCAL_FALLBACK_DIR / username / "index.json"

    def _local_snapshot_path(self, username: str, run_id: str) -> Path:
        return LOCAL_FALLBACK_DIR / username / f"{run_id}.json"

    # ---- Index ----
    def _load_index_raw(self, username: str) -> list[dict]:
        if self._api is not None:
            try:
                index = self._download_index_from_hf(username)
                self._resolved_backend = "hf_dataset"
                self._last_error = None
                self._last_error_at = None
                return index
            except Exception as exc:  # noqa: BLE001
                self._record_error(exc)
        index = self._download_index_from_local(username)
        self._resolved_backend = "local_json"
        return index

    def _save_index_raw(self, username: str, index: list[dict]) -> None:
        payload = json.dumps(index, indent=2, ensure_ascii=False,
                             default=str).encode("utf-8")
        if self._api is not None and self._resolved_backend in (None, "hf_dataset"):
            try:
                self._upload_to_hf(self._index_path_in_repo(username), payload,
                                   commit_message=f"Update run index for {username}")
                self._resolved_backend = "hf_dataset"
                self._last_error = None
                self._last_error_at = None
                return
            except Exception as exc:  # noqa: BLE001
                self._record_error(exc)
        self._write_local(self._local_index_path(username), payload)
        self._resolved_backend = "local_json"

    # ---- Snapshot ----
    def _load_snapshot_raw(self, username: str, run_id: str) -> dict | None:
        if self._api is not None:
            try:
                return self._download_snapshot_from_hf(username, run_id)
            except Exception as exc:  # noqa: BLE001
                self._record_error(exc)
        return self._download_snapshot_from_local(username, run_id)

    def _save_snapshot_raw(self, username: str, run_id: str, payload: bytes) -> None:
        if self._api is not None and self._resolved_backend in (None, "hf_dataset"):
            last_exc: BaseException | None = None
            for attempt in range(MAX_RETRIES):
                try:
                    self._upload_to_hf(
                        self._snapshot_path_in_repo(username, run_id), payload,
                        commit_message=f"Save run {run_id} for {username}",
                    )
                    self._resolved_backend = "hf_dataset"
                    self._last_error = None
                    self._last_error_at = None
                    return
                except HfHubHTTPError as exc:
                    last_exc = exc
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status not in (409, 412, 503):
                        break
                    time.sleep(0.25 * (2 ** attempt))
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    break
            if last_exc is not None:
                self._record_error(last_exc)
        self._write_local(self._local_snapshot_path(username, run_id), payload)
        self._resolved_backend = "local_json"

    def _delete_snapshot_raw(self, username: str, run_id: str) -> bool:
        # Delete from HF (best-effort) and from local fallback. We
        # don't fail the operation if HF deletion errors — the index
        # entry has already been pruned, so the file is just an orphan.
        deleted = False
        if self._api is not None:
            try:
                self._api.delete_file(
                    path_in_repo=self._snapshot_path_in_repo(username, run_id),
                    repo_id=self._dataset,
                    repo_type="dataset",
                    commit_message=f"Delete run {run_id} for {username}",
                )
                deleted = True
            except Exception as exc:  # noqa: BLE001
                self._record_error(exc)
        local_path = self._local_snapshot_path(username, run_id)
        if local_path.is_file():
            try:
                local_path.unlink()
                deleted = True
            except OSError as exc:
                self._record_error(exc)
        return deleted

    # ---- HF helpers ----
    def _download_index_from_hf(self, username: str) -> list[dict]:
        assert self._api is not None
        try:
            local_path = hf_hub_download(
                repo_id=self._dataset,
                repo_type="dataset",
                filename=self._index_path_in_repo(username),
                token=self._token,
            )
        except (EntryNotFoundError, RepositoryNotFoundError, HfHubHTTPError, ValueError):
            # First-time-per-user reads land here. Make sure the dataset
            # exists so later writes don't trip on a missing repo.
            try:
                self._ensure_dataset_exists()
            except Exception:  # noqa: BLE001
                pass
            return []
        with open(local_path, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError:
                return []
        return data if isinstance(data, list) else []

    def _download_snapshot_from_hf(self, username: str, run_id: str) -> dict | None:
        assert self._api is not None
        try:
            local_path = hf_hub_download(
                repo_id=self._dataset,
                repo_type="dataset",
                filename=self._snapshot_path_in_repo(username, run_id),
                token=self._token,
            )
        except (EntryNotFoundError, RepositoryNotFoundError, HfHubHTTPError, ValueError):
            return None
        with open(local_path, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except json.JSONDecodeError:
                return None
        return data if isinstance(data, dict) else None

    def _upload_to_hf(self, path_in_repo: str, payload: bytes,
                      commit_message: str) -> None:
        assert self._api is not None
        self._ensure_dataset_exists()
        self._api.upload_file(
            path_or_fileobj=io.BytesIO(payload),
            path_in_repo=path_in_repo,
            repo_id=self._dataset,
            repo_type="dataset",
            commit_message=commit_message,
        )

    def _ensure_dataset_exists(self) -> None:
        assert self._api is not None
        self._api.create_repo(
            repo_id=self._dataset,
            repo_type="dataset",
            private=True,
            exist_ok=True,
        )

    # ---- Local helpers ----
    def _download_index_from_local(self, username: str) -> list[dict]:
        path = self._local_index_path(username)
        if not path.is_file():
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _download_snapshot_from_local(self, username: str, run_id: str) -> dict | None:
        path = self._local_snapshot_path(username, run_id)
        if not path.is_file():
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _write_local(self, path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(payload)

    # ---- Error capture ----
    def _record_error(self, exc: BaseException) -> None:
        chain = []
        cur: BaseException | None = exc
        seen: set[int] = set()
        while cur is not None and id(cur) not in seen:
            chain.append(f"{type(cur).__name__}: {cur}")
            seen.add(id(cur))
            cur = cur.__cause__ or cur.__context__
        self._last_error = " ← ".join(chain)
        self._last_error_at = (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_STORE: Optional[RunStore] = None


def get_run_store() -> RunStore:
    global _STORE
    if _STORE is None:
        _STORE = RunStore()
    return _STORE


__all__ = [
    "DEFAULT_HISTORY_CAP",
    "MAX_SNAPSHOT_BYTES",
    "RunStore",
    "get_run_store",
]

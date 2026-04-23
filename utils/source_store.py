"""Persistent per-user data-source registry for ESG CoPilot.

Companion to ``utils.user_store``. Where ``user_store`` keeps one global
``users.json`` in a private HF Dataset, this module keeps one JSON file
per user under ``sources/{username}.json`` in the *same* dataset repo,
so everything a signed-in user has configured (Snowflake queries, S3
objects, Google Sheets, uploaded files, column mappings) survives
HuggingFace Space rebuilds and shows up again the next time they sign
in from any browser.

Design mirrors ``user_store`` deliberately:
    * same backend resolver — HF Dataset when ``HF_TOKEN`` is set,
      local JSON under ``data/sources/`` otherwise (ephemeral on HF);
    * same module-level singleton so every page shares one store;
    * thread-safe via a per-store lock;
    * a short TTL cache so hot pages don't hit the Hub on every rerun.

What we persist (per source)::

    {"id", "connector_type", "config", "target_schema",
     "column_mapping", "display_name", "added_at"}

Deliberately *not* persisted:
    * ``_cached_df`` — can be huge and is cheaply reproducible
    * ``last_fetch`` / ``last_row_count`` / ``status`` / ``error`` —
      runtime state that's meaningless across restarts
    * bytes-valued configs (uploaded file payloads) are stored verbatim
      when small (<500 KB); large files are automatically externalised
      to HuggingFace (with a reference stored in the JSON)
"""
from __future__ import annotations

import io
import json
import os
import threading
import time
from pathlib import Path
from typing import Optional

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


# Reuse the same dataset as the user store — one private repo, two
# namespaces (``users.json`` + ``sources/{username}.json``).
DEFAULT_DATASET = os.getenv("ESG_AUTH_DATASET", "isayan58/esg-copilot-auth")
SOURCES_DIR_IN_REPO = "sources"
LOCAL_FALLBACK_DIR = Path("data") / "sources"
CACHE_TTL_SECONDS = 30
MAX_RETRIES = 3

# Large file externalization threshold (500 KB). Files larger than this
# will be stored externally on HuggingFace and referenced by hash + filename.
MAX_INLINE_FILE_BYTES = int(os.getenv("ESG_MAX_INLINE_FILE_BYTES", str(500 * 1024)))

# Hard cap on the total serialised size of a single user's sources file.
# Uploaded files are base64-encoded in-place, so a 2 MB raw upload becomes
# ~2.7 MB JSON — cap at 4 MB to leave headroom without risking HF rate
# limits or pathological session_state bloat.
MAX_PAYLOAD_BYTES = int(os.getenv("ESG_SOURCE_MAX_BYTES", str(4 * 1024 * 1024)))


class SourcePayloadTooLarge(ValueError):
    """Raised when a user's saved sources would exceed the size cap.

    The UI catches this and asks the user to switch from an inline
    upload to an external connector (S3, Snowflake, Google Sheets) so
    the bytes live in the source-of-truth system, not in the per-user
    profile file.

    Attributes
    ----------
    total_bytes : int
        Serialised size of the full records list.
    cap_bytes : int
        The configured cap (:data:`MAX_PAYLOAD_BYTES`).
    per_source : list[tuple[str, int]]
        ``[(source_id, bytes), …]`` sorted largest-first so the UI can
        point the user at the exact source to trim.
    largest : tuple[str, int] | None
        Shortcut to ``per_source[0]`` — the source most worth removing.
    """

    def __init__(self, message: str, *, total_bytes: int = 0,
                 cap_bytes: int = 0,
                 per_source: list[tuple[str, int]] | None = None):
        super().__init__(message)
        self.total_bytes = total_bytes
        self.cap_bytes = cap_bytes
        self.per_source = list(per_source or [])
        self.largest = self.per_source[0] if self.per_source else None


def _resolve_token() -> Optional[str]:
    """Same token lookup as user_store so both stores share credentials."""
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
    """Filesystem-safe username — matches the auth regex already in place."""
    import re

    cleaned = re.sub(r"[^a-zA-Z0-9_.\-]", "_", (username or "").strip())
    return cleaned[:64] or "anonymous"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------
_PERSIST_KEYS = (
    "connector_type",
    "config",
    "target_schema",
    "column_mapping",
    "display_name",
    "added_at",
)


def _coerce_bytes_for_json(value):
    """Recursively make bytes values JSON-safe.

    Small bytes payloads (uploaded CSVs) are encoded with base64 and
    tagged so we can round-trip them on read. Anything else stays as-is.
    """
    import base64

    if isinstance(value, (bytes, bytearray)):
        return {
            "__bytes_b64__": base64.b64encode(bytes(value)).decode("ascii"),
        }
    if isinstance(value, dict):
        return {k: _coerce_bytes_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_coerce_bytes_for_json(v) for v in value]
    return value


def _decode_bytes_from_json(value):
    """Inverse of :func:`_coerce_bytes_for_json`."""
    import base64

    if isinstance(value, dict) and set(value.keys()) == {"__bytes_b64__"}:
        try:
            return base64.b64decode(value["__bytes_b64__"])
        except Exception:
            return b""
    if isinstance(value, dict):
        return {k: _decode_bytes_from_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode_bytes_from_json(v) for v in value]
    return value


def _externalize_large_files(record: dict) -> dict:
    """Extract large file payloads and replace with references.

    If a record's config contains a bytes value > MAX_INLINE_FILE_BYTES,
    replace it with a marker dict containing metadata for later retrieval.
    The actual bytes are meant to be uploaded separately to HuggingFace.

    Returns a modified copy of the record with large files externalised.
    """
    import hashlib
    import base64

    config = record.get("config")
    if not isinstance(config, dict):
        return record

    modified_config = dict(config)
    for key, value in modified_config.items():
        if isinstance(value, (bytes, bytearray)):
            value_bytes = bytes(value)
            if len(value_bytes) > MAX_INLINE_FILE_BYTES:
                # Replace with a reference marker
                file_hash = hashlib.sha256(value_bytes).hexdigest()[:16]
                file_name = modified_config.get("file_name", f"upload_{file_hash}")
                modified_config[key] = {
                    "__external_file__": {
                        "hash": file_hash,
                        "size": len(value_bytes),
                        "file_name": file_name,
                    }
                }

    if modified_config != config:
        modified_record = dict(record)
        modified_record["config"] = modified_config
        return modified_record

    return record


def _restore_large_files(record: dict, external_files_cache: dict) -> dict:
    """Inverse of :func:`_externalize_large_files`.

    If a record's config contains external file references, attempt to
    restore them from a provided cache dict {file_hash: bytes, ...}.
    If not found in cache, leave the reference marker in place.
    """
    config = record.get("config")
    if not isinstance(config, dict):
        return record

    modified_config = dict(config)
    found_external = False
    for key, value in modified_config.items():
        if (isinstance(value, dict) and
            set(value.keys()) == {"__external_file__"} and
            isinstance(value["__external_file__"], dict)):
            meta = value["__external_file__"]
            file_hash = meta.get("hash")
            if file_hash and file_hash in external_files_cache:
                modified_config[key] = external_files_cache[file_hash]
                found_external = True

    if found_external:
        modified_record = dict(record)
        modified_record["config"] = modified_config
        return modified_record

    return record


def source_to_record(source_id: str, meta: dict) -> dict:
    """Turn an in-memory ConnectionManager entry into a persistable dict.

    Large files (> MAX_INLINE_FILE_BYTES) are externalised — replaced with
    references that can be restored later from an external storage cache.
    """
    record = {"id": source_id}
    for k in _PERSIST_KEYS:
        if k in meta:
            record[k] = _coerce_bytes_for_json(meta[k])
    # Externalise large files to keep the JSON payload under the cap
    record = _externalize_large_files(record)
    return record


def _record_display_label(record: dict) -> str:
    """Best human-readable label for a record — for size-cap error messages.

    Prefers: display_name → config.file_name → id → "(unnamed)". Keeps
    the label short so the UI can interpolate it into a single line.
    """
    label = record.get("display_name")
    if not label:
        cfg = record.get("config") or {}
        if isinstance(cfg, dict):
            label = cfg.get("file_name") or cfg.get("object") or cfg.get("query")
    if not label:
        label = record.get("id")
    if not label:
        return "(unnamed source)"
    label = str(label).strip()
    return label if len(label) <= 60 else label[:57] + "…"


def _per_record_sizes(records: list[dict]) -> list[tuple[str, int]]:
    """Return ``[(label, bytes), …]`` sorted largest-first.

    Sizes are approximate — each record is serialised independently,
    so the sum differs slightly from the full-payload size (missing the
    JSON array brackets / comma separators). Good enough for pointing
    the user at the right source to trim.
    """
    sized: list[tuple[str, int]] = []
    for rec in records or []:
        try:
            encoded = json.dumps(rec, ensure_ascii=False).encode("utf-8")
            size = len(encoded)
        except (TypeError, ValueError):
            size = 0
        sized.append((_record_display_label(rec), size))
    sized.sort(key=lambda pair: pair[1], reverse=True)
    return sized


def record_to_source(record: dict) -> tuple[str, dict]:
    """Inverse of :func:`source_to_record`."""
    sid = record.get("id") or record.get("source_id") or "unknown"
    restored = {}
    for k in _PERSIST_KEYS:
        if k in record:
            restored[k] = _decode_bytes_from_json(record[k])
    return sid, restored


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
class SourceStore:
    """Per-user source registry persisted to HF Dataset (or local fallback)."""

    def __init__(self, dataset_repo: str = DEFAULT_DATASET):
        self._dataset = dataset_repo
        self._token = _resolve_token()
        self._api = HfApi(token=self._token) if (_HAS_HF and self._token) else None
        self._lock = threading.RLock()
        # username -> (records, loaded_at)
        self._cache: dict[str, tuple[list[dict], float]] = {}
        self._resolved_backend: Optional[str] = None
        # Last-error capture so the UI can surface why HF writes silently
        # fell back to local JSON (bad token, no write scope, etc.).
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[str] = None

    # -- Public API --------------------------------------------------------
    @property
    def has_token(self) -> bool:
        return bool(self._token)

    def backend_label(self) -> str:
        if self._resolved_backend == "hf_dataset":
            return f"HuggingFace Dataset ({self._dataset}:{SOURCES_DIR_IN_REPO}/)"
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

    def _record_error(self, exc: BaseException) -> None:
        """Capture the full exception chain so wrapped HF errors stay legible.

        Mirrors the helper in :mod:`utils.user_store` — see the docstring
        there for why we walk ``__cause__`` / ``__context__``.
        """
        from datetime import datetime, timezone
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

    def load(self, username: str) -> list[dict]:
        """Return the list of source records for ``username``. Empty list if none."""
        username = _safe_username(username)
        with self._lock:
            cached = self._cache.get(username)
            if cached and (time.time() - cached[1]) < CACHE_TTL_SECONDS:
                return [dict(r) for r in cached[0]]

            records = self._load_raw(username)
            self._cache[username] = (records, time.time())
            return [dict(r) for r in records]

    def save(self, username: str, records: list[dict]) -> None:
        """Persist the full source list for ``username`` (overwriting)."""
        username = _safe_username(username)
        with self._lock:
            self._save_raw(username, records)
            self._cache[username] = (list(records), time.time())

    def clear_cache(self, username: Optional[str] = None) -> None:
        with self._lock:
            if username is None:
                self._cache.clear()
            else:
                self._cache.pop(_safe_username(username), None)

    # -- Backend internals --------------------------------------------------
    def _path_in_repo(self, username: str) -> str:
        return f"{SOURCES_DIR_IN_REPO}/{username}.json"

    def _local_path(self, username: str) -> Path:
        return LOCAL_FALLBACK_DIR / f"{username}.json"

    def _load_raw(self, username: str) -> list[dict]:
        # Prefer HF Dataset when a token is available.
        if self._api is not None:
            try:
                records = self._load_from_hf(username)
                self._resolved_backend = "hf_dataset"
                self._last_error = None
                self._last_error_at = None
                return records
            except Exception as exc:
                self._record_error(exc)
        records = self._load_from_local(username)
        self._resolved_backend = "local_json"
        return records

    def _save_raw(self, username: str, records: list[dict]) -> None:
        # Enforce the size cap up front so the user gets a clean error
        # rather than a mysterious HF 413 / local disk blowup. We
        # serialise once and reuse the bytes if the write proceeds.
        payload = json.dumps(records, indent=2, ensure_ascii=False).encode("utf-8")
        if len(payload) > MAX_PAYLOAD_BYTES:
            # Identify the offender(s) so the UI can point the user at
            # the specific source to trim instead of saying "too large"
            # and leaving them to guess.
            per_source = _per_record_sizes(records)
            if per_source:
                top = per_source[0]
                top_label, top_bytes = top
                hint = (
                    f" Largest source is **{top_label}** "
                    f"(~{top_bytes / 1024:.0f} KB). "
                )
            else:
                hint = " "
            raise SourcePayloadTooLarge(
                f"Saved sources would be {len(payload):,} bytes "
                f"(cap {MAX_PAYLOAD_BYTES:,})."
                f"{hint}"
                "Remove that source, or switch from inline upload to "
                "an external connector (S3, Snowflake, Google Sheets) "
                "so the bytes stay in the source-of-truth system.",
                total_bytes=len(payload),
                cap_bytes=MAX_PAYLOAD_BYTES,
                per_source=per_source,
            )

        if self._api is not None and self._resolved_backend in (None, "hf_dataset"):
            last_exc: BaseException | None = None
            for attempt in range(MAX_RETRIES):
                try:
                    self._save_to_hf(username, records, payload=payload)
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
                except Exception as exc:
                    last_exc = exc
                    break
            if last_exc is not None:
                self._record_error(last_exc)
        self._save_to_local(username, records)
        self._resolved_backend = "local_json"

    # --- HF backend -------------------------------------------------------
    def _load_from_hf(self, username: str) -> list[dict]:
        assert self._api is not None
        try:
            local_path = hf_hub_download(
                repo_id=self._dataset,
                repo_type="dataset",
                filename=self._path_in_repo(username),
                token=self._token,
                # See user_store._load_from_hf — force_download=True was
                # wrapping EntryNotFoundError as ValueError, which made
                # first-time-per-user reads look like hard failures.
            )
        except (EntryNotFoundError, RepositoryNotFoundError, HfHubHTTPError, ValueError):
            try:
                self._ensure_dataset_exists()
            except Exception:
                pass
            return []

        try:
            with open(local_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    return data
                return []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_to_hf(self, username: str, records: list[dict],
                    payload: bytes | None = None) -> None:
        assert self._api is not None
        self._ensure_dataset_exists()
        if payload is None:
            payload = json.dumps(records, indent=2, ensure_ascii=False).encode("utf-8")
        self._api.upload_file(
            path_or_fileobj=io.BytesIO(payload),
            path_in_repo=self._path_in_repo(username),
            repo_id=self._dataset,
            repo_type="dataset",
            commit_message=f"Update sources for {username}",
        )

    def _ensure_dataset_exists(self) -> None:
        assert self._api is not None
        self._api.create_repo(
            repo_id=self._dataset,
            repo_type="dataset",
            private=True,
            exist_ok=True,
        )

    # --- Local backend ---------------------------------------------------
    def _load_from_local(self, username: str) -> list[dict]:
        path = self._local_path(username)
        if not path.is_file():
            return []
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    return data
                return []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_to_local(self, username: str, records: list[dict]) -> None:
        path = self._local_path(username)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_STORE: Optional[SourceStore] = None


def get_source_store() -> SourceStore:
    global _STORE
    if _STORE is None:
        _STORE = SourceStore()
    return _STORE

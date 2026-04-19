"""Persistent per-user company-profile registry.

Sibling to :mod:`utils.user_store` and :mod:`utils.source_store`. Stores
one JSON file per signed-in user under ``profiles/{username}.json`` in the
same private HF Dataset repo, so each user gets their *own* company
profile (name, sector, financials, ESG posture, tunable thresholds,
material topics, etc.) — independent of every other user on the same
deployment.

Design mirrors the other stores:
    * same backend resolver (HF Dataset when token present, local JSON
      under ``data/profiles/`` otherwise — ephemeral on Spaces);
    * same module-level singleton + per-store lock + TTL cache;
    * structured ``diagnostic()`` for the sidebar indicator;
    * concurrency-safe writes via read-modify-write retries (per-user
      files only collide if the same user has two tabs racing).

The schema is whatever ``data/company_profile.json`` defines — we treat
it as opaque JSON so `core.company_config.CompanyConfig` can keep owning
the field-by-field interpretation.
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


DEFAULT_DATASET = os.getenv("ESG_AUTH_DATASET", "isayan58/esg-copilot-auth")
PROFILES_DIR_IN_REPO = "profiles"
LOCAL_FALLBACK_DIR = Path("data") / "profiles"
DEFAULT_PROFILE_PATH = Path("data") / "company_profile.json"
CACHE_TTL_SECONDS = 30
MAX_RETRIES = 3


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


def _load_default_profile() -> dict:
    """Return the bundled default profile (used when a user has none yet)."""
    try:
        if DEFAULT_PROFILE_PATH.is_file():
            with open(DEFAULT_PROFILE_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
class ProfileStore:
    """Per-user company profile registry persisted to HF Dataset (or local)."""

    def __init__(self, dataset_repo: str = DEFAULT_DATASET):
        self._dataset = dataset_repo
        self._token = _resolve_token()
        self._api = HfApi(token=self._token) if (_HAS_HF and self._token) else None
        self._lock = threading.RLock()
        # username -> (profile_dict, loaded_at)
        self._cache: dict[str, tuple[dict, float]] = {}
        self._resolved_backend: Optional[str] = None
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[str] = None
        self._default_profile = _load_default_profile()

    # -- Public API --------------------------------------------------------
    @property
    def has_token(self) -> bool:
        return bool(self._token)

    def backend_label(self) -> str:
        if self._resolved_backend == "hf_dataset":
            return f"HuggingFace Dataset ({self._dataset}:{PROFILES_DIR_IN_REPO}/)"
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

    def default_profile(self) -> dict:
        """Return a fresh copy of the bundled default profile."""
        return json.loads(json.dumps(self._default_profile))

    def _record_error(self, exc: BaseException) -> None:
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

    def load(self, username: str) -> dict:
        """Return the profile dict for ``username``.

        If the user has no saved profile, a *copy* of the bundled default
        profile is returned so the caller can mutate it freely.
        """
        username = _safe_username(username)
        with self._lock:
            cached = self._cache.get(username)
            if cached and (time.time() - cached[1]) < CACHE_TTL_SECONDS:
                return json.loads(json.dumps(cached[0]))

            profile = self._load_raw(username)
            if not profile:
                profile = self.default_profile()
            self._cache[username] = (profile, time.time())
            return json.loads(json.dumps(profile))

    def save(self, username: str, profile: dict) -> None:
        """Persist ``profile`` for ``username``.

        Concurrency: per-user JSON files only collide when the same user
        has two tabs racing. We retry on HF write errors but make no
        attempt at multi-writer merge — last-write-wins by design.
        """
        username = _safe_username(username)
        with self._lock:
            self._save_raw(username, profile)
            # Refresh cache with what we just wrote (TTL window resets).
            self._cache[username] = (json.loads(json.dumps(profile)), time.time())

    def clear_cache(self, username: Optional[str] = None) -> None:
        with self._lock:
            if username is None:
                self._cache.clear()
            else:
                self._cache.pop(_safe_username(username), None)

    # -- Backend internals --------------------------------------------------
    def _path_in_repo(self, username: str) -> str:
        return f"{PROFILES_DIR_IN_REPO}/{username}.json"

    def _local_path(self, username: str) -> Path:
        return LOCAL_FALLBACK_DIR / f"{username}.json"

    def _load_raw(self, username: str) -> dict:
        if self._api is not None:
            try:
                profile = self._load_from_hf(username)
                self._resolved_backend = "hf_dataset"
                self._last_error = None
                self._last_error_at = None
                return profile
            except Exception as exc:
                self._record_error(exc)
        profile = self._load_from_local(username)
        self._resolved_backend = "local_json"
        return profile

    def _save_raw(self, username: str, profile: dict) -> None:
        if self._api is not None and self._resolved_backend in (None, "hf_dataset"):
            last_exc: BaseException | None = None
            for attempt in range(MAX_RETRIES):
                try:
                    self._save_to_hf(username, profile)
                    self._resolved_backend = "hf_dataset"
                    self._last_error = None
                    self._last_error_at = None
                    return
                except HfHubHTTPError as exc:
                    last_exc = exc
                    # 409 = commit conflict (concurrent write). Brief
                    # backoff then retry; everything else fails fast.
                    status = getattr(getattr(exc, "response", None), "status_code", None)
                    if status not in (409, 412, 503):
                        break
                    time.sleep(0.25 * (2 ** attempt))
                except Exception as exc:
                    last_exc = exc
                    break
            if last_exc is not None:
                self._record_error(last_exc)
        self._save_to_local(username, profile)
        self._resolved_backend = "local_json"

    # --- HF backend -------------------------------------------------------
    def _load_from_hf(self, username: str) -> dict:
        assert self._api is not None
        try:
            local_path = hf_hub_download(
                repo_id=self._dataset,
                repo_type="dataset",
                filename=self._path_in_repo(username),
                token=self._token,
            )
        except (EntryNotFoundError, RepositoryNotFoundError, HfHubHTTPError, ValueError):
            try:
                self._ensure_dataset_exists()
            except Exception:
                pass
            return {}

        try:
            with open(local_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
                return {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_to_hf(self, username: str, profile: dict) -> None:
        assert self._api is not None
        self._ensure_dataset_exists()
        payload = json.dumps(profile, indent=2, ensure_ascii=False).encode("utf-8")
        self._api.upload_file(
            path_or_fileobj=io.BytesIO(payload),
            path_in_repo=self._path_in_repo(username),
            repo_id=self._dataset,
            repo_type="dataset",
            commit_message=f"Update profile for {username}",
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
    def _load_from_local(self, username: str) -> dict:
        path = self._local_path(username)
        if not path.is_file():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, dict):
                    return data
                return {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_to_local(self, username: str, profile: dict) -> None:
        path = self._local_path(username)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(profile, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_STORE: Optional[ProfileStore] = None


def get_profile_store() -> ProfileStore:
    global _STORE
    if _STORE is None:
        _STORE = ProfileStore()
    return _STORE

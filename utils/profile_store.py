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

import hashlib
import io
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

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
PROFILES_DIR_IN_REPO = "profiles"
LOCAL_FALLBACK_DIR = Path("data") / "profiles"
DEFAULT_PROFILE_PATH = Path("data") / "company_profile.json"
CACHE_TTL_SECONDS = 30
MAX_RETRIES = 3


# Sentinel for "the caller did not supply a load token" so we can
# distinguish it from an explicit ``None`` that means "forced overwrite".
_TOKEN_UNSET = object()


class ProfileConflict(RuntimeError):
    """Raised when a profile save would overwrite changes made by another
    writer (another tab, another replica, another user session).

    The caller is expected to surface a "someone else edited this — reload
    or overwrite?" prompt to the user. Re-raise with ``force=True`` (or
    pass ``expected_token=None``) to intentionally clobber.
    """

    def __init__(self, message: str, *, current_profile: dict, current_token: str):
        super().__init__(message)
        self.current_profile = current_profile
        self.current_token = current_token


def _compute_token(profile: dict | None) -> str:
    """Stable short hash of a profile dict — used for optimistic concurrency.

    Two semantically-identical profiles produce the same token regardless
    of key order. ``None`` / empty profile yields a sentinel token so a
    user who has never saved a profile is distinguishable from a user
    whose last-known state was empty-dict.
    """
    if profile is None:
        return "none"
    try:
        serialised = json.dumps(profile or {}, sort_keys=True, default=str,
                                 ensure_ascii=False)
    except Exception:
        serialised = repr(profile)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]


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


# Tracks *why* the default profile came back empty so the diagnostic can
# explain it to the operator. Values: None (not loaded yet), "ok",
# "missing" (file doesn't exist), "invalid" (file exists but is broken),
# "empty" (file parsed to a non-dict).
_DEFAULT_PROFILE_STATUS: Optional[str] = None
_DEFAULT_PROFILE_REASON: Optional[str] = None


def _load_default_profile() -> dict:
    """Return the bundled default profile (used when a user has none yet).

    Side effects: records the load status on module-level globals so
    :meth:`ProfileStore.diagnostic` can surface a "default profile file
    missing" warning — otherwise a bad deploy that drops the JSON ships
    every user the same empty dict with no signal in the logs.
    """
    global _DEFAULT_PROFILE_STATUS, _DEFAULT_PROFILE_REASON
    try:
        if not DEFAULT_PROFILE_PATH.is_file():
            _DEFAULT_PROFILE_STATUS = "missing"
            _DEFAULT_PROFILE_REASON = (
                f"Default profile file not found at {DEFAULT_PROFILE_PATH}. "
                "Every new signup will start with an empty profile until "
                "this file is restored."
            )
            _log.warning(_DEFAULT_PROFILE_REASON)
            return {}
        with open(DEFAULT_PROFILE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            _DEFAULT_PROFILE_STATUS = "empty"
            _DEFAULT_PROFILE_REASON = (
                f"Default profile at {DEFAULT_PROFILE_PATH} parsed to "
                f"{type(data).__name__}, not a JSON object."
            )
            _log.warning(_DEFAULT_PROFILE_REASON)
            return {}
        _DEFAULT_PROFILE_STATUS = "ok"
        _DEFAULT_PROFILE_REASON = None
        return data
    except (OSError, json.JSONDecodeError) as exc:
        _DEFAULT_PROFILE_STATUS = "invalid"
        _DEFAULT_PROFILE_REASON = (
            f"Default profile at {DEFAULT_PROFILE_PATH} is unreadable: "
            f"{type(exc).__name__}: {exc}"
        )
        _log.warning(_DEFAULT_PROFILE_REASON)
        return {}


def default_profile_status() -> tuple[Optional[str], Optional[str]]:
    """Return ``(status, reason)`` for the bundled default profile load.

    Used by the Settings page diagnostic expander to tell the operator
    that all new users are getting an empty profile because a bad deploy
    dropped ``data/company_profile.json``.
    """
    return _DEFAULT_PROFILE_STATUS, _DEFAULT_PROFILE_REASON


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
        status, reason = default_profile_status()
        return {
            "backend": self._resolved_backend,
            "label": self.backend_label(),
            "has_token": bool(self._token),
            "dataset": self._dataset,
            "last_error": self._last_error,
            "last_error_at": self._last_error_at,
            # New: status of the bundled default profile. The Settings
            # page surfaces a banner when status != "ok" so operators
            # notice a missing / corrupt ``data/company_profile.json``
            # instead of silently shipping empty profiles to every new
            # signup.
            "default_profile_status": status,
            "default_profile_reason": reason,
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
        profile, _token = self.load_with_token(username)
        return profile

    def load_with_token(self, username: str) -> tuple[dict, str]:
        """Same as :meth:`load` but also returns an opaque token describing
        the loaded state.

        Pass the token back into :meth:`save` as ``expected_token=`` to
        get optimistic-concurrency protection: if the stored profile has
        changed since this load, the save raises :class:`ProfileConflict`
        instead of silently clobbering the other writer's changes.
        """
        username = _safe_username(username)
        with self._lock:
            cached = self._cache.get(username)
            if cached and (time.time() - cached[1]) < CACHE_TTL_SECONDS:
                snapshot = json.loads(json.dumps(cached[0]))
                return snapshot, _compute_token(cached[0])

            profile = self._load_raw(username)
            had_stored_profile = bool(profile)
            if not profile:
                profile = self.default_profile()
            self._cache[username] = (profile, time.time())
            # If the user has *no* stored profile yet, the token represents
            # "nothing on disk" — first-save must pass expected_token="none"
            # (our sentinel) to enforce "no one else beat me to the create".
            token = _compute_token(profile) if had_stored_profile else "none"
            return json.loads(json.dumps(profile)), token

    def save(self, username: str, profile: dict,
             *, expected_token=_TOKEN_UNSET) -> str:
        """Persist ``profile`` for ``username``; return the new token.

        Parameters
        ----------
        expected_token
            Opt-in optimistic concurrency. When supplied, we re-load the
            currently-stored profile and compare its token against this
            one. On mismatch we raise :class:`ProfileConflict` with the
            current state attached so the caller can merge / prompt /
            retry. Pass the sentinel (default) to preserve the old
            last-write-wins behaviour for legacy callers.

        Concurrency notes
        -----------------
        * Per-user JSON files only collide when the same user has two
          tabs or two replicas racing.
        * The check-then-write is not a hard lock (HF Dataset doesn't
          expose one) — two writers arriving within the same
          millisecond could still both observe a matching token and
          both commit. The window is small and the blast radius is a
          single user's own profile, so we accept it.
        """
        username = _safe_username(username)
        with self._lock:
            if expected_token is not _TOKEN_UNSET:
                # Force a fresh read from the backend (bypass cache) so
                # we actually see a concurrent writer's commit. Clearing
                # the cache entry makes ``_load_raw`` re-query the store.
                self._cache.pop(username, None)
                current_raw = self._load_raw(username)
                current_token = (
                    _compute_token(current_raw) if current_raw else "none"
                )
                if current_token != expected_token:
                    # Refresh the cache with the server's version so
                    # subsequent reads on this process are honest about
                    # what's actually there.
                    refreshed = current_raw or self.default_profile()
                    self._cache[username] = (refreshed, time.time())
                    raise ProfileConflict(
                        "Profile was modified by another session since "
                        "you loaded it. Reload to see the latest state "
                        "or force-overwrite to discard the other change.",
                        current_profile=json.loads(json.dumps(refreshed)),
                        current_token=current_token,
                    )

            self._save_raw(username, profile)
            # Refresh cache with what we just wrote (TTL window resets).
            self._cache[username] = (json.loads(json.dumps(profile)), time.time())
            return _compute_token(profile)

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

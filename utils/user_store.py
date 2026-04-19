"""Persistent user store for ESG CoPilot authentication.

Primary backend: a *private* HuggingFace Dataset repo containing a single
``users.json`` file. This is free, writable with a user access token, and
survives HuggingFace Space rebuilds (which wipe the container filesystem).

Fallback: a local JSON file under ``./data/auth_users.json``. This is used
when no HF token is available (e.g. first run in a dev environment) or when
the Hub refuses writes. The fallback is explicit and surfaces a warning to
the caller via ``backend_label()`` so the UI can tell the user their
accounts might not persist.

Concurrency note: signups race-condition-ally read and rewrite the entire
``users.json``. For a small-scale demo that is acceptable; for production
we would move to a proper DB with transactions.
"""
from __future__ import annotations

import io
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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
except Exception:  # pragma: no cover - the library is a hard requirement
    HfApi = None  # type: ignore
    hf_hub_download = None  # type: ignore
    _HAS_HF = False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_DATASET = os.getenv("ESG_AUTH_DATASET", "isayan58/esg-copilot-auth")
USERS_PATH_IN_REPO = "users.json"
LOCAL_FALLBACK_PATH = Path("data") / "auth_users.json"
CACHE_TTL_SECONDS = 60


class _ConcurrentWriteConflict(Exception):
    """Raised internally when an HF commit is rejected by a concurrent write.

    Signals ``create_user`` to re-read + retry so a racing signup from
    another process doesn't lose the account we're trying to create.
    """


def _resolve_token() -> Optional[str]:
    """Best-effort HF token lookup across the conventional locations."""
    for name in ("HF_TOKEN", "HF_API_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(name)
        if value:
            return value.strip()
    # Fall back to the CLI-cached token file (only useful in dev)
    candidate = Path.home() / ".cache" / "huggingface" / "token"
    if candidate.is_file():
        try:
            text = candidate.read_text().strip()
            if text:
                return text
        except OSError:  # pragma: no cover
            pass
    return None


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class User:
    username: str
    email: str
    password_hash: str
    full_name: str
    role: str = "viewer"
    created_at: str = ""
    last_login: str = ""

    def to_public_dict(self) -> dict:
        """Return a dict safe to place in session_state (no password hash)."""
        return {
            "username": self.username,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }

    def to_record(self) -> dict:
        return {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash,
            "full_name": self.full_name,
            "role": self.role,
            "created_at": self.created_at,
            "last_login": self.last_login,
        }


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
class UserStore:
    """Thread-safe user store with pluggable backend (HF Dataset or local)."""

    def __init__(self, dataset_repo: str = DEFAULT_DATASET):
        self._dataset = dataset_repo
        self._token = _resolve_token()
        self._api = HfApi(token=self._token) if (_HAS_HF and self._token) else None
        self._lock = threading.RLock()
        self._cache: list[dict] = []
        self._cache_loaded_at: float = 0.0
        # The authoritative backend decided on first successful operation.
        # "hf_dataset" when we can read/write the dataset, else "local_json".
        self._resolved_backend: Optional[str] = None
        # Diagnostic: captured exception text whenever the HF backend
        # silently fell back to local JSON. Surfaced via diagnostic().
        self._last_error: Optional[str] = None
        self._last_error_at: Optional[str] = None

    # -- Public helpers -----------------------------------------------------
    @property
    def has_token(self) -> bool:
        return bool(self._token)

    def backend_label(self) -> str:
        """Return a short string describing which backend is in use."""
        if self._resolved_backend == "hf_dataset":
            return f"HuggingFace Dataset ({self._dataset})"
        if self._resolved_backend == "local_json":
            return f"Local JSON ({LOCAL_FALLBACK_PATH}) — ephemeral"
        return "Unresolved — will pick backend on first read"

    def diagnostic(self) -> dict:
        """Structured diagnostic for the sidebar / debug pages."""
        return {
            "backend": self._resolved_backend,
            "label": self.backend_label(),
            "has_token": bool(self._token),
            "dataset": self._dataset,
            "last_error": self._last_error,
            "last_error_at": self._last_error_at,
        }

    def _record_error(self, exc: BaseException) -> None:
        """Capture exception text + timestamp so the UI can show why HF failed.

        Walks the exception chain (``__cause__`` then ``__context__``) so a
        wrapped ``ValueError("Force download failed due to the above error.")``
        from huggingface_hub still surfaces the real ``EntryNotFoundError`` /
        ``HfHubHTTPError`` underneath it.
        """
        chain = []
        cur: BaseException | None = exc
        seen: set[int] = set()
        while cur is not None and id(cur) not in seen:
            chain.append(f"{type(cur).__name__}: {cur}")
            seen.add(id(cur))
            cur = cur.__cause__ or cur.__context__
        self._last_error = " ← ".join(chain)
        self._last_error_at = _utcnow_iso()

    # -- CRUD --------------------------------------------------------------
    def find_by_username(self, username: str) -> Optional[User]:
        username = (username or "").strip().lower()
        for record in self._load_users():
            if record.get("username", "").lower() == username:
                return User(**record)
        return None

    def find_by_email(self, email: str) -> Optional[User]:
        email = (email or "").strip().lower()
        for record in self._load_users():
            if record.get("email", "").lower() == email:
                return User(**record)
        return None

    def create_user(self, user: User) -> User:
        """Persist a new user. Raises ValueError on duplicate username/email.

        Concurrency: we hold the in-process ``RLock`` around the whole
        read-modify-write, and :meth:`_save_users` retries transient HF
        commit conflicts so two signups racing from different Space
        replicas (or the same process via different threads) both settle
        without losing one of the new accounts. Within a single replica,
        the lock is enough — the retry loop is insurance for the
        multi-replica case.
        """
        with self._lock:
            lower_username = user.username.lower()
            lower_email = user.email.lower()
            if not user.created_at:
                user.created_at = _utcnow_iso()

            # Retry the read-modify-write on HF commit conflict so a
            # concurrent signup from another process can't clobber this one.
            attempts = 3
            last_exc: BaseException | None = None
            for attempt in range(attempts):
                users = list(self._load_users(force_refresh=True))
                for existing in users:
                    if existing.get("username", "").lower() == lower_username:
                        raise ValueError("Username already exists.")
                    if existing.get("email", "").lower() == lower_email:
                        raise ValueError("Email is already registered.")
                candidate = list(users) + [user.to_record()]
                try:
                    self._save_users(candidate)
                    self._cache = candidate
                    self._cache_loaded_at = time.time()
                    return user
                except _ConcurrentWriteConflict as exc:
                    last_exc = exc
                    time.sleep(0.2 * (2 ** attempt))
                    continue
            if last_exc is not None:
                raise last_exc
        return user

    def touch_last_login(self, username: str) -> None:
        """Update a user's last_login timestamp; best-effort, never raises."""
        with self._lock:
            try:
                users = list(self._load_users(force_refresh=True))
                for record in users:
                    if record.get("username", "").lower() == username.lower():
                        record["last_login"] = _utcnow_iso()
                        self._save_users(users)
                        self._cache = users
                        self._cache_loaded_at = time.time()
                        return
            except Exception:  # pragma: no cover - best effort
                pass

    def count(self) -> int:
        return len(self._load_users())

    # -- Backend internals --------------------------------------------------
    def _load_users(self, *, force_refresh: bool = False) -> list[dict]:
        """Return the list of user records, hitting the cache when possible."""
        age = time.time() - self._cache_loaded_at
        if not force_refresh and self._cache and age < CACHE_TTL_SECONDS:
            return self._cache

        # Prefer HF Dataset when a token is available
        if self._api is not None:
            try:
                users = self._load_from_hf()
                self._resolved_backend = "hf_dataset"
                self._cache = users
                self._cache_loaded_at = time.time()
                # A successful read clears any prior error.
                self._last_error = None
                self._last_error_at = None
                return users
            except Exception as exc:
                # Fall through to local JSON, but record why so the UI can
                # tell the user their writes are going to ephemeral storage.
                self._record_error(exc)

        users = self._load_from_local()
        self._resolved_backend = "local_json"
        self._cache = users
        self._cache_loaded_at = time.time()
        return users

    def _save_users(self, users: list[dict]) -> None:
        """Persist users via whichever backend last resolved.

        Raises :class:`_ConcurrentWriteConflict` when the HF backend
        rejects the commit with a 409/412 (another writer got there
        first) so callers in a read-modify-write loop know to retry.
        Any other error falls back to local JSON as before.
        """
        # If HF is available and we've been using it (or never resolved), try HF.
        if self._api is not None and self._resolved_backend in (None, "hf_dataset"):
            try:
                self._save_to_hf(users)
                self._resolved_backend = "hf_dataset"
                self._last_error = None
                self._last_error_at = None
                return
            except HfHubHTTPError as exc:
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in (409, 412):
                    # Concurrent write — caller should re-read and retry.
                    raise _ConcurrentWriteConflict(
                        f"HF commit rejected (status {status}); "
                        "another writer got there first."
                    ) from exc
                self._record_error(exc)
            except Exception as exc:
                # Capture the failure reason before falling back so the
                # operator can see exactly which HF call failed and why.
                self._record_error(exc)
        self._save_to_local(users)
        self._resolved_backend = "local_json"

    # --- HF Dataset backend -----------------------------------------------
    def _load_from_hf(self) -> list[dict]:
        assert self._api is not None
        try:
            local_path = hf_hub_download(
                repo_id=self._dataset,
                repo_type="dataset",
                filename=USERS_PATH_IN_REPO,
                token=self._token,
                # NOTE: ``force_download=True`` was wrapping
                # EntryNotFoundError as a generic ValueError on some
                # huggingface_hub versions, which made first-time
                # bootstrap (no users.json yet) look like a hard failure.
                # Our own TTL cache handles freshness — leave this off.
            )
        except (EntryNotFoundError, RepositoryNotFoundError, HfHubHTTPError, ValueError):
            # Either the dataset or the file does not exist yet — both are
            # fine on first signup. Make sure the repo exists, then return
            # an empty user list so create_user() will write the first one.
            try:
                self._ensure_dataset_exists()
            except Exception:
                # Permissions issue creating the repo will surface on the
                # subsequent _save_to_hf call where it gets recorded.
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

    def _save_to_hf(self, users: list[dict]) -> None:
        assert self._api is not None
        self._ensure_dataset_exists()
        payload = json.dumps(users, indent=2, ensure_ascii=False).encode("utf-8")
        self._api.upload_file(
            path_or_fileobj=io.BytesIO(payload),
            path_in_repo=USERS_PATH_IN_REPO,
            repo_id=self._dataset,
            repo_type="dataset",
            commit_message="Update ESG CoPilot user registry",
        )

    def _ensure_dataset_exists(self) -> None:
        assert self._api is not None
        try:
            self._api.create_repo(
                repo_id=self._dataset,
                repo_type="dataset",
                private=True,
                exist_ok=True,
            )
        except HfHubHTTPError:
            # Permission or network error — let the caller fall back
            raise

    # --- Local JSON backend -----------------------------------------------
    def _load_from_local(self) -> list[dict]:
        if not LOCAL_FALLBACK_PATH.is_file():
            return []
        try:
            with open(LOCAL_FALLBACK_PATH, "r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    return data
                return []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_to_local(self, users: list[dict]) -> None:
        LOCAL_FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOCAL_FALLBACK_PATH, "w", encoding="utf-8") as fh:
            json.dump(users, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Module-level singleton (cheap to share between pages)
# ---------------------------------------------------------------------------
_STORE: Optional[UserStore] = None


def get_user_store() -> UserStore:
    global _STORE
    if _STORE is None:
        _STORE = UserStore()
    return _STORE


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

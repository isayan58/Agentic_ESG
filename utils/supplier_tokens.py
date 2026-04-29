"""Supplier portal — token store, submission validation, intake.

Suppliers don't have ESG Pilot logins. They get a tokenised URL
(``/Supplier_Portal?t=<token>``), open the form, fill in their ESG data,
submit. The submission lands in a per-org inbox; the org admin reviews
and (one click) merges it into the live ``supply_chain`` schema for the
next pipeline run.

Why tokens, not API keys?
-------------------------
* Single-use or rate-limited tokens make a leaked URL low-blast-radius —
  a token bound to "Supplier ABC, Q3 2026" cannot be reused for a
  different supplier or a different period.
* No supplier-side auth UX — they click a link, fill a form, done.
  This is what actually moves Scope 3 data quality.

Public surface
--------------
``SupplierToken`` — dataclass for a token + the supplier it represents
``Submission``    — dataclass for a single supplier submission
``TokenStore``    — CRUD: mint, list, revoke, redeem-and-validate
``SubmissionStore`` — CRUD: append, list per org, mark merged
"""
from __future__ import annotations

import io
import json
import logging
import os
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
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
TOKENS_DIR_IN_REPO = "supplier_tokens"
SUBMISSIONS_DIR_IN_REPO = "supplier_submissions"
LOCAL_TOKENS_DIR = Path("data") / "supplier_tokens"
LOCAL_SUBMISSIONS_DIR = Path("data") / "supplier_submissions"
CACHE_TTL_SECONDS = 30


def _resolve_token() -> Optional[str]:
    for name in ("HF_TOKEN", "HF_API_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _safe_owner(owner: str) -> str:
    import re
    cleaned = re.sub(r"[^a-zA-Z0-9_.\-]", "_", (owner or "").strip())
    return cleaned[:64] or "anonymous"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class SupplierToken:
    token: str
    supplier_name: str
    org_id: str                       # the buying org issuing the link
    period: str = ""                  # free-form: "Q3 2026", "FY2026", ...
    contact_email: str = ""
    created_by: str = ""
    created_at: str = ""
    expires_at: str = ""              # ISO timestamp; "" → no expiry
    used_at: str = ""                 # set when redeemed; blank → unused
    revoked: bool = False
    notes: str = ""

    @staticmethod
    def mint(*, supplier_name: str, org_id: str,
             created_by: str = "", period: str = "",
             contact_email: str = "",
             expires_at: str = "",
             notes: str = "") -> "SupplierToken":
        # 32 bytes URL-safe → ~43 character token, plenty of entropy
        # to make brute-forcing impractical without a per-IP rate limit
        # in front of us. We deliberately don't shorten — the URL is
        # used once via a copy/paste handoff so length doesn't matter.
        return SupplierToken(
            token=secrets.token_urlsafe(32),
            supplier_name=(supplier_name or "Unknown supplier").strip(),
            org_id=(org_id or "").strip(),
            period=(period or "").strip(),
            contact_email=(contact_email or "").strip(),
            created_by=(created_by or "").strip(),
            created_at=_utcnow(),
            expires_at=(expires_at or "").strip(),
            notes=(notes or "").strip(),
        )

    def is_valid(self) -> tuple[bool, str]:
        """Return (ok, reason). Reason is empty when valid.

        Order matters: revoked > expired > used. We surface the most
        actionable error to the supplier filling the form ("link
        revoked, contact your buyer") rather than chaining everything
        into one generic 'invalid' state.
        """
        if self.revoked:
            return False, "This link has been revoked. Please contact your buyer for a new one."
        if self.used_at:
            return False, "This link has already been used. One submission per link."
        if self.expires_at:
            try:
                exp = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp:
                    return False, f"This link expired on {self.expires_at}. Contact your buyer for a new one."
            except ValueError:
                # Treat malformed expiry as no-expiry rather than
                # silently rejecting the supplier.
                pass
        return True, ""


@dataclass
class Submission:
    id: str
    org_id: str
    token: str
    supplier_name: str
    period: str
    submitted_at: str
    submitted_by_email: str = ""
    rows: list[dict] = field(default_factory=list)
    merged: bool = False
    merged_at: str = ""
    merged_by: str = ""

    @staticmethod
    def new(*, org_id: str, token: str, supplier_name: str,
            period: str, rows: list[dict],
            submitted_by_email: str = "") -> "Submission":
        return Submission(
            id=uuid.uuid4().hex[:12],
            org_id=org_id,
            token=token,
            supplier_name=supplier_name,
            period=period,
            submitted_at=_utcnow(),
            submitted_by_email=submitted_by_email,
            rows=rows,
        )


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------
class _BaseStore:
    """Shared HF-or-local persistence wiring used by both stores below."""

    def __init__(self, dataset_repo: str = DEFAULT_DATASET):
        self._dataset = dataset_repo
        self._token = _resolve_token()
        self._api = HfApi(token=self._token) if (_HAS_HF and self._token) else None
        self._lock = threading.RLock()
        self._resolved_backend: Optional[str] = None
        self._last_error: Optional[str] = None

    def diagnostic(self) -> dict:
        return {
            "backend": self._resolved_backend,
            "has_token": bool(self._token),
            "dataset": self._dataset,
            "last_error": self._last_error,
        }

    def _load_json_list(self, *, path_in_repo: str,
                        local_path: Path) -> list[dict]:
        if self._api is not None:
            try:
                p = hf_hub_download(
                    repo_id=self._dataset, repo_type="dataset",
                    filename=path_in_repo, token=self._token,
                )
                self._resolved_backend = "hf_dataset"
                self._last_error = None
                with open(p, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                return data if isinstance(data, list) else []
            except (EntryNotFoundError, RepositoryNotFoundError,
                    HfHubHTTPError, ValueError):
                self._resolved_backend = "hf_dataset"
                return []
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"{type(exc).__name__}: {exc}"
        if not local_path.is_file():
            self._resolved_backend = "local_json"
            return []
        try:
            with open(local_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._resolved_backend = "local_json"
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save_json_list(self, *, records: list[dict], path_in_repo: str,
                        local_path: Path, commit_message: str) -> None:
        payload = json.dumps(records, indent=2, ensure_ascii=False,
                             default=str).encode("utf-8")
        if self._api is not None and self._resolved_backend in (None, "hf_dataset"):
            try:
                self._api.create_repo(
                    repo_id=self._dataset, repo_type="dataset",
                    private=True, exist_ok=True,
                )
                self._api.upload_file(
                    path_or_fileobj=io.BytesIO(payload),
                    path_in_repo=path_in_repo,
                    repo_id=self._dataset, repo_type="dataset",
                    commit_message=commit_message,
                )
                self._resolved_backend = "hf_dataset"
                self._last_error = None
                return
            except Exception as exc:  # noqa: BLE001
                self._last_error = f"{type(exc).__name__}: {exc}"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as fh:
            fh.write(payload)
        self._resolved_backend = "local_json"


class TokenStore(_BaseStore):
    """Mint, list, revoke, and validate supplier tokens."""

    def __init__(self, dataset_repo: str = DEFAULT_DATASET):
        super().__init__(dataset_repo)
        # token -> SupplierToken cache (read-mostly so a single global
        # cache is safe under the lock)
        self._cache: dict[str, tuple[list[SupplierToken], float]] = {}

    def _path_in_repo(self, owner: str) -> str:
        return f"{TOKENS_DIR_IN_REPO}/{owner}.json"

    def _local_path(self, owner: str) -> Path:
        return LOCAL_TOKENS_DIR / f"{owner}.json"

    def list_tokens(self, owner: str) -> list[SupplierToken]:
        owner = _safe_owner(owner)
        with self._lock:
            cached = self._cache.get(owner)
            if cached and (time.time() - cached[1]) < CACHE_TTL_SECONDS:
                return [SupplierToken(**asdict(t)) for t in cached[0]]
            records = self._load_json_list(
                path_in_repo=self._path_in_repo(owner),
                local_path=self._local_path(owner),
            )
            tokens = [_token_from_record(r) for r in records]
            self._cache[owner] = (list(tokens), time.time())
            return tokens

    def add_token(self, owner: str, token: SupplierToken) -> SupplierToken:
        owner = _safe_owner(owner)
        with self._lock:
            tokens = self.list_tokens(owner)
            tokens.append(token)
            self._save_json_list(
                records=[asdict(t) for t in tokens],
                path_in_repo=self._path_in_repo(owner),
                local_path=self._local_path(owner),
                commit_message=f"Mint supplier token for {owner}",
            )
            self._cache[owner] = (list(tokens), time.time())
            return token

    def patch_token(self, owner: str, token_str: str, patch: dict) -> bool:
        owner = _safe_owner(owner)
        with self._lock:
            tokens = self.list_tokens(owner)
            updated = False
            new_tokens = []
            for t in tokens:
                if t.token == token_str:
                    new_kwargs = {**asdict(t), **(patch or {})}
                    new_tokens.append(_token_from_record(new_kwargs))
                    updated = True
                else:
                    new_tokens.append(t)
            if not updated:
                return False
            self._save_json_list(
                records=[asdict(t) for t in new_tokens],
                path_in_repo=self._path_in_repo(owner),
                local_path=self._local_path(owner),
                commit_message=f"Patch supplier token for {owner}",
            )
            self._cache[owner] = (list(new_tokens), time.time())
            return True

    def revoke_token(self, owner: str, token_str: str) -> bool:
        return self.patch_token(owner, token_str, {"revoked": True})

    def find_token(self, token_str: str,
                    owners_to_search: list[str] | None = None) -> Optional[tuple[str, SupplierToken]]:
        """Locate a token across orgs. Returns ``(owner, token)`` or None.

        The supplier portal page hits this with no ``owners_to_search``
        because the supplier doesn't know which org issued their link.
        Without an index, we walk every org file we know about — fine
        for small deployments, swap for an index lookup at scale.
        """
        candidates = owners_to_search or self._known_owners()
        for owner in candidates:
            for t in self.list_tokens(owner):
                if t.token == token_str:
                    return owner, t
        return None

    def _known_owners(self) -> list[str]:
        """Best-effort discovery of orgs that have minted tokens.

        For HF backend: list filenames under ``supplier_tokens/``.
        For local: list files under ``data/supplier_tokens/``.
        """
        owners: list[str] = []
        if self._api is not None:
            try:
                tree = self._api.list_repo_files(
                    repo_id=self._dataset, repo_type="dataset",
                )
                prefix = f"{TOKENS_DIR_IN_REPO}/"
                for path in tree:
                    if path.startswith(prefix) and path.endswith(".json"):
                        owners.append(path[len(prefix):-5])
            except Exception:  # noqa: BLE001
                pass
        try:
            for p in LOCAL_TOKENS_DIR.glob("*.json"):
                owners.append(p.stem)
        except Exception:  # noqa: BLE001
            pass
        return list(dict.fromkeys(owners))


class SubmissionStore(_BaseStore):
    """Per-org append-only inbox of supplier submissions."""

    def __init__(self, dataset_repo: str = DEFAULT_DATASET):
        super().__init__(dataset_repo)
        self._cache: dict[str, tuple[list[Submission], float]] = {}

    def _path_in_repo(self, owner: str) -> str:
        return f"{SUBMISSIONS_DIR_IN_REPO}/{owner}.json"

    def _local_path(self, owner: str) -> Path:
        return LOCAL_SUBMISSIONS_DIR / f"{owner}.json"

    def list_submissions(self, owner: str) -> list[Submission]:
        owner = _safe_owner(owner)
        with self._lock:
            cached = self._cache.get(owner)
            if cached and (time.time() - cached[1]) < CACHE_TTL_SECONDS:
                return [Submission(**asdict(s)) for s in cached[0]]
            records = self._load_json_list(
                path_in_repo=self._path_in_repo(owner),
                local_path=self._local_path(owner),
            )
            subs = [_submission_from_record(r) for r in records]
            self._cache[owner] = (list(subs), time.time())
            return subs

    def add_submission(self, owner: str, submission: Submission) -> Submission:
        owner = _safe_owner(owner)
        with self._lock:
            subs = self.list_submissions(owner)
            subs.append(submission)
            self._save_json_list(
                records=[asdict(s) for s in subs],
                path_in_repo=self._path_in_repo(owner),
                local_path=self._local_path(owner),
                commit_message=f"Add supplier submission for {owner}",
            )
            self._cache[owner] = (list(subs), time.time())
            return submission

    def mark_merged(self, owner: str, submission_id: str,
                     merged_by: str = "") -> bool:
        owner = _safe_owner(owner)
        with self._lock:
            subs = self.list_submissions(owner)
            updated = False
            new_subs: list[Submission] = []
            for s in subs:
                if s.id == submission_id:
                    new_subs.append(Submission(**{
                        **asdict(s),
                        "merged": True,
                        "merged_at": _utcnow(),
                        "merged_by": merged_by,
                    }))
                    updated = True
                else:
                    new_subs.append(s)
            if not updated:
                return False
            self._save_json_list(
                records=[asdict(s) for s in new_subs],
                path_in_repo=self._path_in_repo(owner),
                local_path=self._local_path(owner),
                commit_message=f"Mark submission {submission_id} merged",
            )
            self._cache[owner] = (list(new_subs), time.time())
            return True


def _token_from_record(record: dict) -> SupplierToken:
    known = {f.name for f in SupplierToken.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return SupplierToken(**{k: v for k, v in (record or {}).items() if k in known})


def _submission_from_record(record: dict) -> Submission:
    known = {f.name for f in Submission.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    payload = {k: v for k, v in (record or {}).items() if k in known}
    payload.setdefault("id", uuid.uuid4().hex[:12])
    payload.setdefault("org_id", "")
    payload.setdefault("token", "")
    payload.setdefault("supplier_name", "")
    payload.setdefault("period", "")
    payload.setdefault("submitted_at", _utcnow())
    return Submission(**payload)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
ALLOWED_FIELDS: tuple[str, ...] = (
    "supplier_name", "scope3_emissions_tco2e",
    "energy_consumption_kwh", "renewable_energy_pct",
    "water_consumption_kl", "waste_kg",
    "diversity_pct", "lost_time_incidents",
    "esg_score", "notes",
)
NUMERIC_FIELDS: tuple[str, ...] = (
    "scope3_emissions_tco2e", "energy_consumption_kwh",
    "renewable_energy_pct", "water_consumption_kl",
    "waste_kg", "diversity_pct", "lost_time_incidents",
    "esg_score",
)


def validate_submission(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Coerce + validate supplier-supplied rows.

    Returns ``(clean_rows, errors)``. Rows that fail validation are
    dropped, and the index + reason is appended to ``errors``. The
    portal page surfaces both: clean rows for the inbox, errors for
    the supplier so they can fix them.
    """
    clean: list[dict] = []
    errors: list[str] = []
    for idx, raw in enumerate(rows or []):
        if not isinstance(raw, dict):
            errors.append(f"Row {idx + 1}: not a key/value record.")
            continue
        cleaned = {}
        for key in ALLOWED_FIELDS:
            if key not in raw:
                continue
            value = raw[key]
            if key in NUMERIC_FIELDS:
                try:
                    cleaned[key] = float(value) if value not in (None, "") else None
                except (TypeError, ValueError):
                    errors.append(
                        f"Row {idx + 1}: '{key}' must be numeric (got {value!r}).",
                    )
                    continue
            else:
                cleaned[key] = str(value).strip() if value is not None else ""
        # Reject empty rows so the portal doesn't accept blank
        # submissions silently.
        if not any(v not in (None, "", 0) for v in cleaned.values()):
            errors.append(f"Row {idx + 1}: empty.")
            continue
        clean.append(cleaned)
    return clean, errors


# ---------------------------------------------------------------------------
# Module singletons
# ---------------------------------------------------------------------------
_TOKEN_STORE: Optional[TokenStore] = None
_SUBMISSION_STORE: Optional[SubmissionStore] = None


def get_token_store() -> TokenStore:
    global _TOKEN_STORE
    if _TOKEN_STORE is None:
        _TOKEN_STORE = TokenStore()
    return _TOKEN_STORE


def get_submission_store() -> SubmissionStore:
    global _SUBMISSION_STORE
    if _SUBMISSION_STORE is None:
        _SUBMISSION_STORE = SubmissionStore()
    return _SUBMISSION_STORE


__all__ = [
    "ALLOWED_FIELDS", "NUMERIC_FIELDS",
    "SupplierToken", "Submission",
    "TokenStore", "SubmissionStore",
    "get_token_store", "get_submission_store",
    "validate_submission",
]

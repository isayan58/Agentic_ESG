"""Authentication primitives for ESG Pilot.

This module glues together:
    * ``utils.user_store`` — persistence (HF Dataset or local JSON)
    * ``bcrypt``            — password hashing
    * ``itsdangerous``      — signed, expiring session cookies
    * ``extra_streamlit_components`` — cookie bridge between browser & server

Public surface
--------------
``hash_password(password)``                 -> str
``verify_password(password, hash_)``        -> bool
``sign_token(payload)``                     -> str
``verify_token(token, max_age_seconds)``    -> dict | None
``signup(username, email, password, ...)``  -> dict          (raises ValueError)
``login(identifier, password)``             -> dict | None
``logout()``                                -> None
``current_user()``                          -> dict | None
``require_login()``                         -> dict            (gate; st.stop()s)
``sidebar_auth_widget()``                   -> None
``session_backend_label()``                 -> str
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import threading
import time
from collections import deque
from typing import Optional

import streamlit as st

try:
    import bcrypt
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "bcrypt is required for authentication. Install via "
        "`pip install bcrypt`."
    ) from exc

try:
    from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
except Exception as exc:  # pragma: no cover
    raise RuntimeError(
        "itsdangerous is required for authentication. Install via "
        "`pip install itsdangerous`."
    ) from exc

try:
    import extra_streamlit_components as stx
    _HAS_STX = True
except Exception:  # pragma: no cover - optional cookie bridge
    stx = None  # type: ignore
    _HAS_STX = False

try:
    from email_validator import EmailNotValidError, validate_email
    _HAS_EMAIL_VALIDATOR = True
except Exception:  # pragma: no cover
    validate_email = None  # type: ignore
    EmailNotValidError = Exception  # type: ignore
    _HAS_EMAIL_VALIDATOR = False

from utils.user_store import User, get_user_store


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
COOKIE_NAME = os.getenv("ESG_AUTH_COOKIE", "esg_copilot_session")
SESSION_TTL_SECONDS = int(os.getenv("ESG_AUTH_TTL", str(60 * 60 * 24 * 14)))  # 14d
COOKIE_SALT = "esg-copilot-session-v1"
MIN_PASSWORD_LENGTH = 8
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.\-]{3,32}$")

# Rate limits (per identifier, rolling window). In-memory only — fine for
# one Space replica. If we ever run multi-replica we'll need a shared
# backend (Redis / the HF Dataset itself). Keep the numbers generous so
# real users aren't impeded; these exist to blunt brute-force / script
# abuse, not to annoy legitimate traffic.
LOGIN_RATE_LIMIT = int(os.getenv("ESG_AUTH_LOGIN_LIMIT", "10"))      # attempts
LOGIN_RATE_WINDOW = int(os.getenv("ESG_AUTH_LOGIN_WINDOW", "300"))   # seconds (5 min)
SIGNUP_RATE_LIMIT = int(os.getenv("ESG_AUTH_SIGNUP_LIMIT", "5"))
SIGNUP_RATE_WINDOW = int(os.getenv("ESG_AUTH_SIGNUP_WINDOW", "3600"))  # 1h

_rate_lock = threading.Lock()
_login_attempts: dict[str, deque] = {}
_signup_attempts: dict[str, deque] = {}

# Janitor cadence — sweep idle keys once every N check calls. Keeps
# the cost amortised to roughly O(1)/call while guaranteeing no key
# stays in the bucket longer than ~N*window seconds worst case.
_RATE_SWEEP_EVERY = int(os.getenv("ESG_AUTH_SWEEP_EVERY", "500"))
_rate_check_counter = 0


class RateLimitExceeded(ValueError):
    """Raised when too many auth attempts from the same identifier."""


def _sweep_idle_keys(bucket: dict[str, deque], window: int,
                     now: float | None = None) -> int:
    """Drop keys whose newest entry is older than ``window``.

    Called periodically from :func:`_check_rate_limit` so the attempt
    buckets don't grow without bound. Returns the number of keys
    evicted so tests / diagnostics can observe the sweep.

    Must be called with ``_rate_lock`` held (or from a single-threaded
    context like a unit test).
    """
    if now is None:
        now = time.monotonic()
    stale = [
        k for k, dq in bucket.items()
        if not dq or (now - dq[-1]) > window
    ]
    for k in stale:
        bucket.pop(k, None)
    return len(stale)


def _check_rate_limit(bucket: dict[str, deque], key: str,
                       limit: int, window: int) -> None:
    """Record an attempt and raise if we've exceeded ``limit`` in ``window``.

    Keyed on the normalised identifier (username lowered, remote IP
    would be ideal but Streamlit doesn't expose it reliably). This is
    a best-effort brake, not a security boundary.

    Memory hygiene: every ``_RATE_SWEEP_EVERY`` calls we sweep idle
    keys out of the bucket. Without this, an attacker cycling random
    usernames could grow either bucket O(unique-identifiers) without
    ever triggering the per-key eviction logic.
    """
    global _rate_check_counter
    now = time.monotonic()
    with _rate_lock:
        _rate_check_counter += 1
        if _rate_check_counter % _RATE_SWEEP_EVERY == 0:
            # Sweep BOTH buckets — the caller only holds a reference
            # to one, but the lock covers both and the cost is O(N)
            # over mostly-dead keys.
            _sweep_idle_keys(_login_attempts, LOGIN_RATE_WINDOW, now=now)
            _sweep_idle_keys(_signup_attempts, SIGNUP_RATE_WINDOW, now=now)

        dq = bucket.setdefault(key, deque())
        # Drop entries older than the window.
        while dq and (now - dq[0]) > window:
            dq.popleft()
        if len(dq) >= limit:
            oldest = dq[0]
            retry_in = int(window - (now - oldest)) + 1
            raise RateLimitExceeded(
                f"Too many attempts. Try again in ~{retry_in}s."
            )
        dq.append(now)


def _resolve_secret() -> str:
    """Resolve a stable secret for signing session cookies.

    Preference order:
      1. ``SESSION_SECRET`` environment variable (recommended for prod)
      2. ``STREAMLIT_SESSION_SECRET`` (alternative name)
      3. A file at ``.streamlit/.session_secret`` (auto-created & .gitignored)
      4. Process-ephemeral random key (invalidates all cookies on restart)
    """
    for name in ("SESSION_SECRET", "STREAMLIT_SESSION_SECRET"):
        val = os.getenv(name)
        if val:
            return val

    # Dev convenience — persist a random key next to the streamlit config
    try:
        from pathlib import Path

        secret_path = Path(".streamlit") / ".session_secret"
        secret_path.parent.mkdir(parents=True, exist_ok=True)
        if secret_path.is_file():
            text = secret_path.read_text().strip()
            if text:
                return text
        generated = secrets.token_urlsafe(48)
        secret_path.write_text(generated)
        try:
            os.chmod(secret_path, 0o600)
        except OSError:  # pragma: no cover
            pass
        return generated
    except Exception:  # pragma: no cover
        return secrets.token_urlsafe(48)


_SECRET = _resolve_secret()
_SERIALIZER = URLSafeTimedSerializer(_SECRET, salt=COOKIE_SALT)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Token signing
# ---------------------------------------------------------------------------
def sign_token(payload: dict) -> str:
    return _SERIALIZER.dumps(payload)


def verify_token(token: str, max_age: int = SESSION_TTL_SECONDS) -> Optional[dict]:
    if not token:
        return None
    try:
        return _SERIALIZER.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None


# ---------------------------------------------------------------------------
# Cookie manager (lazy, session-scoped)
# ---------------------------------------------------------------------------
def _cookie_manager():
    if not _HAS_STX:
        return None
    if "_auth_cookie_manager" not in st.session_state:
        # A stable key means the component reuses the same React mount across reruns
        st.session_state["_auth_cookie_manager"] = stx.CookieManager(key="esg_cm")
    return st.session_state["_auth_cookie_manager"]


def _read_cookie() -> Optional[str]:
    """Read the auth cookie, forcing the browser component to sync first.

    ``stx.CookieManager`` is asynchronous — on the very first render of a
    page the React component hasn't yet posted its cookie dict back to the
    server, so ``cm.get(name)`` returns ``None`` even when the cookie exists.
    Streamlit will re-run the script once the component reports, but by then
    any ``require_login`` call has already fired ``st.stop()`` and redirected
    to the sign-in page. Calling ``cm.get_all()`` surfaces that "not yet
    hydrated" state explicitly — we set a session flag so ``require_login``
    can render a brief splash instead of a false sign-in gate.
    """
    cm = _cookie_manager()
    if cm is None:
        return None
    try:
        all_cookies = cm.get_all()
    except Exception:  # pragma: no cover - defensive
        all_cookies = None
    if all_cookies is None:
        # Component hasn't posted yet — mark pending so require_login can wait.
        st.session_state["_auth_cookie_pending"] = True
        return None
    st.session_state["_auth_cookie_pending"] = False
    return all_cookies.get(COOKIE_NAME)


def _write_cookie(value: str) -> None:
    cm = _cookie_manager()
    if cm is None:
        return
    try:
        from datetime import datetime, timedelta, timezone

        expires = datetime.now(timezone.utc) + timedelta(seconds=SESSION_TTL_SECONDS)
        cm.set(COOKIE_NAME, value, expires_at=expires, key=f"set_{COOKIE_NAME}")
    except Exception:  # pragma: no cover
        pass


def _delete_cookie() -> None:
    cm = _cookie_manager()
    if cm is None:
        return
    try:
        cm.delete(COOKIE_NAME, key=f"del_{COOKIE_NAME}")
    except Exception:  # pragma: no cover
        pass


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _validate_username(username: str) -> str:
    username = (username or "").strip()
    if not USERNAME_PATTERN.match(username):
        raise ValueError(
            "Username must be 3–32 characters: letters, digits, '_', '.' or '-'."
        )
    return username


def _validate_email(email: str) -> str:
    email = (email or "").strip()
    if not email:
        raise ValueError("Email is required.")
    if _HAS_EMAIL_VALIDATOR:
        try:
            result = validate_email(email, check_deliverability=False)
            return result.normalized
        except EmailNotValidError as exc:
            raise ValueError(f"Invalid email: {exc}") from exc
    # Fallback regex — good enough for the demo
    if "@" not in email or "." not in email.split("@")[-1]:
        raise ValueError("Invalid email address.")
    return email.lower()


def _validate_password(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        )


# ---------------------------------------------------------------------------
# Auth actions
# ---------------------------------------------------------------------------
def signup(
    username: str,
    email: str,
    password: str,
    full_name: str = "",
    role: str = "viewer",
) -> dict:
    """Create a new user. Raises ``ValueError`` on validation / duplicates.

    Rate-limited per username-or-email to blunt signup-spam scripts. The
    cap is intentionally generous (5/hour) so a real user typo-ing their
    password a few times isn't locked out.
    """
    username = _validate_username(username)
    email = _validate_email(email)
    _validate_password(password)
    full_name = (full_name or "").strip() or username

    _check_rate_limit(_signup_attempts, username.lower(),
                      SIGNUP_RATE_LIMIT, SIGNUP_RATE_WINDOW)
    _check_rate_limit(_signup_attempts, email.lower(),
                      SIGNUP_RATE_LIMIT, SIGNUP_RATE_WINDOW)

    store = get_user_store()
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
    )
    store.create_user(user)
    store.touch_last_login(username)
    public = user.to_public_dict()
    _start_session(public)
    return public


def login(identifier: str, password: str) -> Optional[dict]:
    """Authenticate using *username or email* + password.

    Rate-limited to slow credential-stuffing against a known identifier.
    Raises :class:`RateLimitExceeded` when tripped so the caller can
    surface the retry window instead of silently returning ``None``
    (which would look like a bad password).
    """
    identifier = (identifier or "").strip()
    if not identifier or not password:
        return None
    _check_rate_limit(_login_attempts, identifier.lower(),
                      LOGIN_RATE_LIMIT, LOGIN_RATE_WINDOW)
    store = get_user_store()
    user = store.find_by_username(identifier)
    if user is None and "@" in identifier:
        user = store.find_by_email(identifier)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    store.touch_last_login(user.username)
    public = user.to_public_dict()
    _start_session(public)
    return public


def logout() -> None:
    # Capture the username *before* we clear it from session_state so we
    # can drop the corresponding state_manager bucket too.
    _user = st.session_state.get("user") or {}
    _username = (_user.get("username") or "").strip()

    st.session_state.pop("user", None)
    st.session_state.pop("_auth_token", None)
    # Drop the per-user ConnectionManager so the next signed-in user
    # doesn't briefly inherit this account's sources before hydration.
    st.session_state.pop("conn_manager", None)
    st.session_state.pop("_conn_manager_owner", None)
    # Same idea for the per-user company profile / CompanyConfig.
    st.session_state.pop("company_profile", None)
    st.session_state.pop("_company_profile_owner", None)
    st.session_state.pop("_company_profile_token", None)
    st.session_state.pop("_company_cfg", None)
    # Drop any pipeline / agent results for this user from the
    # process-wide state_manager bucket. Without this the next sign-in
    # of the *same* username on the same process would briefly see
    # stale carbon / regulatory / audit / report payloads from this
    # session before they re-ran the pipeline.
    try:
        from core.state_manager import state_manager
        if _username:
            state_manager.clear_user(_username)
        # Also clear the guest bucket so a logged-out user doesn't see
        # their own pre-login state on a fresh visit.
        state_manager.clear_user("_anonymous")
    except Exception:
        pass
    # Drop any cached agent instances that might hold references to
    # the previous user's results in attributes (defensive).
    for k in list(st.session_state.keys()):
        if k.endswith("_agent") or k.endswith("_results") or k == "data_collector":
            st.session_state.pop(k, None)
    try:
        from core.company_config import set_active_company_config
        set_active_company_config(None)
    except Exception:
        pass
    _delete_cookie()


# ---------------------------------------------------------------------------
# Session hydration
# ---------------------------------------------------------------------------
def _start_session(user: dict) -> None:
    st.session_state["user"] = user
    token = sign_token({"u": user["username"]})
    st.session_state["_auth_token"] = token
    _write_cookie(token)


def _hydrate_from_cookie() -> Optional[dict]:
    """If a valid session cookie exists, load the user into session_state."""
    if st.session_state.get("user"):
        return st.session_state["user"]
    token = _read_cookie()
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        _delete_cookie()
        return None
    username = payload.get("u")
    if not username:
        return None
    store = get_user_store()
    user = store.find_by_username(username)
    if user is None:
        _delete_cookie()
        return None
    public = user.to_public_dict()
    st.session_state["user"] = public
    st.session_state["_auth_token"] = token
    return public


def current_user() -> Optional[dict]:
    """Return the signed-in user (hydrating from cookie if needed)."""
    if st.session_state.get("user"):
        return st.session_state["user"]
    return _hydrate_from_cookie()


# ---------------------------------------------------------------------------
# Page gate + sidebar
# ---------------------------------------------------------------------------
def require_login(message: str = "Please sign in to access this page.") -> dict:
    """Gate a page. Renders a sign-in CTA + calls ``st.stop()`` if unauthed.

    Side effect on success: binds the signed-in user's :class:`CompanyConfig`
    to the current thread so every agent import of ``company_cfg`` in this
    rerun automatically resolves to the user's profile. Imported lazily
    to avoid a circular dependency at module-load time.
    """
    user = current_user()
    if user:
        try:
            from utils.session import get_session_company_config
            get_session_company_config()
        except Exception:
            # Never let a profile-store hiccup block access to a page
            # the user has already authenticated for.
            pass
        return user

    # Cookie component may still be hydrating on the first render after a
    # browser refresh. Show a tiny splash and stop — Streamlit will re-run
    # once the component posts the cookie, and the second pass will hit the
    # ``if user`` branch above.
    if st.session_state.get("_auth_cookie_pending"):
        st.markdown(
            """
            <div style="
                padding: 1.25rem 1.5rem;
                border-radius: 12px;
                background: linear-gradient(135deg, #FFF7EF 0%, #FFF1E3 100%);
                border: 1px solid rgba(253, 81, 8, 0.18);
                color: #7a2e0c;
                font-family: 'Inter', sans-serif; font-size: 0.95rem;
            ">⏳ Restoring your session…</div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    st.markdown(
        """
        <div style="
            padding: 2rem 1.5rem;
            border-radius: 16px;
            background: linear-gradient(135deg, #D04A02 0%, #A23A02 100%);
            color: white;
            text-align: center;
            box-shadow: 0 12px 32px rgba(208, 74, 2, 0.18);
        ">
            <div style="font-size: 2.5rem;">&#128274;</div>
            <h2 style="margin:0.25rem 0 0.5rem 0; color:white;">Authentication required</h2>
            <p style="margin:0; opacity:0.9;">""" + message + """</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")

    col_a, col_b, _ = st.columns([1, 1, 2])
    with col_a:
        if st.button("Go to Sign In", type="primary", use_container_width=True):
            try:
                st.switch_page("pages/0_Sign_In.py")
            except Exception:
                st.info("Open the **Sign In** page from the left sidebar.")
    with col_b:
        if st.button("Back to Home", use_container_width=True):
            try:
                st.switch_page("Home.py")
            except Exception:
                pass

    st.stop()


# Sidebar nav gating — injected once per render by sidebar_auth_widget().
# Streamlit renders the sidebar nav in this order (filename sort, Home first):
#   1) Home        2) Sign In        3+) page routes
# Signed-in users see only the app pages (Home + Sign In hidden);
# signed-out users see only Home + Sign In.
#
# Streamlit's sidebar-nav DOM shape shifts across minor versions (sometimes
# `ul > li`, sometimes `stSidebarNavItems` directly, sometimes nav-link
# anchors as flat siblings), so each rule has a href-based fallback and
# targets every wrapper we've seen in the wild.
_HIDE_SIGNIN_NAV_CSS = """
<style>
    /* Home — hidden when signed in. Match by href (empty / root), by
       position (first li / first nav-link), and by Streamlit's labeled
       nav-item testid. */
    [data-testid="stSidebarNav"] a[href="./"],
    [data-testid="stSidebarNav"] a[href="/"],
    [data-testid="stSidebarNav"] li:has(a[href="./"]),
    [data-testid="stSidebarNav"] li:has(a[href="/"]),
    [data-testid="stSidebarNav"] ul > li:first-child,
    [data-testid="stSidebarNav"] ul > li:nth-child(1),
    [data-testid="stSidebarNavItems"] > li:first-child,
    [data-testid="stSidebarNavItems"] > li:nth-child(1),
    [data-testid="stSidebarNav"] > ul > li:first-child,
    /* Sign In — hidden when signed in. */
    [data-testid="stSidebarNav"] a[href$="/Sign_In"],
    [data-testid="stSidebarNav"] li:has(a[href$="/Sign_In"]),
    [data-testid="stSidebarNav"] ul > li:nth-child(2),
    [data-testid="stSidebarNavItems"] > li:nth-child(2) {
        display: none !important;
    }
</style>
"""

# Applied on every page when there's no user in session — only Home +
# Sign In remain visible in the sidebar nav; everything else is hidden.
_HIDE_AUTHED_NAV_CSS = """
<style>
    [data-testid="stSidebarNav"] ul > li:nth-child(n+3),
    [data-testid="stSidebarNavItems"] > li:nth-child(n+3) {
        display: none !important;
    }
</style>
"""


def _render_storage_diagnostic() -> None:
    """Show the persistence backend (and the last HF error if any) in the
    sidebar. This is the loud signal you need when ``HF_TOKEN`` is misset:
    instead of "looks fine but data vanished on rebuild", you'll see
    ``Local JSON — ephemeral`` plus the exception that pushed you there.
    """
    try:
        from utils.user_store import get_user_store
        from utils.source_store import get_source_store
    except Exception:
        return

    user_diag = get_user_store().diagnostic()
    src_diag = get_source_store().diagnostic()
    backend = user_diag.get("backend") or src_diag.get("backend")
    err = user_diag.get("last_error") or src_diag.get("last_error")

    # Color-coded one-liner — green for HF, amber for local fallback.
    if backend == "hf_dataset":
        color, label = "#16a34a", "HF Dataset (persistent)"
    elif backend == "local_json":
        color, label = "#d97706", "Local JSON (ephemeral)"
    else:
        # Backend hasn't been resolved yet — show token presence so the
        # operator can confirm HF_TOKEN was even read by the process.
        has_token = user_diag.get("has_token") or src_diag.get("has_token")
        color = "#16a34a" if has_token else "#dc2626"
        label = (
            "HF token detected — backend resolves on first signup/login"
            if has_token else "No HF_TOKEN — set as a Space secret"
        )

    st.caption(
        f"<span style='color:{color}'>● Storage: {label}</span>",
        unsafe_allow_html=True,
    )
    if err:
        with st.expander("⚠ Last persistence error", expanded=False):
            st.code(err, language="text")
            st.caption(
                f"Dataset: `{user_diag.get('dataset')}` · "
                f"Token loaded: {'yes' if user_diag.get('has_token') else 'no'}"
            )


def sidebar_auth_widget() -> None:
    """Render a compact auth widget in the sidebar on every page."""
    user = current_user()
    # Gate the sidebar nav based on auth: signed-in users never see
    # Home / Sign In; signed-out users only ever see those two.
    if user:
        st.markdown(_HIDE_SIGNIN_NAV_CSS, unsafe_allow_html=True)
    else:
        st.markdown(_HIDE_AUTHED_NAV_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("---")
        _render_storage_diagnostic()
        if user:
            name = user.get("full_name") or user.get("username", "user")
            role = user.get("role", "viewer").title()
            initials = "".join(part[:1].upper() for part in name.split()[:2]) or "U"
            st.markdown(
                f"""
                <div style="
                    display:flex; align-items:center; gap:0.65rem;
                    padding:0.65rem 0.75rem;
                    border:1px solid #e2e8f0; border-radius:12px;
                    background: #f6f8fb;">
                    <div style="
                        width:36px; height:36px; border-radius:50%;
                        background: linear-gradient(135deg, #D04A02, #A23A02);
                        color:white; font-weight:600;
                        display:flex; align-items:center; justify-content:center;
                        font-size:0.85rem;">{initials}</div>
                    <div style="line-height:1.2;">
                        <div style="font-weight:600; color:#1a202c; font-size:0.9rem;">{name}</div>
                        <div style="color:#64748b; font-size:0.75rem;">{role}</div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Sign out", use_container_width=True, key="sidebar_signout"):
                logout()
                st.rerun()
        else:
            st.caption("You are browsing as a guest.")
            if st.button("Sign In / Sign Up", type="primary", use_container_width=True, key="sidebar_signin"):
                try:
                    st.switch_page("pages/0_Sign_In.py")
                except Exception:
                    st.info("Open the **Sign In** page from the sidebar.")


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------
def session_backend_label() -> str:
    return get_user_store().backend_label()


def secret_fingerprint() -> str:
    """Short non-reversible fingerprint of the signing secret for diagnostics."""
    return hashlib.sha256(_SECRET.encode("utf-8")).hexdigest()[:8]

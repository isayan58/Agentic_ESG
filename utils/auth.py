"""Authentication primitives for ESG CoPilot.

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
    cm = _cookie_manager()
    if cm is None:
        return None
    try:
        return cm.get(COOKIE_NAME)
    except Exception:  # pragma: no cover - defensive
        return None


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
    """Create a new user. Raises ``ValueError`` on validation / duplicates."""
    username = _validate_username(username)
    email = _validate_email(email)
    _validate_password(password)
    full_name = (full_name or "").strip() or username

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
    """Authenticate using *username or email* + password."""
    identifier = (identifier or "").strip()
    if not identifier or not password:
        return None
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
    st.session_state.pop("user", None)
    st.session_state.pop("_auth_token", None)
    # Drop the per-user ConnectionManager so the next signed-in user
    # doesn't briefly inherit this account's sources before hydration.
    st.session_state.pop("conn_manager", None)
    st.session_state.pop("_conn_manager_owner", None)
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
    """Gate a page. Renders a sign-in CTA + calls ``st.stop()`` if unauthed."""
    user = current_user()
    if user:
        return user

    st.markdown(
        """
        <div style="
            padding: 2rem 1.5rem;
            border-radius: 16px;
            background: linear-gradient(135deg, #0f9d58 0%, #0b7a43 100%);
            color: white;
            text-align: center;
            box-shadow: 0 12px 32px rgba(15,157,88,0.18);
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


# CSS that hides the "Sign In" sidebar nav entry when the user is logged in.
# We inject this at the top of every page via sidebar_auth_widget() so it
# runs before Streamlit's nav renders.
_HIDE_SIGNIN_NAV_CSS = """
<style>
    [data-testid="stSidebarNav"] a[href$="/Sign_In"],
    [data-testid="stSidebarNav"] li:has(a[href$="/Sign_In"]) {
        display: none !important;
    }
</style>
"""


def sidebar_auth_widget() -> None:
    """Render a compact auth widget in the sidebar on every page."""
    user = current_user()
    # When authenticated, hide the Sign In entry from the sidebar nav.
    if user:
        st.markdown(_HIDE_SIGNIN_NAV_CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("---")
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
                        background: linear-gradient(135deg, #0f9d58, #0b7a43);
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

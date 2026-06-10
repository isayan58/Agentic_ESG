"""Sign In / Sign Up page for ESG Pilot.

Presents two tabs — Sign In and Create account — backed by
``utils.auth``. On success the user is redirected to ESG Command Center.
"""
import streamlit as st

from utils.auth import (
    RateLimitExceeded,
    current_user,
    login,
    logout,
    session_backend_label,
    sidebar_auth_widget,
    signup,
)
from utils.ui import hero, inject_global_css, pwc_header, section_header

st.set_page_config(
    page_title="Sign In | ESG Intelligence Hub",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_global_css()
pwc_header()
sidebar_auth_widget()

hero(
    title="Sign in to ESG Intelligence Hub",
    emoji="🔐",
    subtitle=(
        "Authenticate to unlock the 9-agent autonomous pipeline, ESG Command Center, "
        "and ROI dashboards. New here? Create a free account in seconds."
    ),
    chips=[
        "Secure — bcrypt password hashing",
        "14-day signed session cookie",
        "Your accounts persist across deployments",
    ],
)

# Already signed in? Offer a quick jump + sign-out.
existing = current_user()
if existing:
    section_header(
        "You are already signed in",
        f"Welcome back, {existing.get('full_name') or existing.get('username')}.",
    )
    col_a, col_b, _ = st.columns([1, 1, 2])
    with col_a:
        if st.button("Go to ESG Command Center", type="primary", use_container_width=True):
            try:
                st.switch_page("pages/1_ESG_Command_Center.py")
            except Exception:
                st.info("Open **ESG Command Center** from the left sidebar.")
    with col_b:
        if st.button("Sign out", use_container_width=True):
            logout()
            st.rerun()
    st.stop()


st.markdown(
    """
    <style>
    /* Constrain the auth forms to a readable card width */
    [data-testid="stTabs"] { max-width: 640px; margin: 0 auto; }
    </style>
    """,
    unsafe_allow_html=True,
)

tab_signin, tab_signup = st.tabs(["Sign in", "Create account"])

# ---------------------------------------------------------------------------
# Sign in
# ---------------------------------------------------------------------------
with tab_signin:
    section_header(
        "Welcome back",
        "Sign in with your username or email to resume your ESG pipeline.",
    )
    with st.form("signin_form", clear_on_submit=False):
        identifier = st.text_input(
            "Username or email",
            placeholder="jane.doe  or  jane@example.com",
            autocomplete="username",
        )
        password = st.text_input(
            "Password",
            type="password",
            autocomplete="current-password",
        )
        submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

    if submitted:
        if not identifier or not password:
            st.error("Enter your username/email and password.")
        else:
            try:
                user = login(identifier, password)
            except RateLimitExceeded as exc:
                user = None
                st.warning(f"🚧 {exc}", icon="🚧")
            else:
                if user is None:
                    st.error("Invalid credentials. Please check your username/email and password.")
                else:
                    st.success(f"Welcome, {user.get('full_name') or user.get('username')}! Redirecting…")
                    try:
                        st.switch_page("pages/1_ESG_Command_Center.py")
                    except Exception:
                        st.rerun()

# ---------------------------------------------------------------------------
# Sign up
# ---------------------------------------------------------------------------
with tab_signup:
    section_header(
        "Create your account",
        "Self-serve signup. Your account is stored in a private, persistent registry.",
    )
    with st.form("signup_form", clear_on_submit=False):
        col_a, col_b = st.columns(2)
        with col_a:
            full_name = st.text_input("Full name", placeholder="Jane Doe")
            username = st.text_input(
                "Username",
                placeholder="jane.doe",
                help="3–32 characters — letters, digits, '_', '.' or '-'.",
            )
        with col_b:
            email = st.text_input("Work email", placeholder="jane@example.com")
            role = st.selectbox(
                "Role",
                options=["viewer", "analyst", "admin"],
                index=0,
                help="Controls which dashboards you can see. Start as viewer; upgrade later.",
            )

        new_password = st.text_input(
            "Password",
            type="password",
            autocomplete="new-password",
            help="Minimum 8 characters. Use a passphrase.",
        )
        confirm = st.text_input(
            "Confirm password",
            type="password",
            autocomplete="new-password",
        )
        agreed = st.checkbox(
            "I understand my credentials are stored securely and can be deleted on request.",
            value=False,
        )
        submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)

    if submitted:
        if not agreed:
            st.error("Please acknowledge the storage notice to continue.")
        elif not new_password or new_password != confirm:
            st.error("Passwords do not match.")
        else:
            try:
                user = signup(
                    username=username,
                    email=email,
                    password=new_password,
                    full_name=full_name,
                    role=role,
                )
            except RateLimitExceeded as exc:
                user = None
                st.warning(f"🚧 {exc}", icon="🚧")
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.error(f"Could not create account: {exc}")
            else:
                st.success(
                    f"Account created — welcome, {user.get('full_name') or user.get('username')}!"
                )
                try:
                    st.switch_page("pages/1_ESG_Command_Center.py")
                except Exception:
                    st.rerun()


# ---------------------------------------------------------------------------
# Footer — backend + session transparency
# ---------------------------------------------------------------------------
st.markdown("<div style='max-width:640px;margin:0 auto;'>", unsafe_allow_html=True)
with st.expander("About this sign-in"):
    st.markdown(
        f"""
**Credential backend:** `{session_backend_label()}`

- Passwords are hashed with **bcrypt** (12 rounds) before storage — we never see your plaintext password.
- Your session is a signed cookie issued with **itsdangerous** and expires after 14 days.
- You can sign out at any time from the sidebar widget on every page.
"""
    )
st.markdown("</div>", unsafe_allow_html=True)

"""Team & Roles — manage org members, change roles, invite teammates.

Visibility: every signed-in user can see this page (so they can find out
who their org admin is) but only users with ``manage_users`` can mutate
roles or rename the org. Lower-privilege users see a read-only roster.
"""
from __future__ import annotations

import streamlit as st

from utils.auth import require_login, sidebar_auth_widget, signup, RateLimitExceeded
from utils.rbac import (
    ROLES, has_permission, permission_matrix, role_label,
)
from utils.ui import hero, inject_global_css, pwc_header, section_header
from utils.user_store import get_user_store

st.set_page_config(
    page_title="Team & Roles | ESG Intelligence Hub",
    page_icon="👥",
    layout="wide",
)
inject_global_css()
pwc_header()
sidebar_auth_widget()
user = require_login("Sign in to manage your team.")

org_id = (user.get("org_id") or "").strip()
org_name = (user.get("org_name") or "").strip() or org_id or "Your workspace"
can_manage = has_permission(user, "manage_users")

hero(
    title=f"Team — {org_name}",
    emoji="👥",
    subtitle=(
        "Manage who has access to this workspace and what they can do. "
        "Roles are enforced consistently across pipeline runs, regulatory "
        "approvals, supplier portal tokens, and exports."
    ),
    chips=[
        f"Org id: {org_id or '—'}",
        f"Your role: {role_label(user.get('role', 'viewer'))}",
        "Read-only mode" if not can_manage else "Admin mode",
    ],
)

store = get_user_store()
members = store.list_org_members(org_id) if org_id else []

# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------
section_header(
    "Members",
    f"{len(members)} member(s) in this workspace.",
)

if not members:
    st.info("No members found for this workspace.")
else:
    for member in members:
        cols = st.columns([3, 2, 2, 2])
        with cols[0]:
            st.markdown(
                f"**{member.full_name or member.username}** "
                f"<span style='color:#64748b;'>· @{member.username}</span>",
                unsafe_allow_html=True,
            )
            st.caption(member.email)
        with cols[1]:
            st.markdown(f"**{role_label(member.role)}**")
            st.caption(f"Joined {member.created_at[:10] if member.created_at else 'n/a'}")
        with cols[2]:
            st.caption(
                f"Last login: {member.last_login[:16].replace('T', ' ') if member.last_login else 'never'}"
            )
        with cols[3]:
            if can_manage and member.username != user.get("username"):
                new_role = st.selectbox(
                    "Role",
                    options=list(ROLES),
                    index=ROLES.index(member.role) if member.role in ROLES else 3,
                    key=f"role_{member.username}",
                    label_visibility="collapsed",
                )
                if new_role != member.role:
                    if st.button("Save", key=f"save_{member.username}",
                                 type="primary", use_container_width=True):
                        try:
                            store.update_role(member.username, new_role)
                            st.success(
                                f"Role updated to {role_label(new_role)} for "
                                f"{member.username}."
                            )
                            st.rerun()
                        except ValueError as exc:
                            st.error(str(exc))
            elif member.username == user.get("username"):
                st.caption("(you)")
        st.divider()

# ---------------------------------------------------------------------------
# Invite — admins only
# ---------------------------------------------------------------------------
if can_manage:
    section_header(
        "Invite a teammate",
        "Create an account directly inside this workspace. The new user "
        "logs in with the password you set here and can change it later.",
    )
    with st.form("invite_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            inv_full = st.text_input("Full name", placeholder="Aisha Patel")
            inv_user = st.text_input("Username", placeholder="aisha.patel")
        with c2:
            inv_email = st.text_input("Work email", placeholder="aisha@example.com")
            inv_role = st.selectbox("Role", options=list(ROLES), index=3)
        inv_pw = st.text_input(
            "Initial password (share securely; user can rotate later)",
            type="password",
            help="Minimum 8 characters.",
        )
        submitted = st.form_submit_button(
            "Send invite", type="primary", use_container_width=True,
        )
    if submitted:
        if not inv_user or not inv_email or not inv_pw:
            st.error("Username, email, and an initial password are all required.")
        else:
            try:
                # signup() opens a new session; we don't want that for the
                # admin who's still working — so we use the user_store
                # directly, then restore admin's session afterwards.
                from utils.user_store import User as _User
                from utils.auth import hash_password as _hash

                new_user = _User(
                    username=inv_user.strip(),
                    email=inv_email.strip().lower(),
                    password_hash=_hash(inv_pw),
                    full_name=(inv_full.strip() or inv_user.strip()),
                    role=inv_role,
                    org_id=org_id,
                    org_name=org_name,
                )
                store.create_user(new_user)
                st.success(
                    f"Invited @{inv_user} as {role_label(inv_role)}. "
                    "Share the password with them via a secure channel."
                )
                st.rerun()
            except RateLimitExceeded as exc:
                st.warning(f"🚧 {exc}", icon="🚧")
            except ValueError as exc:
                st.error(str(exc))

# ---------------------------------------------------------------------------
# Permission matrix — visible to everyone for transparency
# ---------------------------------------------------------------------------
section_header(
    "Permission matrix",
    "What each role can do. Useful when planning who to invite at which level.",
)
matrix = permission_matrix()
all_perms = sorted({p for plist in matrix.values() for p in plist})
header = ["Permission"] + [role_label(r) for r in ROLES]
rows = []
for perm in all_perms:
    row = [f"`{perm}`"]
    for r in ROLES:
        row.append("✅" if perm in matrix.get(r, []) else "—")
    rows.append(row)
import pandas as _pd
st.dataframe(
    _pd.DataFrame(rows, columns=header),
    use_container_width=True,
    hide_index=True,
)

"""Role-based access control for ESG Pilot.

Adds an *organisation* layer above the existing per-user isolation. A
user belongs to exactly one org (auto-created at signup as
``org_<username>`` so single-user demos keep working), holds one of four
roles within it, and is gated on the actions below by the permission
matrix.

Roles
-----
* ``admin``   — manages users, billing, sources, approvals, notifications
* ``analyst`` — edits sources, runs pipelines, approves regulatory updates
* ``auditor`` — read everything, plus access the audit-trail page
* ``viewer``  — read-only on dashboards

Public surface
--------------
``has_permission(user, perm)``       -> bool
``require_permission(perm)``         -> dict | st.stop()
``role_label(role)``                 -> str
``ROLES``, ``PERMISSIONS``           -> tuples of valid identifiers
``permission_matrix()``              -> dict[role, list[perm]]
``default_org_for(username)``        -> str
"""
from __future__ import annotations

from typing import Optional

# ---------------------------------------------------------------------------
# Role + permission catalogue
# ---------------------------------------------------------------------------
ROLES: tuple[str, ...] = ("admin", "analyst", "auditor", "viewer")

# All permissions exposed across the app. Each gate in the UI / agents
# should resolve to one of these strings — adding a permission here
# without updating ``_MATRIX`` deliberately leaves it ungranted.
PERMISSIONS: tuple[str, ...] = (
    "manage_users",            # invite / remove team members
    "manage_org",              # rename org, update billing
    "manage_sources",          # add / remove / replace data sources
    "run_pipeline",            # execute the orchestrator
    "approve_regulatory",      # approve / dismiss / revert framework updates
    "manage_notifications",    # configure notification routes
    "manage_supplier_tokens",  # mint / revoke supplier portal tokens
    "manage_xbrl",             # generate XBRL exports
    "view_dashboards",         # any pipeline / agent page
    "view_audit",              # audit trail / audit log expander
    "view_lineage",            # data lineage page
)

# role -> permissions granted. Higher roles inherit lower permissions
# explicitly (no transitive resolution at runtime — keeps the matrix
# auditable from one place).
_MATRIX: dict[str, frozenset[str]] = {
    "admin": frozenset({
        "manage_users", "manage_org", "manage_sources", "run_pipeline",
        "approve_regulatory", "manage_notifications", "manage_supplier_tokens",
        "manage_xbrl", "view_dashboards", "view_audit", "view_lineage",
    }),
    "analyst": frozenset({
        "manage_sources", "run_pipeline", "approve_regulatory",
        "manage_supplier_tokens", "manage_xbrl",
        "view_dashboards", "view_audit", "view_lineage",
    }),
    "auditor": frozenset({
        "view_dashboards", "view_audit", "view_lineage",
    }),
    "viewer": frozenset({
        "view_dashboards",
    }),
}


def has_permission(user: Optional[dict], perm: str) -> bool:
    """Return True iff ``user``'s role grants ``perm``.

    A missing user, an unknown role, or an unknown permission all return
    False — the safe default. Designed so a misspelled permission string
    never silently grants access.
    """
    if not user or perm not in PERMISSIONS:
        return False
    role = (user.get("role") or "").strip().lower()
    return perm in _MATRIX.get(role, frozenset())


def role_label(role: str) -> str:
    """Human-readable label for a role string."""
    return {
        "admin":   "Admin",
        "analyst": "Analyst",
        "auditor": "Auditor",
        "viewer":  "Viewer",
    }.get((role or "").strip().lower(), role.title() if role else "Unknown")


def permission_matrix() -> dict[str, list[str]]:
    """Snapshot of the role/permission table for the Team Settings UI."""
    return {role: sorted(perms) for role, perms in _MATRIX.items()}


def default_org_for(username: str) -> str:
    """Personal org id auto-assigned at signup.

    A user who signs up without being invited gets their own one-person
    org. Inviting a teammate later moves them into your org via the
    ``set_user_org`` helper in ``utils.user_store``.
    """
    cleaned = (username or "").strip().lower()
    return f"org_{cleaned}" if cleaned else "org_anonymous"


def require_permission(perm: str, message: str | None = None):
    """Streamlit gate — render an "access denied" panel and stop on miss.

    Usage at the top of a page, after ``require_login()``::

        from utils.rbac import require_permission
        require_permission("manage_users")

    The function returns the current user dict on success so the caller
    can use it without a second lookup. On failure it renders a small
    branded panel and calls ``st.stop()``.
    """
    import streamlit as st
    from utils.auth import current_user

    user = current_user()
    if has_permission(user, perm):
        return user

    role = (user or {}).get("role", "viewer") if user else "(anonymous)"
    msg = message or (
        f"This page requires the **{perm}** permission. "
        f"Your current role is **{role_label(role)}** — ask your org admin "
        "to upgrade your role or open the Team Settings page."
    )
    st.markdown(
        """
        <div style="
            padding: 1.5rem;
            border-radius: 12px;
            border: 1px solid #FBBF24;
            background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
            color: #78350F;
        ">
            <div style="font-size:1.15rem; font-weight:600; margin-bottom:0.35rem;">
                🔒 Access denied
            </div>
            <div style="font-size:0.95rem;">""" + msg + """</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()


__all__ = [
    "ROLES",
    "PERMISSIONS",
    "has_permission",
    "require_permission",
    "role_label",
    "permission_matrix",
    "default_org_for",
]

"""Pin the RBAC matrix and the user-store role helpers."""
from __future__ import annotations

import pytest

from utils.rbac import (
    PERMISSIONS,
    ROLES,
    default_org_for,
    has_permission,
    permission_matrix,
    role_label,
)


class TestPermissionMatrix:
    def test_admin_holds_every_permission(self):
        # If we ever add a permission and forget to grant it to admins,
        # this test fails before the change ships. Admins exist precisely
        # so someone always has every action available.
        admin_perms = set(permission_matrix()["admin"])
        assert admin_perms == set(PERMISSIONS)

    def test_viewer_is_strictly_read_only(self):
        viewer = set(permission_matrix()["viewer"])
        assert viewer == {"view_dashboards"}, (
            "Viewer scope expanded — update this test deliberately if "
            "that's intended."
        )

    def test_auditor_can_read_audit_log(self):
        # Auditor's whole purpose. If view_audit ever leaves the role,
        # the audit-trail page becomes unreachable for compliance staff.
        assert "view_audit" in permission_matrix()["auditor"]

    def test_only_admin_manages_users(self):
        # Membership management is admin-only by design — analyst can
        # edit data, but not promote teammates.
        assert has_permission({"role": "admin"}, "manage_users")
        for role in ("analyst", "auditor", "viewer"):
            assert not has_permission({"role": role}, "manage_users"), role

    def test_unknown_permission_denied(self):
        # Misspelled permission strings must NEVER grant access. A
        # silent grant on a typo would be a security regression.
        assert not has_permission({"role": "admin"}, "manage_typo_does_not_exist")

    def test_unknown_role_denied(self):
        assert not has_permission({"role": "superuser"}, "manage_users")
        assert not has_permission({}, "view_dashboards")
        assert not has_permission(None, "view_dashboards")


class TestHelpers:
    def test_role_label_known_values(self):
        assert role_label("admin") == "Admin"
        assert role_label("analyst") == "Analyst"
        assert role_label("auditor") == "Auditor"
        assert role_label("viewer") == "Viewer"

    def test_role_label_unknown_passthrough(self):
        # Unknown roles get title-cased, not silently substituted.
        assert role_label("contractor") == "Contractor"
        assert role_label("") == "Unknown"

    def test_default_org_namespacing(self):
        assert default_org_for("alice") == "org_alice"
        assert default_org_for("Alice") == "org_alice"  # case-insensitive
        assert default_org_for("") == "org_anonymous"


class TestUserStoreRoleUpdate:
    """Round-trip role + org changes through the user store."""

    def setup_method(self):
        from utils.user_store import UserStore, User
        # Use a temp local backend so the test doesn't touch HF.
        from pathlib import Path
        import tempfile
        self.tmpdir = Path(tempfile.mkdtemp())
        store = UserStore()
        # Force local-JSON backend by clearing the API
        store._api = None
        store._token = None
        # Repoint the local fallback file to a temp path
        import utils.user_store as us_mod
        self._orig_local = us_mod.LOCAL_FALLBACK_PATH
        us_mod.LOCAL_FALLBACK_PATH = self.tmpdir / "users.json"
        self.store = store
        self.User = User

    def teardown_method(self):
        import utils.user_store as us_mod
        us_mod.LOCAL_FALLBACK_PATH = self._orig_local
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_role_round_trip(self):
        u = self.User(
            username="bob", email="b@x.com", password_hash="h",
            full_name="Bob", role="viewer",
            org_id="org_test", org_name="Test Workspace",
        )
        self.store.create_user(u)
        # Promote to analyst
        assert self.store.update_role("bob", "analyst") is True
        loaded = self.store.find_by_username("bob")
        assert loaded.role == "analyst"

    def test_update_role_rejects_unknown(self):
        u = self.User(
            username="cara", email="c@x.com", password_hash="h",
            full_name="Cara", role="viewer", org_id="org_test",
        )
        self.store.create_user(u)
        with pytest.raises(ValueError, match="Unknown role"):
            self.store.update_role("cara", "wizard")

    def test_list_org_members_filters_correctly(self):
        for u in [
            self.User("alice", "a@x.com", "h", "Alice", "admin",
                      org_id="org_acme"),
            self.User("bob", "b@x.com", "h", "Bob", "analyst",
                      org_id="org_acme"),
            self.User("eve", "e@x.com", "h", "Eve", "viewer",
                      org_id="org_other"),
        ]:
            self.store.create_user(u)
        members = self.store.list_org_members("org_acme")
        assert {m.username for m in members} == {"alice", "bob"}

"""Supplier portal: token lifecycle + submission validation."""
from __future__ import annotations

import pytest

from utils.supplier_tokens import (
    Submission,
    SupplierToken,
    validate_submission,
)


class TestTokenLifecycle:
    def test_mint_produces_unique_long_token(self):
        a = SupplierToken.mint(supplier_name="A", org_id="o")
        b = SupplierToken.mint(supplier_name="B", org_id="o")
        assert a.token != b.token
        # ~43 chars for 32 bytes URL-safe base64. Tight bound here makes
        # an accidental shortening (e.g. someone swapping to 8 bytes)
        # surface as a test failure.
        assert len(a.token) >= 32

    def test_fresh_token_is_valid(self):
        t = SupplierToken.mint(supplier_name="A", org_id="o")
        ok, reason = t.is_valid()
        assert ok and reason == ""

    def test_revoked_token_rejected(self):
        t = SupplierToken.mint(supplier_name="A", org_id="o")
        t.revoked = True
        ok, reason = t.is_valid()
        assert not ok
        assert "revoked" in reason.lower()

    def test_used_token_rejected(self):
        t = SupplierToken.mint(supplier_name="A", org_id="o")
        t.used_at = "2026-04-29T10:00:00+00:00"
        ok, reason = t.is_valid()
        assert not ok
        assert "already" in reason.lower()

    def test_expired_token_rejected(self):
        t = SupplierToken.mint(supplier_name="A", org_id="o")
        t.expires_at = "2020-01-01T00:00:00+00:00"
        ok, reason = t.is_valid()
        assert not ok
        assert "expired" in reason.lower()

    def test_revoke_takes_priority_over_expiry(self):
        # When a link is both revoked and expired, the revoked message
        # is more actionable for the supplier ("contact your buyer").
        t = SupplierToken.mint(supplier_name="A", org_id="o")
        t.revoked = True
        t.expires_at = "2020-01-01T00:00:00+00:00"
        ok, reason = t.is_valid()
        assert not ok
        assert "revoked" in reason.lower()


class TestSubmissionValidation:
    def test_drops_empty_rows(self):
        clean, errors = validate_submission([{}])
        assert clean == []
        assert any("empty" in e.lower() for e in errors)

    def test_drops_non_numeric_value_in_numeric_field(self):
        clean, errors = validate_submission([
            {"scope3_emissions_tco2e": "not a number"},
        ])
        # Whole row drops because the only numeric field failed.
        assert clean == []
        assert errors and "scope3_emissions_tco2e" in errors[0]

    def test_keeps_known_fields_only(self):
        clean, errors = validate_submission([{
            "supplier_name": "ACME",
            "scope3_emissions_tco2e": 12.5,
            "evil_injection_attempt": "<script>",
        }])
        assert len(clean) == 1
        # Unknown fields are silently dropped — they never reach the
        # buyer's inbox even if a malicious supplier tries to inject them.
        assert "evil_injection_attempt" not in clean[0]
        assert clean[0]["supplier_name"] == "ACME"
        assert clean[0]["scope3_emissions_tco2e"] == 12.5

    def test_coerces_string_numbers(self):
        clean, _ = validate_submission([{
            "scope3_emissions_tco2e": "12.5",
        }])
        assert len(clean) == 1
        assert clean[0]["scope3_emissions_tco2e"] == 12.5

    def test_handles_non_dict_rows_gracefully(self):
        clean, errors = validate_submission(["not a dict", 42])
        assert clean == []
        assert len(errors) == 2


class TestSubmissionConstruction:
    def test_new_assigns_id_and_timestamp(self):
        s = Submission.new(
            org_id="o", token="tok", supplier_name="A",
            period="Q3 2026", rows=[{"scope3_emissions_tco2e": 1.0}],
        )
        assert s.id and len(s.id) >= 6
        assert s.merged is False
        assert s.submitted_at  # ISO timestamp set at construction

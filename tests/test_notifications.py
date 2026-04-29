"""Notifications: dispatch fan-out, severity gating, transport isolation."""
from __future__ import annotations

import pytest

from utils.notifications import (
    Event,
    Route,
    notify,
    _severity_rank,
)


def _route(channel="generic_webhook", **overrides) -> Route:
    base = dict(channel=channel, label="t", target="https://example.com",
                event_types=[], min_severity="info")
    base.update(overrides)
    return Route.new(**base)


class TestSeverityGating:
    def test_severity_rank_ordering(self):
        assert _severity_rank("info") < _severity_rank("warning") < _severity_rank("critical")

    def test_route_filters_below_min_severity(self):
        # A route configured for warning+ ignores info-level events.
        route = _route(min_severity="warning")
        info_event = Event("test", title="t", summary="s", severity="info")
        warn_event = Event("test", title="t", summary="s", severity="warning")
        assert route.matches(info_event) is False
        assert route.matches(warn_event) is True

    def test_disabled_route_never_matches(self):
        route = _route()
        route.enabled = False
        assert route.matches(Event("test", title="t", summary="s")) is False

    def test_event_type_filter(self):
        # Empty event_types means "all events". A non-empty list filters.
        all_route = _route(event_types=[])
        narrow = _route(event_types=["regulatory_update_pending"])
        e1 = Event("regulatory_update_pending", title="t", summary="s")
        e2 = Event("pipeline_run_completed", title="t", summary="s")
        assert all_route.matches(e1) is True
        assert all_route.matches(e2) is True
        assert narrow.matches(e1) is True
        assert narrow.matches(e2) is False


class TestDispatchIsolation:
    """One bad route shouldn't block delivery to others in the same call."""

    def test_one_bad_webhook_does_not_block_others(self, monkeypatch):
        sent: list[str] = []

        def fake_post(url, *_a, **_kw):
            if "broken" in url:
                raise RuntimeError("boom")
            sent.append(url)
            class _R:
                def raise_for_status(self_inner): pass
            return _R()

        monkeypatch.setattr(
            "utils.notifications.requests.post", fake_post,
        )
        good = _route(target="https://hooks.example.com/good")
        bad = _route(target="https://broken.example.com/")
        another_good = _route(target="https://hooks.example.com/also")

        results = notify(
            Event("test", title="t", summary="s"),
            routes=[good, bad, another_good],
        )
        # Both good ones should have been sent; bad one captures the
        # error in its DispatchResult instead of bubbling out.
        assert len(results) == 3
        ok_targets = [r for r in results if r.ok]
        assert len(ok_targets) == 2
        bad_results = [r for r in results if not r.ok]
        assert len(bad_results) == 1
        assert "boom" in bad_results[0].detail.lower()
        assert "https://hooks.example.com/good" in sent
        assert "https://hooks.example.com/also" in sent

    def test_no_routes_means_no_op(self):
        # Critical: a call site without routes / owner must not raise.
        results = notify(Event("test", title="t", summary="s"))
        assert results == []


class TestEmailWithoutSMTP:
    def test_email_route_reports_missing_smtp(self, monkeypatch):
        # Strip every SMTP env var so the channel can't accidentally
        # pick up dev credentials.
        for k in ("ESG_SMTP_HOST", "ESG_SMTP_SENDER",
                   "ESG_SMTP_PORT", "ESG_SMTP_USER", "ESG_SMTP_PASS"):
            monkeypatch.delenv(k, raising=False)
        route = _route(channel="email", target="dest@example.com")
        results = notify(
            Event("test", title="t", summary="s"),
            routes=[route],
        )
        assert len(results) == 1
        assert results[0].ok is False
        assert "SMTP" in results[0].detail


class TestRendering:
    """Render functions are pure — they're easy to pin without I/O."""

    def test_email_render_uses_severity(self):
        from utils.notifications import _render_email
        subject, _, html = _render_email(
            Event("test", title="The Title", summary="x", severity="critical"),
        )
        assert "🚨" in subject  # critical emoji
        assert "The Title" in subject
        assert "<h2" in html

    def test_slack_render_has_blocks(self):
        from utils.notifications import _render_slack
        payload = _render_slack(Event("test", title="X", summary="Y",
                                       severity="warning",
                                       url="https://app/page"))
        assert payload["text"].startswith(":warning:")
        # The button block only appears when a URL is set.
        block_types = [b["type"] for b in payload["blocks"]]
        assert "actions" in block_types

    def test_teams_render_color_by_severity(self):
        from utils.notifications import _render_teams
        info = _render_teams(Event("test", title="i", summary="s", severity="info"))
        warn = _render_teams(Event("test", title="w", summary="s", severity="warning"))
        crit = _render_teams(Event("test", title="c", summary="s", severity="critical"))
        # Distinct colors per severity — auditable from the matrix
        # docstring at the top of the module.
        assert info["themeColor"] != warn["themeColor"] != crit["themeColor"]

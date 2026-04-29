"""Notification routes — configure where ESG Pilot fans out alerts.

Channels supported: SMTP email, Slack incoming webhook, Microsoft Teams
incoming webhook, generic JSON webhook. Routes are persisted per-org so
every member of the workspace shares (and inherits) the same routing
table — exactly the behaviour that makes a "team-wide regulatory queue
landed in Slack" mental model work.
"""
from __future__ import annotations

import streamlit as st

from utils.auth import require_login, sidebar_auth_widget
from utils.notifications import (
    CHANNELS,
    EVENT_TYPES,
    Event,
    Route,
    get_route_store,
    notify,
)
from utils.rbac import has_permission, require_permission
from utils.ui import hero, inject_global_css, pwc_header, section_header

st.set_page_config(
    page_title="Notifications | ESG Intelligence Hub",
    page_icon="🔔",
    layout="wide",
)
inject_global_css()
pwc_header()
sidebar_auth_widget()
user = require_login("Sign in to manage notifications.")
require_permission(
    "manage_notifications",
    "Notification routes are managed by the org admin. "
    "You can still receive notifications others have routed to you.",
)

org_id = (user.get("org_id") or "").strip()
org_name = (user.get("org_name") or "").strip() or org_id

hero(
    title="Notification routes",
    emoji="🔔",
    subtitle=(
        "Send ESG Pilot events to email, Slack, Teams, or any JSON webhook. "
        "Routes are workspace-wide — your team sees the same queue. "
        "Configure SMTP via the env vars listed below to enable email."
    ),
    chips=[
        "Email · Slack · Teams · Generic webhook",
        f"Workspace: {org_name or '—'}",
        f"You can manage routes" if has_permission(user, "manage_notifications") else "Read-only",
    ],
)

store = get_route_store()
existing = store.list_routes(org_id)

# ---------------------------------------------------------------------------
# Existing routes
# ---------------------------------------------------------------------------
section_header(
    "Configured routes",
    f"{len(existing)} active route(s) for this workspace.",
)

if not existing:
    st.info("No routes configured yet. Add one below.")
else:
    for route in existing:
        with st.container(border=True):
            cols = st.columns([3, 2, 2, 1, 1])
            with cols[0]:
                st.markdown(f"**{route.label}**")
                st.caption(f"`{route.target[:80]}`")
            with cols[1]:
                st.markdown(f"Channel: **{route.channel}**")
                event_filter = (
                    "All events" if not route.event_types
                    else ", ".join(route.event_types)
                )
                st.caption(f"Events: {event_filter}")
            with cols[2]:
                st.markdown(f"Min severity: `{route.min_severity}`")
                st.caption(f"Enabled: {'✅' if route.enabled else '⏸️'}")
            with cols[3]:
                if st.button("Test", key=f"test_{route.id}",
                             use_container_width=True):
                    test_event = Event(
                        type="test",
                        title="ESG Pilot · Test notification",
                        summary=("This is a test message from your ESG Pilot "
                                 f"workspace ({org_name or org_id}). If you can "
                                 "see this, the route is wired correctly."),
                        severity="info",
                        actor=user.get("username"),
                    )
                    results = notify(test_event, routes=[route])
                    for res in results:
                        if res.ok:
                            st.success(
                                f"Sent via {res.channel} — {res.detail}", icon="✅",
                            )
                        else:
                            st.error(
                                f"Failed via {res.channel} — {res.detail}",
                                icon="🚨",
                            )
            with cols[4]:
                if st.button("Delete", key=f"del_{route.id}",
                             use_container_width=True):
                    if store.remove_route(org_id, route.id):
                        st.success("Route removed.")
                        st.rerun()

# ---------------------------------------------------------------------------
# Add a new route
# ---------------------------------------------------------------------------
section_header(
    "Add a route",
    "Pick a channel and the events you want it to fire on.",
)
with st.form("new_route", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        channel = st.selectbox("Channel", options=list(CHANNELS))
        label = st.text_input(
            "Label",
            placeholder="ESG team Slack · #esg-alerts",
        )
    with c2:
        target_help = {
            "email": "Recipient email address.",
            "slack": "Slack incoming-webhook URL (https://hooks.slack.com/services/...).",
            "teams": "Microsoft Teams incoming-webhook URL.",
            "generic_webhook": "Any HTTPS endpoint that accepts JSON POST.",
        }
        target = st.text_input(
            "Target",
            help=target_help.get(channel, ""),
            placeholder="alerts@example.com / https://hooks.slack.com/...",
        )
        min_severity = st.selectbox(
            "Minimum severity",
            options=["info", "warning", "critical"],
            index=0,
        )
    selected_events = st.multiselect(
        "Event types (leave empty for all)",
        options=list(EVENT_TYPES),
    )
    submitted = st.form_submit_button(
        "Add route", type="primary", use_container_width=True,
    )

if submitted:
    if not target.strip() or not label.strip():
        st.error("Label and target are both required.")
    else:
        route = Route.new(
            channel=channel,
            label=label.strip(),
            target=target.strip(),
            event_types=list(selected_events),
            min_severity=min_severity,
        )
        store.add_route(org_id, route)
        st.success(f"Route '{route.label}' added.")
        st.rerun()

# ---------------------------------------------------------------------------
# Operator notes
# ---------------------------------------------------------------------------
section_header(
    "Configuration",
    "Email requires SMTP env vars on the server. Webhooks need no extra setup.",
)
st.markdown(
    """
| Env var | Purpose |
| --- | --- |
| `ESG_SMTP_HOST` | SMTP server host (e.g. `smtp.sendgrid.net`) |
| `ESG_SMTP_PORT` | Port (default `587`) |
| `ESG_SMTP_USER` | SMTP auth user (optional) |
| `ESG_SMTP_PASS` | SMTP auth password (optional) |
| `ESG_SMTP_SENDER` | `From:` address (required for email channel) |
| `ESG_SMTP_TLS` | `1` (default) to STARTTLS, `0` for plain |
| `ESG_DEFAULT_ORG` | Fallback org id when notifications fire from a non-Streamlit context (CLI / cron) |
"""
)

with st.expander("Diagnostic"):
    st.json(store.diagnostic())

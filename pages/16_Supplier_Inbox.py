"""Supplier portal management — mint tokens, review the inbox, merge data.

Authenticated counterpart to ``pages/15_Supplier_Portal.py``. Org admins
and analysts mint per-supplier links here, watch the inbox fill up, and
merge clean submissions into the live ``supply_chain`` schema for the
next pipeline run.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from utils.auth import require_login, sidebar_auth_widget
from utils.rbac import require_permission
from utils.supplier_tokens import (
    SupplierToken,
    get_submission_store,
    get_token_store,
)
from utils.ui import hero, inject_global_css, pwc_header, section_header

st.set_page_config(
    page_title="Supplier Inbox | ESG Intelligence Hub",
    page_icon="📥",
    layout="wide",
)
inject_global_css()
pwc_header()
sidebar_auth_widget()
user = require_login("Sign in to manage supplier links.")
require_permission("manage_supplier_tokens")

org_id = (user.get("org_id") or "").strip() or "org_anonymous"
org_name = (user.get("org_name") or "").strip() or org_id

token_store = get_token_store()
submission_store = get_submission_store()

hero(
    title="Supplier Inbox",
    emoji="📥",
    subtitle=(
        "Mint single-use links for your suppliers, monitor incoming "
        "submissions, and merge them into your live supply-chain schema. "
        "No supplier-side login required — they fill a form and submit."
    ),
    chips=[
        f"Workspace: {org_name}",
        f"Active links: {sum(1 for t in token_store.list_tokens(org_id) if not t.revoked and not t.used_at)}",
        f"Pending submissions: {sum(1 for s in submission_store.list_submissions(org_id) if not s.merged)}",
    ],
)

# ---------------------------------------------------------------------------
# Mint a new token
# ---------------------------------------------------------------------------
section_header(
    "Issue a supplier link",
    "Send the resulting URL to your supplier — they fill a form and submit.",
)
with st.form("mint", clear_on_submit=True):
    c1, c2, c3 = st.columns([2, 2, 2])
    with c1:
        supplier_name = st.text_input("Supplier name", placeholder="ACME Industries")
    with c2:
        period = st.text_input("Reporting period", placeholder="Q3 2026")
    with c3:
        contact = st.text_input("Supplier contact email (optional)")
    notes = st.text_input("Internal notes (optional)")
    submitted = st.form_submit_button(
        "Mint single-use link", type="primary", use_container_width=True,
    )

if submitted:
    if not supplier_name.strip():
        st.error("Supplier name is required.")
    else:
        token = SupplierToken.mint(
            supplier_name=supplier_name,
            org_id=org_id,
            period=period,
            contact_email=contact,
            created_by=user.get("username", ""),
            notes=notes,
        )
        token_store.add_token(org_id, token)

        # Compose a copy/paste URL using the configured base if set, else
        # whatever the current Streamlit host serves at /Supplier_Portal.
        base = os.getenv("ESG_PUBLIC_URL", "").rstrip("/")
        suffix = f"/Supplier_Portal?t={token.token}"
        url = (base + suffix) if base else suffix
        st.success("Link minted — copy it and share with your supplier:")
        st.code(url, language="text")
        st.caption(
            "Set `ESG_PUBLIC_URL` (e.g. `https://your-space.hf.space`) for a "
            "fully-qualified URL in this confirmation."
        )

# ---------------------------------------------------------------------------
# Active tokens
# ---------------------------------------------------------------------------
section_header(
    "Active supplier links",
    "Single-use by default. Revoke a link if a supplier loses it or you "
    "need to regenerate.",
)
tokens = token_store.list_tokens(org_id)
if not tokens:
    st.info("No supplier links minted yet.")
else:
    rows = []
    for t in tokens:
        rows.append({
            "Supplier": t.supplier_name,
            "Period": t.period or "—",
            "Status": ("revoked" if t.revoked
                       else "used" if t.used_at
                       else "active"),
            "Created": (t.created_at[:16].replace("T", " ")
                        if t.created_at else ""),
            "Used at": (t.used_at[:16].replace("T", " ")
                        if t.used_at else "—"),
            "Token": t.token[:14] + "…",
            "_full_token": t.token,
        })
    df = pd.DataFrame(rows).drop(columns=["_full_token"])
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Per-row actions live below the table to keep the table clean
    revoke_target = st.selectbox(
        "Revoke a link",
        options=[""] + [f"{t.supplier_name} · {t.token[:14]}…"
                        for t in tokens
                        if not t.revoked and not t.used_at],
    )
    if revoke_target and st.button("Revoke selected link", type="secondary"):
        # Map back from "Name · prefix…" to the full token
        for t in tokens:
            label = f"{t.supplier_name} · {t.token[:14]}…"
            if label == revoke_target:
                if token_store.revoke_token(org_id, t.token):
                    st.success(f"Revoked link for {t.supplier_name}.")
                    st.rerun()
                break

# ---------------------------------------------------------------------------
# Submissions inbox
# ---------------------------------------------------------------------------
section_header(
    "Submissions",
    "Review supplier submissions and merge them into your live supply-chain "
    "schema. Merging publishes a row to `supply_chain` for the next run.",
)
submissions = submission_store.list_submissions(org_id)
if not submissions:
    st.info(
        "No supplier submissions yet. After you mint a link above and a "
        "supplier completes the form, their data will appear here."
    )
else:
    pending = [s for s in submissions if not s.merged]
    merged = [s for s in submissions if s.merged]
    st.caption(
        f"{len(pending)} pending · {len(merged)} merged · {len(submissions)} total"
    )

    for s in submissions:
        status = "✅ Merged" if s.merged else "📥 Pending"
        with st.expander(
            f"{status} · {s.supplier_name} · {s.period or '—'} "
            f"· {s.submitted_at[:16].replace('T', ' ')}",
            expanded=not s.merged and len(pending) <= 3,
        ):
            cols = st.columns([3, 1])
            with cols[0]:
                if s.submitted_by_email:
                    st.caption(f"Submitted by **{s.submitted_by_email}**")
                if s.rows:
                    st.dataframe(
                        pd.DataFrame(s.rows),
                        use_container_width=True,
                        hide_index=True,
                    )
                if s.merged:
                    st.caption(
                        f"Merged at {s.merged_at[:16].replace('T', ' ')} "
                        f"by {s.merged_by or '—'}"
                    )
            with cols[1]:
                if not s.merged:
                    if st.button("Merge into supply_chain",
                                 key=f"merge_{s.id}",
                                 type="primary",
                                 use_container_width=True):
                        # Publish to the per-user state bus so the next
                        # pipeline run picks it up under the canonical
                        # ``supply_chain`` schema. We deliberately don't
                        # rewrite anyone's persisted dataset — merge here
                        # is "include this row in the next run", not
                        # "store it forever".
                        try:
                            from core.state_manager import state_manager
                            existing = state_manager.subscribe(
                                "dataset_supply_chain"
                            ) or pd.DataFrame()
                            new_rows = pd.DataFrame(s.rows)
                            combined = (pd.concat([existing, new_rows],
                                                   ignore_index=True)
                                        if isinstance(existing, pd.DataFrame)
                                           and not existing.empty
                                        else new_rows)
                            state_manager.publish(
                                "dataset_supply_chain", combined,
                                "supplier_inbox",
                            )
                        except Exception as exc:  # noqa: BLE001
                            st.error(f"Could not publish merge: {exc}")
                        else:
                            submission_store.mark_merged(
                                org_id, s.id,
                                merged_by=user.get("username", ""),
                            )
                            st.success(
                                f"Merged {len(s.rows)} row(s) into supply_chain."
                            )
                            st.rerun()

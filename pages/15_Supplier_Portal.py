"""Supplier self-service portal — no login, token-only.

A supplier receives a tokenised URL (``/Supplier_Portal?t=<token>``)
from a buyer. They open it, fill in their ESG data for the period the
token was minted for, submit. The submission lands in the buyer's
per-org inbox.

This page is intentionally accessible without ``require_login()``: the
token *is* the credential. We keep the surface tiny — one form, one
submit — so suppliers actually fill it out.
"""
from __future__ import annotations

import json

import streamlit as st

from utils.notifications import Event, notify
from utils.supplier_tokens import (
    ALLOWED_FIELDS,
    NUMERIC_FIELDS,
    Submission,
    get_submission_store,
    get_token_store,
    validate_submission,
)
from utils.ui import hero, inject_global_css, pwc_header

st.set_page_config(
    page_title="Supplier Portal | ESG Intelligence Hub",
    page_icon="🤝",
    layout="centered",
)
inject_global_css()
pwc_header()

# ---------------------------------------------------------------------------
# Resolve the token from the URL
# ---------------------------------------------------------------------------
query = st.query_params
url_token = query.get("t") or query.get("token") or ""
if isinstance(url_token, list):
    url_token = url_token[0] if url_token else ""
url_token = (url_token or "").strip()

# Hide the sidebar nav on this page — suppliers should never see app
# pages. We don't render ``sidebar_auth_widget()`` for the same reason.
st.markdown(
    """
    <style>
        [data-testid="stSidebarNav"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

hero(
    title="Supplier ESG submission",
    emoji="🤝",
    subtitle=(
        "Thanks for sharing your ESG data with your buyer. "
        "Submissions go straight to their team — you don't need an account. "
        "Each link can only be used once."
    ),
)

if not url_token:
    st.error(
        "Missing token. The supplier link should look like "
        "`.../Supplier_Portal?t=<token>`. Contact your buyer to get a fresh link.",
    )
    st.stop()

token_store = get_token_store()
found = token_store.find_token(url_token)
if not found:
    st.error(
        "We couldn't find that link. It may have been deleted or never issued. "
        "Contact your buyer to get a fresh one."
    )
    st.stop()

owner_org, supplier_token = found
ok, reason = supplier_token.is_valid()
if not ok:
    st.error(reason)
    st.stop()

st.info(
    f"You're submitting on behalf of **{supplier_token.supplier_name}** "
    f"for **{supplier_token.period or 'the current reporting period'}**.",
    icon="✅",
)

# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------
with st.form("supplier_form", clear_on_submit=False):
    st.markdown("### Your reporting period figures")
    contact_email = st.text_input(
        "Your email (for follow-up)",
        value=supplier_token.contact_email or "",
        placeholder="you@example.com",
    )

    c1, c2 = st.columns(2)
    with c1:
        scope3 = st.number_input(
            "Scope 3 emissions (tCO₂e)", min_value=0.0, step=10.0, value=0.0,
            help="Estimated tonnes of CO₂-equivalent emissions across your operations.",
        )
        energy = st.number_input(
            "Total energy consumption (kWh)", min_value=0.0, step=100.0, value=0.0,
        )
        renewable_pct = st.number_input(
            "Renewable energy share (%)", min_value=0.0, max_value=100.0,
            step=1.0, value=0.0,
        )
        water = st.number_input(
            "Water consumption (kilolitres)", min_value=0.0, step=10.0, value=0.0,
        )
    with c2:
        waste = st.number_input(
            "Waste generated (kg)", min_value=0.0, step=10.0, value=0.0,
        )
        diversity_pct = st.number_input(
            "Workforce diversity (%)", min_value=0.0, max_value=100.0,
            step=1.0, value=0.0,
            help="Share of women / under-represented groups in your workforce.",
        )
        lti = st.number_input(
            "Lost-time incidents (count)", min_value=0, step=1, value=0,
        )
        esg_score = st.number_input(
            "Self-reported ESG score (0–100, optional)",
            min_value=0.0, max_value=100.0, step=1.0, value=0.0,
        )

    notes = st.text_area(
        "Notes (optional)",
        placeholder="Anything else your buyer should know — methodology caveats, "
                    "exclusions, certifications, ...",
        height=100,
    )
    consent = st.checkbox(
        "I confirm the data above is accurate to the best of my knowledge "
        "and may be used by the buyer for ESG reporting.",
    )
    submitted = st.form_submit_button(
        "Submit ESG data", type="primary", use_container_width=True,
    )

if submitted:
    if not consent:
        st.error("Please confirm the data accuracy statement to submit.")
        st.stop()

    row = {
        "supplier_name": supplier_token.supplier_name,
        "scope3_emissions_tco2e": scope3,
        "energy_consumption_kwh": energy,
        "renewable_energy_pct": renewable_pct,
        "water_consumption_kl": water,
        "waste_kg": waste,
        "diversity_pct": diversity_pct,
        "lost_time_incidents": lti,
        "esg_score": esg_score,
        "notes": notes,
    }
    clean_rows, errors = validate_submission([row])
    if errors:
        st.error(
            "Some fields couldn't be processed:\n\n"
            + "\n".join(f"• {e}" for e in errors)
        )
        st.stop()

    submission = Submission.new(
        org_id=owner_org,
        token=url_token,
        supplier_name=supplier_token.supplier_name,
        period=supplier_token.period,
        rows=clean_rows,
        submitted_by_email=contact_email.strip(),
    )
    get_submission_store().add_submission(owner_org, submission)
    # Single-use token — mark it spent so the same link can't be replayed.
    token_store.patch_token(owner_org, url_token, {"used_at": submission.submitted_at})

    # Best-effort fan-out to the buyer's notification routes so the
    # data hits Slack/Teams/email the moment it arrives.
    try:
        notify(
            Event(
                type="supplier_submission_received",
                title=f"Supplier submission · {supplier_token.supplier_name}",
                summary=(
                    f"{supplier_token.supplier_name} submitted ESG data for "
                    f"{supplier_token.period or 'the current reporting period'} "
                    f"with {len(clean_rows)} row(s)."
                ),
                severity="info",
                actor=contact_email.strip() or supplier_token.supplier_name,
                payload={"submission_id": submission.id, "rows": len(clean_rows)},
            ),
            owner=owner_org,
        )
    except Exception:  # noqa: BLE001 — never block the supplier on notifications
        pass

    st.success(
        f"✅ Thank you. Your submission has been received by your buyer "
        f"(reference: `{submission.id}`). You can close this tab.",
    )
    st.balloons()

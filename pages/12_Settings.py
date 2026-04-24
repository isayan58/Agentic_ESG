"""Settings — per-user company profile.

Lets each signed-in user edit their own company profile (name, sector,
financials, ESG posture, material topics, frameworks). The profile is
persisted to the per-user store and bound to ``company_cfg`` for every
subsequent agent run, so the entire platform — narratives, charts,
thresholds — is personalised to whatever the user enters here.

Guests are redirected to sign-in: there is nowhere durable to save a
guest profile, and we don't want them editing the bundled defaults.
"""
import json

import streamlit as st

from utils.auth import require_login, sidebar_auth_widget
from utils.profile_store import ProfileConflict
from utils.profile_validator import validate_profile
from utils.session import (
    get_session_company_config,
    get_session_company_profile,
    save_session_company_profile,
)
from utils.ui import inject_global_css, pwc_header


st.set_page_config(page_title="Settings | ESG Pilot", page_icon="⚙️", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
user = require_login("Sign in to manage your company profile.")
get_session_company_config()  # bind active config for this rerun

st.title("⚙️ Settings — Your Company Profile")
st.markdown(
    f"*Personalises every agent, KPI, and AI narrative for **{user['username']}**. "
    "Changes save to your private profile and apply on the next pipeline run.*"
)

# If the last CompanyConfig build rejected the stored profile, tell the
# user loudly — otherwise they'd silently see the bundled default on
# every other page without knowing why their edits aren't showing up.
_build_error = st.session_state.get("_company_cfg_build_error")
if _build_error:
    st.error(
        f"⚠️ Your stored profile is not loading — all agents are currently "
        f"using the bundled default. **{_build_error}** Fix the issues "
        "below and save again, or use the Reset button to start from the default."
    )

st.markdown("---")

# Load the current profile (mutable copy).
profile = get_session_company_profile()


def _list_text(values):
    return "\n".join(values or [])


def _parse_list(text: str):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


tab_identity, tab_financials, tab_esg, tab_advanced = st.tabs([
    "Identity", "Financials", "ESG posture", "Advanced (raw JSON)"
])

with tab_identity:
    st.subheader("Company identity")
    col1, col2 = st.columns(2)
    with col1:
        company_name = st.text_input(
            "Company name", value=profile.get("company_name", ""),
            help="Displayed in every narrative and report header.")
        sector = st.text_input("Sector", value=profile.get("sector", ""))
        sub_sector = st.text_input("Sub-sector", value=profile.get("sub_sector", ""))
        founded = st.number_input(
            "Founded (year)", min_value=0, max_value=2100,
            value=int(profile.get("founded") or 0))
    with col2:
        headquarters = st.text_input("Headquarters", value=profile.get("headquarters", ""))
        employees = st.number_input(
            "Employees", min_value=0,
            value=int(profile.get("employees") or 0))
        offices_text = st.text_area(
            "Offices (one per line)", value=_list_text(profile.get("offices")),
            height=100)
        countries_text = st.text_area(
            "Operating countries (one per line)",
            value=_list_text(profile.get("operating_countries")),
            height=100)
    exchanges_text = st.text_area(
        "Listed exchanges (one per line)",
        value=_list_text(profile.get("listed_exchanges")),
        height=80)

with tab_financials:
    st.subheader("Financials")
    currency_unit = st.text_input(
        "Currency unit", value=profile.get("currency_unit", "INR lakhs"),
        help="Free-text label shown in cost figures.")
    rev = profile.get("revenue") or {}
    col1, col2 = st.columns(2)
    with col1:
        rev_curr_usd = st.number_input(
            "Current revenue (USD millions)",
            min_value=0.0, value=float(rev.get("current_usd_millions") or 0))
        rev_prev_usd = st.number_input(
            "Previous revenue (USD millions)",
            min_value=0.0, value=float(rev.get("previous_usd_millions") or 0))
    with col2:
        rev_curr_local = st.number_input(
            f"Current revenue (local — {currency_unit})",
            min_value=0.0, value=float(rev.get("current_local") or 0))
        rev_prev_local = st.number_input(
            f"Previous revenue (local — {currency_unit})",
            min_value=0.0, value=float(rev.get("previous_local") or 0))
    market_cap = st.number_input(
        "Market cap (INR crores)", min_value=0.0,
        value=float(profile.get("market_cap_inr_crores") or 0))
    col3, col4 = st.columns(2)
    with col3:
        current_fy = st.number_input(
            "Current FY", min_value=2000, max_value=2100,
            value=int(profile.get("current_fy") or 2024))
    with col4:
        previous_fy = st.number_input(
            "Previous FY", min_value=2000, max_value=2100,
            value=int(profile.get("previous_fy") or (current_fy - 1)))

with tab_esg:
    st.subheader("ESG posture & commitments")
    col1, col2 = st.columns(2)
    with col1:
        esg_rating_current = st.text_input(
            "Current ESG rating", value=profile.get("esg_rating_current", ""))
        esg_rating_target = st.text_input(
            "Target ESG rating", value=profile.get("esg_rating_target", ""))
    with col2:
        frameworks_adopted = st.text_area(
            "Frameworks adopted (one per line)",
            value=_list_text(profile.get("frameworks_adopted")), height=110)
        frameworks_planned = st.text_area(
            "Frameworks planned (one per line)",
            value=_list_text(profile.get("frameworks_planned")), height=110)
    commitments_text = st.text_area(
        "Key commitments (one per line)",
        value=_list_text(profile.get("key_commitments")), height=140,
        help="Used by AI narratives across every report and recommendation.")
    materials_text = st.text_area(
        "Material topics (one per line)",
        value=_list_text(profile.get("material_topics")), height=140)

with tab_advanced:
    st.subheader("Raw profile JSON")
    st.caption(
        "Power-user escape hatch — edit the entire profile as JSON. "
        "Useful for tuning thresholds, risk weights, scenario parameters, "
        "or sector-risk defaults. Saved as-is; invalid JSON is rejected.")
    raw_json = st.text_area(
        "Profile JSON",
        value=json.dumps(profile, indent=2, ensure_ascii=False),
        height=400, key="raw_profile_json",
        label_visibility="collapsed")
    raw_save = st.button("Save raw JSON only", key="save_raw_json")
    if raw_save:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
        else:
            # Structural check before commit — prevents a malformed
            # paste from saving successfully and then crashing the
            # next page load when CompanyConfig tries to read it.
            validation_errors = validate_profile(parsed)
            if validation_errors:
                st.error("Profile failed validation — fix the issues below and retry:")
                for err in validation_errors:
                    st.markdown(f"- {err}")
            else:
                try:
                    save_session_company_profile(parsed)
                except ProfileConflict as conflict:
                    st.session_state["_settings_conflict"] = {
                        "pending_profile": parsed,
                        "current_profile": conflict.current_profile,
                        "message": str(conflict),
                    }
                    st.rerun()
                else:
                    st.success("Raw profile saved. Reload any agent page to "
                               "see the new values flow through.")
                    st.rerun()

st.markdown("---")
col_save, col_reset, _ = st.columns([1, 1, 3])
with col_save:
    save_clicked = st.button("💾 Save changes", type="primary",
                             use_container_width=True)
with col_reset:
    reset_clicked = st.button("↺ Reset to default profile",
                              use_container_width=True)

if reset_clicked:
    from utils.profile_store import get_profile_store
    save_session_company_profile(get_profile_store().default_profile())
    st.success("Profile reset to the bundled default.")
    st.rerun()

if save_clicked:
    # Merge form fields back into the existing profile so we don't drop
    # any keys the form doesn't expose (advanced sections like
    # `sector_risk_defaults`, `action_cost_templates`, etc.).
    updated = dict(profile)
    updated.update({
        "company_name": company_name.strip() or "Your Company",
        "sector": sector.strip(),
        "sub_sector": sub_sector.strip(),
        "headquarters": headquarters.strip(),
        "founded": int(founded),
        "employees": int(employees),
        "offices": _parse_list(offices_text),
        "operating_countries": _parse_list(countries_text),
        "listed_exchanges": _parse_list(exchanges_text),
        "currency_unit": currency_unit.strip() or "INR lakhs",
        "revenue": {
            "current_usd_millions": rev_curr_usd,
            "previous_usd_millions": rev_prev_usd,
            "current_local": rev_curr_local,
            "previous_local": rev_prev_local,
        },
        "market_cap_inr_crores": market_cap,
        "current_fy": int(current_fy),
        "previous_fy": int(previous_fy),
        "esg_rating_current": esg_rating_current.strip(),
        "esg_rating_target": esg_rating_target.strip(),
        "frameworks_adopted": _parse_list(frameworks_adopted),
        "frameworks_planned": _parse_list(frameworks_planned),
        "key_commitments": _parse_list(commitments_text),
        "material_topics": _parse_list(materials_text),
    })

    try:
        save_session_company_profile(updated)
    except ProfileConflict as conflict:
        # Stash the in-flight edit so we can offer "overwrite anyway".
        st.session_state["_settings_conflict"] = {
            "pending_profile": updated,
            "current_profile": conflict.current_profile,
            "message": str(conflict),
        }
        st.rerun()
    except Exception as exc:
        st.error(f"Couldn't save profile: {exc}")
    else:
        st.success(
            f"Profile saved for **{user['username']}**. Your changes "
            "apply to every agent the next time you run them.")

# ── Conflict banner ────────────────────────────────────────────────
# Shown after a save was rejected because another tab / replica wrote
# to this user's profile between load and save. We surface both sides
# so the user can choose reload vs. overwrite instead of silently
# clobbering.
conflict = st.session_state.get("_settings_conflict")
if conflict:
    st.markdown("---")
    st.warning(
        "⚠️ **Save conflict.** " + conflict["message"],
        icon="⚠️",
    )
    col_reload, col_force, col_cancel = st.columns(3)
    with col_reload:
        if st.button("↻ Reload latest", use_container_width=True):
            # Drop our cached profile so the next get_ call re-reads
            # from the store and captures a fresh token.
            st.session_state.pop("company_profile", None)
            st.session_state.pop("_company_profile_token", None)
            st.session_state.pop("_settings_conflict", None)
            st.rerun()
    with col_force:
        if st.button("💥 Overwrite anyway", type="primary",
                     use_container_width=True):
            try:
                save_session_company_profile(
                    conflict["pending_profile"], force=True,
                )
                st.session_state.pop("_settings_conflict", None)
                st.success("Profile saved (other writer's changes discarded).")
                st.rerun()
            except Exception as exc:  # pragma: no cover - defensive
                st.error(f"Couldn't force-save: {exc}")
    with col_cancel:
        if st.button("✕ Dismiss", use_container_width=True):
            st.session_state.pop("_settings_conflict", None)
            st.rerun()
    with st.expander("Show the other writer's version"):
        st.code(
            json.dumps(conflict["current_profile"], indent=2, ensure_ascii=False),
            language="json",
        )

# ── Storage diagnostic ──────────────────────────────────────────────
from utils.profile_store import get_profile_store

with st.expander("Where is my profile stored?"):
    diag = get_profile_store().diagnostic()
    backend = diag["backend"] or "unresolved"
    color = (
        "#16a34a" if backend == "hf_dataset"
        else ("#d97706" if backend == "local_json" else "#6b7280")
    )
    st.markdown(
        f"<div style='padding:0.5rem 0.75rem; border-radius:8px; "
        f"background:{color}20; border-left:4px solid {color};'>"
        f"<strong>Backend:</strong> {diag['label']}<br>"
        f"<small>Dataset: <code>{diag['dataset']}</code> · "
        f"HF token loaded: {'yes' if diag['has_token'] else 'no'}</small>"
        "</div>",
        unsafe_allow_html=True,
    )
    if diag["last_error"]:
        st.warning(
            f"Last persistence error ({diag['last_error_at']}): "
            f"{diag['last_error']}")

    # Operator-visible signal when the bundled default profile file is
    # missing / corrupt — otherwise every new signup silently starts on
    # an empty profile and nobody notices the bad deploy.
    default_status = diag.get("default_profile_status")
    if default_status and default_status != "ok":
        st.warning(
            f"⚠️ **Default profile unavailable** ({default_status}): "
            f"{diag.get('default_profile_reason') or '(no details)'}"
        )

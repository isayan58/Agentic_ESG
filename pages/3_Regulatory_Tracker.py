"""Streamlit page for the Regulatory Tracker Agent — with 24h auto-updates and Compliance Radar."""
import streamlit as st
import pandas as pd
from agents.regulatory_tracker import RegulatoryTrackerAgent
from utils.charts import compliance_radar, chart_unavailable_message
from utils.monitoring import regulatory_updater
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, page_agent_header_live, pwc_header
from utils.pipeline_refresh import data_freshness_caption
from utils.gap_suggestions import suggestions_for_gap, render_suggestion_block
from utils.framework_refresh import (
    TRACKED_FRAMEWORKS,
    apply_update,
    dismiss_update,
    load_updates_store,
    pending_updates,
    applied_updates,
    dismissed_updates,
    refresh_and_store,
    time_since_last_check,
)

st.set_page_config(page_title="Regulatory Tracker | ESG Intelligence Hub", page_icon="📋", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Regulatory Tracker agent.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="regulatory_tracker",
    agent_icon="📋",
)

st.title("📋 Regulatory Tracker Agent")
st.markdown("*Monitors global ESG frameworks — auto-updates within 24 hours of any mandate shift*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "reg_tracker" not in st.session_state:
    st.session_state.reg_tracker = RegulatoryTrackerAgent()
    st.session_state.reg_tracker_results = None

agent = st.session_state.reg_tracker


def render_chart(fig):
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(fig, use_container_width=True)

# Framework selection — includes US frameworks (SOX, SEC Climate Rule)
frameworks_display = st.multiselect(
    "Frameworks to analyze",
    list(TRACKED_FRAMEWORKS),
    default=list(TRACKED_FRAMEWORKS),
)

if st.button("🔄 Run Compliance Analysis", type="primary"):
    with st.spinner("Analyzing regulatory compliance..."):
        results = agent.run()
        st.session_state.reg_tracker_results = results
    st.success("Compliance analysis complete!")

results = st.session_state.reg_tracker_results
if results and "error" not in results:
    st.markdown("---")

    # Overall compliance KPI
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Overall Compliance", f"{results.get('overall_compliance', 0)}%")
    with k2:
        st.metric("Frameworks Analyzed", results.get("frameworks_analyzed", 0))
    with k3:
        total_gaps = sum(len(fr.get("gaps", [])) for fr in results.get("framework_results", {}).values())
        st.metric("Total Gaps", total_gaps)
    with k4:
        _store = load_updates_store()
        st.metric("Pending Updates", len(pending_updates(_store)))

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Compliance Radar", "Gap Analysis", "Global Framework Updates", "AI Narrative"
    ])

    with tab1:
        fw_results = results.get("framework_results", {})
        scores = {fw: data["compliance_pct"] for fw, data in fw_results.items() if fw in frameworks_display}
        if scores:
            fig = compliance_radar(scores)
            render_chart(fig)

        # Framework details table
        rows = []
        for fw, data in fw_results.items():
            if fw in frameworks_display:
                rows.append({
                    "Framework": fw,
                    "Full Name": data.get("full_name", ""),
                    "Mandatory": "Yes" if data.get("mandatory") else "No",
                    "Compliance": f"{data['compliance_pct']}%",
                    "Covered": data["covered"],
                    "Partial": data["partial"],
                    "Missing": data["missing"],
                    "Total": data["total"],
                })
        if rows:
            safe_dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with tab2:
        st.caption(
            "Each gap below is paired with a **Fix this gap** expander that "
            "tells you exactly which ESG schema to upload and what columns it "
            "should contain. Head to the **Data Collector** page to add the "
            "suggested dataset."
        )
        _priority_icons = {
            "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢",
        }
        for fw, data in fw_results.items():
            if fw not in frameworks_display:
                continue
            gaps = data.get("gaps", [])
            if not gaps:
                continue
            st.markdown(f"#### {fw} Gaps ({len(gaps)})")
            gap_rows = []
            for gap in gaps:
                icon = _priority_icons.get(gap["priority"], "⚪")
                gap_rows.append({
                    "ID": gap["requirement_id"],
                    "Requirement": gap["requirement"],
                    "Status": gap["status"].capitalize(),
                    "Priority": f"{icon} {gap['priority'].capitalize()}",
                    "Reason": gap["reason"],
                })
            safe_dataframe(
                pd.DataFrame(gap_rows),
                use_container_width=True,
                hide_index=True,
            )

            # Per-gap actionable fix hints. Critical/high first so
            # skimming the page surfaces the urgent ones up top.
            st.markdown("##### How to close these gaps")
            sorted_gaps = sorted(
                gaps,
                key=lambda g: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(
                    g.get("priority", "medium"), 9
                ),
            )
            for gap in sorted_gaps:
                suggestions = suggestions_for_gap(gap)
                icon = _priority_icons.get(gap["priority"], "⚪")
                with st.expander(
                    f"{icon} Fix **{gap['requirement_id']}** — {gap['requirement']}"
                ):
                    missing = gap.get("missing_fields") or []
                    if missing:
                        st.markdown(
                            "**Missing data fields:** "
                            + ", ".join(f"`{f}`" for f in missing)
                        )
                    if not suggestions:
                        st.info(
                            "No tailored dataset suggestion available for "
                            "this gap yet. Consider uploading a custom "
                            "`esg_metrics` CSV with a `data_source` column "
                            "that cites the governance document or policy "
                            "that satisfies this requirement."
                        )
                        continue
                    for i, sugg in enumerate(suggestions):
                        if i:
                            st.markdown("---")
                        render_suggestion_block(st, sugg)

    with tab3:
        store = load_updates_store()
        pending = pending_updates(store)
        applied = applied_updates(store)
        dismissed = dismissed_updates(store)

        st.markdown("#### Global Framework Updates")
        st.caption(
            "Claude searches authoritative sources (SEBI, EFRAG, SEC, PCAOB, "
            "GRI, IFRS/SASB) for recent changes to the frameworks you track. "
            "Every change lands here for human approval before it modifies the "
            "live framework set."
        )

        ru1, ru2, ru3, ru4 = st.columns(4)
        with ru1:
            st.metric("Last checked", time_since_last_check(store))
        with ru2:
            st.metric("Pending review", len(pending))
        with ru3:
            st.metric("Applied", len(applied))
        with ru4:
            st.metric("Dismissed", len(dismissed))

        refresh_col, status_col = st.columns([1, 3])
        with refresh_col:
            do_refresh = st.button("🌐 Check for global updates now", type="primary", use_container_width=True)
        with status_col:
            if store.get("last_error"):
                st.error(f"Last refresh failed: {store['last_error']}", icon="⚠️")
            elif store.get("last_checked"):
                st.caption(f"Last successful refresh: {store['last_checked']}")

        if do_refresh:
            with st.spinner("Searching authoritative sources for framework updates…"):
                store = refresh_and_store()
            if store.get("last_error"):
                st.error(f"Refresh failed: {store['last_error']}", icon="⚠️")
            else:
                added = store.get("last_added_count", 0)
                if added:
                    st.success(f"Found {added} new update(s) — review below.", icon="✅")
                else:
                    st.info("No new updates since last check.", icon="✨")
            pending = pending_updates(store)
            applied = applied_updates(store)
            dismissed = dismissed_updates(store)

        # ── Pending updates — approval queue ──
        st.markdown("##### Pending review")
        if not pending:
            st.caption("No pending updates. Click **Check for global updates now** to refresh.")
        else:
            _impact_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
            for upd in sorted(pending, key=lambda u: u.get("detected_at", ""), reverse=True):
                fw = upd.get("framework", "?")
                title = upd.get("title", "(untitled)")
                impact = upd.get("impact", "medium")
                with st.expander(f"{_impact_icon.get(impact, '⚪')} {fw} — {title}"):
                    st.markdown(f"**Type:** {upd.get('type', 'update')}")
                    st.markdown(f"**Description:** {upd.get('description', '—')}")
                    eff = upd.get("effective_date")
                    if eff:
                        st.markdown(f"**Effective date:** {eff}")
                    src = upd.get("source_url")
                    if src:
                        st.markdown(f"**Source:** [{src}]({src})")
                    st.markdown(f"**Detected at:** {upd.get('detected_at', '—')}")
                    prop = upd.get("proposed_requirement")
                    if prop:
                        st.markdown("**Proposed new requirement:**")
                        safe_dataframe(
                            pd.DataFrame([{
                                "ID": prop.get("id"),
                                "Section": prop.get("section"),
                                "Requirement": prop.get("requirement"),
                                "Data fields": ", ".join(prop.get("data_fields") or []),
                                "Priority": prop.get("priority"),
                            }]),
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.caption("No new requirement proposed — this is a guidance / deadline update for awareness only.")

                    ac, dc = st.columns(2)
                    with ac:
                        if st.button("✅ Apply update", key=f"apply_{upd['id']}", type="primary", use_container_width=True):
                            result = apply_update(upd["id"])
                            if result.get("ok"):
                                st.success("Applied. The framework set has been updated.", icon="✅")
                                st.rerun()
                            else:
                                st.error(result.get("reason", "Apply failed."), icon="⚠️")
                    with dc:
                        if st.button("🗑️ Dismiss", key=f"dismiss_{upd['id']}", use_container_width=True):
                            dismiss_update(upd["id"], reason="Dismissed by reviewer")
                            st.rerun()

        # ── Applied history ──
        if applied:
            with st.expander(f"📘 Applied updates ({len(applied)})", expanded=False):
                safe_dataframe(
                    pd.DataFrame([{
                        "Framework": u.get("framework"),
                        "Title": u.get("title"),
                        "Applied at": u.get("applied_at"),
                        "Source": u.get("source_url"),
                    } for u in sorted(applied, key=lambda u: u.get("applied_at", ""), reverse=True)]),
                    use_container_width=True,
                    hide_index=True,
                )

        # ── Dismissed audit trail ──
        if dismissed:
            with st.expander(f"🗑️ Dismissed updates ({len(dismissed)})", expanded=False):
                safe_dataframe(
                    pd.DataFrame([{
                        "Framework": u.get("framework"),
                        "Title": u.get("title"),
                        "Dismissed at": u.get("dismissed_at"),
                        "Reason": u.get("dismiss_reason", ""),
                        "Source": u.get("source_url"),
                    } for u in sorted(dismissed, key=lambda u: u.get("dismissed_at", ""), reverse=True)]),
                    use_container_width=True,
                    hide_index=True,
                )

    with tab4:
        narrative = results.get("gap_narrative", "")
        if narrative:
            st.markdown("#### AI-Generated Gap Analysis")
            st.markdown(narrative)

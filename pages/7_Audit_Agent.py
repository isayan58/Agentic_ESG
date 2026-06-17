"""Streamlit page for the Audit Agent."""
import streamlit as st
import pandas as pd
from agents.audit_agent import AuditAgent
from utils.streamlit_compat import safe_dataframe
from utils.auth import require_login, sidebar_auth_widget
from utils.ui import inject_global_css, page_agent_header_live, pwc_header
from utils.pipeline_refresh import data_freshness_caption
from utils.gap_suggestions import (
    suggestion_for_audit_dataset,
    render_suggestion_block,
)

st.set_page_config(page_title="Audit Agent | ESG Intelligence Hub", page_icon="🔍", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to access the Audit Agent.")

# Top-of-page status strip — shows the signed-in user, the current
# agent, and the agent's LIVE status (auto-refreshes while running).
page_agent_header_live(
    agent_key="audit_agent",
    agent_icon="🔍",
)

st.title("🔍 Audit Agent")
st.markdown("*Compliance verification, data auditing, and audit trail management*")
data_freshness_caption(can_refresh=False)
st.markdown("---")

if "audit_agent" not in st.session_state:
    st.session_state.audit_agent = AuditAgent()
    st.session_state.audit_results = None

agent = st.session_state.audit_agent

st.info("For best results, run Data Collector, Regulatory Tracker, and Carbon Accountant first.")

if st.button("🔄 Run Audit Verification", type="primary"):
    with st.spinner("Running compliance audit..."):
        results = agent.run()
        st.session_state.audit_results = results
    st.success("Audit complete!")

results = st.session_state.audit_results
if results and "error" not in results:
    st.markdown("---")

    readiness = results.get("readiness_score", {})
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Audit Readiness", f"{readiness.get('overall', 0):.0f}%")
    with k2:
        st.metric("Grade", readiness.get("grade", "N/A"))
    with k3:
        st.metric("Issues Found", results.get("issues_count", 0))
    with k4:
        st.metric("Evidence Score", f"{readiness.get('evidence', 0):.0f}%")

    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Readiness Breakdown", "Compliance Checklist", "Data Completeness", "Audit Trail"
    ])

    with tab1:
        st.markdown("#### Readiness Score Components")
        components = {
            "Data Completeness": readiness.get("completeness", 0),
            "Compliance Score": readiness.get("compliance", 0),
            "Evidence Verifiability": readiness.get("evidence", 0),
        }
        for comp_name, score in components.items():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(min(score / 100, 1.0), text=f"{comp_name}: {score:.0f}%")
            with col2:
                status = "✅" if score >= 80 else ("⚠️" if score >= 60 else "❌")
                st.markdown(f"### {status}")

    with tab2:
        checklist = results.get("compliance_checklist", [])
        if checklist:
            status_icon = {"Pass": "✅", "Warning": "⚠️", "Fail": "❌"}
            rows = []
            for item in checklist:
                rows.append({
                    "Status": status_icon.get(item["status"], "⚪"),
                    "Framework": item.get("framework", "General"),
                    "Requirement": item.get("requirement", ""),
                    "Score": f"{item.get('score', 'N/A')}%",
                    "Result": item["status"],
                })
            df = pd.DataFrame(rows)
            safe_dataframe(df, use_container_width=True, hide_index=True)

    with tab3:
        completeness = results.get("completeness_audit", [])
        if completeness:
            # Status summary first so skimmers see the counts immediately.
            _weak = [
                item for item in completeness
                if item["status"] in {"Warning", "Fail", "Missing"}
            ]
            if _weak:
                st.caption(
                    f"{len(_weak)} dataset(s) need attention. Each row below "
                    "with a ⚠️ / ❌ / 🚫 status has a **Fix this gap** "
                    "expander pointing at the Data Collector schema to upload."
                )
            for item in completeness:
                status_icon = {"Pass": "✅", "Warning": "⚠️", "Fail": "❌", "Missing": "🚫"}.get(item["status"], "⚪")
                priority_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(item["priority"], "⚪")
                st.markdown(
                    f"{status_icon} **{item['dataset']}** — "
                    f"Completeness: {item['completeness']}% | "
                    f"Records: {item['records']} | "
                    f"Priority: {priority_icon} {item['priority'].capitalize()}"
                )
                # Only show the gap-fix hint for datasets that aren't
                # already passing — keeps the passing rows compact.
                if item["status"] in {"Warning", "Fail", "Missing"}:
                    sugg = suggestion_for_audit_dataset(item["dataset"])
                    with st.expander(
                        f"🛠️ Fix this gap — add / improve `{item['dataset']}`"
                    ):
                        if sugg is None:
                            st.info(
                                "No tailored dataset suggestion — upload a "
                                "custom CSV via the Data Collector and map "
                                "it to the closest ESG schema."
                            )
                        else:
                            render_suggestion_block(st, sugg)
                            if item["status"] != "Missing":
                                st.caption(
                                    f"Current completeness is "
                                    f"{item['completeness']}% ({item['records']} "
                                    "records). Adding more rows to the "
                                    "existing source will also lift this score."
                                )

    with tab4:
        trail = results.get("audit_trail", [])
        if trail:
            # Verify chain integrity
            import hashlib, json as _json
            chain_intact = True
            prev_hash = "0" * 64
            for entry in trail:
                stored_hash = entry.get("chain_hash", "")
                payload = _json.dumps(
                    {k: v for k, v in entry.items() if k != "chain_hash"},
                    sort_keys=True, default=str,
                )
                expected = hashlib.sha256((prev_hash + payload).encode()).hexdigest()
                if stored_hash != expected:
                    chain_intact = False
                    break
                prev_hash = stored_hash

            if chain_intact:
                st.success(f"✅ Audit trail integrity verified — {len(trail)} entries, hash-chain intact")
            else:
                st.error("⚠️ Audit trail integrity check FAILED — chain hash mismatch detected")

            for entry in trail:
                chain_hash = entry.get("chain_hash", "")
                short_hash = f"`…{chain_hash[-8:]}`" if chain_hash else ""
                st.markdown(
                    f"- `{entry['timestamp'][:19]}` — **{entry['event']}** "
                    f"(by {entry['agent']}) — {entry['status']} {short_hash}"
                )
        else:
            st.info("No audit trail entries yet. Run the full pipeline to populate.")

    # Findings summary
    st.markdown("---")
    st.markdown("#### AI Findings Summary")
    gap_analysis = results.get("gap_analysis") or {}
    if gap_analysis.get("specific_gaps"):
        from utils.gap_analyzer import render_specific_gaps
        render_specific_gaps(
            st, gap_analysis,
            heading="Field-level audit gaps",
        )
    else:
        st.markdown(results.get("findings_summary", ""))

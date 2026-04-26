"""Mission Control — Full pipeline overview with business impact, pipeline visualization, and transformation view."""
import io
import json
import os
from datetime import datetime
import pandas as pd
import streamlit as st
import anthropic
import config
from core.orchestrator import Orchestrator
from config import AGENT_CONFIG
from utils.charts import (
    pipeline_flow_diagram,
    before_after_comparison, enterprise_stack_layers, tier_comparison_chart,
    chart_unavailable_message, apply_chart_theme,
)
from utils.streamlit_compat import safe_dataframe
from utils.monitoring import monitoring_engine
from utils.ui import (
    hero, section_header, kpi_card, agent_card, pipeline_chips,
    badge, grade_pill, inject_global_css, pwc_header,
    log_panel, retry_button, drilldown, live_badge, collect_audit_trail,
    format_relative_time, esg_roi_featured_card,
)
from utils.auth import require_login, sidebar_auth_widget
from utils.pipeline_refresh import stamp_refresh_from_pipeline
from utils.session import get_session_connection_manager
from utils.data_gaps import compute_data_gaps
from utils import agent_telemetry
from utils.run_store import get_run_store

st.set_page_config(page_title="Mission Control | ESG Intelligence Hub", page_icon="🎛️", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to run the 9-agent pipeline and view Mission Control.")
# Hydrate (or rebuild) this user's persistent ConnectionManager as early
# as possible so the Run buttons below see sources the user registered
# in a previous session.
get_session_connection_manager()

hero(
    title="Mission Control",
    emoji="🎛️",
    subtitle=(
        "Orchestrate all 9 agents — the command center for autonomous ESG intelligence. "
        "Run the full pipeline, monitor agent health in real time, and drill into the "
        "business lens behind every metric."
    ),
    chips=[
        "9 Agents · Orchestrated",
        "Shared-state pub/sub",
        "BRSR · CSRD · GRI · SASB · SOX · SEC",
        "AI-generated reports, dashboards, and insights",
    ],
)

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()
if "pipeline_results" not in st.session_state:
    st.session_state.pipeline_results = None

orch = st.session_state.orchestrator


def render_chart(fig):
    """Render Plotly charts when available, otherwise show a fallback note.
    Applies the design-system theme so every chart inherits the PwC palette."""
    if fig is None:
        st.info(chart_unavailable_message())
    else:
        st.plotly_chart(apply_chart_theme(fig), use_container_width=True)


def signal_label(value, good_threshold, watch_threshold=None):
    """Return a simple status label for layman-friendly hypothesis tables."""
    if value is None:
        return "Not available"
    if watch_threshold is None:
        watch_threshold = good_threshold * 0.7
    if value >= good_threshold:
        return "Positive signal"
    if value >= watch_threshold:
        return "Mixed signal"
    return "Needs attention"


# ── Featured ESG ROI Agent card ──
# Mission Control is the new home — surface the headline investment-quality
# card at the top so signed-in users see their live numbers first.
_roi_results = None
try:
    _roi_agent_obj = getattr(orch, "agents", {}).get("roi_agent")
    if _roi_agent_obj is not None:
        _r = getattr(_roi_agent_obj, "results", None)
        if _r:
            _roi_results = _r
except Exception:
    _roi_results = None

_mc_user = st.session_state.get("user") or {}
_mc_user_name = (_mc_user.get("full_name") or _mc_user.get("username") or "").strip() or None

esg_roi_featured_card(
    results=_roi_results,
    mode="auto",
    user_name=_mc_user_name,
    height=440,
)

roi_cta_cols = st.columns([1.2, 1, 3])
with roi_cta_cols[0]:
    if st.button(
        "⭐  Open ROI Dashboard  →",
        type="primary",
        use_container_width=True,
        key="mc_featured_roi_open",
    ):
        try:
            st.switch_page("pages/11_ESG_ROI_Agent.py")
        except Exception:
            st.info("Open ESG ROI Agent from the sidebar.")

# ── Agent Fleet Status ──
section_header("Agent Fleet Status",
               "Every agent in the orchestrated pipeline with its most recent run.")
statuses = orch.get_agent_statuses()
fleet_head_l, fleet_head_r = st.columns([5, 1])
with fleet_head_l:
    pipeline_chips(statuses, AGENT_CONFIG)
with fleet_head_r:
    if any((s.get("status") or "idle").lower() == "running" for s in statuses.values()):
        live_badge("Live")

cols = st.columns(4)
for i, (key, agent_cfg) in enumerate(AGENT_CONFIG.items()):
    agent_status = statuses.get(key, {})
    with cols[i % 4]:
        agent_card(
            name=agent_cfg["name"],
            icon=agent_cfg["icon"],
            status=agent_status.get("status", "idle"),
            last_run=agent_status.get("last_run") or "Never",
            color=agent_cfg["color"],
            runtime_seconds=agent_status.get("runtime_seconds"),
            last_error=agent_status.get("last_error"),
            description=agent_cfg.get("description"),
            run_count=agent_status.get("run_count"),
        )
        if (agent_status.get("status") or "").lower() == "error":
            if retry_button("Retry agent", key=f"retry_{key}"):
                with st.spinner(f"Retrying {agent_cfg['name']}…"):
                    orch.run_single_agent(key)
                st.rerun()

# ── Activity Log (L2: real timestamps, level + agent filters, search) ──
audit_rows = collect_audit_trail(getattr(orch, "agents", {}), limit=300)
if audit_rows:
    section_header("Activity Log",
                   "Real-time timeline across every agent — filter by level, agent, or keyword.")
    log_panel(audit_rows, key="mc_log", height=320)

# ── Observability: per-agent telemetry + token spend ──
# Surfaces persistent run history from ``data/agent_telemetry.json`` plus
# the in-memory planning log of the most recent run. Answers the operator
# question "which agents are slow / failing / costing me tokens?" without
# needing to grep logs or open files.
section_header(
    "Pipeline Observability",
    "Per-agent run history, runtime trends, and token spend from the most recent pipeline.",
)
try:
    _telem_all = agent_telemetry.load_all()
except Exception:
    _telem_all = {}

_telem_rows = []
for _key in orch.agent_order:
    rec = _telem_all.get(_key) or {}
    history = rec.get("history") or []
    completed = [h for h in history if (h.get("status") or "").lower() == "completed"]
    runtimes = [h.get("runtime_seconds") for h in completed
                if isinstance(h.get("runtime_seconds"), (int, float))]
    runtimes_sorted = sorted(runtimes)
    p50 = runtimes_sorted[len(runtimes_sorted) // 2] if runtimes_sorted else None
    p95_idx = max(0, int(len(runtimes_sorted) * 0.95) - 1) if runtimes_sorted else 0
    p95 = runtimes_sorted[p95_idx] if runtimes_sorted else None
    err_count = sum(1 for h in history if (h.get("status") or "").lower() == "error")
    last_run = rec.get("last_run")
    last_err = rec.get("last_error")
    _telem_rows.append({
        "Agent": AGENT_CONFIG.get(_key, {}).get("name", _key),
        "Status": (rec.get("status") or "idle").capitalize(),
        "Last run": format_relative_time(last_run) if last_run else "Never",
        "Last runtime (s)": (round(rec.get("runtime_seconds"), 2)
                             if isinstance(rec.get("runtime_seconds"), (int, float))
                             else "—"),
        "Median runtime (s)": round(p50, 2) if p50 is not None else "—",
        "p95 runtime (s)": round(p95, 2) if p95 is not None else "—",
        "Runs (total)": int(rec.get("run_count") or 0),
        "Errors (history)": err_count,
        "Last error": (str(last_err)[:80] + "…")
                      if last_err and len(str(last_err)) > 80
                      else (last_err or "—"),
    })

if _telem_rows:
    safe_dataframe(pd.DataFrame(_telem_rows), use_container_width=True, hide_index=True)
else:
    st.caption("No agent telemetry recorded yet — run the pipeline to populate this view.")

# Planner step + token spend from the most recent run
_planning = []
try:
    _planning = list(getattr(orch, "planning_log", []) or [])
except Exception:
    _planning = []

if _planning:
    _input_tokens = sum(int((p.get("usage") or {}).get("input_tokens", 0)) for p in _planning)
    _output_tokens = sum(int((p.get("usage") or {}).get("output_tokens", 0)) for p in _planning)
    _cache_read = sum(int((p.get("usage") or {}).get("cache_read_input_tokens", 0)) for p in _planning)
    _cache_create = sum(int((p.get("usage") or {}).get("cache_creation_input_tokens", 0)) for p in _planning)
    _billable_input = max(0, _input_tokens - _cache_read)
    _cache_total_seen = _cache_read + _cache_create
    _cache_hit_pct = (round(100 * _cache_read / _cache_total_seen, 1)
                      if _cache_total_seen else 0.0)

    o1, o2, o3, o4, o5 = st.columns(5)
    with o1:
        kpi_card("Planner Steps", str(len(_planning)),
                 "Tool-use turns in the most recent run.", key="obs_steps")
    with o2:
        kpi_card("Input Tokens", f"{_input_tokens:,}",
                 f"Billable after cache: {_billable_input:,}", key="obs_in")
    with o3:
        kpi_card("Output Tokens", f"{_output_tokens:,}",
                 "Generated by the planner.", key="obs_out")
    with o4:
        kpi_card("Cache Hit", f"{_cache_hit_pct:.0f}%",
                 f"{_cache_read:,} read / {_cache_create:,} created", key="obs_cache")
    with o5:
        # Rough cost using public Opus 4.x list-price ratios; numbers
        # update from this single constant if pricing changes.
        _per_million_input = 15.0
        _per_million_output = 75.0
        _est_cost = (_billable_input * _per_million_input
                     + _output_tokens * _per_million_output) / 1_000_000
        kpi_card("Est. Cost (USD)", f"${_est_cost:.3f}",
                 "List-price estimate, planner only.", key="obs_cost")
else:
    st.caption("Run the pipeline to see planner-step and token-spend telemetry.")

# ── Real-data status banner ──
_cm = st.session_state.get("conn_manager")
if _cm and _cm.has_sources():
    _srcs = _cm.list_sources()
    _labels = ", ".join(f"**{s['display_name']}** → `{s['target_schema']}`" for s in _srcs)
    st.success(
        f"📂 **{len(_srcs)} real data source(s) registered** — {_labels}. "
        f"The pipeline will use your data instead of sample data.",
        icon="✅",
    )
else:
    st.info(
        "ℹ️ No real data sources registered. The pipeline will run on built-in sample data. "
        "Upload your own data on the **Data Collector** page first.",
        icon="💡",
    )

# ── Run Pipeline ──
goal = st.text_input(
    "Mission Goal",
    value="Prepare for a CSRD filing in Q3 by assessing ESG readiness, gap closure, and ROI.",
    help=(
        "Describe the business objective for this pipeline run. "
        "The planner will decide which agents to execute and when to stop."
    ),
    max_chars=240,
)
col1, col2 = st.columns([1, 3])
with col1:
    run_pipeline = st.button("🚀 Run Full Pipeline", type="primary", use_container_width=True)
with col2:
    st.caption("An LLM plans the next agent(s) to execute based on your goal and the available ESG intelligence modules.")

if run_pipeline:
    progress_bar = st.progress(0)
    status_text = st.empty()

    def progress_callback(agent_key, status, step, total):
        progress_bar.progress(step / total)
        agent_cfg = AGENT_CONFIG.get(agent_key, {})
        name = agent_cfg.get("name", agent_key)
        icon = agent_cfg.get("icon", "🤖")
        if status == "running":
            status_text.info(f"{icon} Running {name}... ({step}/{total})")
        elif status == "completed":
            status_text.success(f"{icon} {name} completed ({step}/{total})")
        elif status == "error":
            status_text.error(f"{icon} {name} failed or was skipped ({step}/{total})")

    with st.spinner("Running full ESG pipeline..."):
        # Forward any real data sources the user registered on the Data
        # Collector page so uploaded files/connections flow into the pipeline.
        conn_mgr = st.session_state.get("conn_manager")
        dc_kwargs = (
            {"connection_manager": conn_mgr}
            if conn_mgr and conn_mgr.has_sources()
            else {}
        )
        # Defence-in-depth: wipe any per-source DataFrame cache before the
        # pipeline fires so a remote change (e.g. Snowflake row delete) is
        # always visible on the next run, regardless of what use_cache flag
        # flows through the agent stack.
        if conn_mgr and conn_mgr.has_sources():
            conn_mgr.invalidate_cache()
        results = orch.run_full_pipeline(
            progress_callback=progress_callback,
            data_collector_kwargs=dc_kwargs or None,
            user_goal=goal,
        )
        st.session_state.pipeline_results = results

        # Keep every agent page's "data freshness" caption in sync — the
        # full pipeline just re-ingested the registered sources via the
        # Data Collector, so stamp the refresh timestamp here.
        if conn_mgr and conn_mgr.has_sources():
            dc_res = results.get("data_collector", {}) if isinstance(results, dict) else {}
            stamp_refresh_from_pipeline(
                sources=len(conn_mgr.list_sources()),
                records=int(dc_res.get("total_records", 0)) if isinstance(dc_res, dict) else 0,
                errors=conn_mgr.source_errors() if hasattr(conn_mgr, "source_errors") else {},
            )

    progress_bar.progress(1.0)
    errored = [key for key, value in results.items() if isinstance(value, dict) and "error" in value]
    if errored:
        status_text.warning(f"⚠️ Pipeline completed with issues in: {', '.join(errored)}")
    else:
        status_text.success("✅ Full pipeline completed successfully!")

# ── Save / Load Run ──
# Closes the README-flagged "session-scoped storage" gap: instead of every
# pipeline run vanishing on browser refresh, the signed-in user can stash
# a snapshot to the same private HF Dataset that backs profile + sources,
# then reload it on any device. Saves are explicit (not auto) so users
# don't accumulate junk runs they didn't ask for.
_run_store = get_run_store()
_user = (st.session_state.get("user") or {})
_username = (_user.get("username") or "").strip()
_results_in_state = st.session_state.get("pipeline_results")

with st.expander("💾 Save / Load Pipeline Runs", expanded=False):
    save_col, load_col = st.columns([1, 1])
    with save_col:
        st.markdown("##### Save the current run")
        if not _results_in_state:
            st.caption("Run the pipeline first — there's nothing to save yet.")
        elif not _username:
            st.caption("Sign in to save runs to your private dataset.")
        else:
            _label = st.text_input(
                "Run label",
                value=f"Run @ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                key="mc_save_run_label",
                max_chars=120,
            )
            if st.button("Save run", key="mc_save_run_btn",
                          use_container_width=True):
                try:
                    _rid = _run_store.save_run(
                        _username,
                        results=_results_in_state,
                        label=_label,
                        goal=goal,
                        saved_by=_username,
                    )
                    st.success(f"Saved run `{_rid}`.", icon="✅")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Save failed: {exc}", icon="⚠️")

    with load_col:
        st.markdown("##### Load a previous run")
        if not _username:
            st.caption("Sign in to see your saved runs.")
        else:
            _runs = _run_store.list_runs(_username)
            if not _runs:
                st.caption("No saved runs yet.")
            else:
                _options = {
                    f"{r.get('label')} · "
                    f"{(r.get('saved_at') or '')[:16]} · "
                    f"IQS {r.get('headline', {}).get('iqs_grade') or '—'}"
                    : r["id"] for r in _runs
                }
                _picked_label = st.selectbox(
                    "Pick a run",
                    list(_options.keys()),
                    key="mc_load_run_select",
                )
                _picked_id = _options[_picked_label]
                _lc1, _lc2 = st.columns([1, 1])
                with _lc1:
                    if st.button("Load", key="mc_load_run_btn",
                                  use_container_width=True):
                        snap = _run_store.load_run(_username, _picked_id)
                        if snap and isinstance(snap.get("results"), dict):
                            st.session_state.pipeline_results = snap["results"]
                            st.success(f"Loaded `{_picked_id}`.", icon="📂")
                            st.rerun()
                        else:
                            st.error("Couldn't load that run.", icon="⚠️")
                with _lc2:
                    if st.button("Delete", key="mc_delete_run_btn",
                                  use_container_width=True):
                        if _run_store.delete_run(_username, _picked_id):
                            st.success(f"Deleted `{_picked_id}`.", icon="🗑️")
                            st.rerun()
                        else:
                            st.error("Couldn't delete that run.", icon="⚠️")
    _diag = _run_store.diagnostic()
    st.caption(
        f"Storage: {_diag.get('label')}"
        + (f" · last error: `{_diag['last_error']}`" if _diag.get("last_error") else "")
    )

# ── Pipeline Results ──
if st.session_state.pipeline_results:
    results = st.session_state.pipeline_results
    st.markdown("---")

    # ── Data Coverage & Next Data to Unlock ──
    # Proactively tells the client exactly which tables are missing, which
    # specific columns in their registered sources are unmapped, and what kind
    # of source would plug the gap. This is the automated answer to "what do
    # you need from me to guide me better?" — shown before the chat so the
    # client has the context before asking follow-ups.
    section_header(
        "Data Coverage & Next Data to Unlock",
        "A read of the data this run actually had available — what's in, what's missing, and the specific source that would close each gap.",
    )

    _gap_conn_mgr = st.session_state.get("conn_manager")
    gap_report = compute_data_gaps(_gap_conn_mgr, results)

    # Stamp one generation timestamp for the whole advisory — reused in
    # every downloadable artefact so filename + CSV header agree.
    gap_generated_at = datetime.now()
    gap_generated_iso = gap_generated_at.isoformat(timespec="seconds")
    gap_filename_stamp = gap_generated_at.strftime("%Y%m%d_%H%M%S")

    def _csv_with_metadata(df: pd.DataFrame, label: str) -> bytes:
        """Prepend a two-line metadata header to a CSV so auditors can see
        exactly when the advisory was generated and downloaded."""
        buf = io.StringIO()
        buf.write(f"# ESG Pilot — {label}\n")
        buf.write(f"# Generated at: {gap_generated_iso}\n")
        buf.write(f"# Downloaded at: {datetime.now().isoformat(timespec='seconds')}\n")
        buf.write("#\n")
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8")

    st.caption(f"Advisory generated at **{gap_generated_iso}** (local time).")

    gc1, gc2, gc3, gc4 = st.columns(4)
    with gc1:
        kpi_card(
            "Registered Sources",
            str(gap_report["source_count"]),
            "Real connectors / uploads in this run."
            if gap_report["has_sources"]
            else "No sources registered — sample data was used.",
        )
    with gc2:
        cov = gap_report["schema_coverage"]
        kpi_card(
            "Schema Coverage",
            f"{cov['covered']}/{cov['total']}",
            "ESG data tables the client has populated.",
        )
    with gc3:
        kpi_card(
            "Agents Completed",
            str(len(gap_report["agents_completed"])),
            "Ran cleanly against the available data.",
        )
    with gc4:
        kpi_card(
            "Agents Degraded",
            str(len(gap_report["agents_errored"])),
            ", ".join(gap_report["agents_errored"])
            if gap_report["agents_errored"]
            else "No agent errored out.",
        )

    if gap_report["using_sample_data"]:
        st.info(
            "ℹ️ This run used built-in sample data because no real sources are "
            "registered. Upload real data on the **Data Collector** page to "
            "see gap guidance tailored to the client's actual systems.",
            icon="💡",
        )

    gap_left, gap_right = st.columns([1, 1])

    with gap_left:
        st.markdown("##### Registered sources — unmapped fields")
        if gap_report["sources"]:
            # Only surface sources that actually have something missing.
            # Fully-mapped sources are quality data — don't ask the client
            # to look at them.
            flagged_sources = [
                s for s in gap_report["sources"]
                if s["missing_required"] or s["missing_optional"]
            ]
            clean_count = len(gap_report["sources"]) - len(flagged_sources)

            if flagged_sources:
                src_rows = [
                    {
                        "Source": s["display_name"],
                        "Type": s["connector_type"],
                        "Schema": s["target_schema"],
                        "Missing required": ", ".join(s["missing_required"]) or "—",
                        "Missing optional": ", ".join(s["missing_optional"]) or "—",
                    }
                    for s in flagged_sources
                ]
                src_df = pd.DataFrame(src_rows)
                safe_dataframe(src_df, use_container_width=True, hide_index=True)
                if clean_count:
                    st.caption(
                        f"Hiding {clean_count} fully-mapped source"
                        f"{'s' if clean_count != 1 else ''} with no gaps."
                    )
                st.download_button(
                    "⬇️ Download source discrepancies (CSV)",
                    data=_csv_with_metadata(src_df, "Source discrepancies — unmapped fields"),
                    file_name=f"esg_source_discrepancies_{gap_filename_stamp}.csv",
                    mime="text/csv",
                    key="mc_gap_dl_sources",
                )
                any_req_missing = any(s["missing_required"] for s in flagged_sources)
                if any_req_missing:
                    st.warning(
                        "One or more registered sources is missing required columns. "
                        "Re-open the source on the **Data Collector** page and map "
                        "those columns before the next run.",
                        icon="⚠️",
                    )
            else:
                st.success(
                    f"All {len(gap_report['sources'])} registered source"
                    f"{'s are' if len(gap_report['sources']) != 1 else ' is'} "
                    "fully mapped — no gaps to address.",
                    icon="✅",
                )
        else:
            st.caption("No sources registered yet — nothing to audit here.")

    with gap_right:
        st.markdown("##### Missing data tables — what each would unlock")
        if gap_report["missing_schemas"]:
            miss_rows = [
                {
                    "Schema": m["schema"],
                    "Unblocks": ", ".join(m["blocks_agents"]),
                    "Why it matters": m["why"],
                    "Suggested source": m["example_source"],
                }
                for m in gap_report["missing_schemas"]
            ]
            miss_df = pd.DataFrame(miss_rows)
            safe_dataframe(miss_df, use_container_width=True, hide_index=True)
            st.download_button(
                "⬇️ Download data suggestions (CSV)",
                data=_csv_with_metadata(miss_df, "Data suggestions — missing tables"),
                file_name=f"esg_data_suggestions_{gap_filename_stamp}.csv",
                mime="text/csv",
                key="mc_gap_dl_missing",
            )
        else:
            st.success("Every supported ESG data table is covered by at least one source.", icon="✅")

    # LLM-layered prioritized recommendations — cached per (sources, results)
    # so re-rendering the page doesn't re-hit the API.
    def _gap_cache_key(report: dict) -> str:
        return json.dumps({
            "sources": [(s["target_schema"],
                         tuple(s["missing_required"]),
                         tuple(s["missing_optional"]))
                        for s in report["sources"]],
            "missing": [m["schema"] for m in report["missing_schemas"]],
            "errored": report["agents_errored"],
            "sample": report["using_sample_data"],
        }, sort_keys=True)

    cache_key = _gap_cache_key(gap_report)
    cache = st.session_state.setdefault("mc_gap_advice_cache", {})
    cached = cache.get(cache_key)

    st.markdown("##### Prioritized recommendations")
    advice_slot = st.empty()

    def _generate_gap_advice(report: dict, run_results: dict) -> str:
        api_key = config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return ("⚠️ `ANTHROPIC_API_KEY` is not set — set it and reload to "
                    "see prioritized recommendations.")
        client = anthropic.Anthropic(api_key=api_key)
        prompt = (
            "You are an ESG data advisor talking to the client. Based on the "
            "data-gap report and this pipeline run's results, give 3–5 "
            "prioritized recommendations. For each: (1) the concrete data "
            "artefact to request (file / system / columns), (2) the source "
            "system or team that likely owns it, and (3) the specific "
            "downstream analysis it unlocks in this app. Order by business "
            "impact. Be concrete — name columns and example sources, not "
            "abstract capability language. If the client already has good "
            "coverage, say so and point to the one or two optional fields "
            "that would most sharpen the current analysis. Markdown bullet "
            "list, no preamble.\n\n"
            f"GAP REPORT:\n{json.dumps(report, indent=2, default=str)}\n\n"
            f"PIPELINE RESULTS (summary):\n"
            f"{json.dumps({k: v for k, v in run_results.items() if k != 'planning'}, default=str)[:20000]}"
        )
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=1400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip() or "(no recommendations generated)"

    if cached:
        advice_slot.markdown(cached)
        advice_text = cached
    else:
        advice_slot.markdown("_Generating prioritized recommendations from the gap report…_")
        try:
            advice_text = _generate_gap_advice(gap_report, results)
        except Exception as exc:
            advice_text = f"⚠️ Recommendation generation failed: `{exc}`"
        cache[cache_key] = advice_text
        advice_slot.markdown(advice_text)

    # Downloadable full advisory bundle — recommendations + both gap tables,
    # with the same generation timestamp stamped into one CSV per row type.
    advice_md = (
        f"# ESG Pilot — Prioritized Recommendations\n"
        f"Generated at: {gap_generated_iso}\n"
        f"Downloaded at: {datetime.now().isoformat(timespec='seconds')}\n\n"
        f"{advice_text}\n"
    )
    st.download_button(
        "⬇️ Download recommendations (Markdown)",
        data=advice_md.encode("utf-8"),
        file_name=f"esg_recommendations_{gap_filename_stamp}.md",
        mime="text/markdown",
        key="mc_gap_dl_advice",
    )

    st.markdown("---")

    # ── Ask the Pilot (natural-language Q&A grounded in this run) ──
    section_header(
        "Ask the Pilot",
        "Ask a question about this pipeline run. Claude answers using the current agent results as context — no data from other runs or the web.",
    )

    if "mc_chat" not in st.session_state:
        st.session_state.mc_chat = []

    def _pipeline_context(run_results: dict, char_limit: int = 40000) -> str:
        """Compact JSON snapshot of the run for the model. Drops planning log
        (shown elsewhere) and truncates hard to stay well under the prompt-
        cache sweet spot even on large runs."""
        snapshot = {k: v for k, v in run_results.items() if k != "planning"}
        try:
            text = json.dumps(snapshot, default=str, indent=2)
        except TypeError:
            text = str(snapshot)
        if len(text) > char_limit:
            text = text[:char_limit] + "\n…[truncated]"
        return text

    def _ask_pilot(question: str, history: list[dict], run_results: dict) -> str:
        api_key = config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return ("⚠️ `ANTHROPIC_API_KEY` is not set in this environment — "
                    "set it and reload to use the Pilot.")
        client = anthropic.Anthropic(api_key=api_key)
        system = [
            {
                "type": "text",
                "text": (
                    "You are the ESG Pilot, answering questions about a single ESG "
                    "pipeline run. Ground every claim in the JSON context provided. "
                    "If the data cannot answer the question (e.g. no sector breakdown, "
                    "no time-series), say so plainly and point to the closest signal "
                    "that *is* available. Prefer concrete numbers from the context "
                    "over generic ESG advice. Be concise — 3–6 short paragraphs or a "
                    "tight bullet list. Never invent fields that aren't in the JSON."
                ),
            },
            {
                "type": "text",
                "text": f"Pipeline run context (JSON):\n{_pipeline_context(run_results)}",
                "cache_control": {"type": "ephemeral"},
            },
        ]
        messages = [
            {"role": turn["role"], "content": turn["content"]}
            for turn in history
        ]
        messages.append({"role": "user", "content": question})
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system,
            messages=messages,
        )
        return "".join(
            block.text for block in response.content
            if getattr(block, "type", None) == "text"
        ).strip() or "(no response)"

    for turn in st.session_state.mc_chat:
        with st.chat_message(turn["role"]):
            st.markdown(turn["content"])

    user_q = st.chat_input(
        "Ask about this run — e.g. 'Which KPI is weakest?' or 'Where is the biggest ROI lever?'"
    )
    if user_q:
        st.session_state.mc_chat.append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("_Thinking…_")
            try:
                answer = _ask_pilot(
                    user_q,
                    st.session_state.mc_chat[:-1],
                    results,
                )
            except Exception as exc:
                answer = f"⚠️ Pilot call failed: `{exc}`"
            placeholder.markdown(answer)
        st.session_state.mc_chat.append({"role": "assistant", "content": answer})

    if st.session_state.mc_chat:
        if st.button("Clear chat", key="mc_chat_clear"):
            st.session_state.mc_chat = []
            st.rerun()

    st.markdown("---")

    tab_results, tab_business, tab_hypotheses, tab_pipeline, tab_transform, tab_stack, tab_tiers, tab_monitor = st.tabs([
        "Results Summary", "Business Lens", "Hypothesis Tracker", "Pipeline Flow",
        "Transformation", "Enterprise Stack", "Tier Config", "24/7 Monitoring",
    ])

    data_res = results.get("data_collector", {})
    carbon_res = results.get("carbon_accountant", {})
    risk_res = results.get("risk_predictor", {})
    audit_res = results.get("audit_agent", {})
    roi_res = results.get("roi_agent", {})
    reg_res = results.get("regulatory_tracker", {})
    action_res = results.get("action_agent", {})
    report_res = results.get("report_generator", {})
    stakeholder_res = results.get("stakeholder_agent", {})
    kpi_res = roi_res.get("kpi_engine", {})
    fin_summary = kpi_res.get("financial_summary", {})
    cagr = kpi_res.get("cagr", {})
    volatility = kpi_res.get("volatility", {})

    with tab_results:
        section_header("Pipeline Results",
                       "Headline metrics from the latest full-pipeline run.")

        planning_steps = results.get("planning", [])
        if planning_steps:
            with st.expander("LLM Planning Audit Trail", expanded=False):
                for idx, step in enumerate(planning_steps, start=1):
                    agent_text = step.get("agent", "planner")
                    reason = step.get("reason", "No reason provided.")
                    st.markdown(f"**{idx}.** {agent_text} — {reason}")

        readiness = audit_res.get("readiness_score", {})
        iqs_card = roi_res.get("investment_quality_score", {})

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            kpi_card(
                "Total Records",
                f"{data_res.get('total_records', 0):,}",
                "Rows ingested and validated",
                key="kpi_records",
            )
        with k2:
            kpi_card(
                "Total Emissions",
                f"{carbon_res.get('total_emissions_current', 0):,.0f} tCO2e",
                f"{carbon_res.get('yoy_change_pct', 0)}% YoY",
                key="kpi_emissions",
            )
        with k3:
            kpi_card(
                "Risk Score",
                f"{risk_res.get('overall_risk_score', 0):.0f}/100",
                "Composite ESG risk",
                key="kpi_risk",
            )
        with k4:
            kpi_card(
                "Audit Readiness",
                f"{readiness.get('overall', 0):.0f}%",
                f"Grade: {readiness.get('grade', 'N/A')}",
                key="kpi_audit",
            )
        with k5:
            kpi_card(
                "Investment Quality",
                f"{iqs_card.get('score', 0):.0f}/100",
                f"Grade: {iqs_card.get('grade', 'N/A')}",
                key="kpi_iqs",
            )

        if iqs_card.get("grade"):
            st.markdown(
                f"Headline investment signal: {grade_pill(iqs_card.get('grade', 'N/A'))}",
                unsafe_allow_html=True,
            )

        # Carbon + Compliance charts
        col1, col2 = st.columns(2)
        with col1:
            if carbon_res and "scope_totals_current" in carbon_res:
                from utils.charts import emissions_donut
                fig = emissions_donut(carbon_res["scope_totals_current"])
                render_chart(fig)
        with col2:
            if reg_res and "framework_results" in reg_res:
                from utils.charts import compliance_radar
                scores = {fw: d["compliance_pct"] for fw, d in reg_res["framework_results"].items()}
                fig = compliance_radar(scores)
                render_chart(fig)

        report_recommendations = report_res.get("recommended_reports", []) if report_res else []
        actionable_insights = report_res.get("actionable_insights", []) if report_res else []
        dashboard_templates = report_res.get("dashboard_templates", {}) if report_res else {}

        if report_recommendations or actionable_insights or dashboard_templates:
            section_header("AI-Generated Report Intelligence",
                           "What the Report Generator produced for this pipeline run.")
            if report_recommendations:
                st.markdown("**Recommended Report Pack**")
                for item in report_recommendations[:5]:
                    st.markdown(f"- {item}")
            # Skip "Key Insights" if it's identical to the Report Pack — both
            # prompts share the HuggingFace fallback, which can return the same
            # generic narrative for both call sites.
            if actionable_insights and actionable_insights != report_recommendations:
                st.markdown("**Key Insights from the Report Generator**")
                for insight in actionable_insights:
                    st.markdown(f"- {insight}")
            if dashboard_templates:
                with st.expander("Sample BI / Dashboard Templates", expanded=False):
                    st.markdown(dashboard_templates.get("summary", ""))
                    if dashboard_templates.get("power_bi"):
                        st.markdown("##### Power BI Template")
                        st.markdown(dashboard_templates.get("power_bi"))
                    if dashboard_templates.get("quicksight"):
                        st.markdown("##### QuickSight Template")
                        st.markdown(dashboard_templates.get("quicksight"))

        data_quality_summary = data_res.get("data_quality_summary", [])
        regulatory_action_plan = reg_res.get("regulatory_action_plan", [])
        carbon_insights = carbon_res.get("carbon_insights", [])
        risk_recommendations = risk_res.get("risk_recommendations", [])
        audit_recommendations = audit_res.get("audit_recommendations", [])
        roi_recommendations = roi_res.get("roi_recommendations", [])
        distribution_plan = stakeholder_res.get("distribution_plan", "")

        if (
            data_quality_summary
            or regulatory_action_plan
            or carbon_insights
            or risk_recommendations
            or audit_recommendations
            or roi_recommendations
            or distribution_plan
        ):
            section_header("Agentic Intelligence Summaries",
                           "Cross-agent recommendations, insights, and operational plans.")
            if data_quality_summary:
                st.markdown("**Data Quality Summary**")
                for item in data_quality_summary[:4]:
                    st.markdown(f"- {item}")
            if regulatory_action_plan:
                st.markdown("**Regulatory Action Plan**")
                for item in regulatory_action_plan[:4]:
                    st.markdown(f"- {item}")
            if carbon_insights:
                st.markdown("**Carbon Accounting Insights**")
                for item in carbon_insights[:4]:
                    st.markdown(f"- {item}")
            if risk_recommendations:
                st.markdown("**Risk Recommendations**")
                for item in risk_recommendations[:4]:
                    st.markdown(f"- {item}")
            if audit_recommendations:
                st.markdown("**Audit Recommendations**")
                for item in audit_recommendations[:4]:
                    st.markdown(f"- {item}")
            if roi_recommendations:
                st.markdown("**ROI Recommendations**")
                for item in roi_recommendations[:4]:
                    st.markdown(f"- {item}")
            if distribution_plan:
                st.markdown("**Stakeholder Distribution Plan**")
                st.markdown(distribution_plan)

        # Actions summary
        if action_res and "actions" in action_res:
            st.markdown("### Top Action Items")
            actions_df = pd.DataFrame(action_res["actions"])
            cols = ["id", "action", "category", "priority", "duration_weeks", "impact"]
            available = [c for c in cols if c in actions_df.columns]
            if available:
                safe_dataframe(actions_df[available].head(5), use_container_width=True, hide_index=True)

        if roi_res and "financial_roi" in roi_res:
            section_header("ESG ROI Snapshot",
                           "Dual ROI and investment-quality signal from the ROI Agent.")
            fin_roi = roi_res.get("financial_roi", {})
            iqs = roi_res.get("investment_quality_score", {})
            col1, col2, col3 = st.columns(3)
            with col1:
                kpi_card("Financial ROI", f"{fin_roi.get('roi_pct', 0)}%",
                         "Payback-weighted return", key="roi_fin")
            with col2:
                kpi_card("Net Financial Benefit",
                         f"INR {fin_roi.get('net_financial_benefit', 0)} Cr",
                         "After ESG capex and friction", key="roi_net")
            with col3:
                kpi_card("IQS Grade", iqs.get("grade", "N/A"),
                         f"Score {iqs.get('score', 0)}/100", key="roi_grade")

    with tab_business:
        st.markdown("### Top Line vs Bottom Line")
        st.caption("This tab translates ESG into plain business language for revenue, profit, capital efficiency, and risk.")

        top1, top2, top3, top4 = st.columns(4)
        with top1:
            st.metric("Revenue (Top Line)", f"INR {fin_summary.get('revenue_current_fy', 0)} Cr",
                      f"{fin_summary.get('revenue_growth_pct', 0)}% growth")
            st.caption("Money coming in from the business.")
        with top2:
            st.metric("EBITDA Margin", f"{fin_summary.get('ebitda_margin_latest', 0)}%")
            st.caption("How much operating profit is left after running costs.")
        with top3:
            st.metric("Net ESG Benefit", f"INR {roi_res.get('financial_roi', {}).get('net_financial_benefit', 0)} Cr")
            st.caption("Estimated financial upside linked to ESG action.")
        with top4:
            st.metric("Cost of Capital", f"{fin_summary.get('cost_of_capital_latest', 0)}%")
            st.caption("How expensive it is for the company to raise money.")

        st.markdown("### In Plain English")
        st.markdown("""
        - If the **top line** improves, ESG may be helping the company win customers, pricing power, or brand trust.
        - If the **bottom line** improves, ESG may be reducing waste, energy spend, tax exposure, or operating friction.
        - If **cost of capital** falls and downside protection rises, ESG may be making the business safer and more investable.
        """)

        finance_rows = pd.DataFrame([
            {
                "Business lens": "Top line",
                "What it means": "Growth and demand",
                "Metric": "Revenue growth",
                "Current signal": f"{fin_summary.get('revenue_growth_pct', 0)}%",
            },
            {
                "Business lens": "Bottom line",
                "What it means": "Profit after costs",
                "Metric": "EBITDA margin",
                "Current signal": f"{fin_summary.get('ebitda_margin_latest', 0)}%",
            },
            {
                "Business lens": "Capital efficiency",
                "What it means": "Return on invested money",
                "Metric": "ROA / ROE",
                "Current signal": f"{fin_summary.get('roa_latest', 0)}% / {fin_summary.get('roe_latest', 0)}%",
            },
            {
                "Business lens": "Funding & risk",
                "What it means": "How safe and attractive the business looks",
                "Metric": "Cost of capital / downside protection",
                "Current signal": (
                    f"{fin_summary.get('cost_of_capital_latest', 0)}% / "
                    f"{risk_res.get('downside_protection', {}).get('score', 0)}/100"
                ),
            },
        ])
        safe_dataframe(finance_rows, use_container_width=True, hide_index=True)

        st.markdown("### Finance Detail")
        finance_detail = pd.DataFrame([
            {"Metric": "Revenue CAGR", "Value": f"{cagr.get('revenue_cagr', 0)}%"},
            {"Metric": "EBITDA CAGR", "Value": f"{cagr.get('ebitda_cagr', 0)}%"},
            {"Metric": "ESG Capex CAGR", "Value": f"{cagr.get('esg_capex_cagr', 0)}%"},
            {"Metric": "Revenue Volatility", "Value": f"{volatility.get('revenue_volatility', 0)}%"},
            {"Metric": "Margin Volatility", "Value": f"{volatility.get('margin_volatility', 0)}"},
            {"Metric": "Earnings Volatility", "Value": f"{volatility.get('earnings_volatility', 0)}%"},
            {"Metric": "Carbon Tax Exposure", "Value": f"INR {fin_summary.get('carbon_tax_exposure_latest', 0)} L"},
            {"Metric": "Energy Cost", "Value": f"INR {fin_summary.get('energy_cost_latest', 0)} Cr"},
        ])
        safe_dataframe(finance_detail, use_container_width=True, hide_index=True)

    with tab_hypotheses:
        st.markdown("### Hypothesis Tracker")
        st.caption("This shows the business ideas the platform is testing, translated into simple language.")

        market_regime = risk_res.get("market_regime", {})
        downside = risk_res.get("downside_protection", {})
        j_curve = roi_res.get("j_curve", {})
        reporter_profile = reg_res.get("reporter_profile", {})
        iqs = roi_res.get("investment_quality_score", {})
        cost_savings = roi_res.get("financial_roi", {}).get("cost_savings", {}).get("total", 0)

        hypothesis_rows = pd.DataFrame([
            {
                "Hypothesis": "H1 Growth",
                "Plain English": "Better ESG can help the company grow sales and brand strength.",
                "Where to see it": "ROI Agent + Report Generator",
                "Current signal": signal_label(kpi_res.get("composite_esg_financial_score"), 65),
                "Evidence now": f"Revenue growth {fin_summary.get('revenue_growth_pct', 0)}%, growth channel {next((c.get('score', 0) for c in kpi_res.get('value_channels', []) if c.get('channel') == 'Growth'), 0)}/100",
            },
            {
                "Hypothesis": "H2 Profitability",
                "Plain English": "Cutting emissions and energy waste can improve profit.",
                "Where to see it": "Carbon Accountant + ROI Agent",
                "Current signal": signal_label(cost_savings, 1),
                "Evidence now": f"ESG-linked cost savings INR {cost_savings} Cr",
            },
            {
                "Hypothesis": "H3 Cyclical",
                "Plain English": "ESG may perform differently in stable, transition, or stress markets.",
                "Where to see it": "Risk Predictor",
                "Current signal": "Observed" if market_regime else "Not available",
                "Evidence now": f"Market regime: {market_regime.get('regime', 'N/A')}",
            },
            {
                "Hypothesis": "H4 Downside",
                "Plain English": "Stronger ESG can protect the business during shocks or downturns.",
                "Where to see it": "Risk Predictor",
                "Current signal": signal_label(downside.get('score'), 70, 55),
                "Evidence now": f"Downside protection score: {downside.get('score', 0)}/100",
            },
            {
                "Hypothesis": "H5 CapEx Quality",
                "Plain English": "ESG spending should create returns, not just cost.",
                "Where to see it": "ROI Agent + Action Agent",
                "Current signal": signal_label(iqs.get('score'), 70, 55),
                "Evidence now": f"Investment quality: {iqs.get('score', 0)}/100 ({iqs.get('grade', 'N/A')})",
            },
            {
                "Hypothesis": "H6 J-Curve",
                "Plain English": "ESG can hurt in the short term but pay back over time.",
                "Where to see it": "ROI Agent + Stakeholder Agent",
                "Current signal": "Breakeven reached" if j_curve.get("breakeven_quarter") else "Still in payback phase",
                "Evidence now": f"Breakeven: {j_curve.get('breakeven_quarter', 'Not yet reached')}",
            },
            {
                "Hypothesis": "H7 India Nuance",
                "Plain English": "Indian reporting context changes what matters, especially BRSR readiness.",
                "Where to see it": "Regulatory Tracker + Report Generator",
                "Current signal": "Context active" if reporter_profile else "Not available",
                "Evidence now": f"Reporter profile: {reporter_profile.get('classification', 'N/A')}",
            },
        ])
        safe_dataframe(hypothesis_rows, use_container_width=True, hide_index=True)

    with tab_pipeline:
        st.markdown("### Agent Pipeline — Data Flow Visualization")
        st.caption("Sankey diagram showing how data flows between all orchestrated agents")
        fig = pipeline_flow_diagram()
        render_chart(fig)
        st.markdown("""
        **Architecture in plain English**
        - The first layer collects and cleans data.
        - The middle layer turns that data into business signals like growth, profit, and risk.
        - The final layer turns those signals into reports, decisions, and stakeholder communication.
        """)

    with tab_transform:
        st.markdown("### Real-World Transformation — From Months to Weeks")
        fig = before_after_comparison()
        render_chart(fig)
        st.markdown("""
        **Key Outcomes:**
        - Reporting cycle slashed from **5 months** to **3 weeks**
        - Scope 3 coverage expanded from **60%** to **90%**
        - Data accuracy improved to **95%** through AI-driven validation
        - ESG rating trajectory: **BBB → A-** (measurable improvement)
        - Audit readiness score: **92%** (up from 55%)
        """)

    with tab_stack:
        st.markdown("### Enterprise Stack Architecture")
        st.caption("7-layer architecture designed for seamless tech stack integration and massive scale")
        fig = enterprise_stack_layers()
        render_chart(fig)
        st.markdown("""
        | Layer | Component | Technology |
        |-------|-----------|------------|
        | 7 | Command Center UI | Streamlit + Gradio dashboards |
        | 6 | 9 Orchestrated Agents | Python agent classes with HF AI |
        | 5 | Foundational AI Models | HuggingFace Inference API (Mistral, BART) |
        | 4 | Integration & Connectors | ERP, HR, IoT, API, SQL connectors |
        | 3 | Data Lake | Pandas/PySpark unified data layer |
        | 2 | Governance & Security | Audit trails, confidence scoring, access control |
        | 1 | Cloud Foundation | Scalable infrastructure |
        """)

    with tab_tiers:
        st.markdown("### Tailored for Every Enterprise")
        fig = tier_comparison_chart()
        render_chart(fig)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("""
            #### Starter Tier
            *For emerging compliance needs*
            - 3 agents (Data, Carbon, Report)
            - 1 framework (BRSR)
            - 2 data sources
            - Monthly refresh
            """)
        with col2:
            st.markdown("""
            #### Professional Tier
            *For comprehensive corporate reporting*
            - 6 agents (+ Regulatory, Risk, Audit)
            - 3 frameworks (BRSR, GRI, SASB)
            - 4 data sources + connectors
            - Weekly refresh
            """)
        with col3:
            st.markdown("""
            #### Enterprise Tier
            *For fully autonomous global ESG intelligence*
            - All 9 agents
            - All 6+ frameworks (BRSR, CSRD, GRI, SASB, SOX, SEC)
            - 6+ sources + full connector suite
            - Real-time / 24/7 monitoring
            """)

        st.markdown("#### Pre-Configured Industry Solutions")
        industries = ["Manufacturing", "Finance", "Pharma", "Retail", "IT", "Government"]
        cols = st.columns(len(industries))
        for i, ind in enumerate(industries):
            with cols[i]:
                st.button(ind, disabled=True, use_container_width=True)

    with tab_monitor:
        st.markdown("### 24/7 Always-On Monitoring")
        monitor_data = monitoring_engine.get_dashboard_data()

        health_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(monitor_data["health"], "⚪")
        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric("Status", f"{health_icon} {monitor_data['health'].capitalize()}")
        with k2:
            st.metric("Uptime", f"{monitor_data['uptime_days']} days")
        with k3:
            st.metric("Events Processed", f"{monitor_data['events_processed']:,}")
        with k4:
            st.metric("Active Streams", f"{monitor_data['active_streams']}/{monitor_data['total_streams']}")
        with k5:
            st.metric("Critical Alerts", monitor_data["critical_alerts"])

        # Alert timeline
        from utils.charts import monitoring_timeline
        fig = monitoring_timeline(monitor_data.get("alerts", []))
        render_chart(fig)

        # Active alerts
        st.markdown("#### Active Alerts")
        for alert in monitor_data.get("alerts", []):
            sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert["severity"], "⚪")
            ack = "✅" if alert.get("acknowledged") else "⬜"
            st.markdown(f"{sev_icon} `{alert['timestamp'][:16]}` **[{alert['type'].upper()}]** "
                        f"{alert['message']} {ack}")

        # Data streams
        st.markdown("#### Data Streams")
        for name, stream in monitor_data.get("streams", {}).items():
            s_icon = {"active": "🟢", "warning": "🟡"}.get(stream["status"], "⚪")
            st.markdown(f"{s_icon} **{name}** — {stream['frequency']} | Last: {(stream.get('last_reading') or 'N/A')[:16]}")

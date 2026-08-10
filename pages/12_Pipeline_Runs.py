"""Pipeline Runs — history, activity log, and observability for every run.

Split out of ESG Command Center. That page answers "what do the results
say?"; this one answers the operator questions that were crowding it out:
what has been run, when, by whom, which agents failed, how long they take,
and what the planner cost in tokens.
"""
import json
from datetime import datetime

import pandas as pd
import streamlit as st

from config import AGENT_CONFIG
from core.orchestrator import Orchestrator
from utils import agent_telemetry
from utils.auth import require_login, sidebar_auth_widget
from utils.run_store import get_run_store
from utils.session import get_session_connection_manager
from utils.streamlit_compat import safe_dataframe
from utils.ui import (
    hero, section_header, kpi_card, inject_global_css, pwc_header,
    log_panel, collect_audit_trail, format_relative_time, section_picker,
    callout, insight_group, verdict_kpi,
)

st.set_page_config(page_title="Pipeline Runs | ESG Intelligence Hub",
                   page_icon="🗂️", layout="wide")
inject_global_css()
pwc_header()
sidebar_auth_widget()
require_login("Sign in to view pipeline run history and observability.")
get_session_connection_manager()

hero(
    title="Pipeline Runs",
    emoji="🗂️",
    subtitle=(
        "Every pipeline run this account has saved — what was produced, which "
        "agents struggled, how long they took, and what the planner spent. "
        "The full operational record behind the dashboards."
    ),
    chips=[
        "Saved run history",
        "Cross-agent activity log",
        "Runtime + token telemetry",
    ],
)

if "orchestrator" not in st.session_state:
    st.session_state.orchestrator = Orchestrator()
orch = st.session_state.orchestrator

_user = st.session_state.get("user") or {}
_username = (_user.get("username") or "").strip()

_section = section_picker([
    "📜 Run History",
    "📡 Activity Log",
    "📊 Pipeline Observability",
], key="pipeline_runs_sec1")


# ══════════════════════════════════════════════════════════════════════════
# RUN HISTORY
# ══════════════════════════════════════════════════════════════════════════
if _section == "📜 Run History":
    store = get_run_store()
    runs = []
    if _username:
        try:
            runs = store.list_runs(_username)
        except Exception as exc:
            st.error(f"Could not load run history: `{exc}`")

    section_header(
        "Saved Runs",
        "Each entry is a complete snapshot of one pipeline run, kept so you "
        "can compare periods or reload an earlier result.",
    )

    if not _username:
        st.info("Sign in to see your saved runs.", icon="🔐")
    elif not runs:
        callout(
            "No runs saved yet. Run the full pipeline from **ESG Command "
            "Center** — each successful run is snapshotted here automatically, "
            "so you can come back to it later or compare it against a "
            "future run.",
            title="Nothing to show yet", icon="📭",
        )
    else:
        # ── Portfolio-level summary ───────────────────────────────────────
        _saved_times = [r.get("saved_at") for r in runs if r.get("saved_at")]
        _clean = sum(1 for r in runs if not r.get("errored_agents"))
        _health = (100 * _clean / len(runs)) if runs else 0

        s1, s2, s3, s4 = st.columns(4)
        with s1:
            verdict_kpi(
                "Runs Saved", str(len(runs)),
                "Complete pipeline snapshots kept for this account.",
                verdict="neutral", verdict_label="History",
                term=f"Storage: {store.backend_label()}",
            )
        with s2:
            verdict_kpi(
                "Most Recent",
                format_relative_time(_saved_times[0]) if _saved_times else "Never",
                "When the last pipeline finished and was snapshotted.",
                verdict="neutral", verdict_label="",
            )
        with s3:
            verdict_kpi(
                "Clean Runs", f"{_clean}/{len(runs)}",
                "Runs where every agent completed without erroring.",
                verdict="good" if _health >= 80 else ("watch" if _health >= 50 else "poor"),
                verdict_label=f"{_health:.0f}%",
            )
        with s4:
            _all_errored = [a for r in runs for a in (r.get("errored_agents") or [])]
            _worst = (max(set(_all_errored), key=_all_errored.count)
                      if _all_errored else None)
            verdict_kpi(
                "Most Fragile Agent",
                AGENT_CONFIG.get(_worst, {}).get("name", _worst) if _worst else "None",
                (f"Errored in {_all_errored.count(_worst)} of {len(runs)} runs."
                 if _worst else "No agent has errored in any saved run."),
                verdict="poor" if _worst else "good",
                verdict_label="Watch" if _worst else "All healthy",
            )

        st.divider()

        # ── The run list ──────────────────────────────────────────────────
        def _run_label(r: dict) -> str:
            when = format_relative_time(r.get("saved_at"))
            errs = len(r.get("errored_agents") or [])
            flag = "⚠️" if errs else "✅"
            return f"{flag} {r.get('label', 'Untitled run')} · {when}"

        table_rows = []
        for r in runs:
            head = r.get("headline") or {}
            table_rows.append({
                "": "⚠️" if r.get("errored_agents") else "✅",
                "Run": r.get("label", "Untitled run"),
                "When": format_relative_time(r.get("saved_at")),
                "Agents OK": r.get("agent_count", 0),
                "Failed": len(r.get("errored_agents") or []) or "—",
                "Records": f"{head.get('total_records'):,}"
                           if isinstance(head.get("total_records"), int) else "—",
                "Audit": head.get("audit_grade") or "—",
                "IQS": head.get("iqs_grade") or "—",
                "By": r.get("saved_by") or "—",
            })
        safe_dataframe(pd.DataFrame(table_rows),
                       use_container_width=True, hide_index=True)

        st.divider()
        section_header("Inspect a Run",
                       "Pick any run to see its detail, reload it, or export it.")

        options = {_run_label(r): r for r in runs}
        chosen_label = st.selectbox("Run", list(options.keys()),
                                    key="pipeline_runs_pick")
        chosen = options[chosen_label]

        errored = chosen.get("errored_agents") or []
        if errored:
            names = [AGENT_CONFIG.get(a, {}).get("name", a) for a in errored]
            callout(
                f"**{len(errored)} of {len(errored) + chosen.get('agent_count', 0)}** "
                f"agents failed in this run: {', '.join(names)}. The results "
                f"below are still usable, but anything those agents feed will "
                f"be incomplete.",
                title="This run had failures", tone="warn", icon="⚠️",
            )
        else:
            callout(
                f"All **{chosen.get('agent_count', 0)}** agents completed "
                f"cleanly in this run.",
                title="Clean run", tone="success", icon="✅",
            )

        head = chosen.get("headline") or {}
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            kpi_card("Records Processed",
                     f"{head.get('total_records'):,}"
                     if isinstance(head.get("total_records"), int) else "—",
                     "Rows ingested and validated in this run.",
                     key="pr_detail_records")
        with d2:
            kpi_card("Audit Grade", str(head.get("audit_grade") or "—"),
                     "Assurance readiness at the time of this run.",
                     key="pr_detail_audit")
        with d3:
            kpi_card("Investment Grade", str(head.get("iqs_grade") or "—"),
                     "ESG investment quality at the time of this run.",
                     key="pr_detail_iqs")
        with d4:
            _emis = head.get("emissions_total")
            kpi_card("Total Emissions",
                     f"{_emis:,.0f}" if isinstance(_emis, (int, float)) else "—",
                     "tCO₂e recorded for this run.",
                     key="pr_detail_emis")

        meta_cols = st.columns(2)
        with meta_cols[0]:
            insight_group("Run details", [
                f"Saved: {chosen.get('saved_at') or 'unknown'}",
                f"Saved by: {chosen.get('saved_by') or 'unknown'}",
                f"Goal: {chosen.get('goal') or 'not recorded'}",
                f"Run id: {chosen.get('id') or 'unknown'}",
            ], icon="🗂️", numbered=False)
        with meta_cols[1]:
            insight_group(
                "Agents that failed",
                [AGENT_CONFIG.get(a, {}).get("name", a) for a in errored],
                icon="⚠️", numbered=False,
                empty_text="None — every agent completed.",
            )

        st.markdown("")
        a1, a2, a3 = st.columns(3)
        with a1:
            if st.button("♻️ Reload this run", use_container_width=True,
                         key="pr_reload"):
                try:
                    snap = store.load_run(_username, chosen["id"])
                except Exception as exc:
                    snap = None
                    st.error(f"Could not load that run: `{exc}`")
                if snap and isinstance(snap.get("results"), dict):
                    st.session_state.pipeline_results = snap["results"]
                    # Republish so every agent page reads this run too, the
                    # same way ESG Command Center rehydrates on load.
                    try:
                        from core.state_manager import state_manager as _sm
                        for _k, _v in snap["results"].items():
                            if isinstance(_v, dict) and "error" not in _v:
                                _sm.publish(f"{_k}_results", _v, "run-history-reload")
                        if isinstance(snap["results"].get("roi_agent"), dict):
                            st.session_state.roi_results = snap["results"]["roi_agent"]
                    except Exception:
                        pass
                    st.success("Run reloaded — open ESG Command Center to view it.",
                               icon="✅")
                elif snap is not None:
                    st.warning("That snapshot has no results payload.")
        with a2:
            try:
                _snap_for_dl = store.load_run(_username, chosen["id"])
            except Exception:
                _snap_for_dl = None
            st.download_button(
                "⬇️ Export run (JSON)",
                data=json.dumps(_snap_for_dl or chosen, indent=2,
                                default=str).encode("utf-8"),
                file_name=f"esg_run_{chosen.get('id', 'snapshot')}.json",
                mime="application/json",
                use_container_width=True,
                key="pr_export",
            )
        with a3:
            if st.button("🗑️ Delete this run", use_container_width=True,
                         key="pr_delete"):
                st.session_state["pr_confirm_delete"] = chosen.get("id")
        if st.session_state.get("pr_confirm_delete") == chosen.get("id"):
            st.warning(
                f"Delete **{chosen.get('label', 'this run')}** permanently? "
                f"This cannot be undone.",
                icon="⚠️",
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, delete it", key="pr_delete_yes"):
                    try:
                        store.delete_run(_username, chosen["id"])
                        st.session_state.pop("pr_confirm_delete", None)
                        st.success("Run deleted.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Delete failed: `{exc}`")
            with c2:
                if st.button("Cancel", key="pr_delete_no"):
                    st.session_state.pop("pr_confirm_delete", None)
                    st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# ACTIVITY LOG  (moved from ESG Command Center)
# ══════════════════════════════════════════════════════════════════════════
elif _section == "📡 Activity Log":
    section_header(
        "Activity Log",
        "Real-time timeline across every agent — filter by level, agent, or keyword.",
    )
    callout(
        "Every step each agent took in the current session, newest first. "
        "Use it to trace **what an agent actually did** before a result "
        "looked wrong.",
        icon="📡",
    )
    audit_rows = collect_audit_trail(getattr(orch, "agents", {}), limit=300)
    if audit_rows:
        log_panel(audit_rows, key="pr_log", height=460)
    else:
        callout(
            "No activity recorded in this session yet. Run the pipeline from "
            "**ESG Command Center** and the timeline will fill in here.",
            title="Nothing logged yet", icon="🕓",
        )


# ══════════════════════════════════════════════════════════════════════════
# PIPELINE OBSERVABILITY  (moved from ESG Command Center)
# ══════════════════════════════════════════════════════════════════════════
elif _section == "📊 Pipeline Observability":
    # Surfaces persistent run history from ``data/agent_telemetry.json`` plus
    # the in-memory planning log of the most recent run. Answers the operator
    # question "which agents are slow / failing / costing me tokens?" without
    # needing to grep logs or open files.
    section_header(
        "Pipeline Observability",
        "Per-agent run history, runtime trends, and token spend from the most "
        "recent pipeline.",
    )
    callout(
        "**Median** is the typical runtime; **p95** is the slow tail — if p95 "
        "is far above the median, that agent is occasionally stalling. A "
        "rising error count is where to look first.",
        icon="📊",
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
        safe_dataframe(pd.DataFrame(_telem_rows), use_container_width=True,
                       hide_index=True)
    else:
        st.caption("No agent telemetry recorded yet — run the pipeline to "
                   "populate this view.")

    # Planner step + token spend from the most recent run
    _planning = []
    try:
        _planning = list(getattr(orch, "planning_log", []) or [])
    except Exception:
        _planning = []

    st.markdown("")
    section_header("Planner Cost",
                   "What the LLM planner consumed on the most recent run.")
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
                     "Tool-use turns in the most recent run.", key="pr_obs_steps")
        with o2:
            kpi_card("Input Tokens", f"{_input_tokens:,}",
                     f"Billable after cache: {_billable_input:,}", key="pr_obs_in")
        with o3:
            kpi_card("Output Tokens", f"{_output_tokens:,}",
                     "Generated by the planner.", key="pr_obs_out")
        with o4:
            kpi_card("Cache Hit", f"{_cache_hit_pct:.0f}%",
                     f"{_cache_read:,} read / {_cache_create:,} created",
                     key="pr_obs_cache")
        with o5:
            # Rough cost using public Opus 4.x list-price ratios; numbers
            # update from this single constant if pricing changes.
            _per_million_input = 15.0
            _per_million_output = 75.0
            _est_cost = (_billable_input * _per_million_input
                         + _output_tokens * _per_million_output) / 1_000_000
            kpi_card("Est. Cost (USD)", f"${_est_cost:.3f}",
                     "List-price estimate, planner only.", key="pr_obs_cost")
        st.caption(
            "Cache hits are input tokens served from the prompt cache — they "
            "cost a fraction of fresh input, which is why a high hit rate "
            "keeps the estimate low."
        )
    else:
        callout(
            "Run the pipeline from **ESG Command Center** to see planner-step "
            "and token-spend telemetry for that run.",
            title="No planner run in this session", icon="🕓",
        )

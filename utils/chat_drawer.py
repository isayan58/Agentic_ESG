"""Global conversational BI drawer.

A right-anchored chat panel mounted on every authenticated page via
``utils.auth.sidebar_auth_widget``. Loads the user's latest pipeline run
lazily so the Pilot can answer grounded questions wherever the user is
in the app, not only on the Command Center. Renders inline charts when
Claude calls the ``render_chart`` tool — Plotly-backed, themed to match
the rest of the dashboards.
"""
from __future__ import annotations

import json
import os
from typing import Optional

import streamlit as st

import config

try:
    import anthropic
    _HAS_ANTHROPIC = True
except Exception:
    _HAS_ANTHROPIC = False

try:
    import plotly.graph_objects as go
    _HAS_PLOTLY = True
except Exception:
    _HAS_PLOTLY = False

from utils.run_store import get_run_store
from utils.run_summary import headline_metrics as _headline_metrics
from utils.chart_spec import (
    RENDER_CHART_DESCRIPTION,
    RENDER_CHART_INPUT_SCHEMA,
    figure_from_spec as _figure_from_tool_input,
)

# LangGraph + MCP Pilot — optional. When importable and configured, the
# chat drawer routes conversations through it (durable memory + MCP tools);
# otherwise it falls back to the legacy in-file tool-use loop below.
#
# The import failure is logged (not swallowed) so a missing/incompatible
# LangGraph/MCP install on a deploy target surfaces in the container logs
# as the *reason* for the legacy fallback, instead of failing invisibly.
import logging as _logging

_pilot_log = _logging.getLogger("esg.pilot")
_PILOT_IMPORT_ERROR: Optional[str] = None
try:
    from core import pilot_agent
    _HAS_PILOT_AGENT = True
except Exception as _exc:  # noqa: BLE001 — any import error means fall back
    pilot_agent = None  # type: ignore
    _HAS_PILOT_AGENT = False
    _PILOT_IMPORT_ERROR = repr(_exc)
    _pilot_log.warning(
        "ESG Pilot: LangGraph/MCP path unavailable — using legacy loop. "
        "core.pilot_agent import failed: %s", _exc, exc_info=True,
    )


_DRAWER_OPEN_KEY = "_chat_drawer_open"
_CHAT_HISTORY_KEY = "_chat_drawer_history"
_CACHED_RUN_KEY = "_chat_drawer_cached_run"
_HISTORY_REHYDRATED_KEY = "_chat_drawer_rehydrated"


# ---------------------------------------------------------------------------
# Tool definition — keep the input schema simple. Claude is more reliable
# emitting structured params than hand-authoring a full Plotly JSON spec,
# and we lose nothing by building the figure server-side from these fields.
# ---------------------------------------------------------------------------
# The legacy in-file tool-use loop (``_ask_pilot``) advertises render_chart as
# an Anthropic tool; the schema/description now live in ``utils.chart_spec`` so
# the MCP ``esg-charts`` server and this fallback can never drift apart.
_RENDER_CHART_TOOL = {
    "name": "render_chart",
    "description": RENDER_CHART_DESCRIPTION,
    "input_schema": RENDER_CHART_INPUT_SCHEMA,
}


# ---------------------------------------------------------------------------
# Run-context loaders — share the same priority logic as the inline chat
# in pages/1_ESG_Command_Center.py so answers are consistent across surfaces.
# ---------------------------------------------------------------------------
def _current_username() -> str:
    user = st.session_state.get("user") or {}
    return (user.get("username") or "").strip()


def _load_run_results() -> Optional[dict]:
    """Freshest pipeline run for the signed-in user.

    Prefers ``st.session_state['pipeline_results']`` (Command Center may
    have just produced one) and falls back to the latest persisted snapshot
    so the drawer is useful on every page, not only where the orchestrator
    lives in session state.
    """
    in_session = st.session_state.get("pipeline_results")
    if in_session:
        return in_session
    cached = st.session_state.get(_CACHED_RUN_KEY)
    if cached is not None:
        return cached or None
    username = _current_username()
    if not username:
        st.session_state[_CACHED_RUN_KEY] = {}
        return None
    try:
        snap = get_run_store().latest_run(username)
    except Exception:
        snap = None
    results = snap.get("results") if isinstance(snap, dict) else None
    st.session_state[_CACHED_RUN_KEY] = results or {}
    return results


def _pipeline_context(run: dict, char_limit: int = 30000) -> str:
    snapshot = {k: v for k, v in run.items() if k != "planning"}
    try:
        text = json.dumps(snapshot, default=str, indent=2)
    except TypeError:
        text = str(snapshot)
    if len(text) > char_limit:
        text = text[:char_limit] + "\n…[truncated]"
    return text


# ---------------------------------------------------------------------------
# Anthropic call — drives a tool-use loop so a single user question can
# return interleaved text and chart blocks.
# ---------------------------------------------------------------------------
def _ask_pilot(
    question: str,
    history: list[dict],
    run: Optional[dict],
) -> list[dict]:
    """Return a list of Anthropic content blocks (text + tool_use) for the
    final assistant message — preserves the order Claude produced them in
    so charts and prose render in the right sequence."""
    api_key = config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return [{"type": "text",
                 "text": "⚠️ `ANTHROPIC_API_KEY` is not set — the Pilot needs it to answer."}]
    if not _HAS_ANTHROPIC:
        return [{"type": "text", "text": "⚠️ `anthropic` SDK is not installed."}]

    client = anthropic.Anthropic(api_key=api_key)

    system: list[dict] = [{
        "type": "text",
        "text": (
            "You are the ESG Pilot, a conversational BI assistant for an enterprise "
            "ESG intelligence platform. Ground every claim in the JSON pipeline "
            "context provided. If the data cannot answer the question, say so plainly "
            "and point to the closest signal that *is* available. Prefer concrete "
            "numbers over generic ESG advice. Be concise — 2–4 short paragraphs or a "
            "tight bullet list. Never invent fields. "
            "When a chart would communicate the answer better than prose — IQS "
            "components, framework compliance comparisons, emissions breakdown by "
            "scope, risk drivers, completeness across datasets — call the "
            "render_chart tool, then add a short prose summary under it. "
            "Don't chart trivial single-value answers."
        ),
    }]
    headline = _headline_metrics(run or {})
    if headline:
        system.append({"type": "text", "text": headline})
    if run:
        system.append({
            "type": "text",
            "text": f"Pipeline run context (JSON):\n{_pipeline_context(run)}",
            "cache_control": {"type": "ephemeral"},
        })
    else:
        system.append({
            "type": "text",
            "text": ("No pipeline run is available for this user yet. Tell them to "
                     "open the ESG Command Center and run the pipeline first."),
        })

    messages: list[dict] = []
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})

    final_blocks: list[dict] = []
    for _ in range(4):
        response = client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=2048,
            system=system,
            messages=messages,
            tools=[_RENDER_CHART_TOOL],
        )
        assistant_blocks: list[dict] = []
        tool_uses: list[dict] = []
        for block in response.content:
            btype = getattr(block, "type", None)
            if btype == "text":
                assistant_blocks.append({"type": "text", "text": block.text})
            elif btype == "tool_use":
                tool_input = dict(getattr(block, "input", {}) or {})
                assistant_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": tool_input,
                })
                tool_uses.append(block.id)
        final_blocks.extend(assistant_blocks)

        if response.stop_reason != "tool_use" or not tool_uses:
            break

        messages.append({"role": "assistant", "content": assistant_blocks})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tu_id,
                "content": "Chart rendered.",
            } for tu_id in tool_uses],
        })

    return final_blocks


def _history_for_api(turns: list[dict]) -> list[dict]:
    """Strip tool_use blocks from prior assistant turns when sending the
    next question. Charts in earlier turns were already resolved with
    inline tool_result; re-sending raw tool_use without its tool_result
    would confuse the API. Keep only the text content of past assistant
    turns — visually the user still sees the chart in the rendered history."""
    out: list[dict] = []
    for turn in turns:
        if turn["role"] == "user":
            out.append({"role": "user", "content": str(turn["content"])})
        else:
            blocks = turn["content"] if isinstance(turn["content"], list) else \
                     [{"type": "text", "text": str(turn["content"])}]
            text_only = "\n\n".join(
                b.get("text", "") for b in blocks
                if b.get("type") == "text" and (b.get("text") or "").strip()
            ).strip()
            if text_only:
                out.append({"role": "assistant", "content": text_only})
    return out


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------
def _render_assistant_blocks(blocks: list[dict], chart_key_prefix: str) -> None:
    chart_idx = 0
    for block in blocks:
        btype = block.get("type")
        if btype == "text":
            text = (block.get("text") or "").strip()
            if text:
                st.markdown(text)
        elif btype == "tool_use" and block.get("name") == "render_chart":
            fig = _figure_from_tool_input(block.get("input") or {})
            if fig is not None:
                st.plotly_chart(
                    fig,
                    use_container_width=True,
                    key=f"{chart_key_prefix}_chart_{chart_idx}",
                )
                chart_idx += 1


# ---------------------------------------------------------------------------
# Answer dispatch — LangGraph + MCP Pilot when available, else legacy loop.
# ---------------------------------------------------------------------------
def _use_langgraph() -> bool:
    """True when the conversation should run through the LangGraph + MCP Pilot.
    Gated on the feature flag, the stack being importable, and an API key."""
    return bool(
        getattr(config, "PILOT_USE_LANGGRAPH", False)
        and _HAS_PILOT_AGENT
        and pilot_agent is not None
        and pilot_agent.available()
    )


def _engine_status() -> tuple[str, str]:
    """(label, reason) describing which Pilot engine is active and why.
    Surfaced in the drawer so 'is LangGraph working?' is answerable at a
    glance, and the *reason* for any legacy fallback is visible in-app."""
    if not getattr(config, "PILOT_USE_LANGGRAPH", False):
        return "legacy", "PILOT_USE_LANGGRAPH is off"
    if not _HAS_PILOT_AGENT or pilot_agent is None:
        return "legacy", f"LangGraph/MCP import failed — {_PILOT_IMPORT_ERROR or 'unknown'}"
    if not pilot_agent.available():
        reason = ("ANTHROPIC_API_KEY not set" if not (
            config.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY"))
            else "LangGraph stack not importable")
        return "legacy", reason
    return "langgraph", "LangGraph + MCP active"


def _render_engine_badge() -> None:
    label, reason = _engine_status()
    if label == "langgraph":
        st.caption("🟢 Engine: **LangGraph + MCP** · durable memory · live tools")
    else:
        st.caption(f"🟡 Engine: **legacy loop** · {reason}")


def _answer_question(question: str, username: str, run: Optional[dict]) -> list[dict]:
    """Produce the assistant's display blocks for one turn.

    Prefers the LangGraph + MCP Pilot (durable memory via the checkpointer,
    MCP-served tools incl. live pipeline runs). Falls back to the legacy
    in-file tool-use loop, which re-sends history and the run JSON each turn.
    """
    if _use_langgraph():
        try:
            return pilot_agent.ask_pilot(question, username)
        except Exception as exc:
            return [{"type": "text",
                     "text": f"⚠️ Pilot (LangGraph) call failed: `{exc}`"}]
    try:
        return _ask_pilot(
            question,
            _history_for_api(st.session_state[_CHAT_HISTORY_KEY][:-1]),
            run,
        )
    except Exception as exc:
        return [{"type": "text", "text": f"⚠️ Pilot call failed: `{exc}`"}]


def _rehydrate_history_from_checkpointer(username: str) -> None:
    """On first drawer render in a fresh session, repopulate the visible
    transcript from the LangGraph checkpointer so memory survives reloads and
    follows the user across devices (replacing the old session-only history)."""
    if st.session_state.get(_HISTORY_REHYDRATED_KEY):
        return
    st.session_state[_HISTORY_REHYDRATED_KEY] = True
    if not _use_langgraph() or st.session_state.get(_CHAT_HISTORY_KEY):
        return
    try:
        turns = pilot_agent.load_history(username)
    except Exception:
        turns = []
    if turns:
        st.session_state[_CHAT_HISTORY_KEY] = turns


# ---------------------------------------------------------------------------
# CSS — every rule is scoped to a ``.st-key-*`` class so styles can't leak
# to the rest of the app. ``st.container(key="X")`` adds a class
# ``st-key-X`` to its wrapper div, which is what we hook off here. The
# previous implementation used ``streamlit_extras.stylable_container``,
# but its CSS scoping turned out to be unreliable in our Streamlit
# version — every ``button`` selector bled to other pages and turned
# normal CTAs (Sign out, Download, Full Pipeline, etc.) into orange FAB
# circles. The class-prefix approach below is the migration path
# Streamlit recommends and is now deprecation-warning-free.
#
# The FAB only renders when the drawer is closed; the drawer's own
# header carries the close (✕) control. Keeping the FAB visible while
# open caused it to sit *inside* the drawer's footprint and end up
# unclickable behind the panel.
# ---------------------------------------------------------------------------
_DRAWER_STYLES = """
<style>
/* ---- Free up `position: fixed` to anchor to the viewport --------------
   Streamlit's outer shells (.stApp, stAppViewContainer, stMain) ship with
   properties — typically a stacking-context-creating transform or a
   `contain` declaration — that establish a new "containing block."
   Anything inside those shells with `position: fixed` then anchors to
   the *shell* rather than the viewport, so a FAB at `bottom: 1.4rem;
   right: 1.4rem` lands at the bottom-right of the *page* and disappears
   below the fold on scroll. Resetting these properties here removes the
   trap without touching the inner widget animations (hover transforms,
   etc.) which actually need transform to work. */
[data-testid="stApp"],
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"],
.main {
    transform: none !important;
    -webkit-transform: none !important;
    perspective: none !important;
    filter: none !important;
    -webkit-filter: none !important;
    contain: none !important;
    will-change: auto !important;
}

/* ---- Drawer panel ----------------------------------------------------- */
.st-key-esg_pilot_drawer {
    position: fixed;
    top: 4rem;
    right: 0;
    width: min(440px, 96vw);
    height: calc(100vh - 4rem);
    background: linear-gradient(180deg, #ffffff 0%, #fffaf4 100%);
    border-left: 1px solid rgba(253, 81, 8, 0.18);
    box-shadow: -16px 0 48px rgba(15, 23, 42, 0.18);
    z-index: 9998;
    overflow-y: auto;
    padding: 0.85rem 1rem 5rem 1rem;
}
.st-key-esg_pilot_drawer .stPlotlyChart,
.st-key-esg_pilot_drawer [data-testid="stPlotlyChart"] {
    max-width: 100% !important;
}
.st-key-esg_pilot_drawer .stPlotlyChart > div,
.st-key-esg_pilot_drawer [data-testid="stPlotlyChart"] > div {
    width: 100% !important;
}
.st-key-esg_pilot_drawer [data-testid="stChatMessage"] {
    padding: 0.5rem 0.6rem !important;
    margin-bottom: 0.5rem !important;
}
.st-key-esg_pilot_drawer [data-testid="stChatMessage"] p {
    font-size: 0.9rem !important;
    line-height: 1.45 !important;
}

/* ---- FAB (open-drawer trigger) ---------------------------------------
   The class lands on the button widget's outer wrapper because we attach
   `key="esg_pilot_fab"` directly to st.button — no st.container wrapper
   between us and the button. !important on the position is defensive
   against any base Streamlit rules that might otherwise win specificity
   and leave the FAB stuck in the document flow. */
.st-key-esg_pilot_fab {
    position: fixed !important;
    bottom: 1.4rem !important;
    right: 1.4rem !important;
    z-index: 9999 !important;
    width: auto !important;
    margin: 0 !important;
}
.st-key-esg_pilot_fab .stButton > button,
.st-key-esg_pilot_fab button {
    width: 56px !important;
    height: 56px !important;
    min-height: 56px !important;
    border-radius: 50% !important;
    background: linear-gradient(135deg, #FD5108 0%, #E0301E 60%, #FFB600 130%) !important;
    color: white !important;
    border: none !important;
    box-shadow:
        0 12px 28px rgba(253, 81, 8, 0.36),
        inset 0 1px 0 rgba(255, 255, 255, 0.35) !important;
    font-size: 1.5rem !important;
    padding: 0 !important;
    transition: transform 180ms ease, box-shadow 180ms ease !important;
}
.st-key-esg_pilot_fab .stButton > button:hover,
.st-key-esg_pilot_fab button:hover {
    transform: translateY(-3px) scale(1.04) !important;
    box-shadow:
        0 18px 36px rgba(253, 81, 8, 0.45),
        inset 0 1px 0 rgba(255, 255, 255, 0.4) !important;
}

/* ---- Close (✕) inside drawer header ---------------------------------- */
.st-key-esg_pilot_close .stButton > button,
.st-key-esg_pilot_close button {
    width: 34px !important;
    height: 34px !important;
    min-height: 34px !important;
    border-radius: 50% !important;
    background: rgba(15, 23, 42, 0.04) !important;
    color: #475569 !important;
    border: 1px solid rgba(15, 23, 42, 0.08) !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    padding: 0 !important;
    line-height: 1 !important;
    transition: background 160ms ease, color 160ms ease,
                border-color 160ms ease !important;
}
.st-key-esg_pilot_close .stButton > button:hover,
.st-key-esg_pilot_close button:hover {
    background: rgba(200, 16, 46, 0.08) !important;
    color: #C8102E !important;
    border-color: rgba(200, 16, 46, 0.30) !important;
}

/* ---- "Clear conversation" subtle text link --------------------------- */
.st-key-esg_pilot_clear .stButton > button,
.st-key-esg_pilot_clear button {
    background: transparent !important;
    color: #64748b !important;
    border: none !important;
    box-shadow: none !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    padding: 0.25rem 0.4rem !important;
    text-decoration: underline !important;
    text-decoration-color: rgba(100, 116, 139, 0.35) !important;
    text-underline-offset: 3px !important;
    width: auto !important;
    min-height: 0 !important;
    height: auto !important;
}
.st-key-esg_pilot_clear .stButton > button:hover,
.st-key-esg_pilot_clear button:hover {
    color: #C8102E !important;
    text-decoration-color: rgba(200, 16, 46, 0.5) !important;
    background: transparent !important;
}
</style>
"""


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def render_chat_drawer() -> None:
    """Render the global Pilot drawer + FAB. Mounted from
    ``utils.auth.sidebar_auth_widget`` so it appears on every page without
    per-page changes. Only signed-in users see it."""
    if not _current_username():
        return

    if _CHAT_HISTORY_KEY not in st.session_state:
        st.session_state[_CHAT_HISTORY_KEY] = []
    if _DRAWER_OPEN_KEY not in st.session_state:
        st.session_state[_DRAWER_OPEN_KEY] = False

    # Pull durable conversation memory back into the visible transcript once
    # per session (no-op on the legacy path or when nothing is stored).
    _rehydrate_history_from_checkpointer(_current_username())

    # Inject scoped styles once per page render. Cheap and idempotent —
    # browsers de-duplicate identical <style> tags effectively, and this
    # keeps the rules co-located with the components they target.
    st.markdown(_DRAWER_STYLES, unsafe_allow_html=True)

    open_now = bool(st.session_state[_DRAWER_OPEN_KEY])

    if not open_now:
        # Attach the key directly to the button so .st-key-esg_pilot_fab
        # lands on the button's own wrapper. An st.container(key=...)
        # around it added an extra DOM level that, in this Streamlit
        # version, didn't reliably receive the class — so the FAB lost
        # its position:fixed styling on rerun and the user saw nothing
        # to reopen the drawer with.
        if st.button("💬", key="esg_pilot_fab", help="Open ESG Pilot"):
            st.session_state[_DRAWER_OPEN_KEY] = True
            st.rerun()
        return

    with st.container(key="esg_pilot_drawer"):
        head_left, head_right = st.columns([6, 1], vertical_alignment="center")
        with head_left:
            st.markdown(
                "<div style='line-height:1.15;'>"
                "<div style='font-family:Plus Jakarta Sans,Inter,sans-serif;"
                "font-weight:700;font-size:1.02rem;color:#0f172a;'>🧭 ESG Pilot</div>"
                "<div style='font-size:0.66rem;color:#94a3b8;letter-spacing:0.08em;"
                "text-transform:uppercase;margin-top:2px;'>Conversational BI</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        with head_right:
            if st.button("✕", key="esg_pilot_close", help="Minimize"):
                st.session_state[_DRAWER_OPEN_KEY] = False
                st.rerun()

        _render_engine_badge()

        run = _load_run_results()
        if not run:
            st.info(
                "No pipeline run yet. Open **ESG Command Center** and run the "
                "pipeline to give the Pilot something to analyse."
            )
        else:
            st.caption(
                "Grounded in your latest pipeline run · ask for a chart anytime."
            )

        history = st.session_state[_CHAT_HISTORY_KEY]
        for idx, turn in enumerate(history):
            with st.chat_message(turn["role"]):
                if turn["role"] == "user":
                    content = turn["content"]
                    st.markdown(content if isinstance(content, str) else str(content))
                else:
                    blocks = turn["content"] if isinstance(turn["content"], list) else \
                             [{"type": "text", "text": str(turn["content"])}]
                    _render_assistant_blocks(blocks, chart_key_prefix=f"hist_{idx}")

        if history:
            if st.button("Clear conversation", key="esg_pilot_clear"):
                st.session_state[_CHAT_HISTORY_KEY] = []
                # Also drop the durable thread so cleared memory stays cleared
                # across reloads/devices, not just in this tab.
                if _use_langgraph():
                    try:
                        pilot_agent.clear_history(_current_username())
                    except Exception:
                        pass
                st.rerun()

        placeholder = (
            "Ask, or say 'run the pipeline' — try 'show me the IQS components'"
            if _use_langgraph()
            else "Ask about your run — try 'show me the IQS components'"
        )
        question = st.chat_input(placeholder, key="_pilot_input")
        if question:
            st.session_state[_CHAT_HISTORY_KEY].append({
                "role": "user", "content": question,
            })
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    blocks = _answer_question(question, _current_username(), run)
                _render_assistant_blocks(blocks, chart_key_prefix="live")
            st.session_state[_CHAT_HISTORY_KEY].append({
                "role": "assistant", "content": blocks,
            })


__all__ = ["render_chat_drawer"]

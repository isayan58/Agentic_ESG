"""ESG Pilot — LangGraph + MCP implementation of the conversational assistant.

This replaces the hand-rolled ``client.messages.create()`` loop in
``utils/chat_drawer.py`` with an off-the-shelf ``create_react_agent`` whose
tools are served by three MCP processes (``esg-data``, ``esg-pipeline``,
``esg-charts``). Conversation memory is a SQLite checkpointer keyed by
``thread_id = username`` — durable across reloads and devices, replacing
``st.session_state``.

The public surface is intentionally tiny and *synchronous* so the Streamlit
client doesn't have to care that the internals are async/MCP:

    blocks = ask_pilot(question, username)        # one turn → display blocks
    turns  = load_history(username)               # rehydrate the transcript

``blocks``/``turns`` use the exact same shape the existing
``chat_drawer._render_assistant_blocks`` already understands
(``[{"type": "text", ...}, {"type": "tool_use", "name": "render_chart", ...}]``),
so the UI rendering code is untouched.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Optional

import config

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SERVERS_DIR = _PROJECT_ROOT / "mcp_servers"


# --------------------------------------------------------------------------
# Availability probe — keep import of this module cheap and crash-free even
# when the LangGraph/MCP stack isn't installed, so chat_drawer can fall back.
# --------------------------------------------------------------------------
try:
    from langchain_anthropic import ChatAnthropic
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    from langgraph.prebuilt import create_react_agent
    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only without the stack
    LANGGRAPH_AVAILABLE = False


SYSTEM_PROMPT = (
    "You are the ESG Pilot, a conversational BI assistant for an enterprise "
    "ESG intelligence platform. Ground every claim in real run data — never "
    "invent fields or numbers.\n\n"
    "Tools available to you:\n"
    "  • esg-data: get_headline_metrics, get_agent_result, list_runs — read "
    "the user's saved pipeline runs. Start here for most questions.\n"
    "  • esg-charts: render_chart — draw a chart inline when it communicates "
    "the answer better than prose (IQS components, framework compliance, "
    "emissions by scope, risk drivers, completeness). Don't chart trivial "
    "single-value answers. After a chart, add a short prose summary.\n"
    "  • esg-pipeline: run_full_pipeline, run_agent — trigger a LIVE compute "
    "run. These are expensive; only call them when the user explicitly asks to "
    "run/refresh the pipeline or an agent.\n\n"
    "Every tool needs the user's username — it is: {username}. Always pass "
    "username=\"{username}\".\n"
    "Be concise: 2–4 short paragraphs or a tight bullet list. If the data "
    "can't answer the question, say so plainly and point to the closest "
    "signal that is available."
)


def available() -> bool:
    """True when the LangGraph + MCP path can run (stack importable + key set)."""
    api_key = config.ANTHROPIC_API_KEY or __import__("os").environ.get("ANTHROPIC_API_KEY", "")
    return bool(LANGGRAPH_AVAILABLE and api_key)


def _server_config() -> dict[str, dict]:
    """stdio launch spec for the three MCP servers. The same Python that runs
    Streamlit spawns each server as a subprocess so they share the venv."""
    def spec(module_file: str) -> dict:
        return {
            "command": sys.executable,
            "args": [str(_SERVERS_DIR / module_file)],
            "transport": "stdio",
        }
    return {
        "esg-data": spec("esg_data_server.py"),
        "esg-pipeline": spec("esg_pipeline_server.py"),
        "esg-charts": spec("esg_charts_server.py"),
    }


def _text_of(message: Any) -> str:
    """Flatten a LangChain message's content (str or list-of-blocks) to text."""
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    parts: list[str] = []
    for block in content or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, str):
            parts.append(block)
    return "\n".join(p for p in parts if p).strip()


def _chart_spec_from_tool_message(message: Any) -> Optional[dict]:
    """Return the chart spec if ``message`` is a render_chart tool result.

    Matches on the ``_esg_chart`` marker the esg-charts server stamps, so it
    works regardless of how the adapter names the tool. The MCP adapter may
    deliver the result either as a raw JSON string or as a list of content
    blocks (``[{"type": "text", "text": "{...}"}]``) — handle both."""
    raw = _text_of(message) if getattr(message, "content", None) else ""
    if "_esg_chart" not in raw:
        return None
    try:
        spec = json.loads(raw)
    except (ValueError, TypeError):
        return None
    if isinstance(spec, dict) and spec.get("_esg_chart"):
        return spec
    return None


def _blocks_from_messages(messages: list) -> list[dict]:
    """Convert a contiguous run of assistant/tool messages into ordered display
    blocks (text + render_chart tool_use), preserving the prose→chart→prose
    interleaving the model produced."""
    blocks: list[dict] = []
    for msg in messages:
        mtype = msg.__class__.__name__
        if mtype == "AIMessage":
            text = _text_of(msg)
            if text:
                blocks.append({"type": "text", "text": text})
        elif mtype == "ToolMessage":
            spec = _chart_spec_from_tool_message(msg)
            if spec is not None:
                blocks.append({
                    "type": "tool_use",
                    "name": "render_chart",
                    "input": {k: v for k, v in spec.items() if k != "_esg_chart"},
                })
    return blocks


def _split_into_turns(messages: list) -> list[dict]:
    """Group a full thread's messages into chat turns matching the
    chat_drawer history format: user turns carry a string, assistant turns
    carry a list of display blocks."""
    turns: list[dict] = []
    pending_assistant: list = []

    def flush_assistant() -> None:
        if pending_assistant:
            blocks = _blocks_from_messages(pending_assistant)
            if blocks:
                turns.append({"role": "assistant", "content": blocks})
            pending_assistant.clear()

    for msg in messages:
        if msg.__class__.__name__ == "HumanMessage":
            flush_assistant()
            turns.append({"role": "user", "content": _text_of(msg)})
        else:
            pending_assistant.append(msg)
    flush_assistant()
    return turns


# --------------------------------------------------------------------------
# Async core
# --------------------------------------------------------------------------
async def _ask_async(question: str, username: str) -> list[dict]:
    Path(config.PILOT_CHECKPOINT_DB).parent.mkdir(parents=True, exist_ok=True)
    client = MultiServerMCPClient(_server_config())
    tools = await client.get_tools()
    model = ChatAnthropic(
        model=config.ANTHROPIC_MODEL,
        api_key=config.ANTHROPIC_API_KEY,
        max_tokens=2048,
    )
    prompt = SYSTEM_PROMPT.format(username=username)
    cfg = {"configurable": {"thread_id": username}}

    async with AsyncSqliteSaver.from_conn_string(config.PILOT_CHECKPOINT_DB) as saver:
        agent = create_react_agent(model, tools, checkpointer=saver, prompt=prompt)
        # Snapshot how many messages already exist on this thread so we render
        # only what THIS turn added (the checkpointer carries the full history).
        state = await agent.aget_state(cfg)
        prior = len(state.values.get("messages", [])) if state and state.values else 0
        result = await agent.ainvoke(
            {"messages": [{"role": "user", "content": question}]}, config=cfg,
        )

    new_messages = result["messages"][prior + 1:]  # +1 skips this turn's human msg
    blocks = _blocks_from_messages(new_messages)
    return blocks or [{"type": "text", "text": "(no response)"}]


async def _history_async(username: str) -> list[dict]:
    db = config.PILOT_CHECKPOINT_DB
    if not Path(db).exists():
        return []
    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        tup = await saver.aget_tuple({"configurable": {"thread_id": username}})
    if not tup:
        return []
    messages = (tup.checkpoint.get("channel_values") or {}).get("messages") or []
    return _split_into_turns(messages)


# --------------------------------------------------------------------------
# Sync public surface — Streamlit calls these. asyncio.run gives each call a
# fresh event loop, which is safe because Streamlit reruns are themselves
# fresh synchronous executions.
# --------------------------------------------------------------------------
def ask_pilot(question: str, username: str) -> list[dict]:
    """Answer one user turn. Returns ordered display blocks (text + charts).
    Conversation memory is loaded/saved by the checkpointer under ``username``,
    so callers do NOT pass prior history."""
    return asyncio.run(_ask_async(question, username))


def load_history(username: str) -> list[dict]:
    """Rehydrate the visible transcript for ``username`` from the checkpointer,
    in chat_drawer's history format. Empty list when no thread exists yet."""
    try:
        return asyncio.run(_history_async(username))
    except Exception:
        return []


async def _clear_async(username: str) -> None:
    db = config.PILOT_CHECKPOINT_DB
    if not Path(db).exists():
        return
    async with AsyncSqliteSaver.from_conn_string(db) as saver:
        await saver.adelete_thread(username)


def clear_history(username: str) -> None:
    """Permanently drop the durable conversation thread for ``username``."""
    try:
        asyncio.run(_clear_async(username))
    except Exception:
        pass


__all__ = [
    "ask_pilot", "load_history", "clear_history", "available", "LANGGRAPH_AVAILABLE",
]

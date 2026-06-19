# ESG Pilot Chatbot — Migrating to LangGraph + MCP
### Slide-by-slide content for the .pptx build

> Two diagrams were rendered inline in chat: the current chatbot architecture, and the proposed LangGraph + MCP target architecture. This doc carries the slide text; once the build sandbox is available, this gets assembled into the actual .pptx with those diagrams as native vector graphics.

---

## Slide 1 — Title

**ESG Pilot Chatbot: From a Hand-Rolled Loop to LangGraph + MCP**
Subtitle: A generic blueprint for re-platforming the "ESG Pilot" conversational assistant

---

## Slide 2 — What the Chatbot Does Today

- A Streamlit chat drawer (`utils/chat_drawer.py`), mounted on every authenticated page, lets users ask questions about their latest ESG pipeline run.
- It is a single conversational layer over cached pipeline output — not one of the 9 domain agents, and not the Gradio dashboard (which is a separate tabbed UI for triggering agents individually).
- Today it works well for "answer questions about the run that's already in this browser tab."

---

## Slide 3 — Current Architecture (as built)

*(See the "current chatbot architecture" diagram shown above.)*

- One hand-rolled loop: `client.messages.create()`, repeated up to 4 times, stopping when the model stops requesting tools.
- One tool: `render_chart` — builds a Plotly figure server-side from the model's chart spec.
- Grounding: the entire latest pipeline-run JSON (up to 30,000 characters) is dumped into the system prompt on every turn, plus a hand-extracted headline-metrics summary.
- Memory: `st.session_state` — conversation history lives only in that browser tab; a reload or a different device starts fresh.

---

## Slide 4 — Why Re-platform It

- No way to trigger a *live* agent run from chat — it can only read whatever was cached the last time the pipeline ran.
- Context is a context-window-eating JSON dump, not a targeted lookup — costly and not scalable as run history or company data grows.
- Tool surface (today: just `render_chart`) is hardcoded into the UI file, so adding a capability means editing the chat loop itself.
- Memory doesn't survive a reload or follow the user across the Streamlit app, the Gradio dashboard, or any future channel (Slack, Teams).

---

## Slide 5 — Target Architecture: LangGraph + MCP

*(See the "target chatbot architecture" diagram shown above.)*

- **MCP servers** wrap each capability behind a standard tool interface:
  - `esg-data` — `get_agent_result`, `get_headline_metrics`, `list_runs`
  - `esg-pipeline` — `run_agent`, `run_full_pipeline` (wraps the existing `Orchestrator`)
  - `esg-charts` — `render_chart`, lifted out of the Streamlit file so any client can use it
- **LangGraph** replaces the hand-rolled loop with `create_react_agent(model, tools, checkpointer=...)` — automatic tool-call looping, no manual `stop_reason` bookkeeping.
- **Checkpointer** (Postgres/SQLite) keyed by `thread_id = username` gives durable, cross-session, cross-device memory in place of `st.session_state`.

---

## Slide 6 — What Changes in the Code

- `chat_drawer.py`'s Streamlit rendering stays as-is — only the call inside it swaps:
  - Before: `_ask_pilot(question, history, run)` (the manual 4-iteration loop)
  - After: `graph.invoke({"messages": [...]}, config={"configurable": {"thread_id": username}})`
- MCP servers run as small standalone processes (`mcp` Python SDK's `FastMCP`), reachable over stdio or HTTP — independent of any one UI.
- Tool definitions move out of the chat file and into the relevant MCP server, so the agent loop never needs to change when a tool is added.

---

## Slide 7 — What This Buys, and What It Costs

**Gains**
- Chat can trigger a live pipeline/agent run, not just read a cached snapshot.
- Conversation memory survives reloads and works across devices.
- New tools register on an MCP server — zero changes to the agent loop.
- The same agent + tools can power Streamlit, the Gradio dashboard, or a future Slack/Teams bot with no duplicated logic.

**Cost**
- One more moving part to deploy and operate: the MCP server process(es).
- Worth it once the chatbot needs to do more than answer questions about a cached run in one browser tab.

---

## Slide 8 — Takeaways

- The current chatbot is a single Claude tool-use loop with one tool and a JSON-dump grounding strategy — simple, and adequate for its original scope.
- LangGraph supplies the orchestration (looping, state, persistence); MCP supplies the tool boundary (capabilities as swappable, shareable servers).
- This mirrors the same "shared state, not direct calls" philosophy already used by ESG Pilot's 9-agent pipeline — the chatbot would just be adopting the off-the-shelf version of that pattern.

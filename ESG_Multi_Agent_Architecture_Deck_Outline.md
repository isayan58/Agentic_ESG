# ESG Pilot — Multi-Agent Architecture
### Slide-by-slide content for the .pptx build

> The two architecture diagrams (ESG pipeline reframed in graph terms, and the generic LangGraph + MCP reference architecture) were rendered and shown inline in chat. This doc carries the text content for each slide; once the build sandbox is back, this gets assembled into the actual .pptx with those diagrams as native vector graphics.

---

## Slide 1 — Title

**ESG Pilot: Multi-Agent Architecture**
Subtitle: How nine domain agents, a Claude-driven orchestration graph, and a shared state layer power the ESG analytics pipeline

---

## Slide 2 — What ESG Pilot Does

- Nine specialist agents cover the full ESG lifecycle: data ingestion, regulatory compliance, carbon accounting, climate risk, audit readiness, ROI, reporting, action planning, and stakeholder communications.
- Every calculation is deterministic Python — Scope 1/2/3 totals, compliance %, risk scores, ROI. The only LLM-driven decision is *which agent runs when*.
- AI narrative polish (HuggingFace) and orchestration planning (Claude) are both optional — the pipeline produces correct numeric output even with zero API keys configured.

---

## Slide 3 — The Agent Graph (mapped to LangGraph concepts)

Framing note for the room: the system is implemented as a **Claude tool-use loop**, not LangGraph — but the shape maps cleanly onto LangGraph's mental model, which is why we present it this way.

| LangGraph concept | ESG Pilot equivalent |
|---|---|
| Graph nodes | The 9 domain agents (`agents/*.py`, each a `BaseAgent` subclass) |
| Supervisor / router | `core/agent_loop.py` — a Claude tool-use loop that decides which agent-tools to call, in what order, parallel or sequential |
| Conditional edges | The dependency graph baked into each tool's description (`PIPELINE_ORDER` in `core/orchestrator.py`) — calling a node before its prerequisites returns an error |
| Shared graph state | `core/state_manager.py` — an in-process pub/sub bus of named **Channels** (`carbon_results`, `risk_results`, etc.) that every node publishes to and subscribes from |
| Checkpointing | Per-run incremental cache — unchanged inputs short-circuit a re-run and reuse the prior node's output |

*(See the architecture diagram shown above for the full layered dependency graph.)*

---

## Slide 4 — Dependency Graph Walkthrough

```
data_collector
   ├─► regulatory_tracker
   ├─► carbon_accountant
   ├─► risk_predictor        (+ regulatory_tracker)
   ├─► audit_agent           (+ regulatory_tracker, carbon_accountant)
   └─► roi_agent             (+ carbon_accountant, risk_predictor)

audit_agent, carbon_accountant, risk_predictor, roi_agent ─► report_generator
risk_predictor, audit_agent, report_generator, roi_agent  ─► action_agent
action_agent, report_generator, roi_agent                 ─► stakeholder_agent
```

- The supervisor calls multiple agent-tools **in parallel** in the same turn whenever their inputs are independent (e.g. `carbon_accountant` and `regulatory_tracker` both only need `data_collector`).
- A hallucinated out-of-order call is rejected at execution time, not just discouraged in the prompt — the dependency check is enforced in code.
- `_ensure_complete()` runs any agent the planner skipped, so "run the full pipeline" always yields all 9 results regardless of what the LLM decided was sufficient.

---

## Slide 5 — Shared State, Not Direct Calls

- Agents never call each other directly. Every result is **published** to a named channel; downstream agents **subscribe** to the channels they depend on.
- Channels are centralized in an enum (`core/channels.py`) specifically so a typo becomes a `NameError` instead of a silent `None` read downstream.
- This in-process pub/sub is a Python dict today (Topology A: the bundled Streamlit monolith). For a distributed deployment, the same five-method interface (`publish`, `subscribe`, `get_all_channels`, …) gets swapped for Redis Streams / NATS / Kafka — the agent code itself never changes.

---

## Slide 6 — Deployment Topologies

| Topology | Shape | State manager |
|---|---|---|
| A — Monolith | 1 process, Streamlit UI | In-process dict |
| B — Single-agent batch | 1 agent, cron/lambda | In-process dict |
| C — Multi-agent batch, no UI | 1 process, CLI/Airflow | In-process dict |
| D — Distributed microservices | 1 process per agent | Redis / NATS / Kafka adapter |

Same agent code runs unmodified across all four — only the orchestration and state layer change.

---

## Slide 7 — Generic Agentic Solution Architecture (Reference Pattern)

A vendor-agnostic version of this pattern for a **new** agentic build, using the two pieces most teams reach for today:

- **LangGraph** for the orchestration layer — a `StateGraph` with a supervisor/router node, worker agent nodes, shared graph state, and a checkpointer for persistence across turns.
- **MCP (Model Context Protocol) servers** for the tool-access layer — each MCP server wraps a coherent capability (internal tools, a data/warehouse layer, search/SaaS connectors) behind a standard JSON-RPC interface; the agent runtime's MCP client discovers and calls them without bespoke integration code per tool.

*(See the generic architecture diagram shown above.)*

Why this combination: LangGraph gives explicit, debuggable control over multi-agent flow and state; MCP gives a clean boundary so new tools/data sources plug in without touching agent code — directly analogous to how ESG Pilot's channel-based pub/sub decouples agents from each other today.

---

## Slide 8 — Takeaways

- ESG Pilot's real orchestration is a **Claude tool-use loop over 9 deterministic agents**, coordinated through a pub/sub state layer — not LangGraph, not MCP, today.
- The architecture already has the right shape (nodes, dependency-aware routing, shared state, swappable transport) to migrate to LangGraph + MCP if/when that's the chosen direction — it would be a re-platform of the orchestration layer, not a redesign of the agents.
- The generic reference architecture (Slide 7) is what we'd propose for a **new** agentic build today, or as a target state for ESG Pilot's next iteration.

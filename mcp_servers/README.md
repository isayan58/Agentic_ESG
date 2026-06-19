# ESG Pilot MCP servers

Three [MCP](https://modelcontextprotocol.io) servers that expose the ESG Pilot's
capabilities behind a standard tool interface, so any client (the LangGraph
Pilot in `core/pilot_agent.py`, a future Slack/Teams bot, an eval harness) can
use them without importing app internals.

| Server | File | Tools |
|---|---|---|
| `esg-data` | `esg_data_server.py` | `list_runs`, `get_headline_metrics`, `get_agent_result` |
| `esg-pipeline` | `esg_pipeline_server.py` | `run_full_pipeline`, `run_agent` (live compute via `core.orchestrator.Orchestrator`) |
| `esg-charts` | `esg_charts_server.py` | `render_chart` (validates a spec; the client paints it) |

## How they run

The Pilot spawns all three over **stdio** as subprocesses — see
`core.pilot_agent._server_config()`. You normally never start them by hand.

To inspect one standalone (serves on stdio, Ctrl-C to stop):

```bash
python -m mcp_servers.esg_data_server
```

## Notes

- `esg-pipeline` triggers real Claude-driven runs and needs `ANTHROPIC_API_KEY`.
- All servers read/write the shared `utils.run_store`, so a run produced by
  `esg-pipeline` is immediately visible to `esg-data` and every UI surface.
- The chart contract (schema + renderer) lives in `utils/chart_spec.py`, shared
  by the `esg-charts` server and every client so they can't drift.

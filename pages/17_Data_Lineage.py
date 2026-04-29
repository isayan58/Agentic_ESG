"""Data Lineage — interactive provenance graph for the current pipeline run.

Closes the "where did this number come from?" gap that auditors ask
about. Walks four layers and renders them as a Sankey + a per-agent
table:

    Sources (connectors)  →  Schemas (canonical names)  →  Agents (9)  →  Outputs (state_manager channels)

Reads from:
* ``utils.connection_manager.ConnectionManager`` — registered sources
* ``utils.schema_mapper.SCHEMAS``                — canonical schema list
* ``core.orchestrator.PIPELINE_ORDER``           — agent dependency graph
* ``core.state_manager.state_manager``           — published channels
* ``utils.agent_telemetry.load_all``             — last-run timing per agent

Performance: pure metadata read, no extra agent runs. This page is safe
to land on while the pipeline is still active — it'll show whatever
state has been published so far.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.orchestrator import PIPELINE_ORDER
from core.state_manager import state_manager
from utils.agent_telemetry import load_all as load_telemetry
from utils.auth import require_login, sidebar_auth_widget
from utils.rbac import require_permission
from utils.session import get_session_connection_manager
from utils.streamlit_compat import safe_dataframe
from utils.ui import hero, inject_global_css, pwc_header, section_header

try:
    import plotly.graph_objects as go
    _PLOTLY = True
except ImportError:
    _PLOTLY = False


st.set_page_config(
    page_title="Data Lineage | ESG Intelligence Hub",
    page_icon="🧬",
    layout="wide",
)
inject_global_css()
pwc_header()
sidebar_auth_widget()
user = require_login("Sign in to view data lineage.")
require_permission("view_lineage")

hero(
    title="Data Lineage",
    emoji="🧬",
    subtitle=(
        "Trace every output back to its source. Walk source connectors → "
        "canonical schemas → agents → published channels. Click an agent "
        "below to see its inputs, output, and last run time."
    ),
    chips=[
        "Source → Schema → Agent → Output",
        "Live state — no extra runs needed",
        "Auditor-friendly",
    ],
)

conn_mgr = get_session_connection_manager()
sources = conn_mgr.list_sources() if conn_mgr else []
telemetry = load_telemetry() or {}

# Map schema → list of agents that publish a channel sourced from it.
# This is *static* knowledge about the pipeline (which agent reads which
# canonical schema) plus *dynamic* knowledge from state_manager (which
# channels actually got published in the current run).
AGENT_SCHEMA_INPUTS = {
    "data_collector": ["emissions", "esg_metrics", "supply_chain",
                       "energy", "waste", "diversity", "financials"],
    "regulatory_tracker": ["esg_metrics"],
    "carbon_accountant": ["emissions", "energy", "supply_chain"],
    "risk_predictor": ["esg_metrics", "supply_chain", "emissions", "financials"],
    "audit_agent": ["esg_metrics"],
    "roi_agent": ["financials", "esg_metrics", "emissions",
                  "energy", "supply_chain", "diversity"],
    "report_generator": ["esg_metrics"],
    "action_agent": [],
    "stakeholder_agent": [],
}

AGENT_OUTPUT_CHANNEL = {
    "data_collector": "data_collection_results",
    "regulatory_tracker": "regulatory_results",
    "carbon_accountant": "carbon_results",
    "risk_predictor": "risk_results",
    "audit_agent": "audit_results",
    "roi_agent": "roi_results",
    "report_generator": "report_results",
    "action_agent": "action_results",
    "stakeholder_agent": "stakeholder_results",
}

PIPELINE_DEPS = {key: deps for key, _, deps in PIPELINE_ORDER}
agent_keys = [key for key, _, _ in PIPELINE_ORDER]
all_channels = state_manager.get_all_channels() or {}

# ---------------------------------------------------------------------------
# Sankey
# ---------------------------------------------------------------------------
section_header(
    "Lineage diagram",
    "Source → schema → agent → output. Width is informational only.",
)
if not _PLOTLY:
    st.info("Plotly is not installed in this environment — showing the table only.")
else:
    # Build a Sankey by accumulating unique node labels per layer, then
    # link source→schema, schema→agent, agent→output.
    source_labels = [f"src · {s['display_name']}" for s in sources] or ["src · (sample data)"]
    source_schemas = [s.get("target_schema", "emissions") for s in sources] \
        if sources else ["emissions", "esg_metrics", "supply_chain",
                          "energy", "waste", "diversity", "financials"]
    schema_labels = [f"schema · {sch}" for sch in
                     sorted(set(source_schemas
                                + [sch for inputs in AGENT_SCHEMA_INPUTS.values()
                                   for sch in inputs]))]
    agent_labels = [f"agent · {k}" for k in agent_keys]
    output_labels = [f"out · {AGENT_OUTPUT_CHANNEL[k]}" for k in agent_keys]

    nodes = source_labels + schema_labels + agent_labels + output_labels
    node_index = {label: idx for idx, label in enumerate(nodes)}
    links_src, links_dst, links_value, links_color = [], [], [], []

    # Layer 1: source → schema
    if sources:
        for s in sources:
            src_label = f"src · {s['display_name']}"
            sch_label = f"schema · {s.get('target_schema', 'emissions')}"
            if src_label in node_index and sch_label in node_index:
                links_src.append(node_index[src_label])
                links_dst.append(node_index[sch_label])
                links_value.append(max(1, int(s.get("last_row_count") or 1)))
                links_color.append("rgba(208, 74, 2, 0.35)")
    else:
        # No registered sources — wire the sample-data placeholder to
        # every canonical schema so the diagram still reads well.
        sample_label = "src · (sample data)"
        for sch in source_schemas:
            sch_label = f"schema · {sch}"
            if sample_label in node_index and sch_label in node_index:
                links_src.append(node_index[sample_label])
                links_dst.append(node_index[sch_label])
                links_value.append(1)
                links_color.append("rgba(148, 163, 184, 0.35)")

    # Layer 2: schema → agent
    for agent_key, schemas_in in AGENT_SCHEMA_INPUTS.items():
        for sch in schemas_in:
            sch_label = f"schema · {sch}"
            agent_label = f"agent · {agent_key}"
            if sch_label in node_index and agent_label in node_index:
                links_src.append(node_index[sch_label])
                links_dst.append(node_index[agent_label])
                links_value.append(1)
                links_color.append("rgba(34, 197, 94, 0.30)")

    # Also link agent dependencies (downstream consumers don't read raw
    # schemas — they read the upstream agent's published channel)
    for agent_key, deps in PIPELINE_DEPS.items():
        for dep in deps:
            up = f"agent · {dep}"
            down = f"agent · {agent_key}"
            if up in node_index and down in node_index:
                links_src.append(node_index[up])
                links_dst.append(node_index[down])
                links_value.append(1)
                links_color.append("rgba(59, 130, 246, 0.30)")

    # Layer 3: agent → output channel
    for agent_key in agent_keys:
        agent_label = f"agent · {agent_key}"
        out_label = f"out · {AGENT_OUTPUT_CHANNEL[agent_key]}"
        if agent_label in node_index and out_label in node_index:
            published = AGENT_OUTPUT_CHANNEL[agent_key] in all_channels
            links_src.append(node_index[agent_label])
            links_dst.append(node_index[out_label])
            links_value.append(1)
            links_color.append(
                "rgba(16, 185, 129, 0.55)" if published
                else "rgba(148, 163, 184, 0.25)"
            )

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15, thickness=14,
            line=dict(color="rgba(15, 23, 42, 0.4)", width=0.5),
            label=nodes,
            color=[
                "#D04A02" if lbl.startswith("src · ") else
                "#22C55E" if lbl.startswith("schema · ") else
                "#3B82F6" if lbl.startswith("agent · ") else
                "#10B981"
                for lbl in nodes
            ],
        ),
        link=dict(
            source=links_src, target=links_dst,
            value=links_value, color=links_color,
        ),
    )])
    fig.update_layout(font_size=11, height=520, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

# ---------------------------------------------------------------------------
# Per-agent table
# ---------------------------------------------------------------------------
section_header(
    "Per-agent lineage",
    "What each agent reads, what it publishes, and when it last ran.",
)
rows = []
for agent_key in agent_keys:
    tele = telemetry.get(agent_key) or {}
    out_channel = AGENT_OUTPUT_CHANNEL[agent_key]
    published = all_channels.get(out_channel)
    rows.append({
        "Agent": agent_key,
        "Reads (schemas)": ", ".join(AGENT_SCHEMA_INPUTS.get(agent_key, [])) or "—",
        "Reads (upstream agents)": ", ".join(PIPELINE_DEPS.get(agent_key, [])) or "—",
        "Publishes": out_channel,
        "Status": tele.get("status") or "idle",
        "Last run": (tele.get("last_run") or "—"),
        "Runtime (s)": tele.get("runtime_seconds") or "—",
        "Output present": "✅" if published else "—",
        "Published by": (published or {}).get("published_by", "—"),
    })
safe_dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Source → schema mapping detail
# ---------------------------------------------------------------------------
section_header(
    "Configured data sources",
    "The connectors that feed canonical schemas in this workspace. "
    "Empty list means the pipeline is running on bundled sample data.",
)
if not sources:
    st.info(
        "No data sources are registered. Open **Data Collector** to wire one "
        "in, or upload a CSV / Excel file directly."
    )
else:
    src_rows = []
    for s in sources:
        src_rows.append({
            "Source": s.get("display_name", s.get("id", "?")),
            "Connector": s.get("connector_type", "?"),
            "Target schema": s.get("target_schema", "?"),
            "Status": s.get("status", "configured"),
            "Last fetch": s.get("last_fetch") or "—",
            "Rows": s.get("last_row_count") or 0,
        })
    safe_dataframe(pd.DataFrame(src_rows), use_container_width=True,
                    hide_index=True)

# ---------------------------------------------------------------------------
# Channel inventory
# ---------------------------------------------------------------------------
section_header(
    "Live channel inventory",
    "Every channel currently populated on the per-user state bus. Useful "
    "when debugging why a downstream agent doesn't see the data you expect.",
)
if not all_channels:
    st.info("No channels published yet — run the pipeline first.")
else:
    ch_rows = []
    for ch_name, info in sorted(all_channels.items()):
        ch_rows.append({
            "Channel": ch_name,
            "Published by": info.get("published_by", "?"),
            "Timestamp": info.get("timestamp", "?"),
            "Has data": "✅" if info.get("has_data") else "—",
        })
    safe_dataframe(pd.DataFrame(ch_rows), use_container_width=True,
                    hide_index=True)

"""ESG CoPilot — Gradio Interface with tabs for all 8 agents."""
import os

# ── Fix jinja2 + starlette incompatibility ──────────────────────────────────
# Newer starlette passes a dict as `globals` to jinja2's get_template(),
# which becomes part of an unhashable cache key. Patch the method directly
# on jinja2.Environment so it catches TypeError and loads without caching.
import jinja2

_orig_get_template = jinja2.Environment.get_template


def _safe_get_template(self, name, parent=None, globals=None):
    try:
        return _orig_get_template(self, name, parent, globals)
    except TypeError:
        # Unhashable globals dict — bypass the cache and load directly
        if self.loader is None:
            raise TypeError("no loader for this environment specified")
        return self.loader.load(self, name, self.make_globals(globals))


jinja2.Environment.get_template = _safe_get_template
# ── End jinja2 fix ──────────────────────────────────────────────────────────

import gradio as gr

# ── Fix Gradio health-check in Docker containers ──
# Gradio's launch() verifies localhost is reachable, which fails in HF Spaces
# Docker. HF has its own reverse-proxy health check so this is safe to skip.
import gradio.networking
gradio.networking.url_ok = lambda url: True
# ── End health-check fix ──

import pandas as pd
import json
from agents.data_collector import DataCollectorAgent
from agents.regulatory_tracker import RegulatoryTrackerAgent
from agents.carbon_accountant import CarbonAccountantAgent
from agents.report_generator import ReportGeneratorAgent
from agents.risk_predictor import RiskPredictorAgent
from agents.audit_agent import AuditAgent
from agents.action_agent import ActionAgent
from agents.stakeholder_agent import StakeholderAgent
from core.orchestrator import Orchestrator

# Initialize agents
orchestrator = Orchestrator()


def format_dict(d, indent=0):
    """Format a dict for display."""
    lines = []
    for k, v in d.items():
        prefix = "  " * indent
        if isinstance(v, dict):
            lines.append(f"{prefix}**{k}:**")
            lines.append(format_dict(v, indent + 1))
        elif isinstance(v, list):
            lines.append(f"{prefix}**{k}:** {len(v)} items")
        else:
            lines.append(f"{prefix}**{k}:** {v}")
    return "\n".join(lines)


# --- Agent functions ---

def run_data_collector():
    agent = orchestrator.get_agent("data_collector")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", ""

    summary = (
        f"## Data Collection Results\n\n"
        f"- **Datasets Loaded:** {results.get('datasets_loaded', 0)}\n"
        f"- **Total Records:** {results.get('total_records', 0):,}\n"
        f"- **Overall Completeness:** {results.get('overall_completeness', 0)}%\n"
        f"- **Avg Confidence:** {results.get('overall_confidence', 0)}%\n\n"
        f"### Quality Scores\n\n"
    )
    for name, q in results.get("quality_scores", {}).items():
        summary += f"- **{name}:** {q['completeness']}% complete, {q['total_records']} records\n"

    issues = results.get("quality_issues", [])
    issues_text = ""
    if issues:
        issues_text = "### Quality Issues\n\n"
        for issue in issues:
            issues_text += f"- **{issue['dataset']}:** {issue['issue']} ({issue['severity']})\n"
    else:
        issues_text = "### No quality issues detected"

    return summary, issues_text


# --- Real data connector functions ---
from utils.schema_mapper import (
    auto_detect_schema, suggest_column_mapping, apply_column_mapping,
    validate_mapped_data, get_schema_names, get_schema_columns, ESG_SCHEMAS,
)
from utils.real_connectors import get_connector, get_available_connectors
from utils.connection_manager import ConnectionManager

# Session-level connection manager (shared across Gradio callbacks)
_conn_manager = ConnectionManager()
_preview_state = {"df": None, "source_type": None, "config": None}


def test_file_upload(file):
    """Test a file upload and return preview + detected schema."""
    if file is None:
        return "❌ No file uploaded", "", "{}"
    try:
        connector = get_connector("file_upload")
        with open(file.name, "rb") as f:
            file_bytes = f.read()
        file_name = os.path.basename(file.name)
        result = connector.test_connection(file_bytes=file_bytes, file_name=file_name)
        if not result["success"]:
            return f"❌ {result['message']}", "", "{}"

        df = connector.fetch(file_bytes=file_bytes, file_name=file_name)
        _preview_state["df"] = df
        _preview_state["source_type"] = "file_upload"
        _preview_state["config"] = {"file_bytes": file_bytes, "file_name": file_name}

        detected = auto_detect_schema(df)
        mapping = suggest_column_mapping(df, detected) if detected else {}

        preview = f"✅ **{result['message']}**\n\n"
        preview += f"**Auto-detected schema:** `{detected or 'Unknown — please select manually'}`\n\n"
        preview += f"**Columns found:** {', '.join(df.columns)}\n\n"
        preview += "**Preview (first 5 rows):**\n\n"
        preview += df.head(5).to_markdown(index=False)

        mapping_text = _format_mapping(mapping, detected) if detected else "Select a target schema to see mapping suggestions."

        return preview, mapping_text, json.dumps({"detected_schema": detected, "mapping": mapping})
    except Exception as e:
        return f"❌ Error: {e}", "", "{}"


def test_google_sheets(url, sheet_id):
    """Test a Google Sheets connection."""
    if not url:
        return "❌ No URL provided", "", "{}"
    try:
        connector = get_connector("google_sheets")
        result = connector.test_connection(url=url, sheet_id=sheet_id or "0")
        if not result["success"]:
            return f"❌ {result['message']}", "", "{}"

        df = connector.fetch(url=url, sheet_id=sheet_id or "0")
        _preview_state["df"] = df
        _preview_state["source_type"] = "google_sheets"
        _preview_state["config"] = {"url": url, "sheet_id": sheet_id or "0"}

        detected = auto_detect_schema(df)
        mapping = suggest_column_mapping(df, detected) if detected else {}

        preview = f"✅ **{result['message']}**\n\n"
        preview += f"**Auto-detected schema:** `{detected or 'Unknown'}`\n\n"
        preview += f"**Columns found:** {', '.join(df.columns)}\n\n"
        preview += "**Preview (first 5 rows):**\n\n"
        preview += df.head(5).to_markdown(index=False)

        mapping_text = _format_mapping(mapping, detected) if detected else "Select a target schema to see mapping."
        return preview, mapping_text, json.dumps({"detected_schema": detected, "mapping": mapping})
    except Exception as e:
        return f"❌ Error: {e}", "", "{}"


def test_rest_api(url, method, headers_str, body, json_path):
    """Test a REST API connection."""
    if not url:
        return "❌ No URL provided", "", "{}"
    try:
        headers = {}
        if headers_str:
            for line in headers_str.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    headers[k.strip()] = v.strip()

        connector = get_connector("rest_api")
        result = connector.test_connection(url=url, method=method, headers=headers,
                                           body=body, json_path=json_path)
        if not result["success"]:
            return f"❌ {result['message']}", "", "{}"

        df = connector.fetch(url=url, method=method, headers=headers,
                             body=body, json_path=json_path)
        _preview_state["df"] = df
        _preview_state["source_type"] = "rest_api"
        _preview_state["config"] = {"url": url, "method": method, "headers": headers,
                                     "body": body, "json_path": json_path}

        detected = auto_detect_schema(df)
        mapping = suggest_column_mapping(df, detected) if detected else {}

        preview = f"✅ **{result['message']}**\n\n"
        preview += f"**Auto-detected schema:** `{detected or 'Unknown'}`\n\n"
        preview += f"**Columns:** {', '.join(df.columns)}\n\n"
        preview += "**Preview (first 5 rows):**\n\n"
        preview += df.head(5).to_markdown(index=False)

        mapping_text = _format_mapping(mapping, detected) if detected else "Select a target schema to see mapping."
        return preview, mapping_text, json.dumps({"detected_schema": detected, "mapping": mapping})
    except Exception as e:
        return f"❌ Error: {e}", "", "{}"


def save_data_source(source_name, target_schema, mapping_json):
    """Save the current previewed data source with its column mapping."""
    if _preview_state["df"] is None:
        return "❌ No data previewed yet. Test a connection first."
    if not source_name:
        return "❌ Please provide a name for this data source."
    if not target_schema:
        return "❌ Please select a target ESG schema."

    try:
        # Parse mapping from JSON state
        state = json.loads(mapping_json) if mapping_json else {}
        mapping = state.get("mapping", {})

        # If no mapping, create auto-mapping
        if not mapping:
            mapping = suggest_column_mapping(_preview_state["df"], target_schema)

        # Validate
        mapped_df = apply_column_mapping(_preview_state["df"], mapping, target_schema)
        validation = validate_mapped_data(mapped_df, target_schema)

        # Register the source
        source_id = source_name.lower().replace(" ", "_")
        _conn_manager.add_source(
            source_id=source_id,
            connector_type=_preview_state["source_type"],
            config=_preview_state["config"],
            target_schema=target_schema,
            column_mapping=mapping,
            display_name=source_name,
        )

        result = f"✅ **Data source '{source_name}' saved!**\n\n"
        result += f"- **Type:** {_preview_state['source_type']}\n"
        result += f"- **Target schema:** {target_schema}\n"
        result += f"- **Rows:** {validation['stats']['rows']}\n"
        result += f"- **Columns mapped:** {validation['stats']['columns_mapped']}/{validation['stats']['columns_total']}\n"
        result += f"- **Completeness:** {validation['stats']['completeness']}%\n\n"

        if validation["warnings"]:
            result += "**Warnings:**\n"
            for w in validation["warnings"]:
                result += f"- ⚠️ {w}\n"
        if validation["errors"]:
            result += "\n**Errors:**\n"
            for e in validation["errors"]:
                result += f"- ❌ {e}\n"

        # Show all registered sources
        result += "\n---\n### All Registered Data Sources\n\n"
        for src in _conn_manager.list_sources():
            result += f"- **{src['display_name']}** → `{src['target_schema']}` ({src['connector_type']}) | Status: {src['status']}\n"

        return result
    except Exception as e:
        return f"❌ Error saving: {e}"


def run_real_collection():
    """Run data collection using all registered real data sources + demo data."""
    if not _conn_manager.has_sources():
        return "❌ No real data sources registered. Add a source first, or use the Demo Collection tab."

    try:
        results_text = "## Real Data Collection Results\n\n"
        by_schema = _conn_manager.fetch_all_by_schema()

        total_rows = 0
        for schema_name, df in by_schema.items():
            total_rows += len(df)
            validation = validate_mapped_data(df, schema_name)
            results_text += f"### {schema_name}\n"
            results_text += f"- **Rows:** {len(df)}\n"
            results_text += f"- **Completeness:** {validation['stats']['completeness']}%\n"
            results_text += f"- **Columns mapped:** {validation['stats']['columns_mapped']}/{validation['stats']['columns_total']}\n"
            if validation["warnings"]:
                for w in validation["warnings"]:
                    results_text += f"- ⚠️ {w}\n"
            results_text += "\n**Preview:**\n\n"
            results_text += df.head(5).to_markdown(index=False)
            results_text += "\n\n"

        results_text += f"---\n**Total: {total_rows:,} rows across {len(by_schema)} schemas**\n"

        # Also list source statuses
        results_text += "\n### Source Status\n"
        for src in _conn_manager.list_sources():
            icon = {"active": "✅", "error": "❌", "configured": "⚪"}.get(src["status"], "⚪")
            results_text += f"- {icon} **{src['display_name']}** — {src['status']}"
            if src.get("error"):
                results_text += f" ({src['error']})"
            results_text += "\n"

        return results_text
    except Exception as e:
        return f"❌ Error during collection: {e}"


def _format_mapping(mapping: dict, schema_name: str) -> str:
    """Format a column mapping as a readable markdown table."""
    schema = ESG_SCHEMAS.get(schema_name, {})
    text = f"### Column Mapping → `{schema_name}`\n\n"
    text += "| ESG Column | Required | Mapped To | Description |\n"
    text += "|-----------|----------|-----------|-------------|\n"
    for esg_col, spec in schema.items():
        mapped = mapping.get(esg_col, None)
        req = "✅" if spec["required"] else ""
        mapped_str = f"`{mapped}`" if mapped else "⚠️ *unmapped*"
        text += f"| {esg_col} | {req} | {mapped_str} | {spec['description']} |\n"
    return text


def run_regulatory_tracker():
    agent = orchestrator.get_agent("regulatory_tracker")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", ""

    summary = f"## Regulatory Compliance: {results.get('overall_compliance', 0)}%\n\n"
    gaps_text = "## Gap Analysis\n\n"

    for fw, data in results.get("framework_results", {}).items():
        summary += (
            f"### {fw} ({data.get('full_name', '')})\n"
            f"- Compliance: {data['compliance_pct']}%\n"
            f"- Covered: {data['covered']}/{data['total']}\n"
            f"- Gaps: {data['missing'] + data['partial']}\n\n"
        )
        for gap in data.get("gaps", [])[:5]:
            gaps_text += f"- **[{gap['requirement_id']}]** {gap['requirement']} — {gap['status']} ({gap['priority']})\n"

    narrative = results.get("gap_narrative", "")
    return summary, gaps_text, narrative


def run_carbon_accountant():
    agent = orchestrator.get_agent("carbon_accountant")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", ""

    summary = (
        f"## Carbon Accounting Results\n\n"
        f"- **Total Emissions (2024):** {results.get('total_emissions_current', 0):,.0f} tCO2e\n"
        f"- **YoY Change:** {results.get('yoy_change_pct', 0)}%\n"
        f"- **Carbon Intensity:** {results.get('carbon_intensity', 0)} tCO2e/$M\n\n"
        f"### Scope Breakdown\n\n"
    )
    for scope, value in results.get("scope_totals_current", {}).items():
        summary += f"- **{scope}:** {value:,.0f} tCO2e\n"

    hotspots = "## Supply Chain Hotspots\n\n"
    for h in results.get("hotspots", []):
        hotspots += f"- **{h['supplier']}** ({h['country']}): {h['emissions']:,.0f} tCO2e — {h['risk_factors']}\n"

    narrative = results.get("narrative", "")
    return summary, hotspots, narrative


def run_risk_predictor():
    agent = orchestrator.get_agent("risk_predictor")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", ""

    climate = results.get("climate_risks", {})
    rating = results.get("rating_prediction", {})

    summary = (
        f"## Risk Analysis\n\n"
        f"- **Overall Risk Score:** {climate.get('overall_score', 0):.0f}/100 ({climate.get('overall_level', 'N/A')})\n"
        f"- **Physical Risk:** {climate.get('physical_risk', 0)}\n"
        f"- **Transition Risk:** {climate.get('transition_risk', 0)}\n\n"
        f"### ESG Rating\n"
        f"- Current: {rating.get('current', 'N/A')} → Predicted: {rating.get('predicted', 'N/A')}\n"
    )

    scenarios = "## Scenario Analysis\n\n"
    for key, s in results.get("scenarios", {}).items():
        scenarios += (
            f"### {s['name']}\n"
            f"- Emission Reduction: {s['emission_reduction_pct']}%\n"
            f"- Projected Rating: {s['projected_rating']}\n"
            f"- Timeline: {s['timeline']}\n\n"
        )

    narrative = results.get("narrative", "")
    return summary, scenarios, narrative


def run_audit_agent():
    agent = orchestrator.get_agent("audit_agent")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", ""

    readiness = results.get("readiness_score", {})
    summary = (
        f"## Audit Results\n\n"
        f"- **Readiness Score:** {readiness.get('overall', 0):.0f}% (Grade: {readiness.get('grade', 'N/A')})\n"
        f"- **Completeness:** {readiness.get('completeness', 0):.0f}%\n"
        f"- **Compliance:** {readiness.get('compliance', 0):.0f}%\n"
        f"- **Evidence:** {readiness.get('evidence', 0):.0f}%\n"
        f"- **Issues Found:** {results.get('issues_count', 0)}\n"
    )

    findings = results.get("findings_summary", "No findings summary available.")
    return summary, findings


def run_action_agent():
    agent = orchestrator.get_agent("action_agent")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", ""

    summary_data = results.get("summary", {})
    summary = (
        f"## Action Recommendations\n\n"
        f"- **Total Actions:** {summary_data.get('total_actions', 0)}\n"
        f"- **Critical:** {summary_data.get('critical', 0)} | "
        f"**High:** {summary_data.get('high', 0)} | "
        f"**Medium:** {summary_data.get('medium', 0)}\n"
        f"- **Est. Investment:** INR {summary_data.get('total_investment', 0)} lakhs\n\n"
        f"### Top Actions\n\n"
    )
    for action in results.get("actions", [])[:5]:
        summary += f"- **[{action['id']}]** {action['action']} ({action['priority']})\n"

    narrative = results.get("roadmap_narrative", "")
    return summary, narrative


def run_stakeholder_agent():
    agent = orchestrator.get_agent("stakeholder_agent")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", "", ""

    comms = results.get("communications", {})
    investor_msg = comms.get("investors", {}).get("message", "N/A")
    regulator_msg = comms.get("regulators", {}).get("message", "N/A")
    employee_msg = comms.get("employees", {}).get("message", "N/A")
    public_msg = comms.get("public", {}).get("message", "N/A")

    return investor_msg, regulator_msg, employee_msg, public_msg


def run_full_pipeline():
    results = orchestrator.run_full_pipeline()

    summary = "## Full Pipeline Results\n\n"
    for agent_key, agent_results in results.items():
        status = "✅" if "error" not in agent_results else "❌"
        summary += f"- {status} **{agent_key.replace('_', ' ').title()}**\n"

    carbon = results.get("carbon_accountant", {})
    risk = results.get("risk_predictor", {})
    audit = results.get("audit_agent", {})

    summary += (
        f"\n### Key Metrics\n"
        f"- Total Emissions: {carbon.get('total_emissions_current', 'N/A')} tCO2e\n"
        f"- Risk Score: {risk.get('overall_risk_score', 'N/A')}/100\n"
        f"- Audit Readiness: {audit.get('readiness_score', {}).get('overall', 'N/A')}%\n"
    )
    return summary


# --- Build Gradio Interface ---

with gr.Blocks(title="ESG CoPilot", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌍 ESG CoPilot — Autonomous ESG Intelligence")
    gr.Markdown("*8 specialized AI agents powered by HuggingFace*")

    with gr.Tab("🎛️ Mission Control"):
        gr.Markdown("Run the full 8-agent pipeline in dependency order.")
        run_btn = gr.Button("🚀 Run Full Pipeline", variant="primary")
        output = gr.Markdown()
        run_btn.click(run_full_pipeline, outputs=output)

    with gr.Tab("📊 Data Collector"):
        gr.Markdown("### Connect Real Data Sources or Run Demo Collection\n"
                     "Connect your own ESG data via file upload, Google Sheets, REST API, "
                     "or SQL database. The system auto-detects the ESG schema and maps columns.")

        with gr.Tabs():
            # ── Sub-tab: Connect Data Sources ──
            with gr.Tab("🔌 Connect Data Source"):
                source_name_input = gr.Textbox(label="Data Source Name", placeholder="e.g. My Emissions Data")
                with gr.Tabs():
                    # File Upload
                    with gr.Tab("📁 File Upload"):
                        gr.Markdown("Upload a **CSV**, **Excel**, or **JSON** file with your ESG data.")
                        file_input = gr.File(label="Upload File", file_types=[".csv", ".xlsx", ".xls", ".json"])
                        test_file_btn = gr.Button("Test & Preview", variant="primary")
                        file_preview = gr.Markdown()
                        file_mapping = gr.Markdown()
                        file_state = gr.Textbox(visible=False)
                        test_file_btn.click(test_file_upload, inputs=[file_input],
                                            outputs=[file_preview, file_mapping, file_state])

                    # Google Sheets
                    with gr.Tab("📊 Google Sheets"):
                        gr.Markdown("Paste the URL of a **public** Google Sheet. "
                                    "Ensure sharing is set to *'Anyone with the link'*.")
                        gs_url = gr.Textbox(label="Google Sheets URL",
                                            placeholder="https://docs.google.com/spreadsheets/d/.../edit")
                        gs_sheet_id = gr.Textbox(label="Sheet GID (optional)", value="0",
                                                 placeholder="0 for first sheet")
                        test_gs_btn = gr.Button("Test & Preview", variant="primary")
                        gs_preview = gr.Markdown()
                        gs_mapping = gr.Markdown()
                        gs_state = gr.Textbox(visible=False)
                        test_gs_btn.click(test_google_sheets, inputs=[gs_url, gs_sheet_id],
                                          outputs=[gs_preview, gs_mapping, gs_state])

                    # REST API
                    with gr.Tab("🌐 REST API"):
                        gr.Markdown("Fetch data from any REST API that returns JSON.")
                        api_url = gr.Textbox(label="API URL", placeholder="https://api.example.com/data")
                        api_method = gr.Radio(["GET", "POST"], label="HTTP Method", value="GET")
                        api_headers = gr.Textbox(label="Headers (one per line: Key: Value)", lines=3,
                                                 placeholder="Authorization: Bearer TOKEN\nContent-Type: application/json")
                        api_body = gr.Textbox(label="Request Body (JSON, for POST)", lines=3, visible=True,
                                              placeholder='{"query": "emissions", "year": 2024}')
                        api_json_path = gr.Textbox(label="JSON Path (dot-separated)",
                                                   placeholder="data.results (navigate to nested array)")
                        test_api_btn = gr.Button("Test & Preview", variant="primary")
                        api_preview = gr.Markdown()
                        api_mapping = gr.Markdown()
                        api_state = gr.Textbox(visible=False)
                        test_api_btn.click(test_rest_api,
                                           inputs=[api_url, api_method, api_headers, api_body, api_json_path],
                                           outputs=[api_preview, api_mapping, api_state])

                gr.Markdown("---")
                gr.Markdown("### Save Data Source")
                target_schema = gr.Dropdown(
                    choices=get_schema_names(),
                    label="Target ESG Schema",
                    info="Select the ESG dataset type this data maps to. Auto-detected if possible.",
                )
                # Use whichever state is populated
                save_btn = gr.Button("💾 Save Data Source", variant="primary")
                save_output = gr.Markdown()

                # Save uses the latest test state
                def save_any_source(name, schema, fs, gs, apis):
                    """Pick the most recently populated state for saving."""
                    state = fs or gs or apis or "{}"
                    if schema is None:
                        # Try auto-detect from state
                        try:
                            s = json.loads(state)
                            schema = s.get("detected_schema", "")
                        except Exception:
                            schema = ""
                    return save_data_source(name, schema, state)

                save_btn.click(save_any_source,
                               inputs=[source_name_input, target_schema, file_state, gs_state, api_state],
                               outputs=save_output)

            # ── Sub-tab: Fetch from Real Sources ──
            with gr.Tab("📥 Fetch Real Data"):
                gr.Markdown("Fetch and process data from all registered real data sources.")
                fetch_real_btn = gr.Button("📥 Fetch from All Real Sources", variant="primary")
                fetch_real_output = gr.Markdown()
                fetch_real_btn.click(run_real_collection, outputs=fetch_real_output)

            # ── Sub-tab: Demo Collection (original) ──
            with gr.Tab("🧪 Demo Collection"):
                gr.Markdown("Run the standard demo pipeline with sample ESG data.")
                btn = gr.Button("Run Demo Data Collection", variant="secondary")
                out1 = gr.Markdown(label="Results")
                out2 = gr.Markdown(label="Issues")
                btn.click(run_data_collector, outputs=[out1, out2])

    with gr.Tab("📋 Regulatory Tracker"):
        gr.Markdown("Monitors BRSR, CSRD, GRI, SASB compliance.")
        btn = gr.Button("Run Compliance Analysis", variant="primary")
        out1 = gr.Markdown(label="Compliance")
        out2 = gr.Markdown(label="Gaps")
        out3 = gr.Markdown(label="AI Narrative")
        btn.click(run_regulatory_tracker, outputs=[out1, out2, out3])

    with gr.Tab("🌱 Carbon Accountant"):
        gr.Markdown("Tracks Scope 1/2/3 emissions.")
        btn = gr.Button("Run Carbon Analysis", variant="primary")
        out1 = gr.Markdown(label="Summary")
        out2 = gr.Markdown(label="Hotspots")
        out3 = gr.Markdown(label="AI Narrative")
        btn.click(run_carbon_accountant, outputs=[out1, out2, out3])

    with gr.Tab("⚠️ Risk Predictor"):
        gr.Markdown("Climate risk and ESG rating forecasting.")
        btn = gr.Button("Run Risk Analysis", variant="primary")
        out1 = gr.Markdown(label="Risk Summary")
        out2 = gr.Markdown(label="Scenarios")
        out3 = gr.Markdown(label="AI Narrative")
        btn.click(run_risk_predictor, outputs=[out1, out2, out3])

    with gr.Tab("🔍 Audit Agent"):
        gr.Markdown("Compliance verification and audit trails.")
        btn = gr.Button("Run Audit", variant="primary")
        out1 = gr.Markdown(label="Audit Results")
        out2 = gr.Markdown(label="Findings")
        btn.click(run_audit_agent, outputs=[out1, out2])

    with gr.Tab("🎯 Action Agent"):
        gr.Markdown("Prioritized ESG recommendations.")
        btn = gr.Button("Generate Recommendations", variant="primary")
        out1 = gr.Markdown(label="Actions")
        out2 = gr.Markdown(label="Roadmap")
        btn.click(run_action_agent, outputs=[out1, out2])

    with gr.Tab("👥 Stakeholder Agent"):
        gr.Markdown("Audience-tailored ESG communications.")
        btn = gr.Button("Generate Communications", variant="primary")
        out1 = gr.Markdown(label="💼 Investors")
        out2 = gr.Markdown(label="🏛️ Regulators")
        out3 = gr.Markdown(label="👩‍💻 Employees")
        out4 = gr.Markdown(label="🌍 Public")
        btn.click(run_stakeholder_agent, outputs=[out1, out2, out3, out4])

    with gr.Tab("📄 Report Generator"):
        gr.Markdown("Generate comprehensive ESG report. Run other agents first for best results.")
        btn = gr.Button("Generate Report", variant="primary")
        output = gr.Markdown()

        def run_report():
            agent = orchestrator.get_agent("report_generator")
            results = agent.run()
            if "error" in results:
                return f"Error: {results['error']}"
            text = f"# {results.get('report_title', 'ESG Report')}\n\n"
            text += f"## Executive Summary\n{results.get('executive_summary', '')}\n\n"
            for key, section in results.get("sections", {}).items():
                text += f"## {section['title']}\n{section.get('narrative', '')}\n\n"
            return text

        btn.click(run_report, outputs=output)

    with gr.Tab("🔌 Enterprise Connectors"):
        gr.Markdown("Connect to ERP, HR, IoT, Supplier Portal, SQL, and API data sources.")
        btn = gr.Button("Fetch from All Connectors", variant="primary")
        out_connectors = gr.Markdown()

        def run_connectors():
            from utils.connectors import fetch_all_external_data
            data, statuses = fetch_all_external_data()
            text = "## Enterprise Connector Status\n\n"
            for key, status in statuses.items():
                icon = {"synced": "✅", "streaming": "📡", "error": "❌"}.get(status.get("status", ""), "⚪")
                text += (f"- {icon} **{status['name']}** ({status['type']}) — "
                         f"Status: {status['status']} | Records: {status.get('records', 0)}\n")
            text += f"\n**Total data sources connected:** {len(data)}\n"
            text += f"**Total records fetched:** {sum(len(df) for df in data.values()):,}\n"
            return text

        btn.click(run_connectors, outputs=out_connectors)

    with gr.Tab("📡 24/7 Monitoring"):
        gr.Markdown("Always-on ESG monitoring with real-time alerts.")
        btn = gr.Button("Check Monitoring Status", variant="primary")
        out_monitor = gr.Markdown()

        def run_monitoring():
            from utils.monitoring import monitoring_engine, regulatory_updater
            mon = monitoring_engine.get_dashboard_data()
            reg = regulatory_updater.check_for_updates()

            health_icon = {"healthy": "🟢", "degraded": "🟡", "critical": "🔴"}.get(mon["health"], "⚪")
            text = (
                f"## 24/7 Monitoring Dashboard\n\n"
                f"- **Health:** {health_icon} {mon['health'].capitalize()}\n"
                f"- **Uptime:** {mon['uptime_days']} days\n"
                f"- **Events Processed:** {mon['events_processed']:,}\n"
                f"- **Active Streams:** {mon['active_streams']}/{mon['total_streams']}\n"
                f"- **Critical Alerts:** {mon['critical_alerts']}\n\n"
                f"### Active Alerts\n\n"
            )
            for alert in mon.get("alerts", []):
                sev_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(alert["severity"], "⚪")
                text += f"- {sev_icon} **[{alert['type'].upper()}]** {alert['message']}\n"

            text += f"\n### Regulatory Auto-Updates\n\n"
            text += f"- **All within 24h:** {'✅ Yes' if reg['within_24h'] else '❌ No'}\n"
            text += f"- **Avg response:** {reg['avg_response_hours']} hours\n\n"
            for upd in reg.get("updates", []):
                text += f"- **{upd['framework']}** ({upd['update_type']}): {upd['description'][:80]} — {upd['status']}\n"
            return text

        btn.click(run_monitoring, outputs=out_monitor)

    with gr.Tab("⚡ Spark Analytics"):
        gr.Markdown("Distributed ESG processing with PySpark.")
        btn = gr.Button("Run Spark Analysis", variant="primary")
        out_spark = gr.Markdown()

        def run_spark():
            from utils.spark_processing import spark_processor, PYSPARK_AVAILABLE
            if PYSPARK_AVAILABLE:
                results = spark_processor.run_full_analysis()
            else:
                from utils.data_processing import (
                    load_emissions, compute_scope_totals, compute_data_quality,
                )
                emissions = load_emissions()
                results = {
                    "scope_totals_2024": compute_scope_totals(emissions, 2024),
                    "scope_totals_2023": compute_scope_totals(emissions, 2023),
                    "engine": "Pandas (PySpark not installed)",
                }

            text = f"## Spark Analysis Results\n\n**Engine:** {results.get('engine', 'N/A')}\n\n"
            text += "### Scope Totals 2024\n"
            for scope, total in results.get("scope_totals_2024", {}).items():
                text += f"- **{scope}:** {total:,.1f} tCO2e\n"
            text += "\n### Scope Totals 2023\n"
            for scope, total in results.get("scope_totals_2023", {}).items():
                text += f"- **{scope}:** {total:,.1f} tCO2e\n"
            return text

        btn.click(run_spark, outputs=out_spark)

if __name__ == "__main__":
    # HuggingFace Spaces (Docker SDK) or local
    demo.queue().launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
    )

"""ESG CoPilot — Gradio Interface with tabs for all core agents."""
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

# ── Fix Gradio API info crash with bool additionalProperties ──
# gradio_client.utils.get_type() does `"const" in schema` where schema
# can be a bool (from additionalProperties: True), causing TypeError.
import gradio_client.utils as _gc_utils

_orig_json_schema_to_python_type = _gc_utils._json_schema_to_python_type


def _safe_json_schema_to_python_type(schema, defs=None):
    if not isinstance(schema, dict):
        return "Any"
    try:
        return _orig_json_schema_to_python_type(schema, defs)
    except TypeError:
        return "Any"


_gc_utils._json_schema_to_python_type = _safe_json_schema_to_python_type
# ── End API info fix ──

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


def test_cloud_connector(connector_type, **config):
    """Generic test for cloud connectors (S3, GCS, BigQuery, Azure)."""
    try:
        connector = get_connector(connector_type)
        result = connector.test_connection(**config)
        if not result["success"]:
            return f"❌ {result['message']}", "", "{}"

        df = connector.fetch(**config)
        _preview_state["df"] = df
        _preview_state["source_type"] = connector_type
        _preview_state["config"] = config

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


def test_aws_s3(bucket, key, access_key, secret_key, region):
    return test_cloud_connector("aws_s3", bucket=bucket, key=key,
                                aws_access_key_id=access_key,
                                aws_secret_access_key=secret_key,
                                region=region or "us-east-1")


def test_gcp_bigquery(project, query, credentials_json):
    return test_cloud_connector("gcp_bigquery", project=project, query=query,
                                credentials_json=credentials_json)


def test_gcp_storage(bucket, blob_path, credentials_json):
    return test_cloud_connector("gcp_storage", bucket=bucket, blob_path=blob_path,
                                credentials_json=credentials_json)


def test_azure_blob(conn_str, container, blob_name):
    return test_cloud_connector("azure_blob", connection_string=conn_str,
                                container=container, blob_name=blob_name)


def test_delta_lake(table_uri, version, columns, row_filter, storage_options_json):
    ver = int(version) if version and str(version).strip().isdigit() else None
    return test_cloud_connector("delta_lake", table_uri=table_uri, version=ver,
                                columns=columns, row_filter=row_filter,
                                storage_options_json=storage_options_json)


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

    reporter = results.get("reporter_profile", {})
    summary = f"## Regulatory Compliance: {results.get('overall_compliance', 0)}%\n\n"
    if reporter:
        summary += (
            f"- **Reporter Classification:** {reporter.get('classification', 'N/A')}\n"
            f"- **Listed Entity:** {'Yes' if reporter.get('listed_entity') else 'No'}\n\n"
        )
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
        f"- **Est. Investment:** INR {summary_data.get('total_investment', 0)} lakhs\n"
        f"- **Adjusted Investment:** INR {summary_data.get('adjusted_investment', 0)} lakhs\n"
        f"- **Portfolio Net Value:** INR {summary_data.get('net_value', 0)} lakhs\n\n"
        f"### Top Actions\n\n"
    )
    for action in results.get("actions", [])[:5]:
        summary += (
            f"- **[{action['id']}]** {action['action']} ({action['priority']}) "
            f"| Net ROI: {action.get('net_roi_pct', 'N/A')}% "
            f"| Friction: {action.get('implementation_friction_score', 'N/A')}\n"
        )

    targets = results.get("targets", [])
    if targets:
        summary += "\n### Suggested Targets\n\n"
        for target in targets[:4]:
            summary += (
                f"- **{target['metric']}:** {target['current']} -> {target['target']} "
                f"{target['unit']} by {target['deadline']}\n"
            )

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


def run_roi_agent():
    agent = orchestrator.get_agent("roi_agent")
    results = agent.run()
    if "error" in results:
        return f"Error: {results['error']}", "", ""

    iqs = results.get("investment_quality_score", {})
    fin_roi = results.get("financial_roi", {})
    summary = (
        f"## ESG ROI Summary\n\n"
        f"- **Investment Quality Score:** {iqs.get('score', 0)}/100 ({iqs.get('grade', 'N/A')})\n"
        f"- **Financial ROI:** {fin_roi.get('roi_pct', 0)}%\n"
        f"- **Net Financial Benefit:** INR {fin_roi.get('net_financial_benefit', 0)} Cr\n"
        f"- **Payback:** {fin_roi.get('payback_years', 'N/A')} years\n"
    )

    channels = results.get("kpi_engine", {}).get("value_channels", [])
    channels_text = "## Value Creation Channels\n\n"
    for ch in channels:
        channels_text += (
            f"- **{ch.get('channel', 'N/A')}:** {ch.get('score', 0)}/100 "
            f"({ch.get('financial_impact', 'N/A')})\n"
        )

    narrative = results.get("narrative", "")
    return summary, channels_text, narrative


def run_full_pipeline():
    results = orchestrator.run_full_pipeline()

    summary = "## Full Pipeline Results\n\n"
    for agent_key, agent_results in results.items():
        status = "✅" if "error" not in agent_results else "❌"
        summary += f"- {status} **{agent_key.replace('_', ' ').title()}**\n"

    carbon = results.get("carbon_accountant", {})
    risk = results.get("risk_predictor", {})
    audit = results.get("audit_agent", {})
    roi = results.get("roi_agent", {})

    summary += (
        f"\n### Key Metrics\n"
        f"- Total Emissions: {carbon.get('total_emissions_current', 'N/A')} tCO2e\n"
        f"- Risk Score: {risk.get('overall_risk_score', 'N/A')}/100\n"
        f"- Audit Readiness: {audit.get('readiness_score', {}).get('overall', 'N/A')}%\n"
        f"- Investment Quality Score: {roi.get('investment_quality_score', {}).get('score', 'N/A')}/100\n"
    )
    return summary


# --- Build Gradio Interface ---

with gr.Blocks(title="ESG CoPilot", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🌍 ESG CoPilot — Autonomous ESG Intelligence")
    gr.Markdown("*9 specialized AI agents powered by HuggingFace*")

    with gr.Tab("🎛️ Mission Control"):
        gr.Markdown("Run the full 9-agent pipeline in dependency order.")
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

                    # AWS S3
                    with gr.Tab("☁️ AWS S3"):
                        gr.Markdown("Read CSV/Excel/JSON/Parquet files from an **AWS S3** bucket.")
                        s3_bucket = gr.Textbox(label="Bucket Name", placeholder="my-esg-data-bucket")
                        s3_key = gr.Textbox(label="Object Key (path)", placeholder="data/emissions_2024.csv")
                        s3_access = gr.Textbox(label="Access Key ID (optional if using IAM role)", type="password")
                        s3_secret = gr.Textbox(label="Secret Access Key", type="password")
                        s3_region = gr.Textbox(label="Region", value="us-east-1")
                        test_s3_btn = gr.Button("Test & Preview", variant="primary")
                        s3_preview = gr.Markdown()
                        s3_mapping = gr.Markdown()
                        s3_state = gr.Textbox(visible=False)
                        test_s3_btn.click(test_aws_s3,
                                          inputs=[s3_bucket, s3_key, s3_access, s3_secret, s3_region],
                                          outputs=[s3_preview, s3_mapping, s3_state])

                    # GCP BigQuery
                    with gr.Tab("🔷 BigQuery"):
                        gr.Markdown("Run a SQL query against **Google BigQuery**.")
                        bq_project = gr.Textbox(label="GCP Project ID", placeholder="my-gcp-project")
                        bq_query = gr.Textbox(label="SQL Query", lines=3,
                                              placeholder="SELECT * FROM `project.dataset.table` WHERE year = 2024")
                        bq_creds = gr.Textbox(label="Service Account JSON (paste full JSON)", lines=4, type="password")
                        test_bq_btn = gr.Button("Test & Preview", variant="primary")
                        bq_preview = gr.Markdown()
                        bq_mapping = gr.Markdown()
                        bq_state = gr.Textbox(visible=False)
                        test_bq_btn.click(test_gcp_bigquery,
                                          inputs=[bq_project, bq_query, bq_creds],
                                          outputs=[bq_preview, bq_mapping, bq_state])

                    # GCP Cloud Storage
                    with gr.Tab("🔷 GCS"):
                        gr.Markdown("Read files from **Google Cloud Storage**.")
                        gcs_bucket = gr.Textbox(label="Bucket Name", placeholder="my-esg-bucket")
                        gcs_blob = gr.Textbox(label="Blob Path", placeholder="data/emissions.csv")
                        gcs_creds = gr.Textbox(label="Service Account JSON (paste full JSON)", lines=4, type="password")
                        test_gcs_btn = gr.Button("Test & Preview", variant="primary")
                        gcs_preview = gr.Markdown()
                        gcs_mapping = gr.Markdown()
                        gcs_state = gr.Textbox(visible=False)
                        test_gcs_btn.click(test_gcp_storage,
                                           inputs=[gcs_bucket, gcs_blob, gcs_creds],
                                           outputs=[gcs_preview, gcs_mapping, gcs_state])

                    # Azure Blob
                    with gr.Tab("🔵 Azure Blob"):
                        gr.Markdown("Read files from **Azure Blob Storage**.")
                        az_conn = gr.Textbox(label="Connection String", type="password",
                                             placeholder="DefaultEndpointsProtocol=https;AccountName=...")
                        az_container = gr.Textbox(label="Container Name", placeholder="esg-data")
                        az_blob = gr.Textbox(label="Blob Name", placeholder="emissions_2024.csv")
                        test_az_btn = gr.Button("Test & Preview", variant="primary")
                        az_preview = gr.Markdown()
                        az_mapping = gr.Markdown()
                        az_state = gr.Textbox(visible=False)
                        test_az_btn.click(test_azure_blob,
                                          inputs=[az_conn, az_container, az_blob],
                                          outputs=[az_preview, az_mapping, az_state])

                    # Delta Lake
                    with gr.Tab("🔺 Delta Lake"):
                        gr.Markdown("Read a **Delta Lake** table from local path, S3 (`s3://`), GCS (`gs://`), or Azure (`az://`).")
                        dl_uri = gr.Textbox(label="Table URI",
                                            placeholder="s3://my-bucket/delta-tables/emissions  or  /data/delta/emissions")
                        dl_version = gr.Textbox(label="Version (optional)", placeholder="Leave blank for latest")
                        dl_columns = gr.Textbox(label="Columns (optional, comma-separated)",
                                                placeholder="year, scope, emissions_tco2e")
                        dl_filter = gr.Textbox(label="Row Filter (optional)",
                                               placeholder="year = 2024, scope = Scope 1")
                        dl_storage = gr.Textbox(label="Storage Options JSON (credentials for cloud paths)",
                                                type="password",
                                                placeholder='{"AWS_ACCESS_KEY_ID": "...", "AWS_SECRET_ACCESS_KEY": "..."}')
                        test_dl_btn = gr.Button("Test & Preview", variant="primary")
                        dl_preview = gr.Markdown()
                        dl_mapping = gr.Markdown()
                        dl_state = gr.Textbox(visible=False)
                        test_dl_btn.click(test_delta_lake,
                                          inputs=[dl_uri, dl_version, dl_columns, dl_filter, dl_storage],
                                          outputs=[dl_preview, dl_mapping, dl_state])

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
                def save_any_source(name, schema, fs, gs, apis, s3s, bqs, gcss, azs, dls):
                    """Pick the most recently populated state for saving."""
                    state = fs or gs or apis or s3s or bqs or gcss or azs or dls or "{}"
                    if schema is None:
                        try:
                            s = json.loads(state)
                            schema = s.get("detected_schema", "")
                        except Exception:
                            schema = ""
                    return save_data_source(name, schema, state)

                save_btn.click(save_any_source,
                               inputs=[source_name_input, target_schema, file_state, gs_state,
                                       api_state, s3_state, bq_state, gcs_state, az_state, dl_state],
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

    with gr.Tab("⭐ ESG ROI Agent"):
        gr.Markdown("Dual ROI, value creation channels, and J-Curve analysis.")
        btn = gr.Button("Run ESG ROI Analysis", variant="primary")
        out1 = gr.Markdown(label="ROI Summary")
        out2 = gr.Markdown(label="Value Channels")
        out3 = gr.Markdown(label="Narrative")
        btn.click(run_roi_agent, outputs=[out1, out2, out3])

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
        gr.Markdown("### Generate Comprehensive ESG Reports\n"
                     "Run other agents first (Data Collector, Carbon Accountant, Regulatory Tracker, "
                     "Audit Agent) for the most complete report. Select a report type below.")

        report_type = gr.Radio(
            ["Full ESG Report", "Framework Compliance", "Carbon & Environment",
             "Social & Governance", "Executive Summary Only"],
            label="Report Type",
            value="Full ESG Report",
        )
        btn = gr.Button("Generate Report", variant="primary")

        with gr.Tabs():
            with gr.Tab("Report"):
                report_output = gr.Markdown()
            with gr.Tab("Metrics Tables"):
                metrics_output = gr.Markdown()
            with gr.Tab("Framework Compliance"):
                framework_output = gr.Markdown()
            with gr.Tab("Audit Trail"):
                audit_output = gr.Markdown()

        def run_report(rtype):
            agent = orchestrator.get_agent("report_generator")
            results = agent.run()
            if "error" in results:
                err = f"Error: {results['error']}"
                return err, err, err, err

            # ── Build report text based on type ──
            report = ""
            metrics_text = ""
            framework_text = ""
            audit_text = ""

            company = results.get("company", {})
            sections = results.get("sections", {})
            framework_sections = results.get("framework_sections", {})
            carbon = results.get("carbon_highlights", {})
            compliance = results.get("compliance_summary", {})
            reporter_profile = results.get("reporter_profile", {})
            roi_summary = results.get("roi_summary", {})
            investment_quality = results.get("investment_quality", {})
            value_channels = results.get("value_channels", {})
            audit_trail = results.get("audit_trail", [])

            # ── Company header ──
            if company and rtype in ("Full ESG Report", "Executive Summary Only"):
                report += f"# {results.get('report_title', 'ESG Report')}\n\n"
                report += f"**Company:** {company.get('company_name', 'N/A')}  \n"
                report += f"**Sector:** {company.get('sector', 'N/A')} | "
                report += f"**Employees:** {company.get('employees', 'N/A'):,}  \n"
                report += f"**Revenue:** INR {company.get('revenue_inr_crores', 'N/A')} Crores | "
                report += f"**Market Cap:** INR {company.get('market_cap_inr_crores', 'N/A')} Crores  \n"
                commitments = company.get("key_commitments", [])
                if commitments:
                    report += f"**Key Commitments:** {', '.join(commitments)}  \n"
                report += f"**Generated:** {results.get('generated_at', '')}\n\n"
                report += "---\n\n"
            else:
                report += f"# {results.get('report_title', 'ESG Report')}\n\n"

            # ── Executive Summary ──
            exec_summary = results.get("executive_summary", "")
            if exec_summary and rtype != "Framework Compliance":
                report += f"## Executive Summary\n\n{exec_summary}\n\n"

            if rtype in ("Full ESG Report", "Executive Summary Only") and reporter_profile:
                report += "## Reporting Profile\n\n"
                report += f"**Classification:** {reporter_profile.get('classification', 'N/A')}  \n"
                report += f"**Listed Entity:** {'Yes' if reporter_profile.get('listed_entity') else 'No'}  \n"
                report += f"**Rationale:** {reporter_profile.get('rationale', 'N/A')}\n\n"

            if rtype in ("Full ESG Report", "Executive Summary Only") and roi_summary:
                report += "## ESG ROI Snapshot\n\n"
                report += f"- **Financial ROI:** {roi_summary.get('roi_pct', 'N/A')}%  \n"
                report += f"- **Net Financial Benefit:** INR {roi_summary.get('net_financial_benefit', 'N/A')} Cr  \n"
                report += f"- **Payback:** {roi_summary.get('payback_years', 'N/A')} years  \n"
                report += f"- **Investment Quality:** {investment_quality.get('score', 'N/A')}/100 ({investment_quality.get('grade', 'N/A')})\n\n"

                if value_channels.get("available"):
                    report += "**Value Creation Channels:**\n\n"
                    for channel in value_channels.get("channels", []):
                        report += (
                            f"- **{channel.get('name', 'N/A')}:** {channel.get('score', 0)}/100 "
                            f"({channel.get('financial_impact', 'N/A')})\n"
                        )
                    report += "\n"

            # ── Carbon Highlights ──
            if rtype in ("Full ESG Report", "Carbon & Environment"):
                total_em = carbon.get("total_emissions", "N/A")
                yoy = carbon.get("yoy_change", "N/A")
                intensity = carbon.get("carbon_intensity", "N/A")

                report += "## Carbon & Emissions Highlights\n\n"
                report += "| Metric | Value |\n|--------|-------|\n"
                if total_em != "N/A":
                    report += f"| Total Emissions (FY2024) | {total_em:,.0f} tCO2e |\n"
                else:
                    report += f"| Total Emissions (FY2024) | {total_em} |\n"
                report += f"| Year-over-Year Change | {yoy}% |\n"
                report += f"| Carbon Intensity | {intensity} tCO2e/$M |\n\n"

            # ── Compliance Overview ──
            if rtype in ("Full ESG Report", "Framework Compliance"):
                overall_comp = compliance.get("overall", "N/A")
                fw_comps = compliance.get("frameworks", {})

                report += f"## Regulatory Compliance Overview\n\n"
                report += f"**Overall Compliance:** {overall_comp}%\n\n"
                if fw_comps:
                    report += "| Framework | Compliance |\n|-----------|------------|\n"
                    for fw, pct in fw_comps.items():
                        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
                        report += f"| {fw} | {bar} {pct}% |\n"
                    report += "\n"

            # ── E/S/G Section Narratives ──
            if rtype in ("Full ESG Report", "Carbon & Environment", "Social & Governance"):
                for key, section in sections.items():
                    if rtype == "Carbon & Environment" and key not in ("environmental",):
                        continue
                    if rtype == "Social & Governance" and key not in ("social", "governance"):
                        continue
                    report += f"## {section['title']}\n\n"
                    narrative = section.get("narrative", "")
                    if narrative:
                        report += f"{narrative}\n\n"
                    # Inline top 3 metrics as quick reference
                    sec_metrics = section.get("metrics", [])
                    if sec_metrics:
                        report += "**Key Metrics:**\n\n"
                        for m in sec_metrics[:3]:
                            status_icon = {"Met": "✅", "Not Met": "❌", "On Track": "🔄"}.get(
                                m.get("status", ""), "⚪"
                            )
                            report += (f"- {status_icon} **{m.get('metric_name', '')}**: "
                                       f"{m.get('value_2024', 'N/A')} {m.get('unit', '')} "
                                       f"(target: {m.get('target_2024', 'N/A')})\n")
                        if len(sec_metrics) > 3:
                            report += f"\n*...and {len(sec_metrics) - 3} more metrics — see Metrics Tables tab*\n"
                        report += "\n"

            # ── Metrics Tables (full detail) ──
            for key, section in sections.items():
                sec_metrics = section.get("metrics", [])
                if sec_metrics:
                    metrics_text += f"## {section['title']} — All Metrics\n\n"
                    metrics_text += "| ID | Metric | 2023 | 2024 | Target | Unit | Status |\n"
                    metrics_text += "|-----|--------|------|------|--------|------|--------|\n"
                    for m in sec_metrics:
                        status_icon = {"Met": "✅", "Not Met": "❌", "On Track": "🔄"}.get(
                            m.get("status", ""), "⚪"
                        )
                        metrics_text += (
                            f"| {m.get('metric_id', '')} "
                            f"| {m.get('metric_name', '')} "
                            f"| {m.get('value_2023', 'N/A')} "
                            f"| {m.get('value_2024', 'N/A')} "
                            f"| {m.get('target_2024', 'N/A')} "
                            f"| {m.get('unit', '')} "
                            f"| {status_icon} {m.get('status', '')} |\n"
                        )
                    metrics_text += "\n"

            if not metrics_text:
                metrics_text = "*No metrics data available. Run the Data Collector agent first.*"

            # ── Framework Sections (full detail) ──
            if framework_sections:
                framework_text += "## Framework-by-Framework Compliance\n\n"
                for fw, info in framework_sections.items():
                    pct = info.get("compliance_pct", 0)
                    bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
                    framework_text += f"### {fw} — {info.get('name', '')}\n\n"
                    framework_text += f"**Compliance:** {bar} **{pct}%**\n\n"
                    framework_text += (
                        f"- Requirements Covered: **{info.get('covered', 0)}** / {info.get('total', 0)}\n"
                        f"- Gaps Remaining: **{info.get('gaps_count', 0)}**\n\n"
                    )
            else:
                framework_text = ("*No framework compliance data available. "
                                  "Run the Regulatory Tracker agent first.*")

            # ── Audit Trail ──
            if audit_trail:
                audit_text += "## Report Audit Trail\n\n"
                audit_text += "| Step | Timestamp | Details | Status |\n"
                audit_text += "|------|-----------|---------|--------|\n"
                for entry in audit_trail:
                    status_icon = {"completed": "✅", "pending": "⏳", "error": "❌"}.get(
                        entry.get("status", ""), "⚪"
                    )
                    audit_text += (
                        f"| {entry.get('step', '')} "
                        f"| {entry.get('timestamp', '')[:19]} "
                        f"| {entry.get('details', '')} "
                        f"| {status_icon} {entry.get('status', '')} |\n"
                    )
                audit_text += "\n*This audit trail provides verifiable provenance for all report data.*"
            else:
                audit_text = "*No audit trail available. Run the full pipeline for complete provenance tracking.*"

            return report, metrics_text, framework_text, audit_text

        btn.click(run_report, inputs=[report_type],
                  outputs=[report_output, metrics_output, framework_output, audit_output])

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

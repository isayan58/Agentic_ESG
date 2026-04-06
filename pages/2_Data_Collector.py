"""Streamlit page for the Data Collector Agent — with Real Connectors, Cloud, & Enterprise Sources."""
import streamlit as st
import pandas as pd
import json
import os
from agents.data_collector import DataCollectorAgent
from utils.charts import quality_bar, connector_status_chart
from utils.real_connectors import get_connector, get_available_connectors
from utils.schema_mapper import (
    auto_detect_schema, suggest_column_mapping, apply_column_mapping,
    validate_mapped_data, get_schema_names, get_schema_columns, ESG_SCHEMAS,
)
from utils.connection_manager import ConnectionManager

st.set_page_config(page_title="Data Collector | ESG CoPilot", page_icon="📊", layout="wide")
st.title("📊 Data Collector Agent")
st.markdown("*Connect real data sources, cloud storage, or run with sample data*")
st.markdown("---")

if "data_collector" not in st.session_state:
    st.session_state.data_collector = DataCollectorAgent()
    st.session_state.data_collector_results = None
if "conn_manager" not in st.session_state:
    st.session_state.conn_manager = ConnectionManager()
if "preview_df" not in st.session_state:
    st.session_state.preview_df = None
    st.session_state.preview_source_type = None
    st.session_state.preview_config = None

agent = st.session_state.data_collector
conn_mgr = st.session_state.conn_manager

# ── Tabs: Connect Sources / Run Collection ──
main_tab1, main_tab2, main_tab3 = st.tabs([
    "🔌 Connect Data Sources", "📥 Run Collection", "📊 Enterprise Connectors",
])

# ────────────────────────────────────────────────────────────────
# TAB 1: Connect Data Sources (File, Google Sheets, REST, Cloud)
# ────────────────────────────────────────────────────────────────
with main_tab1:
    st.markdown("### Connect Your ESG Data")
    st.markdown("Upload files, connect to cloud storage, or fetch from APIs. "
                "The system auto-detects the ESG schema and maps columns.")

    source_name = st.text_input("Data Source Name", placeholder="e.g. My Emissions Data")

    conn_tab1, conn_tab2, conn_tab3, conn_tab4, conn_tab5, conn_tab6, conn_tab7 = st.tabs([
        "📁 File Upload", "📊 Google Sheets", "🌐 REST API",
        "☁️ AWS S3", "🔷 BigQuery", "🔷 GCS", "🔵 Azure Blob",
    ])

    # ── File Upload ──
    with conn_tab1:
        uploaded = st.file_uploader("Upload CSV, Excel, or JSON", type=["csv", "xlsx", "xls", "json"])
        if st.button("Test & Preview", key="test_file") and uploaded:
            try:
                connector = get_connector("file_upload")
                file_bytes = uploaded.read()
                file_name = uploaded.name
                result = connector.test_connection(file_bytes=file_bytes, file_name=file_name)
                if result["success"]:
                    df = connector.fetch(file_bytes=file_bytes, file_name=file_name)
                    st.session_state.preview_df = df
                    st.session_state.preview_source_type = "file_upload"
                    st.session_state.preview_config = {"file_bytes": file_bytes, "file_name": file_name}
                    st.success(result["message"])
                    st.dataframe(df.head(10), use_container_width=True)
                    detected = auto_detect_schema(df)
                    if detected:
                        st.info(f"Auto-detected schema: **{detected}**")
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Google Sheets ──
    with conn_tab2:
        gs_url = st.text_input("Google Sheets URL", placeholder="https://docs.google.com/spreadsheets/d/.../edit")
        gs_gid = st.text_input("Sheet GID (optional)", value="0")
        if st.button("Test & Preview", key="test_gs") and gs_url:
            try:
                connector = get_connector("google_sheets")
                result = connector.test_connection(url=gs_url, sheet_id=gs_gid)
                if result["success"]:
                    df = connector.fetch(url=gs_url, sheet_id=gs_gid)
                    st.session_state.preview_df = df
                    st.session_state.preview_source_type = "google_sheets"
                    st.session_state.preview_config = {"url": gs_url, "sheet_id": gs_gid}
                    st.success(result["message"])
                    st.dataframe(df.head(10), use_container_width=True)
                    detected = auto_detect_schema(df)
                    if detected:
                        st.info(f"Auto-detected schema: **{detected}**")
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # ── REST API ──
    with conn_tab3:
        api_url = st.text_input("API URL", placeholder="https://api.example.com/data")
        api_method = st.radio("HTTP Method", ["GET", "POST"], horizontal=True)
        api_headers_str = st.text_area("Headers (one per line: Key: Value)", height=80)
        api_body = st.text_area("Request Body (JSON, for POST)", height=80)
        api_json_path = st.text_input("JSON Path", placeholder="data.results")
        if st.button("Test & Preview", key="test_api") and api_url:
            try:
                headers = {}
                if api_headers_str:
                    for line in api_headers_str.strip().split("\n"):
                        if ":" in line:
                            k, v = line.split(":", 1)
                            headers[k.strip()] = v.strip()
                connector = get_connector("rest_api")
                result = connector.test_connection(url=api_url, method=api_method,
                                                   headers=headers, body=api_body,
                                                   json_path=api_json_path)
                if result["success"]:
                    df = connector.fetch(url=api_url, method=api_method,
                                         headers=headers, body=api_body,
                                         json_path=api_json_path)
                    st.session_state.preview_df = df
                    st.session_state.preview_source_type = "rest_api"
                    st.session_state.preview_config = {"url": api_url, "method": api_method,
                                                       "headers": headers, "body": api_body,
                                                       "json_path": api_json_path}
                    st.success(result["message"])
                    st.dataframe(df.head(10), use_container_width=True)
                    detected = auto_detect_schema(df)
                    if detected:
                        st.info(f"Auto-detected schema: **{detected}**")
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # ── AWS S3 ──
    with conn_tab4:
        s3_bucket = st.text_input("S3 Bucket Name", placeholder="my-esg-data-bucket")
        s3_key = st.text_input("Object Key", placeholder="data/emissions_2024.csv")
        s3_access = st.text_input("Access Key ID (optional if using IAM)", type="password")
        s3_secret = st.text_input("Secret Access Key", type="password")
        s3_region = st.text_input("Region", value="us-east-1")
        avail = get_available_connectors()["aws_s3"]
        if not avail["available"]:
            st.warning(f"boto3 not installed. Run: `{avail['install_hint']}`")
        if st.button("Test & Preview", key="test_s3") and s3_bucket and s3_key:
            try:
                connector = get_connector("aws_s3")
                config = {"bucket": s3_bucket, "key": s3_key,
                          "aws_access_key_id": s3_access, "aws_secret_access_key": s3_secret,
                          "region": s3_region}
                result = connector.test_connection(**config)
                if result["success"]:
                    df = connector.fetch(**config)
                    st.session_state.preview_df = df
                    st.session_state.preview_source_type = "aws_s3"
                    st.session_state.preview_config = config
                    st.success(result["message"])
                    st.dataframe(df.head(10), use_container_width=True)
                    detected = auto_detect_schema(df)
                    if detected:
                        st.info(f"Auto-detected schema: **{detected}**")
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # ── GCP BigQuery ──
    with conn_tab5:
        bq_project = st.text_input("GCP Project ID", placeholder="my-gcp-project")
        bq_query = st.text_area("SQL Query", placeholder="SELECT * FROM `project.dataset.table`", height=100)
        bq_creds = st.text_area("Service Account JSON (optional)", height=100, type="password")
        avail = get_available_connectors()["gcp_bigquery"]
        if not avail["available"]:
            st.warning(f"google-cloud-bigquery not installed. Run: `{avail['install_hint']}`")
        if st.button("Test & Preview", key="test_bq") and bq_project and bq_query:
            try:
                connector = get_connector("gcp_bigquery")
                config = {"project": bq_project, "query": bq_query, "credentials_json": bq_creds}
                result = connector.test_connection(**config)
                if result["success"]:
                    df = connector.fetch(**config)
                    st.session_state.preview_df = df
                    st.session_state.preview_source_type = "gcp_bigquery"
                    st.session_state.preview_config = config
                    st.success(result["message"])
                    st.dataframe(df.head(10), use_container_width=True)
                    detected = auto_detect_schema(df)
                    if detected:
                        st.info(f"Auto-detected schema: **{detected}**")
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # ── GCP Cloud Storage ──
    with conn_tab6:
        gcs_bucket = st.text_input("GCS Bucket Name", placeholder="my-esg-bucket")
        gcs_blob = st.text_input("Blob Path", placeholder="data/emissions.csv")
        gcs_creds = st.text_area("Service Account JSON (optional)", height=100, key="gcs_creds", type="password")
        avail = get_available_connectors()["gcp_storage"]
        if not avail["available"]:
            st.warning(f"google-cloud-storage not installed. Run: `{avail['install_hint']}`")
        if st.button("Test & Preview", key="test_gcs") and gcs_bucket and gcs_blob:
            try:
                connector = get_connector("gcp_storage")
                config = {"bucket": gcs_bucket, "blob_path": gcs_blob, "credentials_json": gcs_creds}
                result = connector.test_connection(**config)
                if result["success"]:
                    df = connector.fetch(**config)
                    st.session_state.preview_df = df
                    st.session_state.preview_source_type = "gcp_storage"
                    st.session_state.preview_config = config
                    st.success(result["message"])
                    st.dataframe(df.head(10), use_container_width=True)
                    detected = auto_detect_schema(df)
                    if detected:
                        st.info(f"Auto-detected schema: **{detected}**")
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Azure Blob ──
    with conn_tab7:
        az_conn = st.text_input("Connection String", type="password",
                                placeholder="DefaultEndpointsProtocol=https;AccountName=...")
        az_container = st.text_input("Container Name", placeholder="esg-data")
        az_blob_name = st.text_input("Blob Name", placeholder="emissions_2024.csv")
        avail = get_available_connectors()["azure_blob"]
        if not avail["available"]:
            st.warning(f"azure-storage-blob not installed. Run: `{avail['install_hint']}`")
        if st.button("Test & Preview", key="test_az") and az_conn and az_container and az_blob_name:
            try:
                connector = get_connector("azure_blob")
                config = {"connection_string": az_conn, "container": az_container, "blob_name": az_blob_name}
                result = connector.test_connection(**config)
                if result["success"]:
                    df = connector.fetch(**config)
                    st.session_state.preview_df = df
                    st.session_state.preview_source_type = "azure_blob"
                    st.session_state.preview_config = config
                    st.success(result["message"])
                    st.dataframe(df.head(10), use_container_width=True)
                    detected = auto_detect_schema(df)
                    if detected:
                        st.info(f"Auto-detected schema: **{detected}**")
                else:
                    st.error(result["message"])
            except Exception as e:
                st.error(f"Error: {e}")

    # ── Save Data Source ──
    st.markdown("---")
    st.markdown("### Save Data Source")
    if st.session_state.preview_df is not None:
        detected_schema = auto_detect_schema(st.session_state.preview_df)
        target_schema = st.selectbox("Target ESG Schema", get_schema_names(),
                                     index=get_schema_names().index(detected_schema) if detected_schema in get_schema_names() else 0)

        if st.button("💾 Save Data Source", type="primary") and source_name and target_schema:
            mapping = suggest_column_mapping(st.session_state.preview_df, target_schema)
            source_id = source_name.lower().replace(" ", "_")
            conn_mgr.add_source(
                source_id=source_id,
                connector_type=st.session_state.preview_source_type,
                config=st.session_state.preview_config,
                target_schema=target_schema,
                column_mapping=mapping,
                display_name=source_name,
            )
            mapped_df = apply_column_mapping(st.session_state.preview_df, mapping, target_schema)
            validation = validate_mapped_data(mapped_df, target_schema)
            st.success(f"Saved **{source_name}** → `{target_schema}` "
                       f"({validation['stats']['rows']} rows, "
                       f"{validation['stats']['completeness']}% complete)")
            if validation["warnings"]:
                for w in validation["warnings"]:
                    st.warning(w)

        # Show registered sources
        sources = conn_mgr.list_sources()
        if sources:
            st.markdown("#### Registered Data Sources")
            for src in sources:
                st.markdown(f"- **{src['display_name']}** → `{src['target_schema']}` ({src['connector_type']})")
    else:
        st.info("Test a connection above to preview data, then save it here.")

# ────────────────────────────────────────────────────────────────
# TAB 2: Run Collection
# ────────────────────────────────────────────────────────────────
with main_tab2:
    st.markdown("### Run Data Collection")

    col1, col2 = st.columns(2)
    with col1:
        use_real = st.checkbox("Use registered real sources", value=conn_mgr.has_sources(),
                               disabled=not conn_mgr.has_sources())
    with col2:
        use_connectors = st.checkbox("Enable enterprise connectors", value=True)

    uploaded_files = st.file_uploader("Upload additional files (CSV/JSON)",
                                      accept_multiple_files=True, type=["csv", "json"])

    if st.button("🔄 Run Data Collection", type="primary", use_container_width=True):
        file_dict = {}
        if uploaded_files:
            for f in uploaded_files:
                file_dict[f.name] = f

        with st.spinner("Collecting from all sources..."):
            results = agent.run(
                uploaded_files=file_dict if file_dict else None,
                use_connectors=use_connectors,
                connection_manager=conn_mgr if use_real else None,
            )
            st.session_state.data_collector_results = results
        st.success("Data collection complete!")

    # ── Display Results ──
    results = st.session_state.data_collector_results
    if results and "error" not in results:
        st.markdown("---")

        k1, k2, k3, k4, k5 = st.columns(5)
        with k1:
            st.metric("Datasets Loaded", results.get("datasets_loaded", 0))
        with k2:
            st.metric("Total Records", f"{results.get('total_records', 0):,}")
        with k3:
            st.metric("Completeness", f"{results.get('overall_completeness', 0)}%")
        with k4:
            st.metric("Avg Confidence", f"{results.get('overall_confidence', 0)}%")
        with k5:
            active = sum(1 for s in results.get("connector_statuses", {}).values()
                         if s.get("status") in ("synced", "streaming"))
            st.metric("Active Connectors", f"{active}/6")

        st.markdown("---")
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Quality Scores", "Missing Data Alerts", "Verifiable Trust",
            "AI Classification", "Audit Trail",
        ])

        with tab1:
            quality = results.get("quality_scores", {})
            if quality:
                scores = {name: q["completeness"] for name, q in quality.items()}
                fig = quality_bar(scores)
                st.plotly_chart(fig, use_container_width=True)
                rows = []
                for name, q in quality.items():
                    rows.append({
                        "Dataset": name, "Records": q["total_records"],
                        "Fields": q["total_fields"],
                        "Completeness": f"{q['completeness']}%",
                        "Null Values": q["null_count"],
                        "Confidence": f"{q['avg_confidence']}%" if q["avg_confidence"] > 0 else "N/A",
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with tab2:
            alerts = results.get("missing_data_alerts", [])
            if alerts:
                for alert in alerts:
                    icon = {"critical": "🔴", "warning": "🟡", "info": "🟢"}.get(alert["severity"], "⚪")
                    st.markdown(f"{icon} **{alert['severity'].upper()}** — {alert['message']}")
                    st.caption(f"   Recommended action: {alert['action']}")
            else:
                st.success("No missing data gaps detected!")

        with tab3:
            conf = results.get("confidence_scores", {})
            if conf:
                st.caption("Each dataset is scored on completeness, source reliability, and freshness.")
                for name, score_data in conf.items():
                    level_icon = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(score_data["level"], "⚪")
                    audit_icon = "✅" if score_data["audit_ready"] else "❌"
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.progress(min(score_data["score"] / 100, 1.0),
                                    text=f"{level_icon} **{name}** — {score_data['score']}% ({score_data['level']})")
                    with c2:
                        st.markdown(f"Audit Ready: {audit_icon}")

        with tab4:
            issues = results.get("quality_issues", [])
            if issues:
                for issue in issues:
                    severity_color = {"critical issue": "🔴", "moderate concern": "🟡", "minor issue": "🟢"}
                    icon = severity_color.get(issue["severity"], "⚪")
                    st.markdown(f"{icon} **{issue['dataset']}**: {issue['issue']} — *{issue['severity']}*")
            else:
                st.success("No quality issues detected!")

        with tab5:
            if agent.audit_trail:
                for entry in agent.audit_trail:
                    st.text(f"[{entry['timestamp'][:19]}] {entry['message']}")

# ────────────────────────────────────────────────────────────────
# TAB 3: Enterprise Connectors
# ────────────────────────────────────────────────────────────────
with main_tab3:
    st.markdown("### Enterprise Connector Status")
    results = st.session_state.data_collector_results
    if results:
        conn_statuses = results.get("connector_statuses", {})
        if conn_statuses:
            fig = connector_status_chart(conn_statuses)
            st.plotly_chart(fig, use_container_width=True)
            for key, status in conn_statuses.items():
                icon = {"synced": "✅", "streaming": "📡", "connected": "🔗",
                        "error": "❌", "disconnected": "⚪"}.get(status.get("status", ""), "⚪")
                st.markdown(f"{icon} **{status['name']}** ({status['type']}) — "
                            f"Status: {status['status']} | Records: {status.get('records', 0)}")
        else:
            st.info("Run collection with enterprise connectors enabled to see status.")
    else:
        st.info("Run data collection first to see enterprise connector status.")

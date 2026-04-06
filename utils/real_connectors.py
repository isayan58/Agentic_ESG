"""Real data source connectors — File Upload, Google Sheets, REST API, SQL.

Each connector implements test_connection() and fetch() returning a raw
pandas DataFrame. Column mapping to ESG schemas is handled separately
by schema_mapper.py.

All external library imports are optional (try/except) so the app never
crashes if a driver is not installed.
"""
import io
import pandas as pd
import requests as http_requests

# ── Optional driver availability ─────────────────────────────────────────────
try:
    import sqlalchemy
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

try:
    import openpyxl  # noqa: F401
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    from google.cloud import bigquery as gcp_bigquery
    from google.cloud import storage as gcp_storage
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False

try:
    from azure.storage.blob import BlobServiceClient
    AZURE_BLOB_AVAILABLE = True
except ImportError:
    AZURE_BLOB_AVAILABLE = False


# ── Base ─────────────────────────────────────────────────────────────────────

class RealConnector:
    """Base class for real data source connectors."""

    connector_type = "base"
    display_name = "Base Connector"
    icon = "🔌"

    def test_connection(self, **config) -> dict:
        """Test if the connection works. Returns {"success": bool, "message": str}."""
        raise NotImplementedError

    def fetch(self, **config) -> pd.DataFrame:
        """Fetch data from the source. Returns a raw DataFrame."""
        raise NotImplementedError


# ── File Upload ──────────────────────────────────────────────────────────────

class FileUploadConnector(RealConnector):
    """Handles CSV, Excel, and JSON file uploads."""

    connector_type = "file_upload"
    display_name = "File Upload (CSV / Excel / JSON)"
    icon = "📁"

    def test_connection(self, file_bytes: bytes = None, file_name: str = "", **kw) -> dict:
        if not file_bytes:
            return {"success": False, "message": "No file provided"}
        try:
            df = self._parse(file_bytes, file_name)
            return {
                "success": True,
                "message": f"Parsed {len(df)} rows x {len(df.columns)} columns",
                "preview_cols": list(df.columns),
                "preview_rows": len(df),
            }
        except Exception as e:
            return {"success": False, "message": f"Parse error: {e}"}

    def fetch(self, file_bytes: bytes = None, file_name: str = "", **kw) -> pd.DataFrame:
        return self._parse(file_bytes, file_name)

    def _parse(self, file_bytes: bytes, file_name: str) -> pd.DataFrame:
        buf = io.BytesIO(file_bytes)
        name_lower = file_name.lower()
        if name_lower.endswith(".csv"):
            return pd.read_csv(buf)
        elif name_lower.endswith((".xlsx", ".xls")):
            if not OPENPYXL_AVAILABLE:
                raise ImportError("Install openpyxl to read Excel files: pip install openpyxl")
            return pd.read_excel(buf)
        elif name_lower.endswith(".json"):
            return pd.read_json(buf)
        else:
            # Try CSV as fallback
            return pd.read_csv(buf)


# ── Google Sheets ────────────────────────────────────────────────────────────

class GoogleSheetsConnector(RealConnector):
    """Read data from a public/shared Google Sheets URL."""

    connector_type = "google_sheets"
    display_name = "Google Sheets (Public URL)"
    icon = "📊"

    def _to_csv_url(self, url: str, sheet_id: str = "0") -> str:
        """Convert a Google Sheets URL to a CSV export URL."""
        # Handle various URL formats
        import re
        # Extract the spreadsheet ID
        match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
        if not match:
            raise ValueError("Invalid Google Sheets URL. Expected format: "
                             "https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/...")
        spreadsheet_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={sheet_id}"

    def test_connection(self, url: str = "", sheet_id: str = "0", **kw) -> dict:
        if not url:
            return {"success": False, "message": "No URL provided"}
        try:
            csv_url = self._to_csv_url(url, sheet_id)
            resp = http_requests.get(csv_url, timeout=15)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                return {
                    "success": True,
                    "message": f"Connected! {len(df)} rows x {len(df.columns)} columns",
                    "preview_cols": list(df.columns),
                }
            else:
                return {"success": False, "message": f"HTTP {resp.status_code}. "
                        "Make sure the sheet is shared as 'Anyone with the link'."}
        except ValueError as e:
            return {"success": False, "message": str(e)}
        except Exception as e:
            return {"success": False, "message": f"Connection failed: {e}"}

    def fetch(self, url: str = "", sheet_id: str = "0", **kw) -> pd.DataFrame:
        csv_url = self._to_csv_url(url, sheet_id)
        resp = http_requests.get(csv_url, timeout=30)
        resp.raise_for_status()
        return pd.read_csv(io.StringIO(resp.text))


# ── REST API ─────────────────────────────────────────────────────────────────

class RESTAPIConnector(RealConnector):
    """Fetch JSON data from any REST API endpoint."""

    connector_type = "rest_api"
    display_name = "REST API (JSON)"
    icon = "🌐"

    def _extract_data(self, json_data, json_path: str = ""):
        """Navigate into a nested JSON response using a dot-separated path."""
        if not json_path:
            return json_data
        for key in json_path.split("."):
            key = key.strip()
            if not key:
                continue
            if isinstance(json_data, dict):
                json_data = json_data[key]
            elif isinstance(json_data, list) and key.isdigit():
                json_data = json_data[int(key)]
            else:
                raise KeyError(f"Cannot navigate to '{key}' in response")
        return json_data

    def test_connection(self, url: str = "", method: str = "GET",
                        headers: dict = None, body: str = "",
                        json_path: str = "", **kw) -> dict:
        if not url:
            return {"success": False, "message": "No URL provided"}
        try:
            resp = self._make_request(url, method, headers, body, timeout=15)
            data = self._extract_data(resp.json(), json_path)
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                df = pd.DataFrame([data])
            else:
                return {"success": False, "message": f"Unexpected response type: {type(data).__name__}. "
                        "Use JSON Path to navigate to an array."}
            return {
                "success": True,
                "message": f"Connected! {len(df)} rows x {len(df.columns)} columns",
                "preview_cols": list(df.columns),
            }
        except Exception as e:
            return {"success": False, "message": f"Request failed: {e}"}

    def fetch(self, url: str = "", method: str = "GET",
              headers: dict = None, body: str = "",
              json_path: str = "", **kw) -> pd.DataFrame:
        resp = self._make_request(url, method, headers, body, timeout=30)
        data = self._extract_data(resp.json(), json_path)
        if isinstance(data, list):
            return pd.DataFrame(data)
        elif isinstance(data, dict):
            return pd.DataFrame([data])
        raise ValueError(f"Cannot convert {type(data).__name__} to DataFrame")

    def _make_request(self, url, method, headers, body, timeout):
        headers = headers or {}
        if method.upper() == "POST":
            import json
            json_body = json.loads(body) if body else None
            resp = http_requests.post(url, headers=headers, json=json_body, timeout=timeout)
        else:
            resp = http_requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp


# ── SQL Database ─────────────────────────────────────────────────────────────

class SQLDatabaseConnector(RealConnector):
    """Connect to PostgreSQL, MySQL, or SQLite via SQLAlchemy."""

    connector_type = "sql_database"
    display_name = "SQL Database (PostgreSQL / MySQL / SQLite)"
    icon = "🗄️"

    def test_connection(self, connection_string: str = "", query: str = "", **kw) -> dict:
        if not SQLALCHEMY_AVAILABLE:
            return {"success": False,
                    "message": "SQLAlchemy not installed. Run: pip install sqlalchemy"}
        if not connection_string:
            return {"success": False, "message": "No connection string provided"}
        try:
            engine = sqlalchemy.create_engine(connection_string, connect_args={"connect_timeout": 10})
            with engine.connect() as conn:
                conn.execute(sqlalchemy.text("SELECT 1"))
            # If a query is provided, do a limited test
            if query:
                test_query = f"SELECT * FROM ({query}) AS t LIMIT 5"
                try:
                    df = pd.read_sql(test_query, engine)
                    return {
                        "success": True,
                        "message": f"Connected and query valid! Preview: {len(df)} rows x {len(df.columns)} columns",
                        "preview_cols": list(df.columns),
                    }
                except Exception:
                    # The LIMIT wrapping might not work on all dialects;
                    # connection itself is fine
                    return {"success": True, "message": "Connection successful! Query will be validated on fetch."}
            return {"success": True, "message": "Connection successful!"}
        except Exception as e:
            return {"success": False, "message": f"Connection failed: {e}"}

    def fetch(self, connection_string: str = "", query: str = "",
              row_limit: int = 50000, **kw) -> pd.DataFrame:
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError("SQLAlchemy not installed. Run: pip install sqlalchemy")
        if not query:
            raise ValueError("No SQL query provided")
        engine = sqlalchemy.create_engine(connection_string)
        df = pd.read_sql(query, engine)
        if len(df) > row_limit:
            df = df.head(row_limit)
        return df


# ── AWS S3 ──────────────────────────────────────────────────────────────────

class AWSS3Connector(RealConnector):
    """Read CSV/Excel/JSON files from an AWS S3 bucket."""

    connector_type = "aws_s3"
    display_name = "AWS S3 Bucket"
    icon = "☁️"

    def test_connection(self, bucket: str = "", key: str = "",
                        aws_access_key_id: str = "", aws_secret_access_key: str = "",
                        region: str = "us-east-1", **kw) -> dict:
        if not BOTO3_AVAILABLE:
            return {"success": False, "message": "boto3 not installed. Run: pip install boto3"}
        if not bucket or not key:
            return {"success": False, "message": "Bucket name and object key are required"}
        try:
            client = self._get_client(aws_access_key_id, aws_secret_access_key, region)
            resp = client.head_object(Bucket=bucket, Key=key)
            size = resp["ContentLength"]
            return {"success": True,
                    "message": f"Found object: {key} ({size:,} bytes)"}
        except Exception as e:
            return {"success": False, "message": f"S3 error: {e}"}

    def fetch(self, bucket: str = "", key: str = "",
              aws_access_key_id: str = "", aws_secret_access_key: str = "",
              region: str = "us-east-1", **kw) -> pd.DataFrame:
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 not installed. Run: pip install boto3")
        client = self._get_client(aws_access_key_id, aws_secret_access_key, region)
        obj = client.get_object(Bucket=bucket, Key=key)
        body = obj["Body"].read()
        return self._parse_bytes(body, key)

    def _get_client(self, access_key, secret_key, region):
        kwargs = {"region_name": region}
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key
        return boto3.client("s3", **kwargs)

    def _parse_bytes(self, data: bytes, key: str) -> pd.DataFrame:
        buf = io.BytesIO(data)
        k = key.lower()
        if k.endswith(".csv"):
            return pd.read_csv(buf)
        elif k.endswith((".xlsx", ".xls")):
            return pd.read_excel(buf)
        elif k.endswith(".json"):
            return pd.read_json(buf)
        elif k.endswith(".parquet"):
            return pd.read_parquet(buf)
        return pd.read_csv(buf)


# ── GCP BigQuery ────────────────────────────────────────────────────────────

class GCPBigQueryConnector(RealConnector):
    """Run a SQL query against Google BigQuery."""

    connector_type = "gcp_bigquery"
    display_name = "Google BigQuery"
    icon = "🔷"

    def test_connection(self, project: str = "", query: str = "",
                        credentials_json: str = "", **kw) -> dict:
        if not GCP_AVAILABLE:
            return {"success": False,
                    "message": "google-cloud-bigquery not installed. "
                               "Run: pip install google-cloud-bigquery"}
        if not project or not query:
            return {"success": False, "message": "Project ID and SQL query are required"}
        try:
            client = self._get_client(project, credentials_json)
            job = client.query(f"SELECT * FROM ({query}) LIMIT 5")
            df = job.to_dataframe()
            return {"success": True,
                    "message": f"Query OK — preview: {len(df)} rows x {len(df.columns)} columns",
                    "preview_cols": list(df.columns)}
        except Exception as e:
            return {"success": False, "message": f"BigQuery error: {e}"}

    def fetch(self, project: str = "", query: str = "",
              credentials_json: str = "", row_limit: int = 50000, **kw) -> pd.DataFrame:
        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-bigquery not installed")
        client = self._get_client(project, credentials_json)
        df = client.query(query).to_dataframe()
        if len(df) > row_limit:
            df = df.head(row_limit)
        return df

    def _get_client(self, project, credentials_json):
        if credentials_json:
            import json as _json
            from google.oauth2 import service_account
            info = _json.loads(credentials_json)
            creds = service_account.Credentials.from_service_account_info(info)
            return gcp_bigquery.Client(project=project, credentials=creds)
        return gcp_bigquery.Client(project=project)


# ── GCP Cloud Storage ───────────────────────────────────────────────────────

class GCPStorageConnector(RealConnector):
    """Read files from a Google Cloud Storage bucket."""

    connector_type = "gcp_storage"
    display_name = "Google Cloud Storage"
    icon = "🔷"

    def test_connection(self, bucket: str = "", blob_path: str = "",
                        credentials_json: str = "", **kw) -> dict:
        if not GCP_AVAILABLE:
            return {"success": False,
                    "message": "google-cloud-storage not installed. "
                               "Run: pip install google-cloud-storage"}
        if not bucket or not blob_path:
            return {"success": False, "message": "Bucket and blob path are required"}
        try:
            client = self._get_client(credentials_json)
            blob = client.bucket(bucket).blob(blob_path)
            if blob.exists():
                blob.reload()
                return {"success": True,
                        "message": f"Found: {blob_path} ({blob.size:,} bytes)"}
            return {"success": False, "message": f"Blob not found: {blob_path}"}
        except Exception as e:
            return {"success": False, "message": f"GCS error: {e}"}

    def fetch(self, bucket: str = "", blob_path: str = "",
              credentials_json: str = "", **kw) -> pd.DataFrame:
        if not GCP_AVAILABLE:
            raise ImportError("google-cloud-storage not installed")
        client = self._get_client(credentials_json)
        blob = client.bucket(bucket).blob(blob_path)
        data = blob.download_as_bytes()
        return self._parse_bytes(data, blob_path)

    def _get_client(self, credentials_json):
        if credentials_json:
            import json as _json
            from google.oauth2 import service_account
            info = _json.loads(credentials_json)
            creds = service_account.Credentials.from_service_account_info(info)
            return gcp_storage.Client(credentials=creds)
        return gcp_storage.Client()

    def _parse_bytes(self, data: bytes, path: str) -> pd.DataFrame:
        buf = io.BytesIO(data)
        p = path.lower()
        if p.endswith(".csv"):
            return pd.read_csv(buf)
        elif p.endswith((".xlsx", ".xls")):
            return pd.read_excel(buf)
        elif p.endswith(".json"):
            return pd.read_json(buf)
        elif p.endswith(".parquet"):
            return pd.read_parquet(buf)
        return pd.read_csv(buf)


# ── Azure Blob Storage ──────────────────────────────────────────────────────

class AzureBlobConnector(RealConnector):
    """Read files from Azure Blob Storage."""

    connector_type = "azure_blob"
    display_name = "Azure Blob Storage"
    icon = "🔵"

    def test_connection(self, connection_string: str = "", container: str = "",
                        blob_name: str = "", **kw) -> dict:
        if not AZURE_BLOB_AVAILABLE:
            return {"success": False,
                    "message": "azure-storage-blob not installed. "
                               "Run: pip install azure-storage-blob"}
        if not connection_string or not container or not blob_name:
            return {"success": False,
                    "message": "Connection string, container, and blob name are required"}
        try:
            client = BlobServiceClient.from_connection_string(connection_string)
            blob_client = client.get_blob_client(container, blob_name)
            props = blob_client.get_blob_properties()
            return {"success": True,
                    "message": f"Found: {blob_name} ({props.size:,} bytes)"}
        except Exception as e:
            return {"success": False, "message": f"Azure error: {e}"}

    def fetch(self, connection_string: str = "", container: str = "",
              blob_name: str = "", **kw) -> pd.DataFrame:
        if not AZURE_BLOB_AVAILABLE:
            raise ImportError("azure-storage-blob not installed")
        client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = client.get_blob_client(container, blob_name)
        data = blob_client.download_blob().readall()
        return self._parse_bytes(data, blob_name)

    def _parse_bytes(self, data: bytes, name: str) -> pd.DataFrame:
        buf = io.BytesIO(data)
        n = name.lower()
        if n.endswith(".csv"):
            return pd.read_csv(buf)
        elif n.endswith((".xlsx", ".xls")):
            return pd.read_excel(buf)
        elif n.endswith(".json"):
            return pd.read_json(buf)
        elif n.endswith(".parquet"):
            return pd.read_parquet(buf)
        return pd.read_csv(buf)


# ── Connector Registry ───────────────────────────────────────────────────────

REAL_CONNECTORS = {
    "file_upload":    FileUploadConnector,
    "google_sheets":  GoogleSheetsConnector,
    "rest_api":       RESTAPIConnector,
    "sql_database":   SQLDatabaseConnector,
    "aws_s3":         AWSS3Connector,
    "gcp_bigquery":   GCPBigQueryConnector,
    "gcp_storage":    GCPStorageConnector,
    "azure_blob":     AzureBlobConnector,
}


def get_connector(connector_type: str) -> RealConnector:
    """Instantiate a connector by type name."""
    cls = REAL_CONNECTORS.get(connector_type)
    if cls is None:
        raise ValueError(f"Unknown connector type: {connector_type}")
    return cls()


def get_available_connectors() -> dict:
    """Return connector types with availability status."""
    return {
        "file_upload":   {"name": "File Upload (CSV/Excel/JSON)", "icon": "📁", "available": True},
        "google_sheets": {"name": "Google Sheets (Public URL)",   "icon": "📊", "available": True},
        "rest_api":      {"name": "REST API (JSON)",              "icon": "🌐", "available": True},
        "sql_database":  {"name": "SQL Database",                 "icon": "🗄️",
                          "available": SQLALCHEMY_AVAILABLE,
                          "install_hint": "pip install sqlalchemy psycopg2-binary"},
        "aws_s3":        {"name": "AWS S3 Bucket",                "icon": "☁️",
                          "available": BOTO3_AVAILABLE,
                          "install_hint": "pip install boto3"},
        "gcp_bigquery":  {"name": "Google BigQuery",              "icon": "🔷",
                          "available": GCP_AVAILABLE,
                          "install_hint": "pip install google-cloud-bigquery google-cloud-storage"},
        "gcp_storage":   {"name": "Google Cloud Storage",         "icon": "🔷",
                          "available": GCP_AVAILABLE,
                          "install_hint": "pip install google-cloud-storage"},
        "azure_blob":    {"name": "Azure Blob Storage",           "icon": "🔵",
                          "available": AZURE_BLOB_AVAILABLE,
                          "install_hint": "pip install azure-storage-blob"},
    }

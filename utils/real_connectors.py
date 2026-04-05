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


# ── Connector Registry ───────────────────────────────────────────────────────

REAL_CONNECTORS = {
    "file_upload":    FileUploadConnector,
    "google_sheets":  GoogleSheetsConnector,
    "rest_api":       RESTAPIConnector,
    "sql_database":   SQLDatabaseConnector,
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
    }

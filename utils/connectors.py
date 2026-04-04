"""Enterprise data source connectors — ERP, HR, IoT, Suppliers, SQL, API.

Each connector returns a pandas DataFrame. In production, these would connect
to real systems. For the prototype, they simulate enterprise data with realistic
schemas so the full pipeline can demonstrate end-to-end flow.
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from config import DATA_DIR


class BaseConnector:
    """Abstract base for all data source connectors."""

    def __init__(self, name, source_type):
        self.name = name
        self.source_type = source_type
        self.connected = False
        self.last_sync = None
        self.status = "disconnected"
        self.record_count = 0

    def connect(self, **kwargs):
        self.connected = True
        self.status = "connected"
        self.last_sync = datetime.now().isoformat()
        return True

    def disconnect(self):
        self.connected = False
        self.status = "disconnected"

    def fetch(self):
        raise NotImplementedError

    def get_status(self):
        return {
            "name": self.name,
            "type": self.source_type,
            "status": self.status,
            "connected": self.connected,
            "last_sync": self.last_sync,
            "records": self.record_count,
        }


class ERPConnector(BaseConnector):
    """Connects to ERP systems (SAP, Oracle) for financial & operational data."""

    def __init__(self):
        super().__init__("ERP System (SAP)", "ERP")

    def fetch(self):
        self.connect()
        np.random.seed(42)
        months = pd.date_range("2024-01-01", "2024-12-31", freq="MS")
        rows = []
        for m in months:
            rows.append({
                "date": m.strftime("%Y-%m-%d"),
                "revenue_inr_lakhs": round(np.random.normal(3200, 200), 1),
                "opex_inr_lakhs": round(np.random.normal(2400, 150), 1),
                "capex_inr_lakhs": round(np.random.normal(350, 80), 1),
                "esg_budget_inr_lakhs": round(np.random.normal(85, 15), 1),
                "procurement_spend_inr_lakhs": round(np.random.normal(800, 100), 1),
                "travel_spend_inr_lakhs": round(np.random.normal(120, 30), 1),
                "facility_cost_inr_lakhs": round(np.random.normal(180, 20), 1),
            })
        df = pd.DataFrame(rows)
        self.record_count = len(df)
        self.status = "synced"
        return df


class HRConnector(BaseConnector):
    """Connects to HR systems (Workday, SuccessFactors) for workforce data."""

    def __init__(self):
        super().__init__("HR System (Workday)", "HRIS")

    def fetch(self):
        self.connect()
        np.random.seed(43)
        departments = ["Engineering", "Sales", "HR", "Finance", "Operations",
                        "Legal", "Marketing", "R&D", "Support", "Leadership"]
        rows = []
        for dept in departments:
            headcount = np.random.randint(80, 800)
            rows.append({
                "department": dept,
                "headcount": headcount,
                "women_pct": round(np.random.uniform(25, 55), 1),
                "avg_tenure_years": round(np.random.uniform(2, 8), 1),
                "voluntary_turnover_pct": round(np.random.uniform(8, 25), 1),
                "training_hours_avg": round(np.random.uniform(20, 60), 1),
                "safety_incidents": np.random.randint(0, 5),
                "engagement_score": round(np.random.uniform(65, 92), 1),
                "avg_salary_inr_lakhs": round(np.random.uniform(8, 45), 1),
                "pwd_count": np.random.randint(1, 15),
            })
        df = pd.DataFrame(rows)
        self.record_count = len(df)
        self.status = "synced"
        return df


class IoTConnector(BaseConnector):
    """Connects to IoT / Building Management Systems for real-time environmental data."""

    def __init__(self):
        super().__init__("IoT / BMS Sensors", "IoT")

    def fetch(self):
        self.connect()
        np.random.seed(44)
        sensors = [
            ("Mumbai HQ - Electricity Meter", "electricity_kwh", 800, 150),
            ("Mumbai HQ - Water Meter", "water_liters", 5000, 800),
            ("Mumbai HQ - HVAC System", "hvac_kwh", 300, 60),
            ("Mumbai HQ - Solar Inverter", "solar_kwh", 180, 40),
            ("Bangalore - Electricity Meter", "electricity_kwh", 350, 70),
            ("Bangalore - Water Meter", "water_liters", 2200, 400),
            ("Mumbai HQ - Diesel Genset", "diesel_liters", 25, 15),
            ("Mumbai HQ - Indoor AQI", "aqi_index", 45, 12),
            ("Mumbai HQ - Temperature", "temp_celsius", 24, 2),
            ("Mumbai HQ - Waste Scale", "waste_kg", 120, 30),
        ]
        rows = []
        hours = pd.date_range("2024-12-01", periods=24*7, freq="h")
        for ts in hours:
            for sensor_name, metric, mean, std in sensors:
                rows.append({
                    "timestamp": ts.isoformat(),
                    "sensor_id": sensor_name,
                    "metric": metric,
                    "value": round(max(0, np.random.normal(mean, std)), 2),
                    "unit": metric.split("_")[-1],
                    "status": "online",
                })
        df = pd.DataFrame(rows)
        self.record_count = len(df)
        self.status = "streaming"
        return df


class SupplierPortalConnector(BaseConnector):
    """Connects to supplier ESG disclosure portals / CDP / EcoVadis."""

    def __init__(self):
        super().__init__("Supplier Portal (EcoVadis)", "Supplier API")

    def fetch(self):
        self.connect()
        # Load existing supply chain data and enrich with portal data
        path = os.path.join(DATA_DIR, "sample_supply_chain.csv")
        if os.path.exists(path):
            df = pd.read_csv(path)
            np.random.seed(45)
            df["self_reported_emissions"] = (
                df["emission_contribution_tco2e"] * np.random.uniform(0.85, 1.15, len(df))
            ).round(1)
            df["sbti_committed"] = np.random.choice([True, False], len(df), p=[0.35, 0.65])
            df["ecovadis_score"] = np.clip(
                df["esg_score"] + np.random.randint(-10, 10, len(df)), 20, 100
            )
            df["disclosure_completeness_pct"] = np.random.randint(40, 100, len(df))
            df["last_disclosure_date"] = [
                (datetime.now() - timedelta(days=np.random.randint(30, 365))).strftime("%Y-%m-%d")
                for _ in range(len(df))
            ]
        else:
            df = pd.DataFrame()
        self.record_count = len(df)
        self.status = "synced"
        return df


class SQLDatabaseConnector(BaseConnector):
    """Generic SQL database connector (PostgreSQL, MySQL, etc.)."""

    def __init__(self, db_type="PostgreSQL"):
        super().__init__(f"Database ({db_type})", "SQL")
        self.db_type = db_type

    def fetch(self, connection_string=None, query=None):
        """
        In production:
            import sqlalchemy
            engine = sqlalchemy.create_engine(connection_string)
            return pd.read_sql(query, engine)
        """
        self.connect()
        # Simulate: return combined operational data
        np.random.seed(46)
        rows = []
        for month in range(1, 13):
            rows.append({
                "month": f"2024-{month:02d}",
                "electricity_mwh": round(np.random.normal(3200, 200), 1),
                "natural_gas_mmbtu": round(np.random.normal(450, 80), 1),
                "water_kiloliters": round(np.random.normal(6500, 500), 1),
                "waste_metric_tons": round(np.random.normal(95, 15), 1),
                "recycled_metric_tons": round(np.random.normal(65, 12), 1),
                "fleet_km": round(np.random.normal(45000, 5000), 0),
                "business_travel_km": round(np.random.normal(120000, 20000), 0),
            })
        df = pd.DataFrame(rows)
        self.record_count = len(df)
        self.status = "synced"
        return df


class APIConnector(BaseConnector):
    """REST API connector for external ESG data providers (CDP, Bloomberg, MSCI)."""

    def __init__(self, provider="CDP"):
        super().__init__(f"API ({provider})", "REST API")
        self.provider = provider

    def fetch(self, url=None, headers=None):
        """
        In production:
            import requests
            resp = requests.get(url, headers=headers)
            return pd.DataFrame(resp.json())
        """
        self.connect()
        np.random.seed(47)
        # Simulate CDP-style climate disclosure scores
        rows = [
            {"framework": "CDP Climate", "score": "A-", "year": 2024, "percentile": 82},
            {"framework": "CDP Water", "score": "B", "year": 2024, "percentile": 65},
            {"framework": "CDP Forests", "score": "B-", "year": 2024, "percentile": 58},
            {"framework": "MSCI ESG", "score": "BBB", "year": 2024, "percentile": 72},
            {"framework": "Sustainalytics", "score": "22.5 (Medium Risk)", "year": 2024, "percentile": 60},
            {"framework": "ISS ESG", "score": "C+", "year": 2024, "percentile": 68},
            {"framework": "FTSE4Good", "score": "3.8/5", "year": 2024, "percentile": 76},
        ]
        df = pd.DataFrame(rows)
        self.record_count = len(df)
        self.status = "synced"
        return df


# --- Connector Registry ---

ALL_CONNECTORS = {
    "erp": ERPConnector,
    "hr": HRConnector,
    "iot": IoTConnector,
    "supplier_portal": SupplierPortalConnector,
    "sql_database": SQLDatabaseConnector,
    "api_cdp": lambda: APIConnector("CDP/MSCI/Sustainalytics"),
}


def get_all_connectors():
    """Instantiate and return all available connectors."""
    connectors = {}
    for key, cls in ALL_CONNECTORS.items():
        connectors[key] = cls() if callable(cls) else cls
    return connectors


def fetch_all_external_data():
    """Fetch data from all connectors. Returns dict of DataFrames."""
    connectors = get_all_connectors()
    data = {}
    statuses = {}
    for key, connector in connectors.items():
        try:
            df = connector.fetch()
            data[key] = df
            statuses[key] = connector.get_status()
        except Exception as e:
            statuses[key] = {**connector.get_status(), "status": "error", "error": str(e)}
    return data, statuses

"""Common data processing utilities."""
import os
import json
import pandas as pd
from config import DATA_DIR


def load_csv(filename):
    """Load a CSV file from the data directory.

    Falls back to sample_data/company/<name> (stripping the leading
    "sample_" prefix) so locally-placed data files are picked up
    without requiring a manual upload through the UI.
    """
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        return pd.read_csv(path)
    canonical = filename[len("sample_"):] if filename.startswith("sample_") else filename
    alt_path = os.path.join(os.path.dirname(DATA_DIR), "sample_data", "company", canonical)
    if os.path.exists(alt_path):
        try:
            return pd.read_csv(alt_path)
        except UnicodeDecodeError:
            return pd.read_csv(alt_path, encoding="latin-1")
    return pd.DataFrame()


def load_json(filename):
    """Load a JSON file from the data directory."""
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def load_emissions():
    return load_csv("sample_emissions.csv")


def load_esg_metrics():
    return load_csv("sample_esg_metrics.csv")


def load_supply_chain():
    return load_csv("sample_supply_chain.csv")


def load_energy():
    return load_csv("sample_energy.csv")


def load_waste():
    return load_csv("sample_waste.csv")


def load_diversity():
    return load_csv("sample_diversity.csv")


def load_regulatory_frameworks():
    return load_json("regulatory_frameworks.json")


def load_financials():
    return load_csv("sample_financials.csv")


def load_company_profile():
    return load_json("company_profile.json")


def compute_scope_totals(emissions_df, year=None):
    """Compute total emissions by scope."""
    df = emissions_df.copy()
    if year:
        df = df[df["year"] == year]
    return df.groupby("scope")["emissions_tco2e"].sum().to_dict()


def compute_quarterly_trends(emissions_df):
    """Compute quarterly emission trends by scope."""
    df = emissions_df.copy()
    df["period"] = df["year"].astype(str) + " " + df["quarter"]
    return df.groupby(["period", "scope"])["emissions_tco2e"].sum().reset_index()


def compute_data_quality(df):
    """Compute data quality metrics for a dataframe."""
    total_cells = df.size
    non_null = df.notna().sum().sum()
    completeness = (non_null / total_cells * 100) if total_cells > 0 else 0

    # Confidence score if available
    confidence = 0
    if "confidence" in df.columns:
        confidence = df["confidence"].mean() * 100

    return {
        "completeness": round(completeness, 1),
        "total_records": len(df),
        "total_fields": len(df.columns),
        "null_count": total_cells - non_null,
        "avg_confidence": round(confidence, 1),
    }


def compute_esg_summary(metrics_df, year_col="value_2024"):
    """Compute ESG pillar summary scores."""
    if metrics_df.empty:
        return {}

    summary = {}
    for pillar in ["Environmental", "Social", "Governance"]:
        pillar_df = metrics_df[metrics_df["pillar"] == pillar]
        if not pillar_df.empty:
            met_count = (pillar_df["status"] == "Met").sum()
            total = len(pillar_df)
            summary[pillar] = {
                "score": round(met_count / total * 100, 1) if total > 0 else 0,
                "metrics_met": int(met_count),
                "total_metrics": int(total),
            }
    return summary

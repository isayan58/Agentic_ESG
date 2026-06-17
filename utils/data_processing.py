"""Common data processing utilities."""
import os
import json
import pandas as pd
from config import DATA_DIR


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise all column names to lowercase snake_case.

    Strips surrounding whitespace, lowercases every character, and
    collapses interior whitespace runs to a single underscore.  Applied
    at every DataFrame entry point so downstream code that expects
    lowercase names (e.g. df["metric_id"], df["status"]) always works
    regardless of what capitalisation the source file used.

    Examples: "Metric_ID" → "metric_id", "STATUS" → "status",
              "Revenue INR Crores" → "revenue_inr_crores"
    """
    if df.empty and df.columns.empty:
        return df
    df = df.copy()
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"\s+", "_", regex=True)
    )
    return df


def load_csv(filename):
    """Load a CSV file from the data directory.

    Falls back to sample_data/ESG Datasets/ then sample_data/company/
    (stripping the leading "sample_" prefix) so locally-placed data
    files are picked up without requiring a manual upload through the UI.

    Column names are normalised to lowercase snake_case on load so
    upstream capitalisation differences never reach agent code.
    """
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        return _norm_cols(pd.read_csv(path))
    canonical = filename[len("sample_"):] if filename.startswith("sample_") else filename
    sample_root = os.path.join(os.path.dirname(DATA_DIR), "sample_data")
    candidates = [
        os.path.join(sample_root, "ESG Datasets", canonical),
        os.path.join(sample_root, "company", canonical),
    ]
    for alt_path in candidates:
        if os.path.exists(alt_path):
            try:
                return _norm_cols(pd.read_csv(alt_path))
            except UnicodeDecodeError:
                return _norm_cols(pd.read_csv(alt_path, encoding="latin-1"))
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


def compute_data_quality(df, source_tier: str = "sample"):
    """Compute data quality metrics using a 5-component confidence rubric.

    Components and weights (sum to 100):
      - Source reliability   25 pts  — tier: real=25, connector=18, sample=10
      - Completeness         20 pts  — linear scale from null-rate
      - Timeliness           15 pts  — presence of a year/date column with recent data
      - Validation pass rate 20 pts  — status/confidence column pass rate
      - Data lineage         20 pts  — presence of data_source / source columns

    The result is stored in ``avg_confidence`` (0–100) so all downstream
    callers (audit agent, IQS, dashboard) receive a meaningful score regardless
    of whether the raw data has a ``confidence`` column.
    """
    import datetime as _dt

    total_cells = df.size
    non_null = df.notna().sum().sum()
    completeness_pct = (non_null / total_cells * 100) if total_cells > 0 else 0

    cols_lower = {c.lower() for c in df.columns}

    # ── 1. Source reliability (25 pts) ───────────────────────────────────────
    tier_scores = {"real": 25, "connector": 18, "sample": 10}
    src_score = tier_scores.get(source_tier, 10)

    # ── 2. Completeness (20 pts) ─────────────────────────────────────────────
    comp_score = round(completeness_pct / 100 * 20, 1)

    # ── 3. Timeliness (15 pts) ───────────────────────────────────────────────
    # Full 15 if data has a year column containing the current or prior year;
    # 8 if a year column exists but values are older; 3 otherwise.
    time_score = 3
    year_cols = [c for c in df.columns if c.lower() in ("year", "fiscal_year", "reporting_year", "date")]
    if year_cols:
        try:
            current_year = _dt.datetime.now().year
            max_year = pd.to_numeric(df[year_cols[0]], errors="coerce").max()
            if pd.notna(max_year):
                if max_year >= current_year - 1:
                    time_score = 15
                elif max_year >= current_year - 3:
                    time_score = 8
        except Exception:
            time_score = 8

    # ── 4. Validation pass rate (20 pts) ─────────────────────────────────────
    val_score = 10  # baseline when no validation column present
    if "status" in cols_lower:
        status_col = next(c for c in df.columns if c.lower() == "status")
        total_rows = len(df)
        if total_rows > 0:
            pass_vals = {"met", "pass", "passed", "ok", "compliant", "valid", "on track"}
            pass_count = df[status_col].astype(str).str.lower().isin(pass_vals).sum()
            val_score = round(pass_count / total_rows * 20, 1)
    elif "confidence" in cols_lower:
        conf_col = next(c for c in df.columns if c.lower() == "confidence")
        raw_conf = pd.to_numeric(df[conf_col], errors="coerce").dropna()
        if not raw_conf.empty:
            # confidence column is 0-1; scale to 0-20
            val_score = round(float(raw_conf.mean()) * 20, 1)

    # ── 5. Data lineage (20 pts) ─────────────────────────────────────────────
    lineage_cols = {"data_source", "source", "data_origin", "source_system",
                    "emission_factor_source", "data_source_name"}
    present_lineage = lineage_cols & cols_lower
    lineage_score = 0
    if present_lineage:
        lin_col = next(c for c in df.columns if c.lower() in present_lineage)
        non_null_lineage = df[lin_col].notna().sum()
        lineage_score = round(non_null_lineage / max(len(df), 1) * 20, 1)

    avg_confidence = round(src_score + comp_score + time_score + val_score + lineage_score, 1)
    avg_confidence = min(100.0, avg_confidence)

    return {
        "completeness": round(completeness_pct, 1),
        "total_records": len(df),
        "total_fields": len(df.columns),
        "null_count": int(total_cells - non_null),
        "avg_confidence": avg_confidence,
        "_confidence_components": {
            "source_reliability": src_score,
            "completeness": comp_score,
            "timeliness": time_score,
            "validation_pass_rate": val_score,
            "data_lineage": lineage_score,
        },
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

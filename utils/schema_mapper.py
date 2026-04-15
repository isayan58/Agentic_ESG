"""ESG schema definitions, auto-detection, column mapping, and validation.

Maps arbitrary user data columns to the 6 canonical ESG dataset schemas
used throughout the pipeline.
"""
import pandas as pd
import re

# ── Canonical ESG Schemas ────────────────────────────────────────────────────
# Each schema defines the expected columns, their types, whether they're
# required, and a human-readable description for the mapping UI.

ESG_SCHEMAS = {
    "emissions": {
        "year":             {"type": "int",   "required": True,  "description": "Reporting year (e.g. 2024)"},
        "quarter":          {"type": "str",   "required": True,  "description": "Quarter (Q1, Q2, Q3, Q4)"},
        "scope":            {"type": "str",   "required": True,  "description": "Emission scope (Scope 1, Scope 2, Scope 3)"},
        "category":         {"type": "str",   "required": True,  "description": "Emission category (e.g. Fleet Vehicles, Electricity)"},
        "emissions_tco2e":  {"type": "float", "required": True,  "description": "Emissions in tonnes CO2 equivalent"},
        "unit":             {"type": "str",   "required": False, "description": "Unit of measurement (default: tCO2e)"},
        "source":           {"type": "str",   "required": False, "description": "Data source (e.g. Fuel logs, Utility bills)"},
        "confidence":       {"type": "float", "required": False, "description": "Confidence score 0-1"},
    },
    "esg_metrics": {
        "metric_id":    {"type": "str",   "required": True,  "description": "Unique metric identifier (e.g. E01, S03)"},
        "pillar":       {"type": "str",   "required": True,  "description": "ESG pillar (Environmental, Social, Governance)"},
        "category":     {"type": "str",   "required": True,  "description": "Metric category (e.g. Climate, Workforce)"},
        "metric_name":  {"type": "str",   "required": True,  "description": "Human-readable metric name"},
        "unit":         {"type": "str",   "required": False, "description": "Unit of measurement"},
        "value_2023":   {"type": "float", "required": False, "description": "Value for 2023"},
        "value_2024":   {"type": "float", "required": False, "description": "Value for 2024"},
        "target_2024":  {"type": "float", "required": False, "description": "Target value for 2024"},
        "status":       {"type": "str",   "required": False, "description": "Status (Met, Not Met, On Track)"},
        "data_source":  {"type": "str",   "required": False, "description": "Data source description"},
        "confidence":   {"type": "float", "required": False, "description": "Confidence score 0-1"},
    },
    "supply_chain": {
        "supplier_id":                  {"type": "str",   "required": True,  "description": "Unique supplier identifier"},
        "supplier_name":                {"type": "str",   "required": True,  "description": "Supplier company name"},
        "country":                      {"type": "str",   "required": True,  "description": "Country of operation"},
        "sector":                       {"type": "str",   "required": False, "description": "Industry sector"},
        "tier":                         {"type": "str",   "required": False, "description": "Supply chain tier (Tier 1, Tier 2, Tier 3)"},
        "esg_score":                    {"type": "float", "required": False, "description": "ESG score (0-100)"},
        "risk_rating":                  {"type": "str",   "required": False, "description": "Risk rating (Low, Medium, High, Critical)"},
        "emission_contribution_tco2e":  {"type": "float", "required": False, "description": "Emission contribution in tCO2e"},
        "audit_status":                 {"type": "str",   "required": False, "description": "Audit status"},
        "last_audit_date":              {"type": "str",   "required": False, "description": "Last audit date (YYYY-MM-DD)"},
        "key_risk_factors":             {"type": "str",   "required": False, "description": "Key risk factors (comma-separated)"},
    },
    "energy": {
        "year":             {"type": "int",   "required": True,  "description": "Reporting year"},
        "quarter":          {"type": "str",   "required": True,  "description": "Quarter (Q1-Q4)"},
        "energy_source":    {"type": "str",   "required": True,  "description": "Energy source (Grid Electricity, Solar, etc.)"},
        "consumption_mwh":  {"type": "float", "required": True,  "description": "Energy consumption in MWh"},
        "cost_inr_lakhs":   {"type": "float", "required": False, "description": "Cost in INR lakhs"},
        "location":         {"type": "str",   "required": False, "description": "Facility location"},
        "renewable":        {"type": "str",   "required": False, "description": "Is renewable? (Yes/No)"},
    },
    "waste": {
        "year":             {"type": "int",   "required": True,  "description": "Reporting year"},
        "quarter":          {"type": "str",   "required": True,  "description": "Quarter (Q1-Q4)"},
        "waste_type":       {"type": "str",   "required": True,  "description": "Waste type (Hazardous, Non-Hazardous)"},
        "category":         {"type": "str",   "required": True,  "description": "Waste category (e.g. Paper, Plastic, E-waste)"},
        "quantity_mt":      {"type": "float", "required": True,  "description": "Quantity in metric tonnes"},
        "disposal_method":  {"type": "str",   "required": False, "description": "Disposal method (Recycling, Landfill, etc.)"},
        "recycled_pct":     {"type": "float", "required": False, "description": "Recycled percentage (0-100)"},
        "location":         {"type": "str",   "required": False, "description": "Facility location"},
    },
    "diversity": {
        "year":         {"type": "int",   "required": True,  "description": "Reporting year"},
        "category":     {"type": "str",   "required": True,  "description": "Diversity category (Gender, Age, etc.)"},
        "subcategory":  {"type": "str",   "required": True,  "description": "Subcategory (Overall, Leadership, etc.)"},
        "metric":       {"type": "str",   "required": True,  "description": "Metric name"},
        "value":        {"type": "float", "required": True,  "description": "Metric value"},
        "unit":         {"type": "str",   "required": False, "description": "Unit (percentage, count, ratio)"},
    },
    "financials": {
        "year":                          {"type": "int",   "required": True,  "description": "Reporting year"},
        "quarter":                       {"type": "str",   "required": True,  "description": "Quarter (Q1-Q4)"},
        "revenue_inr_crores":            {"type": "float", "required": True,  "description": "Revenue in INR crores"},
        "ebitda_inr_crores":             {"type": "float", "required": False, "description": "EBITDA in INR crores"},
        "ebitda_margin_pct":             {"type": "float", "required": False, "description": "EBITDA margin percentage"},
        "pat_inr_crores":                {"type": "float", "required": False, "description": "Profit after tax in INR crores"},
        "roa_pct":                       {"type": "float", "required": False, "description": "Return on assets percentage"},
        "roe_pct":                       {"type": "float", "required": False, "description": "Return on equity percentage"},
        "debt_equity_ratio":             {"type": "float", "required": False, "description": "Debt to equity ratio"},
        "cost_of_capital_pct":           {"type": "float", "required": False, "description": "Cost of capital percentage"},
        "pe_ratio":                      {"type": "float", "required": False, "description": "Price to earnings ratio"},
        "carbon_tax_exposure_lakhs":     {"type": "float", "required": False, "description": "Carbon tax exposure in INR lakhs"},
        "energy_cost_inr_crores":        {"type": "float", "required": False, "description": "Energy cost in INR crores"},
        "employee_turnover_pct":         {"type": "float", "required": False, "description": "Employee turnover percentage"},
        "brand_value_index":             {"type": "float", "required": False, "description": "Brand value index"},
        "talent_retention_score":        {"type": "float", "required": False, "description": "Talent retention score"},
        "esg_linked_capex_inr_crores":   {"type": "float", "required": False, "description": "ESG-linked CapEx in INR crores"},
    },
}

# Indicator columns used for auto-detection — columns strongly associated
# with each schema.
_SCHEMA_INDICATORS = {
    "emissions":    ["emissions_tco2e", "scope", "tco2e", "ghg", "co2"],
    "esg_metrics":  ["pillar", "metric_id", "metric_name", "esg"],
    "supply_chain": ["supplier_id", "supplier_name", "risk_rating", "supplier"],
    "energy":       ["energy_source", "consumption_mwh", "renewable", "mwh"],
    "waste":        ["waste_type", "disposal_method", "recycled_pct", "quantity_mt"],
    "diversity":    ["subcategory", "diversity", "gender", "workforce"],
    "financials":   ["revenue_inr_crores", "ebitda_margin_pct", "roa_pct", "roe_pct", "esglinkedcapex", "costofcapital"],
}


def _normalize(col: str) -> str:
    """Lowercase, strip, collapse whitespace/special chars."""
    return re.sub(r"[^a-z0-9]", "", col.lower().strip())


# ── Auto-Detection ───────────────────────────────────────────────────────────

def auto_detect_schema(df: pd.DataFrame) -> str | None:
    """Guess which ESG schema best matches a DataFrame's columns.

    Returns the schema name or None if no confident match.
    """
    if df.empty:
        return None

    cols_normalized = {_normalize(c) for c in df.columns}
    scores = {}

    for schema_name, indicators in _SCHEMA_INDICATORS.items():
        score = sum(1 for ind in indicators if _normalize(ind) in cols_normalized)
        # Also check exact column name matches against schema keys
        schema_cols = {_normalize(k) for k in ESG_SCHEMAS[schema_name]}
        exact_matches = len(cols_normalized & schema_cols)
        scores[schema_name] = score * 2 + exact_matches  # indicators weighted higher

    best = max(scores, key=scores.get)
    return best if scores[best] >= 2 else None


# ── Column Mapping ───────────────────────────────────────────────────────────

def suggest_column_mapping(df: pd.DataFrame, target_schema: str) -> dict:
    """Suggest a mapping from source columns to ESG schema columns.

    Returns {esg_column: source_column_or_None}.
    """
    schema = ESG_SCHEMAS.get(target_schema, {})
    source_cols = list(df.columns)
    source_normalized = {_normalize(c): c for c in source_cols}
    mapping = {}

    for esg_col in schema:
        esg_norm = _normalize(esg_col)

        # 1. Exact match
        if esg_col in source_cols:
            mapping[esg_col] = esg_col
            continue

        # 2. Normalized match
        if esg_norm in source_normalized:
            mapping[esg_col] = source_normalized[esg_norm]
            continue

        # 3. Substring / partial match
        matched = None
        for src_norm, src_orig in source_normalized.items():
            if esg_norm in src_norm or src_norm in esg_norm:
                matched = src_orig
                break
            # Check common synonyms
            synonyms = _SYNONYMS.get(esg_col, [])
            for syn in synonyms:
                if _normalize(syn) in src_norm:
                    matched = src_orig
                    break
            if matched:
                break

        mapping[esg_col] = matched  # None if no match found

    return mapping


# Common column name synonyms for better auto-mapping
_SYNONYMS = {
    "emissions_tco2e": ["co2", "ghg", "carbon", "emission", "tco2", "tonnes_co2"],
    "year": ["reporting_year", "fiscal_year", "yr"],
    "quarter": ["qtr", "q", "reporting_quarter", "period"],
    "scope": ["emission_scope", "ghg_scope"],
    "category": ["type", "classification", "class"],
    "supplier_name": ["vendor", "vendor_name", "company", "company_name"],
    "supplier_id": ["vendor_id", "vendor_code", "supplier_code"],
    "country": ["nation", "location_country", "geography"],
    "esg_score": ["sustainability_score", "rating_score", "score"],
    "risk_rating": ["risk_level", "risk", "risk_category"],
    "energy_source": ["source", "fuel_type", "energy_type"],
    "consumption_mwh": ["energy_consumed", "mwh", "consumption", "usage_mwh"],
    "waste_type": ["hazardous", "waste_classification"],
    "quantity_mt": ["weight", "tonnes", "amount", "quantity"],
    "metric_name": ["kpi", "indicator", "measure"],
    "pillar": ["dimension", "esg_pillar", "area"],
    "value": ["amount", "result", "measurement"],
    "confidence": ["confidence_score", "reliability", "quality_score"],
    "emission_contribution_tco2e": ["supplier_emissions", "scope3_contribution"],
    "revenue_inr_crores": ["revenue", "sales", "turnover_inr_crores"],
    "ebitda_inr_crores": ["ebitda", "operating_profit"],
    "ebitda_margin_pct": ["ebitda_margin", "operating_margin"],
    "pat_inr_crores": ["pat", "profit_after_tax", "net_profit"],
    "roa_pct": ["roa", "return_on_assets"],
    "roe_pct": ["roe", "return_on_equity"],
    "debt_equity_ratio": ["de_ratio", "debt_to_equity"],
    "cost_of_capital_pct": ["wacc", "cost_of_capital"],
    "pe_ratio": ["p_e", "price_earnings"],
    "carbon_tax_exposure_lakhs": ["carbon_tax", "carbon_cost"],
    "energy_cost_inr_crores": ["energy_cost", "power_cost"],
    "employee_turnover_pct": ["attrition", "employee_turnover"],
    "brand_value_index": ["brand_index", "brand_value"],
    "talent_retention_score": ["retention_score", "talent_score"],
    "esg_linked_capex_inr_crores": ["esg_capex", "sustainability_capex"],
}


# ── Apply Mapping ────────────────────────────────────────────────────────────

def apply_column_mapping(df: pd.DataFrame, mapping: dict, target_schema: str) -> pd.DataFrame:
    """Rename and reorder columns according to the confirmed mapping.

    Returns a new DataFrame conforming to the ESG schema.
    """
    schema = ESG_SCHEMAS.get(target_schema, {})
    if not schema:
        return df

    # Build rename dict: source_col -> esg_col
    rename = {}
    for esg_col, src_col in mapping.items():
        if src_col is not None and src_col in df.columns:
            rename[src_col] = esg_col

    result = df.rename(columns=rename)

    # Keep only schema columns (+ any extras that mapped)
    schema_cols = list(schema.keys())
    keep = [c for c in schema_cols if c in result.columns]
    result = result[keep].copy()

    # Coerce types
    for col in keep:
        col_type = schema[col]["type"]
        try:
            if col_type == "int":
                result[col] = pd.to_numeric(result[col], errors="coerce").astype("Int64")
            elif col_type == "float":
                result[col] = pd.to_numeric(result[col], errors="coerce")
            else:
                result[col] = result[col].astype(str)
        except (ValueError, TypeError):
            pass

    return result


# ── Validation ───────────────────────────────────────────────────────────────

def validate_mapped_data(df: pd.DataFrame, target_schema: str) -> dict:
    """Validate a mapped DataFrame against its target schema.

    Returns {"valid": bool, "errors": list, "warnings": list, "stats": dict}.
    """
    schema = ESG_SCHEMAS.get(target_schema, {})
    errors = []
    warnings = []

    # Check required columns present
    for col, spec in schema.items():
        if spec["required"] and col not in df.columns:
            errors.append(f"Missing required column: '{col}' — {spec['description']}")
        elif col in df.columns:
            null_pct = df[col].isna().sum() / len(df) * 100 if len(df) > 0 else 0
            if spec["required"] and null_pct > 20:
                warnings.append(f"Column '{col}' has {null_pct:.0f}% null values")
            if null_pct == 100:
                warnings.append(f"Column '{col}' is entirely null — check mapping")

    # Check row count
    if len(df) == 0:
        errors.append("Dataset is empty (0 rows)")
    elif len(df) < 5:
        warnings.append(f"Very small dataset ({len(df)} rows) — results may be unreliable")

    # Check for unexpected values in categorical columns
    if target_schema == "emissions" and "scope" in df.columns:
        valid_scopes = {"Scope 1", "Scope 2", "Scope 3"}
        actual = set(df["scope"].dropna().unique())
        bad = actual - valid_scopes
        if bad:
            warnings.append(f"Non-standard scope values: {bad}. Expected: {valid_scopes}")

    stats = {
        "rows": len(df),
        "columns_mapped": len([c for c in schema if c in df.columns]),
        "columns_total": len(schema),
        "completeness": round(df.notna().sum().sum() / df.size * 100, 1) if df.size > 0 else 0,
    }

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": stats,
    }


def get_schema_names() -> list[str]:
    """Return all available ESG schema names."""
    return list(ESG_SCHEMAS.keys())


def get_schema_columns(schema_name: str) -> list[str]:
    """Return column names for a schema."""
    return list(ESG_SCHEMAS.get(schema_name, {}).keys())

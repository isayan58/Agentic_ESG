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
        "annual_spend_inr_crores":      {"type": "float", "required": False, "description": "Annual spend with this supplier (INR crore)"},
        "scope3_category":              {"type": "str",   "required": False, "description": "GHG Protocol Scope 3 category 1-15 (e.g. 'Cat 1: Purchased Goods')"},
        "single_source_flag":           {"type": "str",   "required": False, "description": "Single-source dependency flag (Yes/No)"},
        "emission_factor_source":       {"type": "str",   "required": False, "description": "Source of emission factor (e.g. EcoInvent v3.10, DEFRA 2024, Supplier-reported)"},
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

    # ── Peer Benchmarking Schemas ─────────────────────────────────────────────
    # Multi-company datasets used for sector comparison and ESG-financial
    # correlation analysis.  These are optional — the core pipeline runs
    # without them.  Upload via Data Collector → File Upload.

    "peer_companies": {
        "company":    {"type": "str", "required": True,  "description": "Company name"},
        "sector":     {"type": "str", "required": True,  "description": "Industry sector (e.g. Power, Mining, PetroChemical)"},
        "company_no": {"type": "int", "required": False, "description": "Sequential company number within the dataset"},
    },
    "peer_financials": {
        "company":             {"type": "str",   "required": True,  "description": "Company name"},
        "year":                {"type": "int",   "required": True,  "description": "Fiscal year"},
        "revenue":             {"type": "float", "required": True,  "description": "Total revenue (INR crore)"},
        "net_profit":          {"type": "float", "required": True,  "description": "Net profit after tax (INR crore)"},
        "total_assets":        {"type": "float", "required": True,  "description": "Total assets on balance sheet (INR crore)"},
        "total_liabilities":   {"type": "float", "required": False, "description": "Total liabilities (INR crore)"},
        "current_assets":      {"type": "float", "required": False, "description": "Short-term assets (INR crore)"},
        "current_liabilities": {"type": "float", "required": False, "description": "Short-term obligations (INR crore)"},
        "ppe_net":             {"type": "float", "required": False, "description": "Net property, plant & equipment (INR crore)"},
        "capex":               {"type": "float", "required": False, "description": "Capital expenditures (INR crore)"},
        "depreciation":        {"type": "float", "required": False, "description": "Depreciation and amortisation (INR crore)"},
        "interest_expense":    {"type": "float", "required": False, "description": "Interest paid on debt (INR crore)"},
        "ebitda":              {"type": "float", "required": False, "description": "EBITDA (INR crore)"},
        "operating_cash_flow": {"type": "float", "required": False, "description": "Net cash from operations (INR crore)"},
        "net_debt":            {"type": "float", "required": False, "description": "Total debt minus cash (INR crore)"},
        "goodwill":            {"type": "float", "required": False, "description": "Goodwill from acquisitions (INR crore)"},
        "intangibles":         {"type": "float", "required": False, "description": "Intangible assets (INR crore)"},
    },
    "peer_esg": {
        "company":                  {"type": "str",   "required": True,  "description": "Company name"},
        "year":                     {"type": "int",   "required": True,  "description": "Fiscal year"},
        "esg_capex":                {"type": "float", "required": True,  "description": "ESG-linked CapEx (INR crore)"},
        "green_assets":             {"type": "float", "required": True,  "description": "Green / sustainable asset value (INR crore)"},
        "scope1_emissions_tco2e":   {"type": "float", "required": True,  "description": "Scope 1 direct emissions (tCO2e)"},
        "scope2_emissions_tco2e":   {"type": "float", "required": True,  "description": "Scope 2 indirect emissions from energy (tCO2e)"},
        "esg_score":                {"type": "float", "required": True,  "description": "Composite ESG score (0-100)"},
        "sustainability_projects":  {"type": "int",   "required": False, "description": "Number of active sustainability initiatives"},
    },
    "peer_metrics": {
        "company":             {"type": "str",   "required": True,  "description": "Company name"},
        "year":                {"type": "int",   "required": True,  "description": "Fiscal year"},
        "roa":                 {"type": "float", "required": True,  "description": "Return on assets (Net Profit / Total Assets)"},
        "asset_turnover":      {"type": "float", "required": False, "description": "Revenue / Total Assets"},
        "working_capital":     {"type": "float", "required": False, "description": "Current Assets - Current Liabilities (INR crore)"},
        "working_cap_turnover":{"type": "float", "required": False, "description": "Revenue / Working Capital"},
        "net_debt_to_ebitda":  {"type": "float", "required": False, "description": "Net Debt / EBITDA (leverage ratio)"},
        "interest_coverage":   {"type": "float", "required": False, "description": "EBITDA / Interest Expense"},
        "fcf":                 {"type": "float", "required": False, "description": "Free Cash Flow = Operating CF - CapEx (INR crore)"},
        "ebitda_margin":       {"type": "float", "required": True,  "description": "EBITDA / Revenue (percentage)"},
        "esg_capex_pct":       {"type": "float", "required": True,  "description": "ESG CapEx / Total CapEx (decimal or percentage)"},
        "green_assets_pct":    {"type": "float", "required": False, "description": "Green Assets / Total Assets (decimal or percentage)"},
        "scope1_2_emissions":  {"type": "float", "required": False, "description": "Combined Scope 1+2 emissions (tCO2e)"},
        "esg_score":           {"type": "float", "required": True,  "description": "Composite ESG score (0-100)"},
    },
    "peer_benchmark": {
        "company":              {"type": "str",   "required": True,  "description": "Company name"},
        "sector":               {"type": "str",   "required": False, "description": "Industry sector"},
        "roa_avg":              {"type": "float", "required": True,  "description": "5-year average ROA"},
        "asset_turnover_avg":   {"type": "float", "required": False, "description": "5-year average asset turnover"},
        "net_debt_ebitda_avg":  {"type": "float", "required": False, "description": "5-year average Net Debt/EBITDA"},
        "fcf_avg":              {"type": "float", "required": False, "description": "5-year average free cash flow (INR crore)"},
        "ebitda_margin_avg":    {"type": "float", "required": True,  "description": "5-year average EBITDA margin"},
        "esg_capex_pct_avg":    {"type": "float", "required": True,  "description": "5-year average ESG CapEx %"},
        "green_assets_pct_avg": {"type": "float", "required": False, "description": "5-year average green assets %"},
        "esg_score_avg":        {"type": "float", "required": True,  "description": "5-year average ESG score (0-100)"},
    },

    # ── Regulatory & Risk Schemas ─────────────────────────────────────────────
    # Closes specific gaps flagged by the Audit Agent and Regulatory Tracker:
    # CSRD Double Materiality, SOX/ICFR coverage, SEC climate financial impact,
    # ERM climate risk register, and CSRD-E3 Pollution Prevention.

    "materiality_assessment": {
        "topic_id":                     {"type": "str",   "required": True,  "description": "Unique topic identifier (e.g. M01, CLIMATE)"},
        "topic_name":                   {"type": "str",   "required": True,  "description": "Material topic name"},
        "esg_pillar":                   {"type": "str",   "required": False, "description": "Pillar (Environmental, Social, Governance)"},
        "impact_materiality_score":     {"type": "float", "required": True,  "description": "Inside-out impact score (0-10)"},
        "financial_materiality_score":  {"type": "float", "required": True,  "description": "Outside-in financial materiality score (0-10)"},
        "stakeholder_group":            {"type": "str",   "required": True,  "description": "Primary stakeholder group affected"},
        "time_horizon":                 {"type": "str",   "required": True,  "description": "Time horizon (Short, Medium, Long)"},
        "assessment_date":              {"type": "str",   "required": True,  "description": "Assessment date (YYYY-MM-DD)"},
        "evidence_link":                {"type": "str",   "required": False, "description": "Link or reference to evidence"},
        "owner":                        {"type": "str",   "required": False, "description": "Topic owner (function or individual)"},
        "decision":                     {"type": "str",   "required": False, "description": "Outcome (Material, Not Material, Watch)"},
        "framework_alignment":          {"type": "str",   "required": False, "description": "Aligned framework (CSRD-DM, BRSR-S4, GRI-3)"},
    },
    "icfr_controls": {
        "control_id":                   {"type": "str",   "required": True,  "description": "Unique control identifier (e.g. ICFR-ESG-001)"},
        "process":                      {"type": "str",   "required": True,  "description": "Business process the control covers"},
        "esg_metric_linked":            {"type": "str",   "required": False, "description": "ESG metric ID linked to this control"},
        "control_owner":                {"type": "str",   "required": True,  "description": "Control owner (function or individual)"},
        "test_date":                    {"type": "str",   "required": True,  "description": "Last test date (YYYY-MM-DD)"},
        "deficiency_flag":              {"type": "str",   "required": False, "description": "Deficiency flag (None, Significant, Material)"},
        "remediation_status":           {"type": "str",   "required": False, "description": "Remediation status"},
        "sox_section":                  {"type": "str",   "required": False, "description": "SOX section (302, 404, 906)"},
        "control_type":                 {"type": "str",   "required": False, "description": "Type (Preventive, Detective, Corrective)"},
        "frequency":                    {"type": "str",   "required": False, "description": "Frequency (Daily, Monthly, Quarterly, Annual)"},
        "tester":                       {"type": "str",   "required": False, "description": "Independent tester (Internal Audit / external)"},
    },
    "climate_financial_impacts": {
        "fiscal_period":                {"type": "str",   "required": True,  "description": "Fiscal period (e.g. FY2024-Q3)"},
        "event_type":                   {"type": "str",   "required": True,  "description": "Event type (Acute, Chronic, Transition)"},
        "capex_climate":                {"type": "float", "required": True,  "description": "Climate-related CapEx (INR crore)"},
        "opex_climate":                 {"type": "float", "required": True,  "description": "Climate-related OpEx (INR crore)"},
        "impairment_amount":            {"type": "float", "required": False, "description": "Impairment recorded (INR crore)"},
        "insurance_recovery":           {"type": "float", "required": False, "description": "Insurance recovery (INR crore)"},
        "affected_asset_id":            {"type": "str",   "required": False, "description": "Affected asset / facility id"},
        "gl_account":                   {"type": "str",   "required": False, "description": "General-ledger account code"},
        "scenario_tag":                 {"type": "str",   "required": False, "description": "Scenario tag (e.g. NGFS-NetZero2050, IEA-STEPS)"},
        "description":                  {"type": "str",   "required": False, "description": "Free-text event description"},
    },
    "climate_risk_register": {
        "risk_id":                      {"type": "str",   "required": True,  "description": "Unique risk identifier (e.g. CR-001)"},
        "category":                     {"type": "str",   "required": True,  "description": "Category (Physical-Acute, Physical-Chronic, Transition-Policy, Transition-Tech, Transition-Market)"},
        "scenario":                     {"type": "str",   "required": True,  "description": "Scenario (e.g. NGFS-NetZero, IEA-STEPS, RCP8.5)"},
        "time_horizon":                 {"type": "str",   "required": True,  "description": "Time horizon (Short, Medium, Long)"},
        "likelihood":                   {"type": "str",   "required": True,  "description": "Likelihood (Rare, Possible, Likely, Almost Certain)"},
        "financial_impact_inr_crores":  {"type": "float", "required": True,  "description": "Estimated financial impact (INR crore)"},
        "mitigation":                   {"type": "str",   "required": False, "description": "Mitigation action(s)"},
        "status":                       {"type": "str",   "required": False, "description": "Risk status (Open, Mitigating, Closed)"},
        "owner":                        {"type": "str",   "required": False, "description": "Risk owner"},
        "affected_business_unit":       {"type": "str",   "required": False, "description": "Affected business unit / facility"},
    },
    "pollution": {
        "year":                         {"type": "int",   "required": True,  "description": "Reporting year"},
        "quarter":                      {"type": "str",   "required": True,  "description": "Quarter (Q1-Q4)"},
        "emission_medium":              {"type": "str",   "required": True,  "description": "Medium (Air, Water, Land)"},
        "pollutant_type":               {"type": "str",   "required": True,  "description": "Pollutant (NOx, SOx, PM2.5, COD, BOD, etc.)"},
        "quantity_kg":                  {"type": "float", "required": True,  "description": "Quantity released (kg)"},
        "location":                     {"type": "str",   "required": False, "description": "Facility location"},
        "regulatory_limit_kg":          {"type": "float", "required": False, "description": "Permitted regulatory limit (kg)"},
        "monitoring_method":            {"type": "str",   "required": False, "description": "Monitoring method (CEMS, manual sampling, etc.)"},
        "discharge_point":              {"type": "str",   "required": False, "description": "Discharge / emission point id"},
        "exceedance_flag":              {"type": "str",   "required": False, "description": "Whether limit was exceeded (Yes/No)"},
    },
}

# Indicator columns used for auto-detection — columns strongly associated
# with each schema.
_SCHEMA_INDICATORS = {
    # Core single-company schemas
    "emissions":    ["emissions_tco2e", "scope", "tco2e", "ghg", "co2"],
    "esg_metrics":  ["pillar", "metric_id", "metric_name", "esg"],
    "supply_chain": ["supplier_id", "supplier_name", "risk_rating", "supplier"],
    "energy":       ["energy_source", "consumption_mwh", "renewable", "mwh"],
    "waste":        ["waste_type", "disposal_method", "recycled_pct", "quantity_mt"],
    "diversity":    ["subcategory", "diversity", "gender", "workforce"],
    "financials":   ["revenue_inr_crores", "ebitda_margin_pct", "roa_pct", "roe_pct", "esglinkedcapex", "costofcapital"],
    # Peer benchmarking schemas — detected after core schemas
    "peer_companies":  ["company_no", "sector"],
    "peer_financials": ["net_profit", "total_liabilities", "current_liabilities", "ppe_net"],
    "peer_esg":        ["scope1_emissions_tco2e", "green_assets", "scope2_emissions_tco2e"],
    "peer_metrics":    ["roa", "asset_turnover", "esg_capex_pct", "net_debt_to_ebitda"],
    "peer_benchmark":  ["roa_avg", "esg_score_avg", "esg_capex_pct_avg"],
    # Regulatory & risk schemas
    "materiality_assessment":   ["impact_materiality_score", "financial_materiality_score", "topic_id"],
    "icfr_controls":            ["control_id", "deficiency_flag", "sox_section"],
    "climate_financial_impacts":["capex_climate", "opex_climate", "fiscal_period"],
    "climate_risk_register":    ["risk_id", "scenario", "financial_impact_inr_crores"],
    "pollution":                ["pollutant_type", "emission_medium", "quantity_kg"],
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
    # peer_financials aliases (Excel dashboard column names)
    "net_profit":          ["Net_Profit", "net profit", "profit"],
    "total_assets":        ["Total_Assets", "total assets", "assets"],
    "total_liabilities":   ["Total_Liabilities", "total liabilities", "liabilities"],
    "current_assets":      ["Current_Assets", "current assets"],
    "current_liabilities": ["Current_Liabilities", "current liabilities"],
    "ppe_net":             ["PPE(Net PPE)", "net_ppe", "ppe"],
    "operating_cash_flow": ["Operating_Cash_Flow", "operating cashflow", "cfo"],
    "net_debt":            ["Net_Debt", "net debt"],
    "interest_expense":    ["Interest_Expense", "interest"],
    "depreciation":        ["Depreciation", "d&a", "da"],
    # peer_esg aliases
    "scope1_emissions_tco2e": ["Scope1_Emissions_tCO2e", "scope1_emissions"],
    "scope2_emissions_tco2e": ["Scope2_Emissions_tCO2e", "scope2_emissions"],
    "esg_capex":              ["ESG_CapEx", "esg capex"],
    "green_assets":           ["Green_Assets", "green assets", "sustainable_assets"],
    "sustainability_projects": ["Number_of_Sustainability_Projects", "sustainability projects"],
    # peer_metrics aliases
    "asset_turnover":      ["Asset_Turnover (Revenue/TotalAssets)", "asset_turnover_ratio"],
    "working_capital":     ["Working_Capital (CurrentAssets-CurrentLiabilities)", "net_working_capital"],
    "working_cap_turnover":["Working_Cap_Turnover (Revenue/WorkingCapital)", "wc_turnover"],
    "net_debt_to_ebitda":  ["Net_Debt/EBITDA", "net_debt_ebitda"],
    "interest_coverage":   ["Interest_Coverage (EBITDA/InterestExpense)", "icr"],
    "ebitda_margin":       ["EBITDA_Margin (EBITDA/Revenue)", "ebitda margin", "operating_margin"],
    "esg_capex_pct":       ["ESG_CapEx_pct (ESG_CapEx/CapEx)", "esg_capex_ratio"],
    "green_assets_pct":    ["Green_Assets_pct (Green_Assets/TotalAssets)", "green_asset_ratio"],
    "scope1_2_emissions":  ["Scope1+2_Emissions", "scope12"],
    # peer_benchmark aliases
    "roa_avg":             ["ROA (avg 5yr)", "roa_5yr", "avg_roa"],
    "asset_turnover_avg":  ["Asset_Turnover (avg 5yr)", "avg_asset_turnover"],
    "net_debt_ebitda_avg": ["Net_Debt/EBITDA (avg 5yr)", "avg_net_debt_ebitda"],
    "fcf_avg":             ["FCF (avg 5yr)", "avg_fcf"],
    "ebitda_margin_avg":   ["EBITDA_Margin (avg 5yr)", "avg_ebitda_margin"],
    "esg_capex_pct_avg":   ["ESG_CapEx_pct (avg 5yr)", "avg_esg_capex_pct"],
    "green_assets_pct_avg":["Green_Assets_pct (avg 5yr)", "avg_green_assets_pct"],
    "esg_score_avg":       ["ESG_Score (avg 5yr)", "avg_esg_score"],
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

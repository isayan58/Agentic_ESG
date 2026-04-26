# ESG Pilot — Schema Reference

This document is the canonical reference for preparing data files to upload into ESG Pilot. It covers every supported schema, the auto-detection logic, how column names are matched, the correct upload workflow, and known column synonyms. Hand this document to your data team when preparing files for the platform.

---

## Table of Contents

**Core schemas (your company's data):**

1. [Schema: emissions](#schema-emissions)
2. [Schema: esg_metrics](#schema-esg_metrics)
3. [Schema: supply_chain](#schema-supply_chain)
4. [Schema: energy](#schema-energy)
5. [Schema: waste](#schema-waste)
6. [Schema: diversity](#schema-diversity)
7. [Schema: financials](#schema-financials)

**Peer benchmarking schemas (multi-company comparison data):**

8. [Schema: peer_companies](#schema-peer_companies)
9. [Schema: peer_financials](#schema-peer_financials)
10. [Schema: peer_esg](#schema-peer_esg)
11. [Schema: peer_metrics](#schema-peer_metrics)
12. [Schema: peer_benchmark](#schema-peer_benchmark)

**Reference:**

13. [Auto-Detection](#auto-detection)
14. [Column Mapping](#column-mapping)
15. [Column Synonyms](#column-synonyms)
16. [Correct Upload Workflow](#correct-upload-workflow)
17. [Session Storage Note](#session-storage-note)

---

## Schema: `emissions`

**Use case:** Scope 1, 2, and 3 greenhouse gas emissions reporting. Powers the Carbon Accountant agent, carbon intensity calculations, and YoY trend analysis.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `year` | int | Required | Reporting year | `2024` |
| `quarter` | str | Required | Quarter | `Q2` |
| `scope` | str | Required | Emission scope | `Scope 1` |
| `category` | str | Required | Emission category | `Fleet Vehicles` |
| `emissions_tco2e` | float | Required | Emissions in tonnes CO2 equivalent | `142.5` |
| `unit` | str | Optional | Unit of measurement (default: tCO2e) | `tCO2e` |
| `source` | str | Optional | Data source | `Fuel logs` |
| `confidence` | float | Optional | Confidence score 0–1 | `0.92` |

---

## Schema: `esg_metrics`

**Use case:** ESG KPI tracking across Environmental, Social, and Governance pillars. Used by the Regulatory Tracker, Audit Agent, and Report Generator.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `metric_id` | str | Required | Unique metric identifier | `E01` |
| `pillar` | str | Required | ESG pillar | `Environmental` |
| `category` | str | Required | Metric category | `Climate` |
| `metric_name` | str | Required | Human-readable metric name | `Total GHG Emissions` |
| `unit` | str | Optional | Unit of measurement | `tCO2e` |
| `value_2023` | float | Optional | Value for 2023 | `8450.0` |
| `value_2024` | float | Optional | Value for 2024 | `7920.0` |
| `target_2024` | float | Optional | Target value for 2024 | `8000.0` |
| `status` | str | Optional | Target achievement status | `Met` |
| `data_source` | str | Optional | Data source description | `ERP emissions module` |
| `confidence` | float | Optional | Confidence score 0–1 | `0.88` |

Valid values for `status`: `Met`, `Not Met`, `On Track`.

---

## Schema: `supply_chain`

**Use case:** Supplier ESG risk profiling, Scope 3 hotspot detection, and supply chain audit tracking.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `supplier_id` | str | Required | Unique supplier identifier | `SUP-042` |
| `supplier_name` | str | Required | Supplier company name | `Apex Components Ltd` |
| `country` | str | Required | Country of operation | `India` |
| `sector` | str | Optional | Industry sector | `Manufacturing` |
| `tier` | str | Optional | Supply chain tier | `Tier 1` |
| `esg_score` | float | Optional | ESG score (0–100) | `62.5` |
| `risk_rating` | str | Optional | Risk rating | `High` |
| `emission_contribution_tco2e` | float | Optional | Emission contribution in tCO2e | `340.0` |
| `audit_status` | str | Optional | Audit status | `Overdue` |
| `last_audit_date` | str | Optional | Last audit date (YYYY-MM-DD) | `2023-11-15` |
| `key_risk_factors` | str | Optional | Key risk factors (comma-separated) | `Labor practices, Waste disposal` |

Valid values for `risk_rating`: `Low`, `Medium`, `High`, `Critical`.
Valid values for `tier`: `Tier 1`, `Tier 2`, `Tier 3`.

---

## Schema: `energy`

**Use case:** Energy consumption tracking by source and facility. Used in renewable energy percentage calculations, energy cost analysis, and carbon intensity reporting.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `year` | int | Required | Reporting year | `2024` |
| `quarter` | str | Required | Quarter (Q1–Q4) | `Q3` |
| `energy_source` | str | Required | Energy source | `Solar` |
| `consumption_mwh` | float | Required | Energy consumption in MWh | `215.8` |
| `cost_inr_lakhs` | float | Optional | Cost in INR lakhs | `18.4` |
| `location` | str | Optional | Facility location | `Pune Plant` |
| `renewable` | str | Optional | Is renewable? | `Yes` |

Valid values for `renewable`: `Yes`, `No`.

---

## Schema: `waste`

**Use case:** Waste generation, classification, and disposal method tracking. Used in GRI 306 and BRSR waste reporting.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `year` | int | Required | Reporting year | `2024` |
| `quarter` | str | Required | Quarter (Q1–Q4) | `Q1` |
| `waste_type` | str | Required | Waste type | `Non-Hazardous` |
| `category` | str | Required | Waste category | `Paper` |
| `quantity_mt` | float | Required | Quantity in metric tonnes | `4.2` |
| `disposal_method` | str | Optional | Disposal method | `Recycling` |
| `recycled_pct` | float | Optional | Recycled percentage (0–100) | `78.0` |
| `location` | str | Optional | Facility location | `Chennai Office` |

Valid values for `waste_type`: `Hazardous`, `Non-Hazardous`.

---

## Schema: `diversity`

**Use case:** Workforce diversity and representation metrics. Used in BRSR Principal 5, CSRD S1, and GRI 405 reporting.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `year` | int | Required | Reporting year | `2024` |
| `category` | str | Required | Diversity category | `Gender` |
| `subcategory` | str | Required | Subcategory | `Leadership` |
| `metric` | str | Required | Metric name | `Female representation %` |

---

## Schema: `financials`

**Use case:** Financial performance and ESG-linked investment data. Drives the KPI Engine, ESG ROI Agent, J-curve modeling, and carbon tax exposure estimates.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `year` | int | Required | Reporting year | `2024` |
| `quarter` | str | Required | Quarter (Q1–Q4) | `Q2` |
| `revenue_inr_crores` | float | Required | Revenue in INR crores | `462.0` |
| `ebitda_inr_crores` | float | Optional | EBITDA in INR crores | `115.5` |
| `ebitda_margin_pct` | float | Optional | EBITDA margin percentage | `25.0` |
| `pat_inr_crores` | float | Optional | Profit after tax in INR crores | `78.2` |
| `roa_pct` | float | Optional | Return on assets percentage | `11.4` |
| `roe_pct` | float | Optional | Return on equity percentage | `18.6` |
| `debt_equity_ratio` | float | Optional | Debt to equity ratio | `0.42` |
| `cost_of_capital_pct` | float | Optional | Cost of capital percentage | `9.8` |
| `pe_ratio` | float | Optional | Price to earnings ratio | `22.1` |
| `carbon_tax_exposure_lakhs` | float | Optional | Carbon tax exposure in INR lakhs | `34.5` |
| `energy_cost_inr_crores` | float | Optional | Energy cost in INR crores | `12.3` |
| `employee_turnover_pct` | float | Optional | Employee turnover percentage | `14.2` |
| `brand_value_index` | float | Optional | Brand value index | `72.0` |
| `talent_retention_score` | float | Optional | Talent retention score | `81.0` |
| `esg_linked_capex_inr_crores` | float | Optional | ESG-linked CapEx in INR crores | `28.7` |

---

## Peer Benchmarking Schemas

The four schemas below come from the multi-company ESG financial dashboard format (`esg_financial_dashboard_15_companies.xlsx`). Together they power peer comparison, sector benchmarking, ESG-to-financial correlation analysis, and multi-company risk profiling in the ESG Pilot platform.

All four sheets follow the same company × year panel structure — 15 companies across FY2020–FY2024 is the reference dataset, but any number of companies and years is supported.

> **How these differ from core schemas:** Core schemas (`emissions`, `financials`, etc.) describe *your* company's data. Peer schemas describe *multiple* companies and are used for benchmarking and comparison — not for your own compliance or reporting calculations.

---

## Schema: `peer_companies`

**Use case:** Master list of companies included in the benchmarking dataset. Provides the company-to-sector mapping used to group peer comparisons. Corresponds to the `Companies` sheet.

**Source files:** `esg_financial_dashboard_15_companies.xlsx` → sheet `Companies`

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `company_no` | int | Optional | Sequential company number within the dataset | `6` |
| `company` | str | Required | Full company name | `NTPC` |
| `sector` | str | Required | Industry sector for peer grouping | `Power` |

**Valid sector values (reference dataset):** `PetroChemical`, `Power`, `Mining`

**Sample rows:**

| company_no | company | sector |
|---|---|---|
| 1 | Reliance Industries | PetroChemical |
| 6 | NTPC | Power |
| 11 | Hindustan Zinc | Mining |
| 13 | Coal India | Mining |

---

## Schema: `peer_financials`

**Use case:** Raw financial statements for all peer companies — P&L, balance sheet, and cash flow line items per company per year. Used for financial benchmarking, leverage analysis, CapEx comparison, and ESG-to-financial correlation modelling. Corresponds to the `Raw_Financials` sheet in the dashboard workbook, and is also the sole content of the standalone `financials_filled_complete.xlsx` file.

**Source files:**
- `esg_financial_dashboard_15_companies.xlsx` → sheet `Raw_Financials`
- `financials_filled_complete.xlsx` → sheet `Sheet1` *(identical data)*

> All monetary values are in **INR crore** unless your dataset uses a different currency — ensure consistency across all rows.

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `company` | str | Required | Company name (must match `peer_companies.company`) | `Tata Steel` |
| `year` | int | Required | Fiscal year | `2024` |
| `revenue` | float | Required | Total revenue | `55,377` |
| `net_profit` | float | Required | Net profit after tax | `5,364` |
| `total_assets` | float | Required | Total assets on balance sheet | `84,757` |
| `total_liabilities` | float | Required | Total liabilities | `61,203` |
| `current_assets` | float | Optional | Short-term assets (cash, receivables, inventory) | `18,450` |
| `current_liabilities` | float | Optional | Short-term obligations due within one year | `14,820` |
| `ppe_net` | float | Optional | Net property, plant & equipment (after depreciation) | `42,100` |
| `capex` | float | Optional | Capital expenditures during the period | `5,976` |
| `depreciation` | float | Optional | Depreciation and amortisation charge | `3,210` |
| `interest_expense` | float | Optional | Interest paid on debt obligations | `1,840` |
| `ebitda` | float | Optional | Earnings before interest, tax, depreciation & amortisation | `12,440` |
| `operating_cash_flow` | float | Optional | Net cash generated from operating activities | `9,870` |
| `net_debt` | float | Optional | Total debt minus cash and cash equivalents | `15,200` |
| `goodwill` | float | Optional | Goodwill from acquisitions on the balance sheet | `2,100` |
| `intangibles` | float | Optional | Intangible assets (patents, licences, etc.) | `980` |

**Column name aliases accepted by the platform:**

| Alias | Maps to |
|-------|---------|
| `Company` | `company` |
| `Year` | `year` |
| `Revenue` | `revenue` |
| `Net_Profit` | `net_profit` |
| `Total_Assets` | `total_assets` |
| `Total_Liabilities` | `total_liabilities` |
| `Current_Assets` | `current_assets` |
| `Current_Liabilities` | `current_liabilities` |
| `PPE(Net PPE)` | `ppe_net` |
| `CapEx` | `capex` |
| `Depreciation` | `depreciation` |
| `Interest_Expense` | `interest_expense` |
| `EBITDA` | `ebitda` |
| `Operating_Cash_Flow` | `operating_cash_flow` |
| `Net_Debt` | `net_debt` |
| `Goodwill` | `goodwill` |
| `Intangibles` | `intangibles` |

---

## Schema: `peer_esg`

**Use case:** ESG-specific inputs for all peer companies — emissions, green asset value, ESG CapEx, ESG score, and sustainability project count per company per year. Powers sector-level emissions benchmarking, ESG score trajectory comparison, and ESG investment intensity analysis. Corresponds to the `Raw_ESG` sheet.

**Source files:** `esg_financial_dashboard_15_companies.xlsx` → sheet `Raw_ESG`

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `company` | str | Required | Company name (must match `peer_companies.company`) | `Adani Green` |
| `year` | int | Required | Fiscal year | `2023` |
| `esg_capex` | float | Required | CapEx allocated to ESG / sustainability activities (INR crore) | `5,493` |
| `green_assets` | float | Required | Book value of green or sustainable assets (INR crore) | `17,169` |
| `scope1_emissions_tco2e` | float | Required | Direct (Scope 1) GHG emissions in tonnes CO2 equivalent | `98,945` |
| `scope2_emissions_tco2e` | float | Required | Indirect (Scope 2) GHG emissions from purchased energy (tCO2e) | `69,602` |
| `esg_score` | float | Required | Composite ESG score — scale is 0–100; higher is better | `71.87` |
| `sustainability_projects` | int | Optional | Number of active sustainability initiatives during the period | `10` |

**Column name aliases accepted by the platform:**

| Alias | Maps to |
|-------|---------|
| `Company` | `company` |
| `Year` | `year` |
| `ESG_CapEx` | `esg_capex` |
| `Green_Assets` | `green_assets` |
| `Scope1_Emissions_tCO2e` | `scope1_emissions_tco2e` |
| `Scope2_Emissions_tCO2e` | `scope2_emissions_tco2e` |
| `ESG_Score` | `esg_score` |
| `Number_of_Sustainability_Projects` | `sustainability_projects` |

**Notes on ESG score scale:** The reference dataset uses a composite score where ~40 is low performance and ~90 is sector-leading. If you source ESG scores from a third-party rating provider (MSCI, Sustainalytics, CDP), normalise to 0–100 before uploading.

---

## Schema: `peer_metrics`

**Use case:** Pre-calculated financial and ESG ratios per company per year — profitability, leverage, liquidity, free cash flow, and ESG intensity metrics. This schema is derived from `peer_financials` + `peer_esg` but can be uploaded directly if your source already contains calculated ratios. Powers peer ranking tables, sector heatmaps, and ESG-to-financial correlation charts. Corresponds to the `Calculated_Metrics` sheet.

**Source files:** `esg_financial_dashboard_15_companies.xlsx` → sheet `Calculated_Metrics`

| Column | Type | Required | Description | Formula | Example Value |
|--------|------|----------|-------------|---------|---------------|
| `company` | str | Required | Company name | — | `Indian Oil` |
| `year` | int | Required | Fiscal year | — | `2022` |
| `roa` | float | Required | Return on assets — net profitability relative to total asset base | `Net_Profit / Total_Assets` | `0.0419` (4.19%) |
| `asset_turnover` | float | Required | Revenue generated per unit of assets — operational efficiency | `Revenue / Total_Assets` | `0.22` |
| `working_capital` | float | Optional | Short-term liquidity buffer | `Current_Assets − Current_Liabilities` | `3,630` |
| `working_cap_turnover` | float | Optional | Revenue generated per unit of working capital | `Revenue / Working_Capital` | `12.1` |
| `net_debt_to_ebitda` | float | Optional | Financial leverage — how many years of EBITDA needed to repay net debt | `Net_Debt / EBITDA` | `1.97` |
| `interest_coverage` | float | Optional | Debt servicing capacity — how comfortably EBITDA covers interest | `EBITDA / Interest_Expense` | `5.66` |
| `fcf` | float | Optional | Free cash flow — cash available after sustaining capex | `Operating_Cash_Flow − CapEx` | `3,894` |
| `ebitda_margin` | float | Required | Core operating profitability as a fraction of revenue | `EBITDA / Revenue` | `0.225` (22.5%) |
| `esg_capex_pct` | float | Required | ESG investment intensity — share of total CapEx directed to sustainability | `ESG_CapEx / CapEx` | `0.916` (91.6%) |
| `green_assets_pct` | float | Optional | Green balance sheet intensity — share of total assets classified as sustainable | `Green_Assets / Total_Assets` | `0.133` (13.3%) |
| `scope1_2_emissions` | float | Required | Combined direct + indirect GHG footprint (tCO2e) | `Scope1 + Scope2` | `168,025` |
| `esg_score` | float | Required | Composite ESG score (0–100) | — (carried from `peer_esg`) | `66.57` |

**Column name aliases accepted by the platform:**

| Alias | Maps to |
|-------|---------|
| `Company` | `company` |
| `Year` | `year` |
| `ROA (NetProfit/TotalAssets)` | `roa` |
| `Asset_Turnover (Revenue/TotalAssets)` | `asset_turnover` |
| `Working_Capital (CurrentAssets-CurrentLiabilities)` | `working_capital` |
| `Working_Cap_Turnover (Revenue/WorkingCapital)` | `working_cap_turnover` |
| `Net_Debt/EBITDA` | `net_debt_to_ebitda` |
| `Interest_Coverage (EBITDA/InterestExpense)` | `interest_coverage` |
| `FCF (OperatingCashFlow - CapEx)` | `fcf` |
| `EBITDA_Margin (EBITDA/Revenue)` | `ebitda_margin` |
| `ESG_CapEx_pct (ESG_CapEx/CapEx)` | `esg_capex_pct` |
| `Green_Assets_pct (Green_Assets/TotalAssets)` | `green_assets_pct` |
| `Scope1+2_Emissions` | `scope1_2_emissions` |
| `ESG_Score` | `esg_score` |

---

## Schema: `peer_benchmark`

**Use case:** One-row-per-company 5-year average summary — a compressed view for at-a-glance peer ranking and dashboard tiles. Corresponds to the `Dashboard` sheet. Use this schema when you want to upload a pre-aggregated comparison table rather than the full year-by-year panel.

**Source files:** `esg_financial_dashboard_15_companies.xlsx` → sheet `Dashboard`

| Column | Type | Required | Description | Example Value |
|--------|------|----------|-------------|---------------|
| `company` | str | Required | Company name | `Hindustan Zinc` |
| `sector` | str | Optional | Industry sector | `Mining` |
| `roa_avg` | float | Required | 5-year average return on assets | `0.0724` (7.24%) |
| `asset_turnover_avg` | float | Optional | 5-year average asset turnover | `0.51` |
| `net_debt_ebitda_avg` | float | Optional | 5-year average leverage ratio | `3.08` |
| `fcf_avg` | float | Optional | 5-year average free cash flow (INR crore) | `4,210` |
| `ebitda_margin_avg` | float | Optional | 5-year average EBITDA margin | `0.286` (28.6%) |
| `esg_capex_pct_avg` | float | Required | 5-year average ESG CapEx as % of total CapEx | `0.342` (34.2%) |
| `green_assets_pct_avg` | float | Optional | 5-year average green assets as % of total assets | `0.118` (11.8%) |
| `esg_score_avg` | float | Required | 5-year average ESG score (0–100) | `63.9` |

**Column name aliases accepted by the platform:**

| Alias | Maps to |
|-------|---------|
| `Company` | `company` |
| `ROA (avg 5yr)` | `roa_avg` |
| `Asset_Turnover (avg 5yr)` | `asset_turnover_avg` |
| `Net_Debt/EBITDA (avg 5yr)` | `net_debt_ebitda_avg` |
| `FCF (avg 5yr)` | `fcf_avg` |
| `EBITDA_Margin (avg 5yr)` | `ebitda_margin_avg` |
| `ESG_CapEx_pct (avg 5yr)` | `esg_capex_pct_avg` |
| `Green_Assets_pct (avg 5yr)` | `green_assets_pct_avg` |
| `ESG_Score (avg 5yr)` | `esg_score_avg` |

---

## Auto-Detection

When you upload a file, ESG Pilot automatically detects which schema it matches by scanning for indicator columns. The table below shows which column(s) trigger each schema.

**Core schemas (single-company data):**

| If the file contains... | Schema detected |
|------------------------|----------------|
| `emissions_tco2e` | `emissions` |
| `metric_id` | `esg_metrics` |
| `supplier_name` or `esg_score` | `supply_chain` |
| `consumption_mwh` or `energy_source` | `energy` |
| `quantity_mt` or `waste_type` | `waste` |
| `subcategory` (with diversity category values) | `diversity` |
| `revenue_inr_crores` or `esg_linked_capex` | `financials` |

**Peer benchmarking schemas (multi-company data):**

| If the file contains... | Schema detected |
|------------------------|----------------|
| `company` + `sector` (no financial or ESG columns) | `peer_companies` |
| `company` + `revenue` + `ebitda` (without ESG columns) | `peer_financials` |
| `company` + `scope1_emissions_tco2e` or `esg_capex` | `peer_esg` |
| `company` + `roa` + `esg_capex_pct` | `peer_metrics` |
| `company` + `roa_avg` or `esg_score_avg` | `peer_benchmark` |

The peer schemas are detected after core schemas. If a file contains both `emissions_tco2e` (core indicator) and `company` + `esg_capex`, the core schema wins — split the data into separate files if needed.

If no indicator matches, detection returns no schema and the file cannot be auto-registered. In that case, rename the key columns to match one of the indicator names above, or use the manual schema selection option.

Only one schema is matched per file. If your data spans multiple schemas (e.g. a combined emissions + energy file), split it into separate files before uploading.

---

## Column Mapping

After schema detection, ESG Pilot attempts to map every column in your file to the corresponding column in the detected schema. Three matching strategies are tried in order:

### Step 1: Exact match

The column name in your file matches the schema column name exactly, character-for-character. This is the most reliable approach. If possible, name your columns to match the schema definitions in this document.

### Step 2: Normalized match

Both column names are lowercased and all underscores and whitespace are stripped before comparing. This tolerates common formatting differences:

| Your column name | Normalizes to | Matches schema column |
|-----------------|--------------|----------------------|
| `Emissions tCO2e` | `emissionstco2e` | `emissions_tco2e` |
| `SupplierName` | `suppliername` | `supplier_name` |
| `ESG Score` | `esgscore` | `esg_score` |

### Step 3: Synonym match

If exact and normalized matching both fail, the column name is checked against a synonym dictionary. See the [Column Synonyms](#column-synonyms) section below for the full list.

---

## Column Synonyms

The following alternative column names are automatically mapped to the canonical schema column. Use these if your internal naming convention differs from the ESG Pilot schema.

| Your column name | Maps to schema column | Schema |
|------------------|-----------------------|--------|
**Core schema synonyms:**

| Your column name | Maps to schema column | Schema |
|------------------|-----------------------|--------|
| `co2` | `emissions_tco2e` | emissions |
| `co2_emissions` | `emissions_tco2e` | emissions |
| `ghg` | `emissions_tco2e` | emissions |
| `ghg_emissions` | `emissions_tco2e` | emissions |
| `tco2e` | `emissions_tco2e` | emissions |
| `scope1` | `scope` | emissions |
| `scope_1` | `scope` | emissions |
| `mwh` | `consumption_mwh` | energy |
| `energy_mwh` | `consumption_mwh` | energy |
| `energy_consumption` | `consumption_mwh` | energy |
| `revenue` | `revenue_inr_crores` | financials |
| `total_revenue` | `revenue_inr_crores` | financials |
| `capex` | `esg_linked_capex_inr_crores` | financials |
| `esg_capex` | `esg_linked_capex_inr_crores` | financials |
| `gender` | `category` | diversity |

**Peer schema synonyms** (column names as they appear in the Excel dashboard files):

| Your column name | Maps to schema column | Schema |
|------------------|-----------------------|--------|
| `Company` | `company` | peer_financials, peer_esg, peer_metrics, peer_benchmark |
| `Year` | `year` | peer_financials, peer_esg, peer_metrics |
| `Net_Profit` | `net_profit` | peer_financials |
| `Total_Assets` | `total_assets` | peer_financials |
| `Total_Liabilities` | `total_liabilities` | peer_financials |
| `Current_Assets` | `current_assets` | peer_financials |
| `Current_Liabilities` | `current_liabilities` | peer_financials |
| `PPE(Net PPE)` | `ppe_net` | peer_financials |
| `CapEx` | `capex` | peer_financials |
| `Interest_Expense` | `interest_expense` | peer_financials |
| `EBITDA` | `ebitda` | peer_financials |
| `Operating_Cash_Flow` | `operating_cash_flow` | peer_financials |
| `Net_Debt` | `net_debt` | peer_financials |
| `ESG_CapEx` | `esg_capex` | peer_esg |
| `Green_Assets` | `green_assets` | peer_esg |
| `Scope1_Emissions_tCO2e` | `scope1_emissions_tco2e` | peer_esg |
| `Scope2_Emissions_tCO2e` | `scope2_emissions_tco2e` | peer_esg |
| `ESG_Score` | `esg_score` | peer_esg, peer_metrics |
| `Number_of_Sustainability_Projects` | `sustainability_projects` | peer_esg |
| `ROA (NetProfit/TotalAssets)` | `roa` | peer_metrics |
| `Asset_Turnover (Revenue/TotalAssets)` | `asset_turnover` | peer_metrics |
| `Working_Capital (CurrentAssets-CurrentLiabilities)` | `working_capital` | peer_metrics |
| `Working_Cap_Turnover (Revenue/WorkingCapital)` | `working_cap_turnover` | peer_metrics |
| `Net_Debt/EBITDA` | `net_debt_to_ebitda` | peer_metrics |
| `Interest_Coverage (EBITDA/InterestExpense)` | `interest_coverage` | peer_metrics |
| `FCF (OperatingCashFlow - CapEx)` | `fcf` | peer_metrics |
| `EBITDA_Margin (EBITDA/Revenue)` | `ebitda_margin` | peer_metrics |
| `ESG_CapEx_pct (ESG_CapEx/CapEx)` | `esg_capex_pct` | peer_metrics |
| `Green_Assets_pct (Green_Assets/TotalAssets)` | `green_assets_pct` | peer_metrics |
| `Scope1+2_Emissions` | `scope1_2_emissions` | peer_metrics |
| `ROA (avg 5yr)` | `roa_avg` | peer_benchmark |
| `Asset_Turnover (avg 5yr)` | `asset_turnover_avg` | peer_benchmark |
| `Net_Debt/EBITDA (avg 5yr)` | `net_debt_ebitda_avg` | peer_benchmark |
| `FCF (avg 5yr)` | `fcf_avg` | peer_benchmark |
| `EBITDA_Margin (avg 5yr)` | `ebitda_margin_avg` | peer_benchmark |
| `ESG_CapEx_pct (avg 5yr)` | `esg_capex_pct_avg` | peer_benchmark |
| `Green_Assets_pct (avg 5yr)` | `green_assets_pct_avg` | peer_benchmark |
| `ESG_Score (avg 5yr)` | `esg_score_avg` | peer_benchmark |

> If your column name is not in this list and the normalized match also fails, the column will not be mapped. You can still proceed — unmapped optional columns generate warnings, not errors. Only missing required columns block registration.

---

## Correct Upload Workflow

Follow these five steps to get your data into the pipeline:

**Step 1 — Prepare your file**

Review the schema tables above. Ensure the file has at least all required columns for your target schema. Name columns to match the schema definitions (or use synonyms from the table above). Supported file formats: `.csv`, `.xlsx`, `.xls`, `.json`.

**Step 2 — Open the upload page**

In the Streamlit dashboard, navigate to **Data Collector → Connect Data Sources → File Upload**.

**Step 3 — Upload and preview**

Select your file. Click **Test & Preview**. ESG Pilot will:
- Detect the schema automatically.
- Suggest a column mapping.
- Show a preview of the first rows.
- Auto-register the source in the session under `real_{schema}` (e.g. `real_emissions`).

A confirmation message confirms the registration. No additional save step is required.

**Step 4 — Confirm wiring in ESG Command Center**

Navigate to **ESG Command Center**. A green or blue banner will appear confirming that real data sources are registered. If the banner is absent or shows no registered sources, return to Step 3.

**Step 5 — Run the pipeline**

Click **Run Full Pipeline**. Your uploaded data will drive all calculations. The sample data for that schema is bypassed.

> **Important:** Data is session-scoped RAM only. If you refresh the browser or the Space restarts, you must re-upload your file and repeat from Step 3. See [Session Storage Note](#session-storage-note) below.

---

## Session Storage Note

All data in ESG Pilot is stored in RAM only. There is no database and no disk persistence.

| Stage | Storage location | Scope |
|-------|-----------------|-------|
| After Test & Preview | `st.session_state.preview_df`, `st.session_state.preview_config` | RAM, this browser tab only |
| After auto-registration | `st.session_state.conn_manager._sources` | RAM, this browser tab only |
| After pipeline run | `state_manager` pub/sub channels | RAM, process-wide |

**What this means in practice:**

- Refreshing the browser tab clears all uploaded data and pipeline results.
- Restarting the Streamlit server or a HuggingFace Space restart clears everything.
- Multiple browser tabs do not share uploaded data — each tab is its own isolated session.
- There is no way to save or export session state between runs.

If you need repeatable results, keep your prepared data file and re-upload it at the start of each session.

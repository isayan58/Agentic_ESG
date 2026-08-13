"""Generate complete sample datasets for ESG Pilot.

Produces one file per supported schema under sample_data/ at the project root.
Each file targets ~1 MB where the schema's natural cardinality supports it.
Files where the schema is inherently small (single-company financials,
peer_companies, peer_benchmark) are produced at maximum realistic size and
flagged in the manifest.
"""
from __future__ import annotations

import csv
import os
import random
from pathlib import Path

random.seed(20260427)

ROOT = Path(__file__).resolve().parents[1] / "sample_data"
COMPANY_DIR = ROOT / "company"
PEER_DIR = ROOT / "peer"
COMPANY_DIR.mkdir(parents=True, exist_ok=True)
PEER_DIR.mkdir(parents=True, exist_ok=True)

QUARTERS = ["Q1", "Q2", "Q3", "Q4"]


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


# =============================================================================
# SINGLE-COMPANY CORE SCHEMAS
# Company: "Helix Industries Ltd" (PetroChemical sector, India)
# 6-year horizon: 2019-2024
# =============================================================================

FACILITIES = [
    ("Mumbai HQ",                "Office",       0.012),
    ("Hazira Refinery",          "Refinery",     0.130),
    ("Jamnagar Polymer Plant",   "Petchem",      0.110),
    ("Vadodara Chemicals",       "Petchem",      0.070),
    ("Paradip Plant",            "Petchem",      0.060),
    ("Haldia Petchem",           "Petchem",      0.050),
    ("Gandhar Gas Cracker",      "Petchem",      0.045),
    ("Dahej Industrial Cluster", "Petchem",      0.045),
    ("Nagothane Plant",          "Petchem",      0.040),
    ("Visakhapatnam Port",       "Logistics",    0.040),
    ("Mangalore Storage",        "Logistics",    0.030),
    ("Kochi Tankage",            "Logistics",    0.025),
    ("Nashik Logistics",         "Logistics",    0.022),
    ("Kandla Terminal",          "Logistics",    0.020),
    ("Tuticorin Port Cluster",   "Logistics",    0.022),
    ("Kolkata Distribution",     "Distribution", 0.025),
    ("Hyderabad Distribution",   "Distribution", 0.020),
    ("Lucknow Distribution",     "Distribution", 0.018),
    ("Indore Distribution",      "Distribution", 0.015),
    ("Pune R&D Center",          "R&D",          0.025),
    ("Bengaluru Tech Park",      "R&D",          0.022),
    ("Surat Polymer Lab",        "R&D",          0.018),
    ("Hyderabad Catalysis Lab",  "R&D",          0.015),
    ("Chennai Office",           "Office",       0.015),
    ("Delhi Sales Hub",          "Office",       0.015),
    ("Ahmedabad Office",         "Office",       0.012),
    ("Kochi Sales Office",       "Office",       0.010),
    ("Coimbatore Office",        "Office",       0.008),
    ("Bhubaneswar Office",       "Office",       0.008),
    ("Jaipur Office",            "Office",       0.008),
]

EMISSION_CATS = [
    ("Scope 1", "Stationary Combustion",   "Boilers & Furnaces",     0.180, "Boiler & furnace fuel logs"),
    ("Scope 1", "Mobile Combustion",       "Fleet & Yard Vehicles",  0.060, "Fleet fuel cards"),
    ("Scope 1", "Process Emissions",       "Reformers & Crackers",   0.160, "Process mass balance"),
    ("Scope 1", "Fugitive Emissions",      "LDAR & Refrigerants",    0.040, "LDAR programme"),
    ("Scope 2", "Purchased Electricity",   "Grid + PPA",             0.200, "DISCOM utility bills"),
    ("Scope 2", "Purchased Steam",         "Industrial Utilities",   0.040, "Steam supply contract"),
    ("Scope 3", "Business Travel",         "Air, Hotel & Rail",      0.020, "Concur travel exports"),
    ("Scope 3", "Employee Commuting",      "Commuter Survey-derived",0.030, "Annual commuter survey"),
    ("Scope 3", "Purchased Goods",         "Raw & Packaging",        0.120, "Supplier invoice EEIO"),
    ("Scope 3", "Logistics & Transport",   "Inbound & Outbound",     0.070, "3PL freight ledgers"),
    ("Scope 3", "Capital Goods",           "Plant, Equipment, Build",0.040, "Project capex registers"),
    ("Scope 3", "End-of-life Treatment",   "Plastics & Hazardous",   0.040, "Waste contractor data"),
]

EMISSION_YEARS = list(range(2018, 2025))     # 7 years
ANNUAL_BASELINE_TCO2E = 985_000               # 2019 baseline
DECLINE_RATE = 0.045                          # 4.5%/yr improvement


def gen_emissions() -> Path:
    rows: list[dict] = []
    methodologies = ["GHG Protocol Cross-Sector", "API Compendium 2009",
                     "IPCC 2006 Tier-1", "IPCC 2006 Tier-2", "IPCC 2006 Tier-3",
                     "DEFRA UK 2024", "CEA Grid Factor v20.0",
                     "GLEC Framework 3.0", "EPA Emission Factors Hub 2024"]
    for yi, year in enumerate(EMISSION_YEARS):
        annual = ANNUAL_BASELINE_TCO2E * ((1 - DECLINE_RATE) ** yi)
        for qi, q in enumerate(QUARTERS):
            q_factor = [0.26, 0.24, 0.25, 0.25][qi]
            for fac, ftype, fw in FACILITIES:
                for scope, cat, sub, cw, source in EMISSION_CATS:
                    val = annual * q_factor * fw * cw * random.uniform(0.82, 1.18)
                    if val < 0.3:
                        continue
                    rows.append({
                        "year": year,
                        "quarter": q,
                        "scope": scope,
                        "category": cat,
                        "subcategory": sub,
                        "facility": fac,
                        "facility_type": ftype,
                        "emissions_tco2e": round(val, 3),
                        "unit": "tCO2e",
                        "source": f"{fac} — {source}",
                        "methodology": random.choice(methodologies),
                        "verified_by": random.choice([
                            "Internal — EHS team", "TUV Nord (limited)", "TUV Nord (reasonable)",
                            "DNV (limited)", "BSI (limited)", "ERM (reasonable)", ""
                        ]),
                        "confidence": round(random.uniform(0.78, 0.97), 2),
                    })
    path = COMPANY_DIR / "emissions.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# energy
# -----------------------------------------------------------------------------

ENERGY_SOURCES = [
    ("Grid Electricity",    "No",  0.45, 7.20),   # share-of-mix, ₹/kWh
    ("Diesel Generators",   "No",  0.05, 9.50),
    ("Natural Gas",         "No",  0.18, 5.80),
    ("Coal",                "No",  0.06, 4.20),
    ("Furnace Oil",         "No",  0.04, 6.10),
    ("Solar (rooftop+OPEN)","Yes", 0.13, 3.90),
    ("Wind PPA",            "Yes", 0.05, 4.40),
    ("Biomass",             "Yes", 0.03, 5.50),
    ("Green Hydrogen Pilot","Yes", 0.01, 18.00),
]
ENERGY_YEARS = list(range(2017, 2025))


def gen_energy() -> Path:
    rows = []
    base_total_mwh_2017 = 1_330_000
    growth = 1.025
    renewable_uplift = {2017: 0.0, 2018: 0.01, 2019: 0.02, 2020: 0.04,
                        2021: 0.07, 2022: 0.11, 2023: 0.16, 2024: 0.22}
    contracts = {
        "Grid Electricity": "DISCOM HT-Cat-A",
        "Diesel Generators": "On-site fuel",
        "Natural Gas": "GAIL APM",
        "Coal": "Coal India e-auction",
        "Furnace Oil": "IOCL bulk supply",
        "Solar (rooftop+OPEN)": "Tata Power Solar PPA",
        "Wind PPA": "ReNew Power PPA-2031",
        "Biomass": "Pellet Plant — local",
        "Green Hydrogen Pilot": "L&T Hydrogen Pilot",
    }
    for yi, year in enumerate(ENERGY_YEARS):
        annual_total = base_total_mwh_2017 * (growth ** yi)
        uplift = renewable_uplift[year]
        for qi, q in enumerate(QUARTERS):
            qf = [0.26, 0.24, 0.25, 0.25][qi]
            for fac, ftype, fw in FACILITIES:
                for src, renew, share, rate in ENERGY_SOURCES:
                    eff_share = share
                    if renew == "Yes":
                        eff_share += uplift / 4
                    if renew == "No":
                        eff_share -= uplift / 6
                    eff_share = max(eff_share, 0.001)
                    mwh = annual_total * qf * fw * eff_share * random.uniform(0.85, 1.15)
                    if mwh < 0.1:
                        continue
                    cost_lakhs = round(mwh * rate * 1000 / 1e5 * random.uniform(0.95, 1.08), 2)
                    peak_kw = round(mwh * 1000 / (90 * 24) * random.uniform(1.4, 2.6), 1)
                    rows.append({
                        "year": year,
                        "quarter": q,
                        "energy_source": src,
                        "consumption_mwh": round(mwh, 3),
                        "cost_inr_lakhs": cost_lakhs,
                        "location": fac,
                        "renewable": renew,
                        "facility_type": ftype,
                        "tariff_inr_per_kwh": rate,
                        "contract_id": f"{contracts[src][:3].upper()}-{year}-{abs(hash((fac, src))) % 9000 + 1000}",
                        "supplier": contracts[src],
                        "peak_demand_kw": peak_kw,
                        "load_factor_pct": round(random.uniform(48, 86), 1),
                        "meter_id": f"MTR-{abs(hash((fac, src, q))) % 999_999:06d}",
                    })
    path = COMPANY_DIR / "energy.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# waste
# -----------------------------------------------------------------------------

WASTE_CATS = [
    ("Non-Hazardous", "Paper",                0.07, 0.92, "Recycling"),
    ("Non-Hazardous", "Plastic (Recyclable)", 0.09, 0.85, "Recycling"),
    ("Non-Hazardous", "Plastic (Mixed)",      0.06, 0.40, "Co-processing"),
    ("Non-Hazardous", "Wood Pallets",         0.04, 0.78, "Recycling"),
    ("Non-Hazardous", "Glass",                0.02, 0.95, "Recycling"),
    ("Non-Hazardous", "Metal Scrap",          0.10, 0.96, "Recycling"),
    ("Non-Hazardous", "Construction Debris",  0.08, 0.55, "Landfill"),
    ("Non-Hazardous", "Food Waste",           0.03, 0.70, "Composting"),
    ("Hazardous",     "Spent Catalyst",       0.06, 0.62, "Authorised TSDF"),
    ("Hazardous",     "Used Oil",             0.08, 0.88, "Re-refining"),
    ("Hazardous",     "Sludge (Process)",     0.10, 0.30, "Co-processing"),
    ("Hazardous",     "Chemical Containers",  0.04, 0.65, "Authorised TSDF"),
    ("Hazardous",     "E-Waste",              0.03, 0.92, "Authorised Recycler"),
    ("Hazardous",     "Lab Solvents",         0.02, 0.74, "Incineration"),
]


def gen_waste() -> Path:
    rows = []
    base_total_mt_2017 = 60_000
    growth = 1.015
    recycle_uplift = {2017: 0.0, 2018: 0.01, 2019: 0.02, 2020: 0.04,
                      2021: 0.06, 2022: 0.09, 2023: 0.12, 2024: 0.15}
    contractors = ["Ramky Enviro", "Re Sustainability", "Saahas Zero Waste",
                   "Eco Recycling Ltd", "Hulladek Recycling", "Tata Steel Recycling",
                   "Antony Lara Enviro", "ALMA Recyclers"]
    for yi, year in enumerate(EMISSION_YEARS):
        annual = base_total_mt_2017 * (growth ** yi)
        ru = recycle_uplift[year]
        for qi, q in enumerate(QUARTERS):
            qf = [0.26, 0.24, 0.25, 0.25][qi]
            for fac, ftype, fw in FACILITIES:
                for wtype, cat, cw, base_rec, method in WASTE_CATS:
                    qty = annual * qf * fw * cw * random.uniform(0.80, 1.20)
                    if qty < 0.02:
                        continue
                    rec_pct = max(0.0, min(99.5, (base_rec + ru) * 100 * random.uniform(0.92, 1.05)))
                    rows.append({
                        "year": year,
                        "quarter": q,
                        "waste_type": wtype,
                        "category": cat,
                        "quantity_mt": round(qty, 3),
                        "disposal_method": method,
                        "recycled_pct": round(rec_pct, 1),
                        "location": fac,
                        "facility_type": ftype,
                        "contractor": random.choice(contractors),
                        "manifest_id": f"WM-{year}{q}-{abs(hash((fac, cat))) % 999_999:06d}",
                        "cost_inr_lakhs": round(qty * random.uniform(0.18, 1.6), 2),
                    })
    path = COMPANY_DIR / "waste.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# supply_chain
# -----------------------------------------------------------------------------

COUNTRIES = ["India", "China", "Vietnam", "Indonesia", "Malaysia", "Thailand",
             "Bangladesh", "Sri Lanka", "South Korea", "Japan", "Germany",
             "Italy", "France", "Netherlands", "Spain", "United Kingdom",
             "United States", "Mexico", "Brazil", "South Africa", "UAE",
             "Saudi Arabia", "Turkey", "Egypt", "Australia"]
SECTORS = ["Manufacturing", "Logistics", "Chemicals", "Plastics & Polymers",
           "Steel & Metals", "Electronics", "Packaging", "IT Services",
           "Engineering Services", "Industrial Equipment", "Construction",
           "Energy Services", "Catering & Facilities", "Transportation",
           "Pharmaceuticals", "Agriculture", "Mining"]
TIERS = ["Tier 1", "Tier 2", "Tier 3"]
RISK_BUCKETS = ["Low", "Medium", "High", "Critical"]
AUDIT_STATUSES = ["Compliant", "Pending", "Overdue", "Action Plan", "Re-audit Required"]
RISK_FACTORS_POOL = [
    "Labor practices", "Waste disposal", "Water stress", "Air emissions",
    "Worker safety", "Child labor risk", "Forced labor risk", "Bribery & corruption",
    "Conflict minerals", "Biodiversity impact", "Energy intensity", "Data security",
    "Ethical sourcing", "Living wage", "Tax transparency", "Diversity gap",
    "Climate transition risk", "Effluent management",
]
NAME_PARTS_A = ["Apex", "Beacon", "Cardinal", "Delta", "Eclipse", "Fortis", "Gemini",
                "Helios", "Indus", "Juno", "Kestrel", "Lumen", "Meridian", "Nimbus",
                "Orion", "Polaris", "Quasar", "Ravelin", "Solstice", "Tempus", "Umbra",
                "Vector", "Wolfram", "Xenon", "Yarrow", "Zenith", "Astra", "Borealis",
                "Cygnus", "Drake", "Ember", "Falcon", "Granite", "Hyperion"]
NAME_PARTS_B = ["Components", "Polymers", "Logistics", "Industries", "Chemicals",
                "Engineering", "Packaging", "Solutions", "Holdings", "Enterprises",
                "Manufacturing", "Resources", "Services", "Group", "Technologies",
                "Materials", "Distributors", "Systems", "Trading", "Works"]
NAME_SUFFIX = ["Ltd", "Pvt Ltd", "Co", "Corp", "Inc", "GmbH", "LLP", "AG", "SA"]


SCOPE3_CATEGORIES = [
    ("Cat 1: Purchased Goods & Services",   ["Manufacturing", "Chemicals", "Plastics & Polymers", "Packaging", "Steel & Metals", "Electronics", "Industrial Equipment", "Pharmaceuticals", "Agriculture", "Mining"]),
    ("Cat 2: Capital Goods",                 ["Industrial Equipment", "Construction", "Engineering Services"]),
    ("Cat 3: Fuel & Energy Related",         ["Energy Services"]),
    ("Cat 4: Upstream Transportation",       ["Logistics", "Transportation"]),
    ("Cat 5: Waste Generated in Operations", []),  # rarely supplier-attributable
    ("Cat 6: Business Travel",               ["Catering & Facilities"]),
    ("Cat 7: Employee Commuting",            []),
    ("Cat 8: Upstream Leased Assets",        []),
    ("Cat 9: Downstream Transportation",     ["Logistics", "Transportation"]),
    ("Cat 11: Use of Sold Products",         ["Plastics & Polymers", "Chemicals"]),
    ("Cat 12: End-of-Life Treatment",        []),
    ("Cat 15: Investments",                  ["IT Services"]),
]
EMISSION_FACTOR_SOURCES = ["EcoInvent v3.10", "DEFRA UK 2024", "EPA Emission Factors Hub 2024",
                           "GLEC Framework v3.0", "EXIOBASE v3.8", "USEEIO v2.0",
                           "Supplier-reported (CDP)", "Supplier-reported (EcoVadis)",
                           "Industry Average (IEA)", "Internal Engineering Estimate"]


def _scope3_category_for_sector(sector: str) -> str:
    candidates = [cat for cat, sectors in SCOPE3_CATEGORIES if sector in sectors]
    if not candidates:
        # fall back to broadly applicable categories
        candidates = ["Cat 1: Purchased Goods & Services", "Cat 4: Upstream Transportation",
                      "Cat 9: Downstream Transportation"]
    return random.choice(candidates)


def gen_supply_chain(target_rows: int = 5000) -> Path:
    rows = []
    used_names = set()
    for i in range(1, target_rows + 1):
        # ~6000 unique combinations exist; once exhausted, append a numeric tag
        for attempt in range(60):
            name = f"{random.choice(NAME_PARTS_A)} {random.choice(NAME_PARTS_B)} {random.choice(NAME_SUFFIX)}"
            if name not in used_names:
                used_names.add(name)
                break
        else:
            name = f"{random.choice(NAME_PARTS_A)} {random.choice(NAME_PARTS_B)} {random.choice(NAME_SUFFIX)} #{i}"
            used_names.add(name)
        country = random.choice(COUNTRIES)
        sector = random.choice(SECTORS)
        tier = random.choices(TIERS, weights=[0.55, 0.30, 0.15])[0]
        # tier-driven ESG score distribution
        if tier == "Tier 1":
            esg = round(random.normalvariate(72, 10), 1)
        elif tier == "Tier 2":
            esg = round(random.normalvariate(60, 12), 1)
        else:
            esg = round(random.normalvariate(48, 14), 1)
        esg = max(15.0, min(95.0, esg))
        # risk inverse to esg
        if esg >= 75:
            risk = random.choices(RISK_BUCKETS, weights=[0.70, 0.25, 0.04, 0.01])[0]
        elif esg >= 60:
            risk = random.choices(RISK_BUCKETS, weights=[0.30, 0.50, 0.18, 0.02])[0]
        elif esg >= 45:
            risk = random.choices(RISK_BUCKETS, weights=[0.05, 0.35, 0.50, 0.10])[0]
        else:
            risk = random.choices(RISK_BUCKETS, weights=[0.01, 0.10, 0.45, 0.44])[0]
        # spend (used to drive emission contribution)
        spend_inr_cr = round(random.lognormvariate(2.4, 1.0), 2)
        # emission factor by sector
        ef = {
            "Manufacturing": 28, "Logistics": 65, "Chemicals": 95,
            "Plastics & Polymers": 80, "Steel & Metals": 140, "Electronics": 22,
            "Packaging": 45, "IT Services": 4, "Engineering Services": 8,
            "Industrial Equipment": 24, "Construction": 70, "Energy Services": 110,
            "Catering & Facilities": 15, "Transportation": 75, "Pharmaceuticals": 32,
            "Agriculture": 90, "Mining": 160,
        }[sector]
        emission_contrib = round(spend_inr_cr * ef * random.uniform(0.7, 1.3), 1)
        if risk in ("High", "Critical"):
            audit = random.choices(AUDIT_STATUSES, weights=[0.10, 0.20, 0.35, 0.25, 0.10])[0]
        else:
            audit = random.choices(AUDIT_STATUSES, weights=[0.55, 0.20, 0.05, 0.15, 0.05])[0]
        last_audit_year = random.randint(2021, 2024)
        last_audit = f"{last_audit_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        n_factors = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}[risk] + random.randint(0, 2)
        factors = ", ".join(random.sample(RISK_FACTORS_POOL, k=min(n_factors, len(RISK_FACTORS_POOL))))
        # ~5% of suppliers are single-sourced; concentrated in tier-1
        single_source = "Yes" if (tier == "Tier 1" and random.random() < 0.10) or \
                                  (tier == "Tier 2" and random.random() < 0.04) else "No"
        rows.append({
            "supplier_id": f"SUP-{i:05d}",
            "supplier_name": name,
            "country": country,
            "sector": sector,
            "tier": tier,
            "esg_score": esg,
            "risk_rating": risk,
            "emission_contribution_tco2e": emission_contrib,
            "audit_status": audit,
            "last_audit_date": last_audit,
            "key_risk_factors": factors,
            "annual_spend_inr_crores": spend_inr_cr,
            "scope3_category": _scope3_category_for_sector(sector),
            "single_source_flag": single_source,
            "emission_factor_source": random.choice(EMISSION_FACTOR_SOURCES),
        })
    path = COMPANY_DIR / "supply_chain.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# esg_metrics
# -----------------------------------------------------------------------------

# Build a wide KPI taxonomy across pillars/categories, then expand by business unit.
# Numbering follows the §9 metric-ID taxonomy in DATA_MODEL.md and matches
# DATA_FIELD_MAPPING in agents/regulatory_tracker.py exactly. Tuple shape:
#     (metric_id, pillar, category, name, unit, baseline, change_per_yr)
# `change_per_yr` is positive when "lower is better" (e.g. emissions, attrition).
ESG_METRIC_TAXONOMY = [
    # ── Environmental — E01..E25 ──
    ("E01", "E", "Climate", "Total GHG Emissions (Scope 1+2)",       "tCO2e",     770000,  0.045),
    ("E02", "E", "Climate", "Scope 3 Emissions",                     "tCO2e",     215000,  0.025),
    ("E03", "E", "Energy", "Renewable Energy Share",                 "%",             22, -0.080),
    ("E04", "E", "Water", "Total Water Withdrawal",                  "ML",          6800,  0.015),
    ("E05", "E", "Water", "Water Recycled & Reused",                 "%",             41, -0.060),
    ("E06", "E", "Waste", "Total Waste Generated",                   "MT",         64000,  0.015),
    ("E07", "E", "Waste", "Waste Diverted from Landfill",            "%",             68, -0.050),
    ("E08", "E", "Waste", "Hazardous Waste Generated",               "MT",         21000,  0.010),
    ("E09", "E", "Biodiversity", "Land Use / Biodiversity Footprint","ha",            28, -0.150),
    ("E10", "E", "Energy", "Total Energy Consumption",               "MWh",      1420000, -0.025),
    ("E11", "E", "Air Quality", "Air Pollutants (NOx + SOx + PM)",   "MT",          1195,  0.030),
    ("E12", "E", "Water Quality", "Water Pollutants (BOD+COD+TSS)",  "MT",            34,  0.020),
    ("E13", "E", "Pollution", "Hazardous Substance Releases",        "kg",          4300, -0.040),
    ("E14", "E", "Climate-Financial", "Climate-related CapEx",       "INR_Cr",       210, -0.080),
    ("E15", "E", "Climate-Financial", "Climate-related OpEx",        "INR_Cr",        85, -0.050),
    ("E16", "E", "Climate-Financial", "Stranded-Asset Impairment",   "INR_Cr",        12,  0.0),
    ("E17", "E", "Climate-Financial", "Insurance Recovery (Climate)","INR_Cr",         8, -0.040),
    ("E18", "E", "Climate-Financial", "Carbon Tax Exposure",         "INR_Lakhs",    34.5, 0.030),
    ("E19", "E", "Sourcing", "Sustainable Sourcing Share",           "%",             64, -0.030),
    ("E20", "E", "Climate", "Green-Asset Intensity",                 "%",             14, -0.080),
    ("E21", "E", "Energy", "Grid Electricity Share",                 "%",             45,  0.025),
    ("E22", "E", "Energy", "Energy Intensity per Revenue",           "MWh/Cr",      18.0,  0.025),
    ("E23", "E", "Climate", "Carbon Intensity per Revenue",          "tCO2e/Cr",    12.5,  0.060),
    ("E24", "E", "Water", "Water Stress Exposure",                   "%",             18,  0.020),
    ("E25", "E", "Climate", "Emissions Assurance Coverage",          "%",             45, -0.080),

    # ── Social — S01..S25 ──
    ("S01", "S", "Workforce", "Total Employees",                     "count",      14200, -0.020),
    ("S02", "S", "Workforce", "Voluntary Turnover",                  "%",           14.5, -0.020),
    ("S03", "S", "Workforce", "Female Representation Overall",       "%",             24, -0.040),
    ("S04", "S", "Workforce", "Female Representation Leadership",    "%",             18, -0.080),
    ("S05", "S", "Workforce", "Pay Ratio (Female:Male)",              "ratio",       0.94, -0.020),
    ("S06", "S", "Health & Safety", "Lost Time Injury Frequency Rate","per_mn_hrs", 0.42,  0.045),
    ("S07", "S", "Health & Safety", "Safety Training Hours / Employee","hrs",       18.5, -0.060),
    ("S08", "S", "Community", "CSR Spend",                            "INR_Cr",        38, -0.080),
    ("S09", "S", "Community", "Community Beneficiaries",              "count",     215000, -0.090),
    ("S10", "S", "Training", "Average Training Hours / Employee",     "hrs",           32, -0.050),
    ("S11", "S", "Workforce", "Differently-Abled Representation",     "%",            1.4, -0.060),
    ("S12", "S", "Supply Chain", "Suppliers Audited on ESG",          "%",             62, -0.080),
    ("S13", "S", "Community", "Local Sourcing Share",                 "%",             64, -0.030),
    ("S14", "S", "Human Rights", "Human Rights Salience Assessment",  "%",             78, -0.050),
    ("S15", "S", "Customer", "Consumer Complaints Resolved",          "%",             87, -0.040),
    ("S16", "S", "Customer", "Product Safety Incidents",              "count",          3,  0.10),
    ("S17", "S", "Human Rights", "Indigenous Rights / FPIC Coverage", "%",             82, -0.040),
    ("S18", "S", "Workforce", "Just Transition Programme Coverage",   "%",             40, -0.120),
    ("S19", "S", "Workforce", "Employee Engagement Score",            "%",             71, -0.025),
    ("S20", "S", "Workforce", "Living Wage Compliance",                "%",             93, -0.020),
    ("S21", "S", "Workforce", "Permanent Employees",                  "count",      11800, -0.015),
    ("S22", "S", "Health & Safety", "Total Recordable Injury Rate",   "per_mn_hrs", 1.18,  0.050),
    ("S23", "S", "Health & Safety", "Fatalities (Employees+Contractors)","count",      2,  0.20),
    ("S24", "S", "Workforce", "Skill Development — Reskilling Hours", "hrs",           14, -0.090),
    ("S25", "S", "Customer", "Product Sustainability Certifications", "count",         18, -0.130),

    # ── Governance — G01..G25 ──
    ("G01", "G", "Board", "Board Size",                              "count",          12,  0.0),
    ("G02", "G", "Board", "Independent Director Share",              "%",              50, -0.020),
    ("G03", "G", "Board", "Board ESG Oversight Frequency",            "meetings/yr",    4, -0.050),
    ("G04", "G", "Ethics", "Anti-Corruption Training Coverage",       "%",             96, -0.005),
    ("G05", "G", "Ethics", "Whistleblower Cases Raised",               "count",         47, -0.020),
    ("G06", "G", "ICFR", "ICFR Assessment Coverage",                  "%",             68, -0.080),
    ("G07", "G", "Risk", "Data Privacy Complaints / Breaches",        "count",          6,  0.0),
    ("G08", "G", "ICFR", "CEO/CFO Sub-Certification (SOX 302/906)",   "%",             92, -0.005),
    ("G09", "G", "Climate Gov", "Climate Governance Structure Disclosed","%",          70, -0.060),
    ("G10", "G", "Climate Gov", "Board Climate Strategy Disclosure",  "%",             65, -0.080),
    ("G11", "G", "Climate Gov", "Climate Risk Process Integration",   "%",             58, -0.090),
    ("G12", "G", "Materiality", "Materiality Assessment Cycle Coverage","%",           74, -0.060),
    ("G13", "G", "Materiality", "Stakeholder Engagement Coverage",    "%",             82, -0.040),
    ("G14", "G", "Assurance", "External ESG Assurance Level",         "%",             45, -0.090),
    ("G15", "G", "Tax Transparency", "Effective Tax Rate",            "%",           24.8,  0.005),
    ("G16", "G", "Lobbying", "Lobbying & Public Policy Spend",        "INR_Lakhs",      8,  0.040),
    ("G17", "G", "Ethics", "Bribery & Corruption Incidents",          "count",          1,  0.0),
    ("G18", "G", "Risk", "Cybersecurity Incidents (Material)",        "count",          3,  0.10),
    ("G19", "G", "ICFR", "Disclosure Controls & Procedures (SOX 302)","%",             88, -0.020),
    ("G20", "G", "ICFR", "Document Retention Programme (SOX 802)",    "%",             92, -0.010),
    ("G21", "G", "Risk", "Material Risks Identified",                 "count",         22, -0.020),
    ("G22", "G", "Compliance", "Regulatory Non-compliances",          "count",          4, -0.050),
    ("G23", "G", "Compliance", "Significant Fines Paid",              "INR_Lakhs",     18, -0.030),
    ("G24", "G", "Risk", "Audit Trail Coverage (ESG data lineage)",   "%",             72, -0.060),
    ("G25", "G", "Risk", "Internal Controls Effectiveness Score",     "0-100",         78, -0.040),
]

# The long tail: ~425 further metrics across the same pillars, giving a
# ~500-metric inventory closer to what a company filing under BRSR, CSRD
# and GRI at once actually tracks. Kept in its own module so the core 25
# per pillar stay readable and their IDs stay stable.
try:
    from esg_taxonomy_extended import EXTENDED_METRICS
except ImportError:  # running from repo root rather than scripts/
    import sys, pathlib as _pl
    sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
    from esg_taxonomy_extended import EXTENDED_METRICS
ESG_METRIC_TAXONOMY = ESG_METRIC_TAXONOMY + EXTENDED_METRICS

BUSINESS_UNITS = [
    ("HQ",       "Corporate / HQ"),
    ("REF-HZR",  "Refinery — Hazira"),
    ("PCH-JMG",  "Petchem — Jamnagar"),
    ("PCH-VDR",  "Petchem — Vadodara"),
    ("PCH-PDP",  "Petchem — Paradip"),
    ("PCH-HLD",  "Petchem — Haldia"),
    ("PCH-GDR",  "Petchem — Gandhar"),
    ("PCH-DHJ",  "Petchem — Dahej"),
    ("PCH-NGT",  "Petchem — Nagothane"),
    ("LOG-VSP",  "Logistics — Visakhapatnam"),
    ("LOG-MNG",  "Logistics — Mangalore"),
    ("LOG-KCH",  "Logistics — Kochi"),
    ("LOG-NSK",  "Logistics — Nashik"),
    ("LOG-KND",  "Logistics — Kandla"),
    ("LOG-TUT",  "Logistics — Tuticorin"),
    ("DST-KOL",  "Distribution — Kolkata"),
    ("DST-HYD",  "Distribution — Hyderabad"),
    ("DST-LKO",  "Distribution — Lucknow"),
    ("DST-IND",  "Distribution — Indore"),
    ("RND-PUN",  "R&D — Pune"),
    ("RND-BLR",  "R&D — Bengaluru"),
    ("RND-SRT",  "R&D — Surat Polymer Lab"),
    ("RND-HYD",  "R&D — Hyderabad Catalysis"),
    ("OFC-CHN",  "Office — Chennai"),
    ("OFC-DLH",  "Office — Delhi"),
    ("OFC-AMD",  "Office — Ahmedabad"),
    ("OFC-KCH",  "Office — Kochi Sales"),
    ("OFC-CMB",  "Office — Coimbatore"),
    ("OFC-BBS",  "Office — Bhubaneswar"),
    ("OFC-JPR",  "Office — Jaipur"),
    ("BIZ-PLM",  "Business Unit — Polymers"),
    ("BIZ-FUE",  "Business Unit — Fuels"),
    ("BIZ-LUB",  "Business Unit — Lubricants"),
    ("BIZ-AGR",  "Business Unit — Agrochemicals"),
    ("BIZ-SPC",  "Business Unit — Specialty Chemicals"),
    ("BIZ-PCK",  "Business Unit — Packaging"),
    ("BIZ-RNW",  "Business Unit — Renewables Division"),
    ("BIZ-HYD",  "Business Unit — Hydrogen Pilot"),
    ("FNC-COR",  "Function — Corporate Finance"),
    ("FNC-PRC",  "Function — Procurement"),
    ("FNC-HRM",  "Function — Human Resources"),
    ("FNC-IT",   "Function — IT & Digital"),
    ("FNC-LGL",  "Function — Legal & Compliance"),
    ("FNC-COM",  "Function — Communications"),
    ("FNC-CSR",  "Function — CSR & Sustainability"),
    # Additional cost-centre level slices for finer KPI granularity
    ("REG-WST",  "Region — West India"),
    ("REG-NTH",  "Region — North India"),
    ("REG-STH",  "Region — South India"),
    ("REG-EST",  "Region — East India"),
    ("REG-INT",  "Region — International (ME + APAC)"),
    ("REG-EUR",  "Region — Europe"),
    ("REG-AMR",  "Region — Americas"),
    ("PJT-NETZ", "Programme — Net-Zero 2050"),
    ("PJT-CIRC", "Programme — Circular Economy"),
    ("PJT-WTR",  "Programme — Water Stewardship"),
    ("PJT-DEI",  "Programme — DEI Acceleration"),
    ("PJT-SAF",  "Programme — Process Safety"),
    ("PJT-DIG",  "Programme — Digital Twin Rollout"),
    ("PJT-CCS",  "Programme — Carbon Capture Pilot"),
    ("PJT-EVS",  "Programme — EV Fleet Transition"),
    ("PJT-RNW",  "Programme — Renewable PPA Expansion"),
    ("PJT-BIO",  "Programme — Bio-feedstock Sourcing"),
    ("PJT-AUD",  "Programme — Independent Assurance"),
    ("PJT-COC",  "Programme — Code of Conduct Refresh"),
    ("PJT-WHB",  "Programme — Whistleblower Strengthening"),
    ("PJT-TAX",  "Programme — Tax Transparency"),
    ("PJT-CYB",  "Programme — Cybersecurity Hardening"),
    ("PJT-DAT",  "Programme — Data Privacy Programme"),
    ("PJT-LIV",  "Programme — Living Wage Audit"),
    ("PJT-COM",  "Programme — Community Investment"),
    ("PJT-HRT",  "Programme — Human Rights Salience"),
    # Frameworks-aligned reporting cuts
    ("FW-BRSR",  "Framework — BRSR (SEBI India)"),
    ("FW-CSRD",  "Framework — CSRD ESRS (EU)"),
    ("FW-CDP",   "Framework — CDP Climate"),
    ("FW-CDPW",  "Framework — CDP Water"),
    ("FW-TCFD",  "Framework — TCFD"),
    ("FW-TNFD",  "Framework — TNFD"),
    ("FW-SBTI",  "Framework — SBTi Validation"),
    ("FW-GRI",   "Framework — GRI Universal"),
    ("FW-SASB",  "Framework — SASB Chemicals"),
    ("FW-IFRS",  "Framework — IFRS S1/S2"),
    # Risk register slices
    ("RSK-PHY",  "Risk Theme — Physical Climate Risk"),
    ("RSK-TRN",  "Risk Theme — Transition Climate Risk"),
    ("RSK-WTR",  "Risk Theme — Water Stress Risk"),
    ("RSK-BIO",  "Risk Theme — Biodiversity Risk"),
    ("RSK-SUP",  "Risk Theme — Supplier Concentration Risk"),
    ("RSK-CYB",  "Risk Theme — Cyber Risk"),
    ("RSK-DAT",  "Risk Theme — Data Privacy Risk"),
    ("RSK-REG",  "Risk Theme — Regulatory Risk"),
    ("RSK-LIT",  "Risk Theme — Litigation Risk"),
    ("RSK-REP",  "Risk Theme — Reputation Risk"),
    # Customer / market slices
    ("MKT-B2B",  "Market — B2B Industrial Customers"),
    ("MKT-B2C",  "Market — B2C Consumer"),
    ("MKT-EXP",  "Market — Export"),
    ("MKT-PSU",  "Market — Public Sector"),
    ("MKT-SMB",  "Market — SMB Channel"),
    ("MKT-OEM",  "Market — OEM Tier-1"),
    ("MKT-DST",  "Market — Distributor Network"),
    ("MKT-DTC",  "Market — Direct to Consumer"),
]


def gen_esg_metrics() -> Path:
    rows = []
    # Each metric is emitted once per business unit so that downstream BU-level
    # analysis still works, but `metric_id` itself is the bare canonical ID
    # (E01, S03, G06, …) so it joins cleanly to DATA_FIELD_MAPPING in
    # agents/regulatory_tracker.py. The BU is held in `business_unit`.
    pillar_full = {"E": "Environmental", "S": "Social", "G": "Governance"}
    data_source_by_pillar = {
        "E": "ERP emissions module / utility bills",
        "S": "HRIS / EHS register",
        "G": "Board secretariat / compliance ledger",
    }
    framework_tags_pool = [
        "BRSR Principal 6", "BRSR Principal 5", "GRI 305", "GRI 302",
        "GRI 303", "GRI 306", "GRI 405", "GRI 403", "TCFD-Metrics",
        "CSRD ESRS E1", "CSRD ESRS S1", "CSRD ESRS G1", "SASB-RT-CH",
        "SOX 404", "SOX 302", "SEC-CLIM SX-14", "IFRS S2", "CSRD-DM",
    ]
    for metric_id, pillar_short, category, name, unit, baseline, change_per_yr in ESG_METRIC_TAXONOMY:
        pillar = pillar_full[pillar_short]
        for bu_id, bu_name in BUSINESS_UNITS:
            bu_share = max(0.005, random.uniform(0.5, 1.5)) * \
                       (1.0 if bu_id == "HQ" else random.uniform(0.4, 1.6))
            v23 = baseline * bu_share / len(BUSINESS_UNITS) * (1 - change_per_yr * 4) * random.uniform(0.85, 1.15)
            v24 = baseline * bu_share / len(BUSINESS_UNITS) * (1 - change_per_yr * 5) * random.uniform(0.85, 1.15)
            tgt = baseline * bu_share / len(BUSINESS_UNITS) * (1 - change_per_yr * 5.2)
            improving = change_per_yr > 0
            if improving:
                status = "Met" if v24 <= tgt else ("On Track" if v24 <= tgt * 1.05 else "Not Met")
            else:
                status = "Met" if v24 >= tgt else ("On Track" if v24 >= tgt * 0.95 else "Not Met")
            rows.append({
                "metric_id": metric_id,
                "pillar": pillar,
                "category": category,
                "metric_name": f"{name} — {bu_name}",
                "unit": unit,
                "value_2023": round(v23, 3),
                "value_2024": round(v24, 3),
                "target_2024": round(tgt, 3),
                "status": status,
                "data_source": f"{data_source_by_pillar[pillar_short]} (BU: {bu_id})",
                "confidence": round(random.uniform(0.78, 0.97), 2),
                "business_unit": bu_id,
                "framework_tags": random.choice(framework_tags_pool),
            })
    path = COMPANY_DIR / "esg_metrics.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# diversity
# -----------------------------------------------------------------------------

DIVERSITY_DEFS = [
    ("Gender", ["Overall", "Leadership", "Middle Management", "Junior", "STEM Roles",
                "Sales Roles", "New Hires", "Promotions", "Voluntary Attrition", "Pay Gap"]),
    ("Age",    ["<30", "30-50", ">50", "Leadership <40", "Leadership 40-55", "Leadership >55",
                "New Hires <30", "Voluntary Attrition <30", "Voluntary Attrition >50"]),
    ("Disability", ["Overall", "Leadership", "Junior", "New Hires", "Accessibility-Trained Sites"]),
    ("Nationality", ["Domestic", "Expat", "Leadership Domestic", "Leadership Expat",
                     "Top-3 Nationalities Share"]),
    ("Tenure", ["<2 yrs", "2-5 yrs", "5-10 yrs", ">10 yrs", "Leadership <5 yrs", "Leadership >10 yrs"]),
    ("LGBTQ+", ["Self-Identified Overall", "Self-Identified Leadership",
                "ERG Membership", "Allyship Pledge"]),
    ("Veterans", ["Overall", "Leadership", "New Hires"]),
    ("Education", ["Postgraduate", "Graduate", "Diploma", "Vocational", "PhD"]),
]
DIV_METRICS_PCT = ["Female representation %", "Male representation %", "Other/Undisclosed %"]
DIV_METRICS_COUNT = ["Headcount", "New Hires Count", "Exits Count"]
DIV_METRICS_RATIO = ["Pay ratio (Female:Male)", "Promotion ratio (Female:Male)"]
LOCATIONS_DIV = ["India - West", "India - North", "India - South", "India - East",
                 "India - Central", "India - North-East",
                 "Asia ex-India - SE Asia", "Asia ex-India - East Asia",
                 "Middle East & Africa", "EMEA - Western Europe",
                 "EMEA - Eastern Europe", "Americas - North", "Americas - LatAm"]


def gen_diversity() -> Path:
    rows = []
    for year in range(2015, 2025):
        for category, subs in DIVERSITY_DEFS:
            for sub in subs:
                for loc in LOCATIONS_DIV:
                    if category == "Gender":
                        f = max(8, min(60, random.normalvariate(28 - 4 * (sub == "Leadership"), 7)))
                        m = 100 - f - random.uniform(0.3, 1.5)
                        o = 100 - f - m
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Female representation %", "value": round(f, 2), "unit": "%",
                                     "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Male representation %", "value": round(m, 2), "unit": "%",
                                     "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Other/Undisclosed %", "value": round(o, 2), "unit": "%",
                                     "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Headcount", "value": round(random.uniform(80, 4500)), "unit": "count",
                                     "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Pay ratio (Female:Male)",
                                     "value": round(random.uniform(0.86, 1.02), 3), "unit": "ratio",
                                     "location": loc, "source": "Compensation review"})
                    elif category == "Age":
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Headcount", "value": round(random.uniform(60, 3500)), "unit": "count",
                                     "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Share of total %",
                                     "value": round(random.uniform(5, 45), 2), "unit": "%",
                                     "location": loc, "source": "HRIS extract"})
                    elif category == "Disability":
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Differently abled %",
                                     "value": round(random.uniform(0.4, 3.6), 2), "unit": "%",
                                     "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Headcount", "value": round(random.uniform(2, 180)),
                                     "unit": "count", "location": loc, "source": "HRIS extract"})
                    elif category == "Nationality":
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Headcount", "value": round(random.uniform(20, 4000)),
                                     "unit": "count", "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Share %", "value": round(random.uniform(2, 96), 2), "unit": "%",
                                     "location": loc, "source": "HRIS extract"})
                    elif category == "Tenure":
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Headcount", "value": round(random.uniform(40, 3000)),
                                     "unit": "count", "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Median tenure",
                                     "value": round(random.uniform(1.0, 14.5), 1), "unit": "years",
                                     "location": loc, "source": "HRIS extract"})
                    elif category == "LGBTQ+":
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Self-identified %",
                                     "value": round(random.uniform(0.2, 4.5), 2), "unit": "%",
                                     "location": loc, "source": "Voluntary self-id survey"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Headcount", "value": round(random.uniform(0, 280)),
                                     "unit": "count", "location": loc, "source": "Voluntary self-id survey"})
                    elif category == "Veterans":
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Veteran share %",
                                     "value": round(random.uniform(0.1, 2.4), 2), "unit": "%",
                                     "location": loc, "source": "Onboarding self-disclosure"})
                    elif category == "Education":
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Share %", "value": round(random.uniform(2, 60), 2), "unit": "%",
                                     "location": loc, "source": "HRIS extract"})
                        rows.append({"year": year, "category": category, "subcategory": f"{sub} | {loc}",
                                     "metric": "Headcount", "value": round(random.uniform(15, 2500)),
                                     "unit": "count", "location": loc, "source": "HRIS extract"})
    # ensure consistent fieldnames
    fieldnames = ["year", "category", "subcategory", "metric", "value", "unit", "location", "source"]
    path = COMPANY_DIR / "diversity.csv"
    write_csv(path, rows, fieldnames)
    return path


# -----------------------------------------------------------------------------
# financials (single-company quarterly)
# -----------------------------------------------------------------------------


def gen_financials() -> Path:
    rows = []
    base_rev = 380.0  # ₹ Cr per quarter starting 2015 Q1
    for year in range(2015, 2025):
        for qi, q in enumerate(QUARTERS):
            growth = (1.06) ** (year - 2015)
            seasonal = [1.00, 0.95, 1.04, 1.06][qi]
            rev = base_rev * growth * seasonal * random.uniform(0.97, 1.03)
            ebitda_margin = max(14.5, min(28.0, random.normalvariate(22.0 + 0.4 * (year - 2019), 1.4)))
            ebitda = rev * ebitda_margin / 100
            pat = ebitda * random.uniform(0.55, 0.68)
            roa = round(random.normalvariate(7.5 + 0.2 * (year - 2019), 1.0), 2)
            roe = round(random.normalvariate(15.0 + 0.4 * (year - 2019), 1.5), 2)
            de = round(random.normalvariate(0.55 - 0.02 * (year - 2019), 0.07), 3)
            coc = round(random.normalvariate(10.5 - 0.1 * (year - 2019), 0.4), 2)
            pe = round(random.normalvariate(20 + 0.5 * (year - 2019), 2.5), 1)
            carbon_tax = round(rev * random.uniform(0.06, 0.10) * (1.0 - 0.04 * (year - 2019)), 1)
            energy_cost = round(rev * random.uniform(0.025, 0.035), 2)
            turnover = round(random.normalvariate(15.0 - 0.3 * (year - 2019), 1.2), 2)
            brand = round(random.normalvariate(70 + 0.8 * (year - 2019), 2.0), 1)
            retain = round(random.normalvariate(78 + 0.6 * (year - 2019), 2.0), 1)
            esg_capex = round(rev * random.uniform(0.04, 0.08) * (1.0 + 0.10 * (year - 2019)), 2)
            rows.append({
                "year": year,
                "quarter": q,
                "revenue_inr_crores": round(rev, 2),
                "ebitda_inr_crores": round(ebitda, 2),
                "ebitda_margin_pct": round(ebitda_margin, 2),
                "pat_inr_crores": round(pat, 2),
                "roa_pct": roa,
                "roe_pct": roe,
                "debt_equity_ratio": de,
                "cost_of_capital_pct": coc,
                "pe_ratio": pe,
                "carbon_tax_exposure_lakhs": carbon_tax,
                "energy_cost_inr_crores": energy_cost,
                "employee_turnover_pct": turnover,
                "brand_value_index": brand,
                "talent_retention_score": retain,
                "esg_linked_capex_inr_crores": esg_capex,
            })
    path = COMPANY_DIR / "financials.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# =============================================================================
# PEER BENCHMARKING SCHEMAS
# 60 fictional companies × 5 sectors × 25 fiscal years (2000-2024)
# =============================================================================

# Programmatically expand to ~200 fictional companies across 8 sectors.
SECTOR_DEFS = [
    ("PetroChemical",                   "Petrochem", "Refinery", 26),
    ("Power",                           "Power",     "Energy",   26),
    ("Mining",                          "Mining",    "Resource", 20),
    ("Cement & Construction Materials", "Cement",    "Materials",20),
    ("Steel & Metals",                  "Steel",     "Metals",   22),
    ("Oil & Gas Upstream",              "OilGas",    "Energy",   20),
    ("Chemicals (Specialty)",           "Specialty", "Chemicals",22),
    ("Renewables & Utilities",          "Green",     "Energy",   24),
    ("Information Technology",          "IT",        "Services", 28),
]
PEER_NAME_FIRST = ["Vertex", "Aurora", "Helios", "Meridian", "Solstice", "Cobalt",
                   "Polaris", "Indigo", "Quartz", "Tellurium", "Argo", "Voltaic",
                   "Ember", "Nimbus", "Apex", "Beacon", "Cascade", "Drift",
                   "Stratus", "Lumen", "Tempest", "Vector", "Quarry", "Iron Crown",
                   "Stratum", "Granite Peak", "Obsidian", "Carbide", "Bedrock",
                   "Lodestone", "Bastion", "Buttress", "Citadel", "Megalith",
                   "Pillar", "Rampart", "Marble Crest", "Forge", "Ironclad",
                   "Anvil", "Crucible", "Tungsten", "Smelter", "Bessemer",
                   "Helix", "Astra", "Borealis", "Cygnus", "Drake", "Ember",
                   "Falcon", "Hyperion", "Indus", "Juno", "Kestrel", "Magnetar",
                   "Nova", "Oryx", "Pyxis", "Quasar", "Ravelin", "Sirius",
                   "Tundra", "Ursa", "Vega", "Wraith", "Xerus", "Yarrow",
                   "Zephyr", "Auriga", "Boreas", "Castor", "Dione", "Electra",
                   "Faro", "Galaxia", "Hesperia", "Ithaca", "Janus", "Kairos",
                   "Larkspur", "Mistral", "Nemesis", "Onyx", "Petra", "Quill"]
PEER_NAME_TYPE = {
    "PetroChemical":                  ["Petrochemicals", "Refining", "Polymers", "Chemicals", "Energy Corp"],
    "Power":                          ["Power Co", "Generation Ltd", "Utilities", "Grid Holdings", "Power Systems"],
    "Mining":                         ["Mining", "Resources", "Minerals", "Holdings", "Mining Group"],
    "Cement & Construction Materials":["Cement", "Materials", "Concrete", "Aggregates", "Building Products"],
    "Steel & Metals":                 ["Steel Co", "Metals", "Alloys", "Steelworks", "Industries"],
    "Oil & Gas Upstream":             ["Oil & Gas", "Petroleum", "Exploration", "Energy", "Resources"],
    "Chemicals (Specialty)":          ["Specialty Chem", "Fine Chemicals", "Pharma Intermediates", "Agro Inputs", "Catalysts"],
    "Renewables & Utilities":         ["Renewables", "Solar Power", "Wind Energy", "Green Utilities", "Hydro Co"],
    "Information Technology":         ["Technologies", "Systems", "Software", "Digital", "InfoSystems",
                                       "Analytics", "Cloud", "Cybersecurity", "Platforms", "IT Services"],
}


def build_peer_company_list() -> list[tuple[int, str, str, float]]:
    out: list[tuple[int, str, str, float]] = []
    used = set()
    no = 0
    rnd = random.Random(101)
    for sector, _short, _grp, count in SECTOR_DEFS:
        types = PEER_NAME_TYPE[sector]
        for _ in range(count):
            for _try in range(50):
                first = rnd.choice(PEER_NAME_FIRST)
                t = rnd.choice(types)
                # 30% add a third differentiator like "Group" / "Ltd"
                suffix = rnd.choice(["", "", "", "Ltd", "Corp", "Group", "Holdings", "Co", "Industries"])
                name = f"{first} {t}" + (f" {suffix}" if suffix else "")
                if name not in used:
                    used.add(name)
                    break
            no += 1
            scale = round(rnd.lognormvariate(-0.4, 0.6), 3)  # log-normal scale → mostly 0.3–1.5
            out.append((no, name, sector, scale))
    # Ensure subject company "Helix Industries Ltd" present at PetroChemical for cross-reference
    out.append((len(out) + 1, "Helix Industries Ltd", "PetroChemical", 0.48))
    return out


PEER_COMPANIES = build_peer_company_list()
PEER_YEARS = list(range(1989, 2025))   # 36 years


def gen_peer_companies() -> Path:
    rows = [{"company_no": no, "company": name, "sector": sector,
             "country": "India",
             "listing_status": random.choices(["Listed", "Unlisted"], weights=[0.85, 0.15])[0],
             "ticker": (name.split()[0].upper()[:5] + ".NS")
             if random.random() < 0.85 else "",
             "fiscal_year_end": "March",
             "currency": "INR Crore",
             "size_scale": scale}
            for (no, name, sector, scale) in PEER_COMPANIES]
    path = PEER_DIR / "peer_companies.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


SECTOR_GROWTH = {
    "PetroChemical":                   1.072,
    "Power":                           1.058,
    "Mining":                          1.066,
    "Cement & Construction Materials": 1.060,
    "Steel & Metals":                  1.064,
    "Oil & Gas Upstream":              1.054,
    "Chemicals (Specialty)":           1.085,
    "Renewables & Utilities":          1.110,
    "Information Technology":          1.135,
}


def gen_peer_financials() -> Path:
    rows = []
    for (no, name, sector, scale) in PEER_COMPANIES:
        sector_growth = SECTOR_GROWTH[sector]
        base_rev = 2200 * scale * random.uniform(0.85, 1.15)
        base_assets = base_rev * random.uniform(2.4, 3.8)
        for yi, year in enumerate(PEER_YEARS):
            cycle = 1.0 + 0.06 * random.choice([-1, 0, 0, 1]) + random.uniform(-0.04, 0.04)
            rev = base_rev * (sector_growth ** yi) * cycle
            np_margin = max(1.5, min(18.0, random.normalvariate(8.5, 2.5)))
            net_profit = rev * np_margin / 100
            total_assets = base_assets * (sector_growth ** (yi * 0.95)) * random.uniform(0.95, 1.06)
            total_liab = total_assets * random.uniform(0.55, 0.78)
            ca = total_assets * random.uniform(0.18, 0.32)
            cl = total_liab * random.uniform(0.22, 0.40)
            ppe = total_assets * random.uniform(0.40, 0.62)
            capex = rev * random.uniform(0.06, 0.14)
            depr = ppe * random.uniform(0.06, 0.10)
            interest = total_liab * random.uniform(0.030, 0.065)
            ebitda = rev * max(0.08, min(0.32, random.normalvariate(0.22, 0.04)))
            ocf = ebitda * random.uniform(0.65, 0.95)
            net_debt = total_liab * random.uniform(0.30, 0.55)
            goodwill = total_assets * random.uniform(0.0, 0.06)
            intangibles = total_assets * random.uniform(0.005, 0.04)
            rows.append({
                "company": name, "year": year, "sector": sector,
                "revenue":             round(rev, 2),
                "net_profit":          round(net_profit, 2),
                "total_assets":        round(total_assets, 2),
                "total_liabilities":   round(total_liab, 2),
                "current_assets":      round(ca, 2),
                "current_liabilities": round(cl, 2),
                "ppe_net":             round(ppe, 2),
                "capex":               round(capex, 2),
                "depreciation":        round(depr, 2),
                "interest_expense":    round(interest, 2),
                "ebitda":              round(ebitda, 2),
                "operating_cash_flow": round(ocf, 2),
                "net_debt":            round(net_debt, 2),
                "goodwill":            round(goodwill, 2),
                "intangibles":         round(intangibles, 2),
            })
    path = PEER_DIR / "peer_financials.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


def gen_peer_esg() -> Path:
    """ESG inputs derived to be consistent with peer_financials scale."""
    rows = []
    sector_emis_intensity = {  # tCO2e per ₹ Cr revenue (rough industry benchmarks)
        "PetroChemical":                   22,
        "Power":                           60,
        "Mining":                          70,
        "Cement & Construction Materials": 95,
        "Steel & Metals":                  110,
        "Oil & Gas Upstream":              35,
        "Chemicals (Specialty)":           18,
        "Renewables & Utilities":          8,
        "Information Technology":          3,
    }
    for (no, name, sector, scale) in PEER_COMPANIES:
        base_rev = 2200 * scale * random.uniform(0.85, 1.15)
        base_score = random.uniform(38, 78)
        score_drift = random.uniform(0.5, 2.0)
        for yi, year in enumerate(PEER_YEARS):
            sector_growth = SECTOR_GROWTH[sector]
            rev = base_rev * (sector_growth ** yi) * random.uniform(0.95, 1.05)
            ei = sector_emis_intensity[sector] * (1 - 0.015 * yi) * random.uniform(0.85, 1.15)
            scope1 = rev * ei * random.uniform(0.55, 0.72)
            scope2 = rev * ei * random.uniform(0.28, 0.45)
            esg_capex = rev * random.uniform(0.02, 0.10) * (1 + 0.05 * yi)
            green_assets = rev * random.uniform(0.05, 0.25) * (1 + 0.04 * yi)
            score = max(20.0, min(95.0, base_score + score_drift * yi + random.uniform(-3, 3)))
            n_proj = max(0, int(random.normalvariate(6 + 0.4 * yi, 2.5)))
            # Sub-scores derived from composite with random spread
            e_sub = max(15.0, min(98.0, score + random.uniform(-8, 12)))
            s_sub = max(15.0, min(98.0, score + random.uniform(-8, 8)))
            g_sub = max(15.0, min(98.0, score + random.uniform(-6, 10)))
            controversies = max(0, int(random.normalvariate(2.5, 2)))
            water_kl = rev * random.uniform(40, 320)
            waste_mt = rev * random.uniform(2.5, 18)
            renew_pct = max(0.0, min(95.0, random.normalvariate(18 + 1.6 * yi, 10)))
            women_lead = max(2.0, min(58.0, random.normalvariate(16 + 0.8 * yi, 5)))
            ltifr = max(0.05, random.normalvariate(0.6 - 0.02 * yi, 0.25))
            assurance = random.choice(["None", "Limited", "Limited", "Reasonable"])
            assurer = random.choice(["—", "EY", "KPMG", "Deloitte", "BSI", "DNV", "TUV Nord", "ERM"])
            rows.append({
                "company": name, "year": year,
                "esg_capex":              round(esg_capex, 2),
                "green_assets":           round(green_assets, 2),
                "scope1_emissions_tco2e": round(scope1, 2),
                "scope2_emissions_tco2e": round(scope2, 2),
                "esg_score":              round(score, 2),
                "sustainability_projects": n_proj,
                "sector":                 sector,
                "rating_provider":        random.choice(["Internal", "MSCI", "Sustainalytics", "CDP", "S&P CSA"]),
                "rating_year":            year,
                "environmental_sub_score": round(e_sub, 2),
                "social_sub_score":        round(s_sub, 2),
                "governance_sub_score":    round(g_sub, 2),
                "controversies_count":     controversies,
                "water_withdrawal_kl":     round(water_kl, 1),
                "waste_generated_mt":      round(waste_mt, 1),
                "renewable_energy_pct":    round(renew_pct, 2),
                "women_in_leadership_pct": round(women_lead, 2),
                "ltifr":                   round(ltifr, 3),
                "assurance_level":         assurance,
                "assurance_provider":      assurer if assurance != "None" else "—",
            })
    path = PEER_DIR / "peer_esg.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


def gen_peer_metrics(financials_path: Path, esg_path: Path) -> Path:
    """Compute calculated metrics from the two raw datasets."""
    fin = {}
    with financials_path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            fin[(row["company"], int(row["year"]))] = row
    esg = {}
    with esg_path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            esg[(row["company"], int(row["year"]))] = row

    rows = []
    for key in sorted(fin.keys() & esg.keys()):
        f = fin[key]; e = esg[key]
        rev = float(f["revenue"]); npr = float(f["net_profit"])
        ta  = float(f["total_assets"]); ca = float(f["current_assets"])
        cl  = float(f["current_liabilities"]); capex = float(f["capex"])
        ie  = float(f["interest_expense"]); ebitda = float(f["ebitda"])
        ocf = float(f["operating_cash_flow"]); nd = float(f["net_debt"])
        ec  = float(e["esg_capex"]); ga = float(e["green_assets"])
        s1  = float(e["scope1_emissions_tco2e"]); s2 = float(e["scope2_emissions_tco2e"])
        wc  = ca - cl
        rows.append({
            "company": key[0], "year": key[1],
            "sector": f["sector"],
            "roa":                   round(npr / ta, 6) if ta else None,
            "asset_turnover":        round(rev / ta, 6) if ta else None,
            "working_capital":       round(wc, 2),
            "working_cap_turnover":  round(rev / wc, 4) if wc else None,
            "net_debt_to_ebitda":    round(nd / ebitda, 4) if ebitda else None,
            "interest_coverage":     round(ebitda / ie, 4) if ie else None,
            "fcf":                   round(ocf - capex, 2),
            "ebitda_margin":         round(ebitda / rev, 6) if rev else None,
            "esg_capex_pct":         round(ec / capex, 6) if capex else None,
            "green_assets_pct":      round(ga / ta, 6) if ta else None,
            "scope1_2_emissions":    round(s1 + s2, 2),
            "esg_score":             float(e["esg_score"]),
            "carbon_intensity_per_revenue": round((s1 + s2) / rev, 4) if rev else None,
            "esg_capex_per_revenue": round(ec / rev, 6) if rev else None,
        })
    path = PEER_DIR / "peer_metrics.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


def gen_peer_benchmark(metrics_path: Path) -> Path:
    """5-year (2020-2024) averages per company from peer_metrics."""
    by_co: dict[str, list[dict]] = {}
    with metrics_path.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            yr = int(row["year"])
            if 2020 <= yr <= 2024:
                by_co.setdefault(row["company"], []).append(row)

    def avg(rows: list[dict], key: str) -> float | None:
        vals = [float(r[key]) for r in rows if r[key] not in (None, "", "None")]
        return round(sum(vals) / len(vals), 6) if vals else None

    sector_lookup = {name: sector for (_, name, sector, _) in PEER_COMPANIES}

    rows = []
    for company, rs in sorted(by_co.items()):
        rows.append({
            "company": company,
            "sector": sector_lookup.get(company, ""),
            "roa_avg":              avg(rs, "roa"),
            "asset_turnover_avg":   avg(rs, "asset_turnover"),
            "net_debt_ebitda_avg":  avg(rs, "net_debt_to_ebitda"),
            "fcf_avg":              avg(rs, "fcf"),
            "ebitda_margin_avg":    avg(rs, "ebitda_margin"),
            "esg_capex_pct_avg":    avg(rs, "esg_capex_pct"),
            "green_assets_pct_avg": avg(rs, "green_assets_pct"),
            "esg_score_avg":        avg(rs, "esg_score"),
            "carbon_intensity_avg": avg(rs, "carbon_intensity_per_revenue"),
            "interest_coverage_avg":avg(rs, "interest_coverage"),
        })
    path = PEER_DIR / "peer_benchmark.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# =============================================================================
# REGULATORY & RISK SCHEMAS
# =============================================================================

# -----------------------------------------------------------------------------
# materiality_assessment — CSRD Double Materiality
# -----------------------------------------------------------------------------

MATERIALITY_TOPICS = [
    # (topic_id, name, pillar, base_impact, base_financial, stakeholder, framework)
    ("M01", "Climate Change Mitigation",            "Environmental", 9.2, 8.7, "Investors / Society",       "CSRD-DM, BRSR-S4, GRI-3"),
    ("M02", "Climate Change Adaptation",            "Environmental", 8.4, 7.8, "Investors / Customers",     "CSRD-DM, TCFD"),
    ("M03", "Water & Marine Resources",             "Environmental", 7.6, 5.4, "Communities / Regulators",  "CSRD-DM, CDP-Water"),
    ("M04", "Biodiversity & Ecosystems",            "Environmental", 6.8, 4.5, "Society / Regulators",      "CSRD-DM, TNFD"),
    ("M05", "Resource Use & Circular Economy",      "Environmental", 7.2, 6.1, "Customers / Regulators",    "CSRD-DM, BRSR-P2"),
    ("M06", "Pollution Prevention (Air/Water/Soil)","Environmental", 7.9, 6.4, "Communities / Regulators",  "CSRD-DM E3, BRSR-P6"),
    ("M07", "Energy Transition & Renewables",       "Environmental", 8.6, 8.2, "Investors / Customers",     "CSRD-DM E1, TCFD"),
    ("M08", "Hazardous Waste Management",           "Environmental", 7.4, 6.7, "Regulators / Communities",  "CSRD-DM E5, BRSR-P6"),
    ("M09", "Own Workforce — H&S",                  "Social",        8.7, 7.6, "Employees / Regulators",    "CSRD-DM S1, BRSR-P3"),
    ("M10", "Own Workforce — Diversity & Inclusion","Social",        7.8, 6.9, "Employees / Investors",     "CSRD-DM S1, BRSR-P5"),
    ("M11", "Workers in the Value Chain",           "Social",        7.1, 5.8, "Suppliers / NGOs",          "CSRD-DM S2, BRSR-P5"),
    ("M12", "Affected Communities",                 "Social",        7.3, 5.2, "Communities / Regulators",  "CSRD-DM S3, BRSR-P8"),
    ("M13", "Consumers & End-Users",                "Social",        6.6, 7.4, "Customers / Regulators",    "CSRD-DM S4, BRSR-P9"),
    ("M14", "Human Rights & Modern Slavery",        "Social",        7.0, 6.4, "NGOs / Regulators",         "CSRD-DM S2, UN-Guiding"),
    ("M15", "Local Sourcing & Community Investment","Social",        6.4, 5.0, "Communities / Government",  "BRSR-P8"),
    ("M16", "Business Ethics & Anti-Corruption",    "Governance",    8.1, 8.0, "Investors / Regulators",    "CSRD-DM G1, BRSR-P1"),
    ("M17", "Board Composition & Independence",     "Governance",    7.5, 7.7, "Investors / Proxy advisers","CSRD-DM G1, ICGN"),
    ("M18", "Cybersecurity & Data Privacy",         "Governance",    8.3, 8.5, "Customers / Regulators",    "ISO-27001, IFRS S1"),
    ("M19", "Tax Transparency",                     "Governance",    6.2, 6.8, "Regulators / Society",      "GRI-207, BRSR-P1"),
    ("M20", "Risk Management & Internal Controls",  "Governance",    7.7, 8.2, "Investors / Auditors",      "SOX-404, COSO-ERM"),
    ("M21", "Lobbying & Public Policy Influence",   "Governance",    6.0, 5.6, "Society / NGOs",            "GRI-415"),
    ("M22", "Product Safety & Quality",             "Social",        7.6, 7.9, "Customers / Regulators",    "BRSR-P9, ISO-9001"),
    ("M23", "Sustainable Sourcing",                 "Environmental", 7.0, 6.2, "Customers / Investors",     "BRSR-P2, CSRD-DM"),
    ("M24", "Innovation in Green Tech",             "Environmental", 7.9, 8.4, "Investors / Customers",     "CSRD-DM E1, BRSR-P2"),
    ("M25", "Supply Chain Resilience",              "Governance",    7.4, 8.1, "Investors / Customers",     "COSO-ERM, BRSR-P2"),
    ("M26", "GHG Emissions — Scope 3 Disclosure",   "Environmental", 8.2, 7.5, "Investors / Customers",     "CSRD-DM E1, GHG-Protocol"),
    ("M27", "Water Stress in Operations",           "Environmental", 7.0, 5.6, "Communities / Investors",   "CDP-Water, CSRD-DM E3"),
    ("M28", "Just Transition for Workforce",        "Social",        6.7, 5.4, "Employees / Trade Unions",  "CSRD-DM S1, ILO"),
]
ASSESSMENT_DATES = [
    "2022-03-15", "2022-09-22", "2023-03-10", "2023-09-18",
    "2024-03-12", "2024-09-25", "2025-03-08", "2025-09-15",
]
MAT_OWNERS = ["Sustainability Team", "Risk & Internal Audit", "ESG Reporting", "Procurement",
              "HR & D&I Council", "EHS", "Corporate Affairs", "Investor Relations",
              "Group Strategy", "Legal & Compliance"]
MAT_DECISIONS = ["Material", "Material", "Material", "Material",
                 "Watch", "Watch", "Not Material"]


ASSESSMENT_PANELS = [
    "Internal — Sustainability Council",
    "Internal — Audit Committee Workshop",
    "External — Investor Roundtable",
    "External — NGO / Society Panel",
    "External — Customer Advisory Board",
    "External — Supplier Forum",
]


def gen_materiality() -> Path:
    rows = []
    horizons = ["Short (0-1 yr)", "Medium (1-3 yr)", "Long (3-10 yr)"]
    # Multiple cuts per topic: by stakeholder × time horizon × assessment cycle × panel.
    # That's the typical structure of a real CSRD-DM register.
    for topic_id, name, pillar, base_imp, base_fin, stakeholders_pri, fw in MATERIALITY_TOPICS:
        primary_stakeholders = [s.strip() for s in stakeholders_pri.split("/")]
        all_stakeholders = primary_stakeholders + ["Employees", "Investors", "Regulators",
                                                    "Customers", "Suppliers", "Communities"]
        seen = set()
        ordered = [s for s in all_stakeholders if not (s in seen or seen.add(s))]
        for panel in ASSESSMENT_PANELS:
            panel_bias = {
                "Internal — Sustainability Council":         (+0.3, -0.1),
                "Internal — Audit Committee Workshop":       (-0.1, +0.4),
                "External — Investor Roundtable":            (-0.2, +0.5),
                "External — NGO / Society Panel":            (+0.6, -0.2),
                "External — Customer Advisory Board":        (+0.1, +0.3),
                "External — Supplier Forum":                 (+0.0, +0.0),
            }[panel]
            for sg in ordered:
                for horizon in horizons:
                    for ad in ASSESSMENT_DATES:
                        cycle_idx = ASSESSMENT_DATES.index(ad)
                        horizon_factor = {"Short (0-1 yr)": 1.00, "Medium (1-3 yr)": 0.92,
                                           "Long (3-10 yr)": 0.84}[horizon]
                        imp = max(0.5, min(10.0, base_imp * horizon_factor + panel_bias[0]
                                            + random.uniform(-1.2, 1.2) + 0.05 * cycle_idx))
                        fin = max(0.5, min(10.0, base_fin * horizon_factor + panel_bias[1]
                                            + random.uniform(-1.2, 1.2) + 0.07 * cycle_idx))
                        decision = "Material" if (imp >= 6.5 or fin >= 6.5) else \
                                   ("Watch" if (imp >= 4.5 or fin >= 4.5) else "Not Material")
                        rows.append({
                            "topic_id": topic_id,
                            "topic_name": name,
                            "esg_pillar": pillar,
                            "impact_materiality_score": round(imp, 2),
                            "financial_materiality_score": round(fin, 2),
                            "stakeholder_group": sg,
                            "time_horizon": horizon,
                            "assessment_date": ad,
                            "evidence_link": f"https://intranet.helix.local/dm/{topic_id}/{ad}.pdf",
                            "owner": random.choice(MAT_OWNERS),
                            "decision": decision,
                            "framework_alignment": fw,
                            "assessment_panel": panel,
                        })
    path = COMPANY_DIR / "materiality_assessment.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# icfr_controls — SOX/ICFR controls register
# -----------------------------------------------------------------------------

ICFR_PROCESSES = [
    ("Revenue Recognition",                   "302", "F"),
    ("Procure-to-Pay",                         "404", "F"),
    ("Fixed Assets & CapEx",                   "404", "F"),
    ("Inventory Valuation",                    "404", "F"),
    ("Financial Close & Reporting",            "302", "F"),
    ("ESG Disclosure Close",                   "302", "ESG"),
    ("GHG Emissions Calculation",              "404", "ESG"),
    ("Energy Consumption Reporting",           "404", "ESG"),
    ("Water Withdrawal Reporting",             "404", "ESG"),
    ("Waste & Recycling Reporting",            "404", "ESG"),
    ("Diversity Metrics Compilation",          "404", "ESG"),
    ("Health & Safety Incident Reporting",     "404", "ESG"),
    ("Supplier ESG Data Aggregation",          "404", "ESG"),
    ("Carbon Tax Provision",                   "404", "F+ESG"),
    ("Climate Risk Disclosure",                "404", "ESG"),
    ("Materiality Assessment Refresh",         "404", "ESG"),
    ("Treasury & Cash Management",             "404", "F"),
    ("Tax Provision",                          "404", "F"),
    ("Payroll & Compensation",                 "404", "F"),
    ("Stock-Based Comp Accounting",            "404", "F"),
    ("Hedging & Derivatives",                  "404", "F"),
    ("Pension & OPEB Accounting",              "404", "F"),
    ("Goodwill & Intangibles Impairment",      "404", "F"),
    ("Lease Accounting (IFRS 16)",             "404", "F"),
    ("Revenue Cut-off Testing",                "404", "F"),
    ("Bank Reconciliations",                   "404", "F"),
    ("Journal Entry Review",                   "404", "F"),
    ("Access Reviews — Financial Systems",     "404", "ITGC"),
    ("Change Management — Financial Systems",  "404", "ITGC"),
    ("Backup & Recovery — Financial Systems",  "404", "ITGC"),
    ("CEO/CFO Sub-Certification — Q",          "302", "Cert"),
    ("CEO/CFO Sub-Certification — Annual",     "302", "Cert"),
    ("Audit Committee Oversight",              "906", "Gov"),
    ("Whistleblower Process",                  "302", "Gov"),
    ("ESG Data Lineage Validation",            "404", "ESG"),
    ("ESG Restatement Approval",               "302", "ESG"),
]
CTRL_TYPES = ["Preventive", "Detective", "Corrective"]
CTRL_FREQUENCIES = ["Daily", "Weekly", "Monthly", "Quarterly", "Annual"]
CTRL_OWNERS = ["Controller's Office", "Internal Audit", "ESG Reporting", "EHS",
               "Treasury", "Tax", "HR Operations", "Procurement",
               "IT Risk", "Legal & Compliance", "Investor Relations",
               "Sustainability — Climate", "Sustainability — Social"]
DEFICIENCY_BUCKETS = ["None", "None", "None", "None", "None",
                      "Deficiency", "Deficiency",
                      "Significant", "Material"]
REMED_STATUSES = ["Not Applicable", "Open", "In Progress", "Tested — Passed",
                  "Tested — Failed", "Closed", "Re-test Required"]
TESTERS = ["Internal Audit (in-house)", "Internal Audit (co-source — KPMG)",
           "Internal Audit (co-source — EY)", "Independent — Deloitte",
           "Independent — PwC", "Self-test (Process Owner)"]


def gen_icfr_controls() -> Path:
    rows = []
    # Each process gets multiple controls (preventive + detective + corrective)
    # tested across multiple periods (FY2022-FY2024 quarterly = 12 cycles).
    seq = 0
    for proc, sox, family in ICFR_PROCESSES:
        n_controls = random.randint(5, 10)
        for c_idx in range(n_controls):
            ctrl_type = random.choice(CTRL_TYPES)
            freq = random.choice(CTRL_FREQUENCIES)
            owner = random.choice(CTRL_OWNERS)
            test_cycles = ["FY21-Q1", "FY21-Q2", "FY21-Q3", "FY21-Q4",
                           "FY22-Q1", "FY22-Q2", "FY22-Q3", "FY22-Q4",
                           "FY23-Q1", "FY23-Q2", "FY23-Q3", "FY23-Q4",
                           "FY24-Q1", "FY24-Q2", "FY24-Q3", "FY24-Q4",
                           "FY25-Q1", "FY25-Q2"]
            for cycle in test_cycles:
                seq += 1
                # Convert FY22-Q1 to a real test date within the quarter
                fy = 2000 + int(cycle[2:4])
                qn = int(cycle[-1])
                month = {1: 6, 2: 9, 3: 12, 4: 3}[qn]
                year = fy if qn != 4 else fy + 1
                day = random.randint(5, 28)
                test_date = f"{year}-{month:02d}-{day:02d}"
                deficiency = random.choice(DEFICIENCY_BUCKETS)
                if deficiency == "None":
                    remed = "Not Applicable"
                elif deficiency == "Deficiency":
                    remed = random.choice(["Open", "In Progress", "Tested — Passed", "Closed"])
                elif deficiency == "Significant":
                    remed = random.choice(["In Progress", "Tested — Failed", "Re-test Required", "Closed"])
                else:  # Material
                    remed = random.choice(["Open", "In Progress", "Re-test Required"])
                esg_metric = ""
                if family in ("ESG", "F+ESG"):
                    esg_metric = random.choice([
                        "E01", "E10", "E14", "S06", "S14",
                        "G06", "G08", "G19", "G24",
                    ])
                rows.append({
                    "control_id":         f"ICFR-{family}-{seq:05d}",
                    "process":            proc,
                    "esg_metric_linked":  esg_metric,
                    "control_owner":      owner,
                    "test_date":          test_date,
                    "deficiency_flag":    deficiency,
                    "remediation_status": remed,
                    "sox_section":        sox,
                    "control_type":       ctrl_type,
                    "frequency":          freq,
                    "tester":             random.choice(TESTERS),
                    "evidence_doc_id":    f"AUD-{cycle}-{seq:06d}",
                    "control_objective":  random.choice([
                        "Ensure completeness of recorded transactions in the period",
                        "Ensure accuracy of recorded amounts and disclosures",
                        "Ensure proper authorisation of journal entries and adjustments",
                        "Ensure existence of underlying assets and obligations",
                        "Ensure rights & obligations are properly recognised",
                        "Ensure proper cut-off of period-end transactions",
                        "Ensure proper classification in financial statements",
                        "Ensure ESG data lineage and source traceability",
                        "Ensure ESG metric calculation conforms to GHG Protocol",
                        "Ensure timely and accurate climate disclosure filing",
                    ]),
                    "business_unit":      random.choice([bu for bu, _ in BUSINESS_UNITS]),
                    "grc_tool":           random.choice(["AuditBoard", "Workiva", "ServiceNow GRC", "MetricStream", "OneTrust"]),
                })
    path = COMPANY_DIR / "icfr_controls.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# climate_financial_impacts — SEC Climate (SX-14, 1502)
# -----------------------------------------------------------------------------

CFI_EVENTS = [
    # (event_type, sub-type, base capex/opex skew)
    ("Acute",      "Cyclone Damage — Coastal Plant",        "high_opex"),
    ("Acute",      "Flood — Plant Shutdown",                "high_opex"),
    ("Acute",      "Wildfire — Asset Loss",                 "high_capex"),
    ("Acute",      "Heatwave — Cooling Surge",              "med_opex"),
    ("Chronic",    "Sea-Level Rise — Coastal Defences",     "high_capex"),
    ("Chronic",    "Drought — Water Sourcing Cost",         "med_opex"),
    ("Chronic",    "Rising Avg Temp — Cooling Demand",      "med_opex"),
    ("Transition", "Carbon Price — Cap & Trade",            "high_opex"),
    ("Transition", "Carbon Border Adjustment Mechanism",    "high_opex"),
    ("Transition", "EV Fleet Conversion",                   "med_capex"),
    ("Transition", "Renewable PPA — Long-term Contract",    "med_capex"),
    ("Transition", "Green Hydrogen Pilot Plant",            "high_capex"),
    ("Transition", "Carbon Capture & Storage Pilot",        "high_capex"),
    ("Transition", "Plant Decommissioning — Coal",          "high_capex"),
    ("Transition", "R&D — Bio-feedstock",                   "med_capex"),
    ("Transition", "Stranded Asset Impairment — Refinery",  "impairment"),
    ("Transition", "Carbon Tax Provision (India)",          "high_opex"),
    ("Transition", "EU CSRD Reporting Compliance",          "med_opex"),
]
CFI_ASSETS = [name for (name, _, _) in FACILITIES]
CFI_GL = ["GL-1100-CapEx", "GL-1200-CapEx", "GL-2300-OpEx", "GL-2400-OpEx",
          "GL-3500-OpEx", "GL-4100-Impair", "GL-5200-Insurance",
          "GL-6300-OpEx", "GL-7400-OpEx", "GL-8500-OpEx"]
CFI_SCENARIOS = ["NGFS-NetZero2050", "NGFS-DivergentNetZero", "NGFS-DelayedTransition",
                 "IEA-NZE2050", "IEA-APS", "IEA-STEPS", "RCP2.6", "RCP4.5", "RCP8.5"]


def gen_climate_financial_impacts() -> Path:
    rows = []
    for fy in range(2014, 2026):  # 12 fiscal years
        for q in QUARTERS:
            period = f"FY{fy}-{q}"
            # 70-120 climate-tagged GL events per quarter (a 30-facility company
            # routinely posts dozens of climate-tagged transactions)
            for _ in range(random.randint(85, 135)):
                event_type, sub, skew = random.choice(CFI_EVENTS)
                # Skew the capex/opex split based on the event archetype
                if skew == "high_capex":
                    capex = random.uniform(2.0, 80.0)
                    opex = random.uniform(0.05, 4.0)
                    impair = 0
                elif skew == "med_capex":
                    capex = random.uniform(1.0, 25.0)
                    opex = random.uniform(0.10, 5.0)
                    impair = 0
                elif skew == "high_opex":
                    capex = random.uniform(0.0, 2.0)
                    opex = random.uniform(2.0, 40.0)
                    impair = 0
                elif skew == "med_opex":
                    capex = random.uniform(0.0, 0.8)
                    opex = random.uniform(0.5, 8.0)
                    impair = 0
                else:  # impairment
                    capex = 0
                    opex = 0
                    impair = random.uniform(8.0, 220.0)
                # Insurance recovery occasionally on acute events
                insurance = round(opex * random.uniform(0.0, 0.6), 2) if event_type == "Acute" else 0.0
                rows.append({
                    "fiscal_period":       period,
                    "event_type":          event_type,
                    "capex_climate":       round(capex, 2),
                    "opex_climate":        round(opex, 2),
                    "impairment_amount":   round(impair, 2),
                    "insurance_recovery":  insurance,
                    "affected_asset_id":   random.choice(CFI_ASSETS),
                    "gl_account":          random.choice(CFI_GL),
                    "scenario_tag":        random.choice(CFI_SCENARIOS),
                    "description":         sub,
                    "approver":            random.choice(["CFO", "Controller", "Treasurer",
                                                         "Plant FC", "Group FC", "Audit Committee"]),
                    "supporting_doc":      f"CFI-{period}-{random.randint(100000, 999999)}.pdf",
                    "currency":            "INR Crore",
                    "narrative":           random.choice([
                        "Adaptation capex tied to multi-year transition plan submitted to board.",
                        "Routine opex tagged climate-related per IFRS S2 paragraph 22.",
                        "One-off impairment driven by NGFS-aligned scenario refresh.",
                        "Carbon-tax pass-through booked against centrally-managed provision.",
                        "Insurance receivable accrued; cash recovery expected in next quarter.",
                        "PPA contract signed; lifetime opex offset to be amortised straight-line.",
                        "Pilot facility commissioned; depreciation begins next period.",
                        "Climate-stress test triggered re-measurement of carrying value.",
                    ]),
                })
    path = COMPANY_DIR / "climate_financial_impacts.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# climate_risk_register — Qualitative ERM register
# -----------------------------------------------------------------------------

CRR_RISKS = [
    # (category, risk_text)
    ("Physical-Acute",     "Cyclone disruption to Hazira, Paradip refineries"),
    ("Physical-Acute",     "Coastal flooding at Visakhapatnam port cluster"),
    ("Physical-Acute",     "Inland flooding at Vadodara Chemicals"),
    ("Physical-Acute",     "Wildfire-driven supply disruption (US/EU suppliers)"),
    ("Physical-Acute",     "Extreme-heat workforce productivity decline"),
    ("Physical-Chronic",   "Rising sea level — coastal asset depreciation"),
    ("Physical-Chronic",   "Water stress at Pune/Jamnagar (CGWB-classified)"),
    ("Physical-Chronic",   "Long-term cooling-water scarcity"),
    ("Physical-Chronic",   "Monsoon variability impacting feedstock logistics"),
    ("Transition-Policy",  "India carbon market (CCTS) compliance cost"),
    ("Transition-Policy",  "EU CBAM exposure on exports"),
    ("Transition-Policy",  "Plastic packaging EPR compliance"),
    ("Transition-Policy",  "BS-VI / BS-VII fuel specification tightening"),
    ("Transition-Policy",  "Methane emissions disclosure regulation"),
    ("Transition-Policy",  "Mandatory Scope 3 disclosure (BRSR Core)"),
    ("Transition-Tech",    "Stranded asset risk — refining capacity"),
    ("Transition-Tech",    "Demand shift to EV / hydrogen mobility"),
    ("Transition-Tech",    "Bio-based feedstock margin compression"),
    ("Transition-Tech",    "Energy efficiency benchmark gap vs peers"),
    ("Transition-Tech",    "CCS technology cost-curve uncertainty"),
    ("Transition-Market",  "Customer ESG procurement criteria"),
    ("Transition-Market",  "Investor divestment from fossil-linked assets"),
    ("Transition-Market",  "Bank lending tied to transition plan quality"),
    ("Transition-Market",  "Insurance premium escalation for high-risk sites"),
    ("Transition-Market",  "Workforce transition — coal-linked roles"),
    ("Transition-Market",  "Reputational risk — transition plan credibility"),
]
CRR_TIME_H = ["Short (0-2 yr)", "Medium (2-5 yr)", "Long (5-10 yr)", "Very Long (10-30 yr)"]
CRR_LIKELIHOOD = ["Rare", "Possible", "Likely", "Almost Certain"]
CRR_STATUS = ["Open", "Mitigating", "Mitigating", "Mitigating", "Closed"]
CRR_OWNERS = ["CRO Office", "EHS Director", "Treasury", "Plant Operations",
              "Sustainability — Climate", "Procurement", "Strategy & Planning",
              "Investor Relations", "Legal & Compliance", "Group HR"]
CRR_BU = [bu for bu, _ in BUSINESS_UNITS]


def gen_climate_risk_register() -> Path:
    rows = []
    seq = 0
    # Multiple analysis cycles per risk × scenario × time-horizon × business unit.
    for category, risk_text in CRR_RISKS:
        for scenario in CFI_SCENARIOS:
            for horizon in CRR_TIME_H:
                # Sample more business units affected (heat-map cells per risk)
                for bu in random.sample(CRR_BU, k=random.randint(5, 10)):
                    seq += 1
                    likelihood = random.choices(CRR_LIKELIHOOD, weights=[0.20, 0.40, 0.30, 0.10])[0]
                    impact = random.lognormvariate(2.0, 1.4)  # INR Cr; lognormal heavy tail
                    impact = max(0.5, min(impact, 1500))
                    mitigation = random.choice([
                        "Site-level adaptation plan",
                        "Insurance coverage expanded",
                        "Capex earmarked in 5-yr plan",
                        "Vendor diversification programme",
                        "Engineering controls — process",
                        "Supplier contract pass-through",
                        "Hedging via carbon market",
                        "PPA conversion to renewables",
                        "Workforce reskilling programme",
                        "Customer transition partnership",
                    ])
                    rows.append({
                        "risk_id":                     f"CR-{seq:05d}",
                        "category":                    category,
                        "scenario":                    scenario,
                        "time_horizon":                horizon,
                        "likelihood":                  likelihood,
                        "financial_impact_inr_crores": round(impact, 2),
                        "mitigation":                  mitigation,
                        "status":                      random.choice(CRR_STATUS),
                        "owner":                       random.choice(CRR_OWNERS),
                        "affected_business_unit":      bu,
                        "risk_description":            risk_text,
                    })
    path = COMPANY_DIR / "climate_risk_register.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# -----------------------------------------------------------------------------
# pollution — CSRD-E3 Pollution Prevention
# -----------------------------------------------------------------------------

POLLUTANTS = [
    # (medium, name, base_kg/qtr/facility, unit_normaliser, regulatory_limit_kg)
    ("Air",   "NOx",            6500,  "kg",  9000),
    ("Air",   "SOx",            8200,  "kg", 11000),
    ("Air",   "PM10",           1300,  "kg",  1800),
    ("Air",   "PM2.5",           780,  "kg",  1100),
    ("Air",   "VOC",            2400,  "kg",  3200),
    ("Air",   "CO",              980,  "kg",  1400),
    ("Air",   "NH3",             420,  "kg",   620),
    ("Water", "BOD",            1800,  "kg",  2500),
    ("Water", "COD",            5200,  "kg",  7000),
    ("Water", "TSS",            3400,  "kg",  4500),
    ("Water", "Oil & Grease",    280,  "kg",   400),
    ("Water", "Total Nitrogen",  640,  "kg",   900),
    ("Water", "Total Phosphorus",195,  "kg",   280),
    ("Water", "Heavy Metals (Pb)",18,  "kg",    32),
    ("Water", "Heavy Metals (Hg)", 4,  "kg",     8),
    ("Land",  "Hazardous Sludge",4300, "kg",  6200),
    ("Land",  "Spent Catalyst",  2800, "kg",  4000),
]
MONITORING_METHODS_AIR = ["CEMS — Continuous", "CEMS — Continuous", "Manual stack sampling"]
MONITORING_METHODS_WATER = ["Auto-sampler 24h composite", "Manual grab sampling",
                            "Online TOC analyser", "Auto-sampler 24h composite"]
MONITORING_METHODS_LAND = ["Manifest reconciliation", "Weighbridge data", "Lab analysis"]


def gen_pollution() -> Path:
    rows = []
    pollution_years = list(range(2017, 2025))  # 8 years
    for yi, year in enumerate(pollution_years):
        # ~3% YoY reduction trend
        decline = (1 - 0.03) ** yi
        for qi, q in enumerate(QUARTERS):
            qf = [0.27, 0.23, 0.25, 0.25][qi]
            for fac, ftype, fw in FACILITIES:
                if ftype not in ("Refinery", "Petchem", "Logistics", "R&D"):
                    # Offices have minimal pollution emissions
                    continue
                site_factor = {"Refinery": 1.4, "Petchem": 1.2,
                               "Logistics": 0.4, "R&D": 0.2}[ftype]
                for medium, pname, base, unit, lim in POLLUTANTS:
                    qty = base * decline * qf * fw * site_factor * random.uniform(0.7, 1.25)
                    if qty < 0.05:
                        continue
                    method = random.choice({
                        "Air":   MONITORING_METHODS_AIR,
                        "Water": MONITORING_METHODS_WATER,
                        "Land":  MONITORING_METHODS_LAND,
                    }[medium])
                    limit = lim * site_factor
                    exceedance = "Yes" if qty > limit * random.uniform(0.95, 1.05) else "No"
                    rows.append({
                        "year": year,
                        "quarter": q,
                        "emission_medium": medium,
                        "pollutant_type": pname,
                        "quantity_kg": round(qty, 2),
                        "location": fac,
                        "regulatory_limit_kg": round(limit, 2),
                        "monitoring_method": method,
                        "discharge_point": f"{fac[:3].upper()}-{medium[0]}-{abs(hash((fac, medium, pname))) % 9000 + 1000}",
                        "exceedance_flag": exceedance,
                        "facility_type": ftype,
                        "unit": unit,
                        "permit_id": f"PCB-{fac[:4].upper()}-{abs(hash((fac, medium))) % 90000 + 10000}",
                        "regulator": random.choice(["CPCB (Central PCB)", "GPCB (Gujarat)",
                                                    "MPCB (Maharashtra)", "TNPCB (Tamil Nadu)",
                                                    "OSPCB (Odisha)", "WBPCB (West Bengal)",
                                                    "APPCB (Andhra Pradesh)", "KSPCB (Karnataka)"]),
                        "lab_accreditation": random.choice(["NABL", "ISO 17025", "MoEF Recognised",
                                                            "NABL + ISO 17025", "External — DNV"]),
                        "test_report_id": f"TR-{year}{q}-{abs(hash((fac, medium, pname, year))) % 999999:06d}",
                    })
    path = COMPANY_DIR / "pollution.csv"
    write_csv(path, rows, list(rows[0].keys()))
    return path


# =============================================================================
# RUN
# =============================================================================

def fmt_size(p: Path) -> str:
    n = p.stat().st_size
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"


if __name__ == "__main__":
    outputs: list[tuple[str, Path]] = []

    print("== Single-company core schemas ==")
    outputs.append(("emissions",     gen_emissions()))
    outputs.append(("energy",        gen_energy()))
    outputs.append(("waste",         gen_waste()))
    outputs.append(("supply_chain",  gen_supply_chain(target_rows=7800)))
    outputs.append(("esg_metrics",   gen_esg_metrics()))
    outputs.append(("diversity",     gen_diversity()))
    outputs.append(("financials",    gen_financials()))

    print("\n== Regulatory & risk schemas ==")
    outputs.append(("materiality_assessment",      gen_materiality()))
    outputs.append(("icfr_controls",               gen_icfr_controls()))
    outputs.append(("climate_financial_impacts",   gen_climate_financial_impacts()))
    outputs.append(("climate_risk_register",       gen_climate_risk_register()))
    outputs.append(("pollution",                   gen_pollution()))

    print("\n== Peer benchmarking schemas ==")
    pf = gen_peer_financials()
    pe = gen_peer_esg()
    outputs.append(("peer_companies", gen_peer_companies()))
    outputs.append(("peer_financials", pf))
    outputs.append(("peer_esg",        pe))
    outputs.append(("peer_metrics",    gen_peer_metrics(pf, pe)))
    outputs.append(("peer_benchmark",  gen_peer_benchmark(PEER_DIR / "peer_metrics.csv")))

    print("\n== Manifest ==")
    print(f"{'schema':<22} {'rows':>8}  {'size':>10}  path")
    for name, p in outputs:
        # rows = lines - 1 header
        with p.open(encoding="utf-8") as f:
            n = sum(1 for _ in f) - 1
        rel = p.relative_to(p.parents[2])
        print(f"{name:<22} {n:>8}  {fmt_size(p):>10}  {rel}")

# ESG Pilot — Calculations Reference

Every numeric formula, weight, threshold, and magic constant in the agent pipeline, with `file:line` citations and the source-of-truth comment where one exists in code. This is the document to open when:

- An analyst asks **"how was this number computed?"**
- An auditor asks **"what is the cutoff for an A-grade audit readiness?"**
- A developer is about to change a threshold and needs to understand who else reads it.

> **Companion docs:** `RUNBOOK.md` covers architecture, deploy, and operations. `SCHEMA.md` covers the input column contracts. This file covers the math in between.

---

## How to read this document

Each agent has a section. Within each section, every distinct calculation is written as:

```
### <name of the calculation>
File:       <path>:<line range>
Formula:    <pseudocode>
Inputs:     <where each input comes from>
Output:     <variable name + unit>
Thresholds: <classification rules, if applicable>
Constants:  <every literal number with the in-code comment if one exists>
Notes:      <fallback behaviour, caps, special cases>
```

**Two classes of constants appear throughout:**

1. **Literal constants** — written directly into the agent file. These are documented inline.
2. **Config-driven constants** — accessed via `company_cfg.<group>.<attribute>`, with defaults living in `core/company_config.py`. These can be overridden per company via the profile JSON. The full default table is in [§ Config defaults](#config-defaults) below.

When a formula references e.g. `t.confidence_high`, that resolves to `company_cfg.thresholds.confidence_high` (default `80.0`) — not a literal in the agent file.

---

## Config defaults (`core/company_config.py`)

Every threshold and weight below is the **default** that ships with the platform. A signed-in user's profile JSON can override any of them via the `thresholds` / `risk_weights` / `audit_weights` / `confidence_weights` / `scenarios` / `sector_risk_defaults` / `action_cost_templates` keys.

### `ThresholdConfig` (`core/company_config.py:35-77`)

| Attribute | Default | Used by |
| --- | --- | --- |
| `completeness_warning` | `80.0` | Data Collector — missing-data warning trigger |
| `completeness_pass` | `90.0` | (reference value) |
| `confidence_high` | `80.0` | Data Collector — trust level "High" |
| `confidence_medium` | `60.0` | Data Collector — trust level "Medium" |
| `confidence_audit_ready` | `75.0` | Data Collector — `audit_ready` flag |
| `quality_issue_completeness` | `90.0` | Data Collector — triggers HF zero-shot quality classification |
| `low_confidence_alert` | `75.0` | Data Collector — `"moderate concern"` flag |
| `source_bonus_real` | `25.0` | Data Collector — confidence bonus for `real_*` sources |
| `source_bonus_connector` | `20.0` | Data Collector — confidence bonus for `connector_*` sources |
| `source_bonus_sample` | `10.0` | Data Collector — confidence bonus for sample data |
| `freshness_bonus` | `18.0` | Data Collector — assumed freshness for sample data |
| `audit_completeness_pass` | `90.0` | Audit Agent — completeness `"Pass"` cutoff |
| `audit_completeness_warning` | `70.0` | Audit Agent — completeness `"Warning"` cutoff |
| `audit_compliance_pass` | `80.0` | Audit Agent — compliance `"Pass"` cutoff |
| `audit_compliance_warning` | `60.0` | Audit Agent — compliance `"Warning"` cutoff |
| `audit_evidence_verifiable` | `0.8` | Audit Agent — confidence cutoff for `verifiable=true` |
| `audit_grade_a` | `90.0` | Audit Agent — readiness grade A |
| `audit_grade_b` | `75.0` | Audit Agent — readiness grade B |
| `audit_grade_c` | `60.0` | Audit Agent — readiness grade C |
| `risk_low` | `30.0` | Risk Predictor — climate risk level "Low" |
| `risk_medium` | `60.0` | Risk Predictor — climate risk level "Medium" |
| `rating_a` | `90.0` | Risk Predictor — ESG rating "A" |
| `rating_a_minus` | `80.0` | Risk Predictor — ESG rating "A-" |
| `rating_bbb_plus` | `70.0` | Risk Predictor — ESG rating "BBB+" |
| `rating_bbb` | `60.0` | Risk Predictor — ESG rating "BBB" |
| `transition_risk_trigger` | `50.0` | Action Agent — flag transition-risk action |
| `evidence_score_trigger` | `80.0` | Action Agent — flag evidence-doc action |
| `renewable_low_trigger` | `50.0` | Action Agent — flag solar-installation action |
| `yoy_reduction_insufficient` | `-10.0` | Action Agent — flag renewable-procurement action when emissions aren't dropping ≥10% YoY |

### `RiskWeightConfig` (`core/company_config.py:80-85`)

Composite weights for the climate risk score. Must sum to 1.0.

| Attribute | Default |
| --- | --- |
| `physical` | `0.25` |
| `transition` | `0.45` |
| `emission` | `0.30` |

### `AuditWeightConfig` (`core/company_config.py:88-93`)

Composite weights for audit readiness.

| Attribute | Default |
| --- | --- |
| `completeness` | `0.30` |
| `compliance` | `0.40` |
| `evidence` | `0.30` |

### `ConfidenceWeightConfig` (`core/company_config.py:96-101`)

Composite weights for per-dataset confidence score.

| Attribute | Default |
| --- | --- |
| `completeness` | `0.4` |
| `raw_confidence` | `0.4` |
| `freshness` | `0.2` |

### `ScenarioConfig` (`core/company_config.py:104-120`)

| Scenario | `*_reduction_pct` | `*_rating` | `*_investment` | `*_timeline` |
| --- | --- | --- | --- | --- |
| Best (`best_*`) | `35.0` | `A` | `High` | `18-24 months` |
| Base (`base_*`) | `18.0` | `A-` | `Medium` | `12-18 months` |
| Worst (`worst_*`) | `5.0` | `BBB` | `Low` | `24+ months` |

### `SectorRiskDefaults` (`core/company_config.py:124-139`)

| Attribute | Default | Description |
| --- | --- | --- |
| `physical_risk` | `28.0` | Climate physical exposure (low for IT-services default) |
| `transition_risk_base` | `52.0` | Pre-compliance baseline for transition risk |
| `emission_risk_base` | `35.0` | Default when no YoY trend data |
| `emission_risk_max` | `80.0` | Cap when emissions rising |
| `emission_risk_min` | `15.0` | Floor when emissions falling |
| `emission_risk_midpoint` | `50.0` | Anchor around which trend deviations are added/subtracted |
| `reputational_risk` | `35.0` | (informational) |
| `supply_chain_risk` | `55.0` | (informational) |
| `compliance_baseline` | `75.0` | Used if `regulatory_results.overall_compliance` is missing |
| `confidence_cap` | `95.0` | Max for ESG-rating prediction confidence |
| `confidence_boost` | `10.0` | Added to `met_pct` for confidence calc |

### `ActionCostTemplate` (`core/company_config.py:142-166`)

Cost values are in `company_cfg.currency_unit` (default `INR lakhs`).

| Action | Cost | Duration (weeks) |
| --- | --- | --- |
| Supplier engagement | `50.0` | `12` |
| Overdue audit closure | `25.0` | `8` |
| Transition risk mitigation | `100.0` | `16` |
| Compliance remediation | `15.0` | `6` |
| Evidence documentation | `10.0` | `8` |
| Renewable energy procurement | `150.0` | `20` |
| Scope 3 supplier program | `40.0` | `16` |
| Solar installation | `200.0` | `24` |
| Regulatory gap closure | `30.0` | `10` |

---

## Agent 1 — Data Collector (`agents/data_collector.py`)

### Per-dataset completeness

**File:** `agents/data_collector.py` (called per dataset in Phase 5)
**Formula:**
```
completeness = (non_null_cells / total_cells) × 100
```
**Output:** `quality_scores[dataset]["completeness"]` — percentage.

### Overall completeness & confidence

**File:** `agents/data_collector.py:144-149`
**Formula:**
```
overall_completeness = mean(q["completeness"] for q in quality_scores.values())
overall_confidence   = mean(q["avg_confidence"] for q in quality_scores.values()
                            if q["avg_confidence"] > 0)
```
**Output:** rounded to 1 decimal place at `:167-168`.
**Notes:** confidence mean **excludes** zero-confidence datasets so missing-but-loaded data doesn't deflate the score.

### Missing-data warning trigger

**File:** `agents/data_collector.py:207`
**Rule:** `completeness < t.completeness_warning` → emit `"warning"` alert.
**Threshold (default):** `80.0` — `t.completeness_warning`.
**Critical alert:** dataset entirely missing → `"critical"` alert (no threshold; binary).

### Per-dataset confidence score

**File:** `agents/data_collector.py:242-276`
**Formula:**
```
source_bonus = t.source_bonus_real        if name.startswith("real_")
             else t.source_bonus_connector if name.startswith("connector_")
             else t.source_bonus_sample

weighted = completeness     × cw.completeness
         + raw_confidence   × cw.raw_confidence
         + source_bonus
         + t.freshness_bonus × cw.freshness

score = min(100, round(weighted, 1))
```
**Inputs (defaults):**

| Symbol | Source | Default |
| --- | --- | --- |
| `cw.completeness` | `confidence_weights.completeness` | `0.4` |
| `cw.raw_confidence` | `confidence_weights.raw_confidence` | `0.4` |
| `cw.freshness` | `confidence_weights.freshness` | `0.2` |
| `t.source_bonus_real` | `thresholds.source_bonus_real` | `25.0` |
| `t.source_bonus_connector` | `thresholds.source_bonus_connector` | `20.0` |
| `t.source_bonus_sample` | `thresholds.source_bonus_sample` | `10.0` |
| `t.freshness_bonus` | `thresholds.freshness_bonus` | `18.0` |

**Trust-level classification:**
```
score >= t.confidence_high           → "High"
score >= t.confidence_medium         → "Medium"
otherwise                            → "Low"
audit_ready = (score >= t.confidence_audit_ready)
```
**Default cutoffs:** High ≥ 80, Medium ≥ 60, audit-ready ≥ 75.

### Quality-issue classification

**File:** `agents/data_collector.py:278-302`
**Trigger:** `completeness < t.quality_issue_completeness` (default `90`).
**HF call:** zero-shot classification with labels `["critical issue", "moderate concern", "minor issue"]`.
**Additional flag:** `0 < avg_confidence < t.low_confidence_alert` (default `75`) → append `"moderate concern"`.

---

## Agent 2 — Regulatory Tracker (`agents/regulatory_tracker.py`)

### Data field → metric ID mapping (52 entries)

**File:** `agents/regulatory_tracker.py:10-54`
Static dictionary mapping raw data-field names to lists of metric IDs (E01–E10, S01–S12, G01–G07). Highlights:

| Data field | Metric IDs |
| --- | --- |
| `emissions_scope1`, `emissions_scope2`, `emissions_all_scopes` | `E01`, `E02` |
| `renewable_energy_pct` | `E03` |
| `water_consumption` / `water_recycling` | `E04` / `E05` |
| `waste_generated` / `waste_recycled` / `hazardous_waste` | `E06` / `E07` / `E08` |
| `biodiversity_impact`, `land_use` | `E09` |
| `energy_consumption` | `E10` |
| `gender_diversity`, `diversity` | `S03`, `S04` |
| `pay_equity` | `S05` |
| `ltifr`, `safety_training` | `S06`, `S07` |
| `board_governance` | `G01`, `G02`, `G03` |
| `anti_corruption_training` | `G04` |
| `whistleblower` | `G05` |
| `data_privacy`, `data_breaches` | `G07` |

### Requirement classification

**File:** `agents/regulatory_tracker.py:100-166`
For each requirement in the framework:

| Condition | Status | Counted as |
| --- | --- | --- |
| `all_required_metrics ⊆ available_metrics` | `covered` | full credit |
| Non-empty intersection but not full | `partial` | half credit (see below), added to gaps list |
| No intersection | `missing` | zero credit, added to gaps list |
| `all_required_metrics` is empty (no mapping defined) | `missing` | zero credit, reason = "No data mapping available" |

### Compliance percentage (with partial credit)

**File:** `agents/regulatory_tracker.py:169`
**Formula:**
```
compliance_pct = round( (covered + partial × 0.5) / total × 100, 1 )
```
**Magic constant:** `0.5` — the **partial-credit weight**. Not config-driven; not commented in code.
**Fallback:** returns `0` when `total == 0`.

### Overall compliance

**File:** `agents/regulatory_tracker.py:86-87`
**Formula:**
```
overall_compliance = round( mean(r["compliance_pct"]
                                  for r in framework_results.values()), 1 )
```

### Gap narrative (LLM prompt input)

**File:** `agents/regulatory_tracker.py:192`
Top **5** critical gaps (`[:5]`) are passed to the HF text-generation prompt. Magic constant `5` — not commented.

### Reporter profile classification

**File:** `agents/regulatory_tracker.py:197-229`
```
is_listed_india        = any exchange in {"BSE", "NSE"}
mandatory_due_to_listing = is_listed_india AND "BRSR" in adopted

if mandatory_due_to_listing OR any mandatory_frameworks:
    → "Mandatory Reporter"
else:
    → "Voluntary Reporter"
```
This profile is reused in the Stakeholder Agent (audience tone) and Report Generator (framing).

---

## Agent 3 — Carbon Accountant (`agents/carbon_accountant.py`)

### Scope totals

**File:** `agents/carbon_accountant.py` (Phase 1)
**Formula:**
```
scope_totals_year = emissions_df[year == Y].groupby("scope")["emissions_tco2e"].sum()
```
Repeated for `current_fy` and `previous_fy` (resolved from `company_cfg`).

### Year-over-year change

**File:** `agents/carbon_accountant.py:54-56`
**Formula:**
```
yoy_change_pct = round( (total_current - total_previous) / total_previous × 100, 1 )
```
**Fallback:** `0` when `total_previous == 0`.

### Carbon intensity (tCO2e per $M revenue)

**File:** `agents/carbon_accountant.py:62-65`
**Formula:**
```
carbon_intensity      = round( total_current  / company_cfg.revenue("current"),  1 )
carbon_intensity_prev = round( total_previous / company_cfg.revenue("previous"), 1 )
```
**Fallback:** `0` when revenue is `0` or `None`.

### Supply-chain hotspots

**File:** `agents/carbon_accountant.py:114`
**Formula:**
```
hotspots = supply_chain_df[risk_rating == "High"]
            .sort_values("emission_contribution_tco2e", ascending=False)
            .head(5)
```
**Magic constant:** `5` — top-N cap.

### Renewable share

**File:** `agents/carbon_accountant.py:133-135`
**Formula:**
```
renewable_pct = round( renewable_mwh / total_mwh × 100, 1 )
```

### Cost linkage — emission reduction savings

**File:** `agents/carbon_accountant.py:145-150`
**Formula:**
```
reduction_tco2e      = max(0, total_prev - total_curr)
cost_per_tco2e       = 0.0015                       # INR crores per tCO2e
emission_cost_saving = round(reduction_tco2e × cost_per_tco2e, 2)
```
**Magic constant `0.0015`:** in-code comment at `:148` reads *"Average cost per tCO2e avoided (carbon credit proxy ~INR 1500/tCO2e)"* — i.e. INR 1,500 per tCO2e expressed in crores.

### Cost linkage — energy savings

**File:** `agents/carbon_accountant.py:152-161`
**Formula:**
```
energy_saving = round( max(0, prev_cost_lakhs - curr_cost_lakhs) / 100, 2 )
                                                      # lakhs → crores
```
**Magic constant `100`:** lakhs-to-crores conversion (inline comment).

### Scope 2 renewable opportunity

**File:** `agents/carbon_accountant.py:172`
**Formula:**
```
scope2_opportunity = round( (100 - renewable_pct) × 0.3, 1 )   # INR crores
```
**Magic constant `0.3`:** "% achievable" (inline comment). The economic basis for this assumed-achievable share is **not cited in code**.

### Carbon tax risk

**File:** `agents/carbon_accountant.py:187-214`
**Formulas:**
```
taxable_emissions   = scope1 + scope2                                   # tCO2e
current_rate        = 400                                                # INR/tCO2e
cbam_rate           = 7200                                               # INR/tCO2e (EU CBAM proxy)

current_exposure    = round( taxable_emissions × 400  / 100_000, 2 )    # INR crores
cbam_exposure       = round( taxable_emissions × 7200 / 100_000, 2 )    # INR crores
future_exposure_3yr = round( current_exposure × (1.10 ** 3), 2 )

mitigation_potential_pct = round( min(35, abs(yoy_change) × 2), 1 )
```
**Risk level:**
```
current_exposure > 5  → "High"
current_exposure > 2  → "Medium"
otherwise             → "Low"
```
**Constants & comments:**

| Value | Line | Comment |
| --- | --- | --- |
| `400` | 190 | "Current Indian carbon tax equivalent (~INR 400/tCO2e)" |
| `7200` | 192 | "EU CBAM rate (~EUR 80 = ~INR 7200/tCO2e) for export exposure" |
| `100_000` | 195/197 | tCO2e·INR → INR crores conversion |
| `1.10 ** 3` | 202 | "assume 10% annual rate increase" |
| `5`, `2` | 204 | High / Medium thresholds (INR crores). **No source comment.** |
| `35`, `2` | 213 | Cap on mitigation potential, multiplier on `abs(yoy_change)`. **No source comment.** |

---

## Agent 4 — Risk Predictor (`agents/risk_predictor.py`)

### Climate risk score (composite)

**File:** `agents/risk_predictor.py:76-104`
**Component formulas:**
```
physical_risk = sr.physical_risk                             # default 28.0

# Transition risk: scaled by regulatory compliance
if regulatory_results present:
    compliance      = regulatory_results["overall_compliance"]
                     or sr.compliance_baseline               # default 75.0
    transition_risk = max(20, 100 - compliance)
else:
    transition_risk = sr.transition_risk_base                # default 52.0

# Emission trajectory risk
if latest > prev:
    emission_risk = min(sr.emission_risk_max,                # default 80.0
                        sr.emission_risk_midpoint            # default 50.0
                        + (latest - prev)/prev × 100)
else:
    emission_risk = max(sr.emission_risk_min,                # default 15.0
                        sr.emission_risk_midpoint
                        - (prev - latest)/prev × 100)

overall = round( physical_risk   × rw.physical               # default 0.25
               + transition_risk × rw.transition             # default 0.45
               + emission_risk   × rw.emission,              # default 0.30
                 1 )
```
**Risk-level classification (`:451-457`):**
```
score < t.risk_low    → "Low"      # default < 30
score < t.risk_medium → "Medium"   # default < 60
otherwise             → "High"
```
**Literal constant `20`:** floor in `max(20, 100 - compliance)`. Not config-driven.

### ESG rating prediction

**File:** `agents/risk_predictor.py:144-174`
**Formulas:**
```
met_pct = (status == "Met").sum() / total × 100

# Letter grade
met_pct >= t.rating_a         → "A"      # default >= 90
met_pct >= t.rating_a_minus   → "A-"     # default >= 80
met_pct >= t.rating_bbb_plus  → "BBB+"   # default >= 70
met_pct >= t.rating_bbb       → "BBB"    # default >= 60
otherwise                     → "BB+"

confidence = round( min(sr.confidence_cap,                   # default 95
                        met_pct + sr.confidence_boost),      # default +10
                    1 )

# Per-pillar
pillar_score = round( (status=="Met").sum() / len(pillar_df) × 100, 1 )
                                                              # for E, S, G
```

### Multi-agency rating translations

#### MSCI-style (`agents/risk_predictor.py:285-294`)
```
met_pct >= 90 → "AA"
met_pct >= 80 → "A"
met_pct >= 70 → "BBB"
met_pct >= 60 → "BB"
otherwise     → "B"
```
**Constants `90/80/70/60`:** literal in code, **not config-driven**, **not source-cited**.

#### Sustainalytics-style (`agents/risk_predictor.py:297-307`)
```
sust_risk = round( max(5, 50 - met_pct × 0.45), 1 )

sust_risk < 10 → "Negligible"
sust_risk < 20 → "Low"
sust_risk < 30 → "Medium"
sust_risk < 40 → "High"
otherwise      → "Severe"
```
**Constants:** `5` floor, `50` anchor, `0.45` slope; category cutoffs `10/20/30/40`. None source-cited.

#### CDP-style (`agents/risk_predictor.py:310-319`)
Based on `env_score` (Environmental pillar `met_pct`):
```
env_score >= 85 → "A"
env_score >= 70 → "A-"
env_score >= 55 → "B"
env_score >= 40 → "B-"
otherwise       → "C"
```

### Scenario analysis

**File:** `agents/risk_predictor.py:222-262`
**Formula per scenario:**
```
projected_emissions = round( base_total × (1 - sc.<scenario>_reduction_pct / 100), 0 )
```
The reduction percentages, projected ratings, investment levels, and timelines all live in `company_cfg.scenarios` (defaults in [§ Config defaults](#scenarioconfig-corecompany_configpy104-120)).

### Supplier risk analysis

**File:** `agents/risk_predictor.py` (Phase: supplier risk)
```
high_risk_count = count(supply_chain_df[risk_rating == "High"])
overdue_audits  = count(supply_chain_df[audit_status == "Overdue"])
avg_esg_score   = mean(supply_chain_df.esg_score)
```

### Market regime detection

**File:** `agents/risk_predictor.py:331-387`
Requires the most recent **4** quarters of financial data.
```
rev_trend    = mean(recent_4.revenue.pct_change())
margin_trend = mean(recent_4.ebitda_margin_pct.diff())
pe_trend     = mean(recent_4.pe_ratio.diff())
volatility   = std (recent_4.revenue.pct_change())
```
**Classification:**
```
rev_trend >  0.01  AND margin_trend >  0     → "Bull"
rev_trend < -0.005 OR  margin_trend < -0.5   → "Stress"
otherwise                                     → "Transition"
```
**Confidence:**
```
Bull       → min(90, 60 + rev_trend × 1000)
Stress     → min(85, 60 + abs(rev_trend) × 1000)
Transition → 55
```
**Constants & rationale:**

| Value | Meaning | Comment in code |
| --- | --- | --- |
| `4` | Recent quarter window | none |
| `0.01` | Bull rev-trend threshold (~1% QoQ) | none |
| `-0.005` | Stress rev-trend trigger | none |
| `0` | Margin-trend gate for Bull | none |
| `-0.5` | Margin-trend gate for Stress (bps drop) | none |
| `60`, `1000`, `90`, `85`, `55` | Confidence anchors and the basis-point scaling | none |

### Downside Protection Score (DPS)

**File:** `agents/risk_predictor.py:389-449`
**Components:**
```
# 1. Governance strength
gov_score      = (Governance.status == "Met").sum() / len(Governance) × 100
                                                              # default 50.0 if empty

# 2. Financial resilience
fin_resilience = min(100, max(0,
                              (1 - debt_equity) × 50 + ebitda_margin × 2))
                                                              # defaults: D/E=0.5, margin=20

# 3. ESG momentum
esg_momentum   = min(100, met_pct × 1.2)                      # default 50.0

# 4. Climate risk shield
climate_shield = max(0, 100 - overall_climate_risk)

# Composite
dps = round(
    gov_score      × 0.30
  + fin_resilience × 0.25
  + esg_momentum   × 0.25
  + climate_shield × 0.20,
  1
)
```
**Levels:**
```
dps >= 70 → "Strong"
dps >= 50 → "Moderate"
otherwise → "Weak"
```
**Constants used:** weights `0.30/0.25/0.25/0.20` (literals); financial-resilience anchors `50` (D/E coefficient) and `2` (margin multiplier); momentum boost `1.2`; defaults `D/E=0.5`, `margin=20`; level cutoffs `70/50`. Each component has an inline docstring comment.

---

## Agent 5 — Audit Agent (`agents/audit_agent.py`)

### Data completeness audit

**File:** `agents/audit_agent.py:81-94`
**Expected datasets and priorities:**

| Dataset | Priority |
| --- | --- |
| `emissions` | critical |
| `esg_metrics` | critical |
| `supply_chain` | high |
| `energy` | high |
| `waste` | medium |
| `diversity` | medium |
| `financials` | high |

**Status:**
```
completeness >= t.audit_completeness_pass    → "Pass"     # default >= 90
completeness >= t.audit_completeness_warning → "Warning"  # default >= 70
otherwise                                     → "Fail"
dataset not found                             → "Missing"
```

### Compliance checklist

**File:** `agents/audit_agent.py:122-148`
**Per-framework status:**
```
score >= t.audit_compliance_pass    → "Pass"     # default >= 80
score >= t.audit_compliance_warning → "Warning"  # default >= 60
otherwise                            → "Fail"
```

**General audit checks (hard-coded scores, `:137-143`):**

| Check | Score | Status |
| --- | --- | --- |
| Data Traceability | `88` | Pass |
| Confidence Scoring | `82` | Pass |
| Year-over-Year Comparability | `95` | Pass |
| Third-Party Verification | `70` | Warning |
| Board ESG Oversight | `90` | Pass |
| Materiality Assessment | `60` | Warning |

**Caveat:** these six scores are static placeholders with no source link to underlying data. They influence the audit-readiness composite below.

### Evidence verifiability

**File:** `agents/audit_agent.py:168-174`
```
verifiable = (confidence >= t.audit_evidence_verifiable)   # default >= 0.8
```

### Audit readiness score

**File:** `agents/audit_agent.py:177-209`
```
completeness_avg = mean(completeness for item in completeness_audit
                         if completeness > 0)
compliance_avg   = mean(score for item in compliance_checklist
                         if "score" in item)
evidence_pct     = verifiable_count / len(evidence_map) × 100

total = round(
    completeness_avg × aw.completeness     # default 0.30
  + compliance_avg   × aw.compliance       # default 0.40
  + evidence_pct     × aw.evidence,        # default 0.30
  1
)
```
**Grade:**
```
total >= t.audit_grade_a → "A"   # default >= 90
total >= t.audit_grade_b → "B"   # default >= 75
total >= t.audit_grade_c → "C"   # default >= 60
otherwise                → "D"
```

### Integrity gap detector

**File:** `agents/audit_agent.py:246-321`
Cross-references self-reported metrics against operational data.

**Carbon-intensity check (`:246-260`):**
```
derived_value = round( fy_emissions / company_cfg.revenue("current"), 1 )
mismatch if abs(reported - derived) / max(reported, 0.01) > 0.15
```
**Constants:** `0.15` (15% relative deviation), `0.01` (min-denominator guard).

**Renewable-% check (`:262-277`):**
```
derived_value = round( renewable_mwh / total_mwh × 100, 1 )
mismatch if abs(reported - derived) > 5
```
**Constant:** `5` percentage points absolute deviation.

**"Met but below target" heuristic (`:280-288`):**
```
if status == "Met" and reported / target < 0.90:
    flag as suspicious
```
**Constant:** `0.90`.

**Mismatch risk level (`:303-308`):**
```
mismatch_pct > 30 → "Critical"
mismatch_pct > 15 → "High"
mismatch_pct > 5  → "Medium"
otherwise         → "Low"
```

**Severity tagging (`:300`):**
```
severity = "High" if derived_value else "Medium"
```

**Recommendation (`:317-321`):**
```
mismatch_pct > 15 → "Significant integrity gaps detected — initiate
                     data reconciliation and third-party verification..."
otherwise         → "Integrity checks passed with minor discrepancies."
```

---

## Agent 6 — ESG ROI Agent (`agents/roi_agent.py`)

### Energy savings proxy

**File:** `agents/roi_agent.py:100-102`
```
energy_prev_approx = energy_cost × 1.08          # "~8% higher previous year"
energy_savings     = round(energy_prev_approx - energy_cost, 2)
```
**Constant `1.08`:** inline comment "~8% higher previous year".

### Carbon tax avoided

**File:** `agents/roi_agent.py:104-106`
```
carbon_tax_saving = round( carbon_tax_curr × 0.15, 2 )   # ~15% avoided via reduction
```
**Constant `0.15`:** inline comment.

### Total savings & financial ROI

**File:** `agents/roi_agent.py:108-109`
```
total_savings = round( emission_savings + energy_savings + carbon_tax_saving, 2 )
roi_pct       = round( total_savings / total_capex × 100, 1 )   if total_capex else 0
```

### ESG revenue uplift

**File:** `agents/roi_agent.py:111-116`
```
esg_revenue_uplift = round( revenue_current_fy × (rev_growth / 100) × 0.20, 2 )
```
**Constant `0.20`:** inline comment "Attribute ~20% of growth to ESG brand effect".

### Payback years

**File:** `agents/roi_agent.py:129`
```
payback_years = round( total_capex / total_savings, 1 )   if total_savings > 0 else None
```

### Strategic ROI components

**File:** `agents/roi_agent.py:141-158`
**Cost-of-capital reduction:**
```
coc_reduction      = max(0, 12 - cost_of_capital)            # baseline ~12%
risk_value         = round( market_cap × coc_reduction / 100, 2 )
cost_of_capital_reduction_bps = round(coc_reduction × 100)
```

**Turnover savings:**
```
turnover_savings = round( max(0, 20 - turnover) × employees × 0.03, 1 )
```
**Constants:** `20` turnover baseline, `0.03` ("~30% of annual salary saved per retained employee" — the magnitude assumes a specific scaling of `employees`; **dimensional consistency depends on `company_cfg.employees`**).

**Brand premium:**
```
brand_premium = round( (brand - 50) × 0.5, 1 )    # points above 50
```

**Rating trajectory:**
```
rating_lift = "Positive" if composite_esg_financial_score > 60 else "Neutral"
```

### J-curve

**File:** `agents/roi_agent.py:187-212`
**Per-quarter benefit (`:187-195`):**
```
margin_benefit = max(0, ebitda_margin_pct - 20) × revenue / 100
energy_benefit = max(0, 30 - energy_cost_inr_crores)
cum_cost   += capex
cum_benefit += margin_benefit + energy_benefit
```
**Constants:** `20` EBITDA margin baseline %; `30` energy-cost baseline (INR crores). Neither is source-cited.

**Breakeven (`:207-212`):**
```
first quarter i > 0 with net_position >= 0  →  breakeven period
```

### Investment Quality Score (IQS)

**File:** `agents/roi_agent.py:223-292`
**Component sub-scores:**
```
fin_score    = min(100, max(0, roi_pct × 2))                      # 50% ROI → 100
channel_avg  = composite_esg_financial_score                      # from KPI engine
strat_score  = min(100, max(0, brand_premium × 3 + coc_bps / 5))
momentum     = min(100, max(0, (capex_cagr + rev_cagr) × 2))
risk_score   = Risk channel score (default 50)
```
**Composite:**
```
iqs = round(
    fin_score    × 0.25
  + channel_avg  × 0.25
  + strat_score  × 0.20
  + momentum     × 0.15
  + risk_score   × 0.15,
  1
)
```
**Grade:**
```
iqs >= 90 → "A+"
iqs >= 80 → "A"
iqs >= 70 → "B+"
iqs >= 60 → "B"
iqs >= 50 → "C"
otherwise → "D"
```
**Weights** are also returned in the output `weights` dict (`:285-291`) for transparency. **Magic constants** include `2` (ROI doubling), `3` (brand multiplier), `1/5` (coc → score scale), `2` (CAGR doubling), `50` default Risk score, and the grade cutoffs `90/80/70/60/50`. None are source-cited.

### Peer benchmarking

**File:** `agents/roi_agent.py:400-416`

**Normalisations (`:400-405`):**
```
if col in {"esg_capex_pct", "green_assets_pct"} and max <= 2.0:
    multiply by 100        # decimal → %
if col == "scope1_2_emissions" and median > 10_000:
    divide by 1000         # tCO2e → ktCO2e
```

**Percentile (`:415-416`):**
```
beats = count(v < cv if higher_is_better else v > cv for v in peers)
percentile = round(beats / n × 100)
```

### Company ESG score derivation

**File:** `agents/roi_agent.py:502-511`
```
company_esg_score = round( 40 + (met / total) × 48, 1 )
                   # 100% met → ~88, 0% met → ~40
```

### Scope 1+2 kt conversion

**File:** `agents/roi_agent.py:379`
```
company_scope12_kt = round( (scope1 + scope2) / 1000, 1 )
```

---

## Agent 7 — Action Agent (`agents/action_agent.py`)

### Recommendation triggers

**File:** `agents/action_agent.py:79-218`

| Trigger | Source | Priority | Action |
| --- | --- | --- | --- |
| `supplier_risks.high_risk_count > 0` | Risk Predictor | Critical | Supplier engagement program |
| `supplier_risks.overdue_audits > 0` | Risk Predictor | High | Audit closure |
| `climate_risks.transition_risk > t.transition_risk_trigger` (default 50) | Risk Predictor | High | "Accelerate transition risk mitigation" — Impact: "Reduce transition risk score by 20 points" |
| Audit checklist item with `status == "Fail"` | Audit Agent | Critical | Per-failure remediation action |
| `readiness_score.evidence < t.evidence_score_trigger` (default 80) | Audit Agent | Medium | "Strengthen evidence documentation" — Impact: "Improve evidence score to 90%+" |
| `yoy_change_pct > t.yoy_reduction_insufficient` (default `-10`) | Carbon Accountant | High | "Increase renewable energy procurement to 60%" — Impact: "Reduce Scope 2 emissions by 25%" |
| `len(hotspots) > 0` | Carbon Accountant | High | Engage top-5 emission-intensive suppliers — Impact: "Target 15% Scope 3 reduction" |
| `energy_analysis.renewable_pct < t.renewable_low_trigger` (default 50) | Carbon Accountant | Medium | Solar installation |
| Any framework with `priority == "critical"` gaps | Regulatory Tracker | Critical | "Address critical {fw} compliance gaps" |

### Deduplication & ordering

**File:** `agents/action_agent.py:222-240`
```
dedupe key = action[:50]                                  # first 50 chars
priority order = {"Critical": 0, "High": 1,
                  "Medium":   2, "Low":  3}
start_date[i]  = today + weeks(i × 2)
end_date[i]    = today + weeks(i × 2 + duration_weeks)
```
**Constant `2`:** weeks-per-action stagger.

### Implementation friction

**File:** `agents/action_agent.py:252-272`
**Adjustment lookup tables:**
```
regime_adj   = {"Bull":0, "Transition":2, "Stress":5}      # default 2
category_adj = {"Compliance":4, "Regulatory":5,
                "Supply Chain":6, "Climate":4,
                "Emissions":4, "Scope 3":6,
                "Energy":5, "Audit Readiness":2}            # default 3
```
**Friction percentage:**
```
friction_pct = 6 + duration_weeks × 0.35 + category_adj + regime_adj
```
**Constants `6` (base) and `0.35` (duration coefficient):** literal, not source-cited.

### Transaction cost & adjusted cost

**File:** `agents/action_agent.py:273-274`
```
transaction_cost = round( base_cost × friction_pct / 100, 2 )
adjusted_cost    = round( base_cost + transaction_cost,    2 )
```

### Gross benefit

**File:** `agents/action_agent.py:276-287`
**Multipliers by category:**
```
{
  "Compliance":      1.15,
  "Regulatory":      1.20,
  "Supply Chain":    1.35,
  "Climate":         1.30,
  "Emissions":       1.25,
  "Scope 3":         1.30,
  "Energy":          1.28,
  "Audit Readiness": 1.10,
}                                                          # default 1.15
```
**Formula:**
```
anchor_share  = max(0, roi_anchor × 0.08)
gross_benefit = round( max(base_cost × benefit_multiplier,
                            base_cost + anchor_share), 2 )
```
**Constant `0.08`:** anchor share of ROI; not source-cited.

### Net value & net ROI

**File:** `agents/action_agent.py:288-289`
```
net_value   = round( gross_benefit - adjusted_cost, 2 )
net_roi_pct = round( net_value / adjusted_cost × 100, 1 )   if adjusted_cost else 0
```

### Liquidity risk

**File:** `agents/action_agent.py:291-296`
```
spend_ratio_pct = adjusted_cost / current_revenue × 100

spend_ratio_pct > 4 → "High"
spend_ratio_pct > 2 → "Medium"
otherwise           → "Low"
```

### Implementation friction score

**File:** `agents/action_agent.py:297-305`
```
friction_score = min(100, round(
      friction_pct × 2
    + (10 if liquidity_risk == "High"
       else 5 if liquidity_risk == "Medium"
       else 0)
    + max(0, 60 - risk_anchor) × 0.2,
    1
))
```

### Execution mode

**File:** `agents/action_agent.py:314-317`
```
friction_score >= 60 OR liquidity_risk != "Low" → "Phased rollout"
otherwise                                        → "Accelerated rollout"
```

### Target recommendations

**File:** `agents/action_agent.py:327-387`

| Target | Formula | Deadline | Linked actions |
| --- | --- | --- | --- |
| Renewable Energy Share | `round(max(current + 10, 60), 1)` | `{cy+1}-12-31` | first 2 in `{Energy, Emissions}` |
| Overall Regulatory Compliance | `round(min(100, max(current + 8, 90)), 1)` | `{cy+1}-09-30` | first 3 in `{Compliance, Regulatory}` |
| Evidence Verifiability | `round(min(100, max(current + 10, 90)), 1)` | `{cy+1}-06-30` | first 2 in `{Audit Readiness}` |
| High-Risk Suppliers | `max(0, high_risk_count - 2)` | `{cy+1}-12-31` | — |
| ESG Investment Quality Score | `round(min(100, max(iqs_current + 8, 75)), 1)` | `{cy+1}-12-31` | — |

`cy` = current calendar year.

---

## Agent 8 — Stakeholder Agent (`agents/stakeholder_agent.py`)

### Audience profiles

**File:** `agents/stakeholder_agent.py:12-37`
Static dict. No numeric formula — defines `tone`, `focus`, and `format` per audience (`investors`, `regulators`, `employees`, `public`).

### Per-audience metric selection

**File:** `agents/stakeholder_agent.py:163-190`

| Audience | Adds to base set |
| --- | --- |
| Base (always) | Total Emissions, YoY Change |
| Investors | + ESG Rating, Carbon Intensity, Risk Score |
| Regulators | + Compliance %, Pending Actions (critical count) |
| Employees | + Renewable Energy % |
| Public | + Renewable Energy %, ESG Rating |

### Business case recommendation

**File:** `agents/stakeholder_agent.py:221`
```
iqs.score >= 60 → "Increase ESG CapEx allocation"
otherwise       → "Maintain current ESG spend, focus on high-ROI initiatives"
```

### J-curve framing (`:224-266`)
```
trough = min(quarters, key=net_position)
status = "Payback achieved" if net >= 0 else "In investment phase"
```
No additional numeric constants beyond the sentinel `0`.

---

## Agent 9 — Report Generator (`agents/report_generator.py`)

The Report Generator does not introduce new numeric formulas; it reads upstream agent outputs and assembles them. Two notable behaviours:

### FY column resolution

**File:** `agents/report_generator.py:143-144, 166-168`
```
prefer "value_{current_fy}"   else "value_2024"
prefer "value_{previous_fy}"  else "value_2023"
prefer "target_{current_fy}"  else "target_2024"
```
**Magic constants `2024` / `2023`:** static fallbacks for older sample data.

### Upstream values consumed

| Source channel | Field | Used in |
| --- | --- | --- |
| `carbon_results` | `total_emissions_current`, `yoy_change_pct`, `carbon_intensity` | Carbon highlights |
| `regulatory_results` | `overall_compliance`, per-framework `compliance_pct` | Compliance summary, per-framework sections |
| `roi_results` | `investment_quality_score`, `financial_roi` | ROI snapshot |
| `audit_results` | various | Audit trail |

The five Gradio report types (Full ESG, Framework Compliance, Carbon & Environment, Social & Governance, Executive Summary) only differ in which sections they emit — same underlying numbers.

---

## KPI Engine (`core/kpi_engine.py`)

Powers the ROI Agent's five value-creation channels (Growth, Cost, Risk, Human Capital, Capital Efficiency).

### Financial summary

**File:** `core/kpi_engine.py:85-115`
```
rev_growth = round( (rev_curr - rev_prev) / rev_prev × 100, 1 )
```
Plus a flat dictionary of latest/prior values (all rounded to 1 dp except `debt_equity_latest` which is 2 dp): `revenue_current_fy`, `revenue_previous_fy`, `ebitda_margin_latest`, `roa_latest`, `roe_latest`, `debt_equity_latest`, `cost_of_capital_latest`, `pe_ratio_latest`, `carbon_tax_exposure_latest`, `energy_cost_latest`, `employee_turnover_latest`, `brand_value_index`, `talent_retention_score`, `esg_capex_current_fy`, `esg_capex_previous_fy`.

### ESG ↔ financial correlations (heuristic, not Pearson)

**File:** `core/kpi_engine.py:119-158`
```
if fin_metric in {"Cost of Capital"} OR esg_metric in {"Turnover", "Tax"}:
    corr = -0.6 if met_pct > 60 else -0.3
    direction = "negative"
else:
    corr =  0.7 if met_pct > 60 else  0.4
    direction = "positive"

strength = "strong"   if abs(corr) >= 0.6
         else "moderate" if abs(corr) >= 0.3
         else "weak"
```
**Preconditions:** `n >= 4` quarters; `met_pct` defaults to `50` if `esg_df` is empty.
**Constants:** correlation magnitudes `0.7 / 0.6 / 0.4 / 0.3`; threshold `met_pct > 60`; strength cutoffs `0.6 / 0.3`. None source-cited.

### Growth channel

**File:** `core/kpi_engine.py:162-183`
```
met_pct = (status == "Met").sum() / len × 100         # default 50

score   = max(0, round( min(100,
                              rev_g × 2
                            + (brand - 50)
                            + met_pct × 0.3 ), 1 ))

trend:
  rev_g > 5  → "improving"
  rev_g > 0  → "stable"
  otherwise  → "declining"

direction anchors:
  metrics[0] = "up"   if rev_g  > 0  else "down"
  metrics[1] = "up"   if brand  > 60 else "flat"
  metrics[2] = "up"   if met_pct > 70 else "flat"
```

### Cost channel

**File:** `core/kpi_engine.py:185-218`
```
score = max(0, round( min(100, margin × 3 + max(0, 50 - carbon_tax)), 1 ))
cost_saving_est = round( (prev_emissions - curr_emissions) × 0.002, 1 )
                                                # "~INR 200/tCO2e avoided cost"
trend = "improving" if margin > 21 else "stable"
```
**Direction anchors:** EBITDA Margin "up" if `> 20`; Carbon Tax "down" if `< 50` else "up"; Energy Cost "down" if `< 25` else "flat"; Emission Reduction Savings "up".

### Risk channel

**File:** `core/kpi_engine.py:220-251`
```
gov_met             = (Governance.status == "Met").sum() / len × 100   # default 0
high_risk_suppliers = (risk_rating == "High").sum()                    # default 0

score = max(0, round( min(100,
                            (100 - coc × 5)
                          + gov_met × 0.3
                          - high_risk_suppliers × 5 ), 1 ))

trend = "improving" if coc < 10 else "stable"
```
**Direction anchors:** `coc < 10`, `de < 0.3`, `gov_met > 70`, `pe < 15`, `high_risk_suppliers < 3`.
**Defaults:** `coc=12`, `de=0.5`, `pe=15`.

### Human Capital channel

**File:** `core/kpi_engine.py:253-291`
```
diversity_score = min(100, female_pct × 2)              # default 50
social_met      = (Social.status == "Met").sum() / len × 100   # default 0

score = max(0, round( min(100,
                            retention × 0.5
                          + (100 - turnover) × 0.3
                          + social_met × 0.2 ), 1 ))

trend = "improving" if turnover < 15 else "stable"
```
**Direction anchors:** `turnover < 15`, `retention > 75`, `diversity_score > 60`, `social_met > 70`.
**Defaults:** `turnover=20`, `retention=70`.

### Capital Efficiency channel

**File:** `core/kpi_engine.py:293-314`
```
capex_growth = round( (capex_curr - capex_prev) / capex_prev × 100, 1 )
                                                        # 0 if prev == 0

score = max(0, round( min(100,
                              roa × 5
                            + roe × 2
                            + min(30, capex_growth × 0.3) ), 1 ))

trend = "improving" if roa > 9 and capex_growth > 0 else "stable"
```
**Direction anchors:** `roa > 9`, `roe > 15`, `capex_growth > 0`.

### Composite ESG-financial score

**File:** `core/kpi_engine.py:78-80`
```
composite_esg_financial_score = round( mean(channel.score for channel in 5 channels), 1 )
```

### CAGR

**File:** `core/kpi_engine.py:318-342`
```
cagr(start, end, n) = round( ((end / start) ** (1/n) - 1) × 100, 2 )
                                                # n = years - 1
```
Returns: `revenue_cagr`, `ebitda_cagr`, `esg_capex_cagr`, `period`.
**Fallback:** `0` when `start <= 0` or `n == 0`.

### Volatility

**File:** `core/kpi_engine.py:344-352`
```
revenue_volatility  = round( std(pct_change(revenue_inr_crores)) × 100, 2 )
margin_volatility   = round( std(ebitda_margin_pct),                2 )
earnings_volatility = round( std(pct_change(pat_inr_crores))    × 100, 2 )
```
**Precondition:** `len(df) >= 4`.

---

## Data Access (`core/data_access.py`)

No numeric calculations. Provides `get_dataset(schema_name, fallback_loader)` which tries channels in this order:

1. `dataset_{schema_name}`
2. `validated_{schema_name}`
3. `validated_real_{schema_name}`

Falls back to the supplied loader function or an empty DataFrame.

---

## Known integrity flags

These are quirks discovered while extracting the formulas. They are **not** bugs blocking deploy, but they are worth knowing about when reading numbers off the dashboard.

### F1. `cost_per_tco2e` display label appears under-scaled

**Where:** `agents/carbon_accountant.py:184` prints
```python
f"INR {cost_per_tco2e * 10000:.0f}/tCO2e"
```
With `cost_per_tco2e = 0.0015` (INR crores per tCO2e), the format multiplier `10_000` yields `15` → label shows `"INR 15/tCO2e"` despite the source-of-truth comment at `:148` citing `~INR 1500/tCO2e`. The underlying calculation (`emission_cost_saving = reduction_tco2e × 0.0015`) is correct in INR crores; only the **displayed unit-cost label** is off by 100×. Worth reconciling.

### F2. Two different per-tCO2e proxies for emission savings

- `agents/carbon_accountant.py:148` uses `0.0015` (claimed INR 1,500/tCO2e).
- `core/kpi_engine.py:198` uses `0.002` (claimed INR 200/tCO2e in inline comment).

The two modules independently estimate emission-reduction savings using **different unit costs**. If both surfaces are shown to a user side-by-side, totals will not reconcile. Decide on one source of truth (most natural is `company_cfg`).

### F3. MSCI / Sustainalytics / CDP cutoffs are literal & uncited

**Where:** `agents/risk_predictor.py:285-319` — all cutoffs (90/80/70/60 for MSCI; 5/50/0.45 anchors for Sustainalytics; 85/70/55/40 for CDP) are hard-coded with no link to the agencies' published methodologies. Treat the resulting "agency-style" letters/numbers as **internal heuristics**, not actual MSCI/Sustainalytics/CDP scores.

### F4. Audit Agent general-check scores are static

**Where:** `agents/audit_agent.py:137-143` — six scores (88/82/95/70/90/60) for Data Traceability, Confidence Scoring, YoY Comparability, Third-Party Verification, Board ESG Oversight, Materiality Assessment. They feed the audit-readiness composite but have no link to underlying signals — i.e. they will not change as data quality changes.

### F5. KPI Engine direction-anchor magic numbers

**Where:** every channel function in `core/kpi_engine.py` uses unexplained anchors (`brand > 60`, `met_pct > 70`, `coc < 10`, `de < 0.3`, `pe < 15`, `turnover < 15`, `retention > 75`, `roa > 9`, `roe > 15`, etc.). These are reasonable rule-of-thumb bands but are not config-driven and have no source-of-truth comment. If a customer's sector has different baselines, the direction arrows will be misleading.

### F6. Action Agent friction & benefit constants are uncommented

**Where:** `agents/action_agent.py:252-289` — friction base (`6`), duration coefficient (`0.35`), regime adjustments (`0/2/5`), category adjustments (`2-6`), benefit multipliers (`1.10-1.35`), anchor share (`0.08`). These drive every action's net ROI and execution mode. Worth promoting to config so they can be tuned per company without a code change.

### F7. Risk-weight / scenario / ESG-rating defaults are config

These look like magic numbers in narrative text but are actually `company_cfg` attributes:

- Climate risk weights `0.25 / 0.45 / 0.30` → `RiskWeightConfig`.
- Audit weights `0.30 / 0.40 / 0.30` → `AuditWeightConfig`.
- Confidence weights `0.4 / 0.4 / 0.2` → `ConfidenceWeightConfig`.
- Scenario reductions `35 / 18 / 5` and ratings `A / A- / BBB` → `ScenarioConfig`.
- ESG rating cutoffs `90 / 80 / 70 / 60` → `ThresholdConfig.rating_*`.
- Audit grade cutoffs `90 / 75 / 60` → `ThresholdConfig.audit_grade_*`.

A customer-specific override should always edit the profile JSON, not the agent code.

---

## Maintaining this document

When you change a formula or add a threshold:

1. Update the agent code with an inline comment citing the source/rationale.
2. Add the constant to `core/company_config.py` if it's expected to vary per company.
3. Update this doc — keep the `file:line` citation accurate.
4. If the change moves a published number on the dashboard, note it in the [Platform Changes](README.md#platform-changes) section of the README so users aren't surprised.

The full extraction behind this document was performed by walking each agent file end-to-end. To regenerate after a refactor, the prompt template lives in the project's `~/.claude` history under `Extract every calculation formula from agents`.

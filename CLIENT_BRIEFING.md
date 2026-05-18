# Client Briefing — ESG CoPilot

Team-facing reference for the three client questions:
**(1)** what they can / can't do, **(2)** value-add vs. existing ESG tools,
**(3)** other context the team should carry into the conversation.

Grounded in the shipped codebase — every claim has a file:line citation.

---

## 1. Core functionality

### Can do today

- **Connect 9 real data sources** — file upload (CSV / Excel / JSON), Google
  Sheets, REST APIs, AWS S3, BigQuery, GCS, Azure Blob, Delta Lake, Snowflake.
  Per-source 🔄 Refresh and 📤 Replace. Auto-schema detection for 7 canonical
  ESG schemas. ([`utils/real_connectors.py`](utils/real_connectors.py),
  [`utils/connection_manager.py`](utils/connection_manager.py))
- **Run a 9-agent ESG pipeline** end-to-end with auditable handoffs:
  Data Collector → Regulatory Tracker → Carbon Accountant → Risk Predictor →
  Audit Agent → ROI Agent → Action Agent → Report Generator → Stakeholder Agent.
- **Track 6 frameworks** — BRSR, CSRD / ESRS, GRI, SASB, SOX, SEC Climate Rule.
  Live framework refresh via Claude + web search with an approval queue.
  ([`utils/framework_refresh.py`](utils/framework_refresh.py))
- **Field-level gap analysis** — Claude tool-use names the exact missing
  field + dataset + upstream source (e.g. "Scope 3 Cat 11 missing — from
  `supplier_emissions` via CDP / EcoVadis"). Renders as a table on Regulatory
  Tracker, Audit, and Data Collector pages.
  ([`utils/gap_analyzer.py`](utils/gap_analyzer.py))
- **ESG Integrity Gap Detector** — compares self-reported KPIs against
  data-derived actuals; flags >15 % mismatches.
  ([`agents/audit_agent.py:221`](agents/audit_agent.py#L221))
- **Dual ROI quantification** — Financial + Strategic ROI, J-Curve payback,
  Investment Quality Score, 5 value-creation channels, What-If simulator
  (see §4 below).
- **Audit-ready reports** in Streamlit + structured JSON, with full audit trail
  of every agent handoff. Per-user isolation throughout
  ([`core/state_manager.py`](core/state_manager.py)).

### Cannot do today (be upfront)

- ❌ **Native PDF / XBRL export** — outputs are Streamlit HTML + JSON.
  Browser-print to PDF works but is manual.
- ❌ **Live peer-benchmark database** — peer data must be uploaded; no
  Bloomberg / S&P / Refinitiv feed.
- ❌ **Always-on background monitoring** — regulatory updater is a 24 h
  per-session thread; dies on Space restart.
- ❌ **Cryptographic / immutable audit trail** — JSON logs are timestamped
  and per-user-isolated, not hash-chained.
- ❌ **Direct vendor data APIs** (MSCI / Sustainalytics / Clarity AI) —
  vendors don't expose them at our tier. CSV import path works.
- ❌ **High-concurrency multi-tenant** — single-process Streamlit. >10
  simultaneous heavy users needs the Redis / queue upgrade.

---

## 2. Value-add vs. existing ESG tools

| Camp | Examples | Their gap | Our angle |
|---|---|---|---|
| Compliance dashboards | Workiva, Diligent ESG, Nasdaq Metrio, Cority | Generic templates, no field-level remediation, vendor-paced content updates, no ROI quantification | Field-level gap analysis names exact missing field + dataset + source; live regulatory refresh with same-run effect; dual ROI built in |
| Carbon accounting | Persefoni, Watershed, Greenly, Sweep | Single domain (emissions only) | One unified pipeline — emissions, risk, audit, regulatory share state and challenge each other |
| Ratings / data vendors | MSCI ESG, Sustainalytics, S&P Global | One-way: they rate, you can't see why or fix it | Every formula in [`CALCULATIONS.md`](CALCULATIONS.md), tunable per profile; Integrity Gap Detector finds where your own numbers don't match your own data |

### Five defensible differentiators

1. **Multi-agent architecture, not a chatbot.** Nine specialised agents with
   typed state handoffs. Every formula references a file:line in code.
2. **Field-level Claude gap analysis** with tool-use forcing structured JSON.
   Cached per input fingerprint so re-running is free.
3. **ESG Integrity Gap Detector** — anti-greenwashing check no major
   competitor offers.
4. **Live regulatory refresh with human-in-the-loop** — Claude + web search
   detects SEBI / EFRAG / SEC / GRI changes; approval queue; takes effect on
   the next compliance click.
5. **Dual ROI with J-Curve + What-If simulator** — tells the CFO what the
   next ₹X crore returns, when it breaks even, and what happens if CBAM
   doubles carbon tax — in milliseconds, no pipeline re-run.

---

## 3. Other context for the team

**Demo positioning.** Lead with the Integrity Gap Detector (Audit page →
Integrity Gaps tab) and the new field-level Gap Analysis table. Those land
hardest with audit and sustainability leads.

**API keys.** `ANTHROPIC_API_KEY` and `HF_INFERENCE_TOKEN` are both optional —
the app degrades to rule-based fallbacks if missing, but narrative quality is
materially better with Anthropic configured. Paid pilots provision their own
keys; we don't bill API usage through.

**"What about PDF / XBRL?"** Position as a 2–4 week add — data is all in
JSON, just needs a headless renderer. Don't promise in scope without sizing.

**"Can you scale to 1000 users?"** Honest answer: not on the current Space.
Path is (a) Redis state manager, (b) external scheduler (Temporal / Airflow)
for background jobs, (c) job queue for pipeline runs. Pitch as the
**enterprise tier**, not as a gap.

**Data security.** Per-user state buckets in
[`core/state_manager.py`](core/state_manager.py) partition by username, not
session. Two analysts on the same instance never see each other's data —
extends through persistence.

**Don't over-promise:**

- Not "real-time" — batch on each pipeline Run.
- Not "AI-driven" without flagging the fallback path. Anthropic / HF are
  optional augments, not the brain.
- Not XBRL / PDF / cryptographic audit out of the box — all roadmap.
- Not live peer benchmarking — needs peer data uploaded.

---

## 4. ROI Agent — Calculations Reference

The ROI Agent ([`agents/roi_agent.py`](agents/roi_agent.py)) is the most
commercially-loaded surface, so the team should be fluent here.

### Hypothesis mapping

ROI quantification is anchored to four product hypotheses (the full set
H1–H8 spans all agents; ROI owns these four):

| Hypothesis | Claim | Where it shows up |
|---|---|---|
| **H1 — Growth** | ESG performance → revenue and market share growth | Growth channel in KPI Engine |
| **H2 — Profitability** | Emissions reduction → operating cost savings | Cost channel + Financial ROI |
| **H5 — CapEx return** | ESG-linked CapEx → ROA / ROIC improvement | Capital Efficiency channel + Financial ROI |
| **H6 — J-Curve** | Short-term cost burden → long-term payback | J-Curve trajectory + IQS Momentum component |

H3 (cyclicality) and H4 (downside protection) live in
[`agents/risk_predictor.py`](agents/risk_predictor.py); H7 (India regulatory
context) and H8 (stakeholder framing) live elsewhere.

### KPI Engine — 5 value-creation channels

[`core/kpi_engine.py`](core/kpi_engine.py) produces a per-channel score
(0–100) plus a `composite_esg_financial_score`. Each channel is
deterministic (no LLM) and fully traceable in
[`CALCULATIONS.md`](CALCULATIONS.md):

| Channel | Driver | Output metric examples |
|---|---|---|
| **Growth** | ESG pillar scores → revenue delta | revenue CAGR, market-share lift, customer-loyalty proxy |
| **Cost** | Emissions ↓ → opex savings | emission-reduction savings, energy savings, carbon-tax avoidance |
| **Risk** | Governance + compliance → cost of capital | cost-of-capital reduction (bps), volatility |
| **Human Capital** | Diversity + safety → talent retention | turnover ↓, engagement, training-hours |
| **Capital Efficiency** | ESG CapEx → ROA / ROIC | ROIC delta, ESG-CapEx CAGR |

### Financial vs. Strategic ROI

- **Financial ROI** ([`roi_agent.py:91`](agents/roi_agent.py#L91)) — hard
  cash returns vs. total ESG CapEx (current FY + previous FY). Combines
  emission-reduction savings, energy savings (proxy via ~8 % YoY cost
  trajectory), and channel-driven cost-out. Output: `roi_pct`, `payback_years`,
  `total_savings_inr_cr`.
- **Strategic ROI** ([`roi_agent.py:130`](agents/roi_agent.py#L130)) — brand
  premium score, cost-of-capital reduction in bps, market-share lift,
  talent-retention uplift. Output: `brand_premium_score`,
  `cost_of_capital_reduction_bps`.

### J-Curve model (H6)

[`agents/roi_agent.py:183`](agents/roi_agent.py#L183) walks quarterly
financials and accumulates:

- `cumulative_cost` += `esg_linked_capex_inr_crores`
- `quarterly_benefit` = `max(0, ebitda_margin_pct − 20) × revenue / 100`
   + `max(0, 30 − energy_cost_inr_crores)`  *(margin-uplift + energy-savings proxy)*
- `cumulative_benefit` += `quarterly_benefit`
- `net_position` = `cumulative_benefit − cumulative_cost`

**Breakeven rule (guard against false positives):** reported only when (a)
some investment has actually happened (`cumulative_cost > 0`) **and** (b) the
trajectory has been underwater at some prior quarter. Pure-positive
trajectories return `breakeven_quarter = None`. The earlier version
(`net_position >= 0 and i > 0`) misfired on pre-investment quarters and
reported a false breakeven while the live Space showed a deeply-negative
net position — that bug is pinned by
`tests/test_roi_agent.py::TestJCurve` and documented in
[`CALCULATIONS.md`](CALCULATIONS.md).

Returned shape: `quarters[]`, `breakeven_quarter`, `total_invested`,
`total_benefit`, `net_position`.

### Investment Quality Score (IQS)

[`agents/roi_agent.py:247`](agents/roi_agent.py#L247) — composite 0–100 score
with letter grade:

| Component | Weight | Derivation |
|---|---:|---|
| Financial ROI | 25 % | `min(100, roi_pct × 2)` — 50 % ROI ≙ 100 |
| Channel performance avg | 25 % | KPI engine `composite_esg_financial_score` |
| Strategic value | 20 % | `brand_premium × 3 + cost_of_capital_bps / 5` (capped 0–100) |
| ESG momentum | 15 % | `(esg_capex_cagr + revenue_cagr) × 2` (capped) |
| Risk reduction | 15 % | Risk channel score from KPI engine |

**Grade thresholds:** A+ ≥ 90, A ≥ 80, B+ ≥ 70, B ≥ 60, C ≥ 50, else D.

### Peer benchmarking (optional)

Runs only if peer data is uploaded (`peer_companies`, `peer_financials`,
`peer_esg`, `peer_metrics` schemas). Otherwise gracefully skipped — no
fabricated peer numbers.

### What-If simulator

The ROI page exposes sliders for carbon-price uplift, ESG-CapEx %,
benefit-realisation timing, and discount rate. Recomputes J-Curve, IQS, and
NPV in pure-functional re-projection — **no agent re-runs**. Lets the CFO
answer questions like "what if CBAM doubled carbon tax?" without waiting for
a fresh pipeline.

### Snapshot diffs

The Command Center surfaces IQS and J-Curve deltas against the previous run
([`CALCULATIONS.md:1380`](CALCULATIONS.md#L1380)) so the user sees "IQS +3.2
points since last run" rather than just a static score.

---

## Elevator line

> ESG CoPilot is an agentic intelligence platform that turns ESG compliance
> from a dashboard into a decision system — auditable, ROI-aware, and honest
> about where the data isn't.

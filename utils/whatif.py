"""What-if simulator for the ESG ROI Agent.

Pure-functional re-projection of an existing pipeline run under
different assumptions. We deliberately don't re-execute the agents —
the goal is "what would the IQS / J-curve look like if the carbon
price doubled?" answered in milliseconds, not the 10-30s a real run
would take.

Inputs we let the user adjust
-----------------------------
* ``carbon_price_uplift_pct`` — % bump on the carbon-tax exposure
  baseline. Drives a delta on the cost-savings line + a flow-through
  to financial ROI.
* ``capex_uplift_pct`` — % change to the ESG-linked capex baseline.
  Higher capex pushes the J-curve trough deeper but also boosts
  long-term benefit (proxied via a per-quarter benefit multiplier).
* ``benefit_uplift_pct`` — % adjustment to expected per-quarter
  ESG-linked benefit. Captures "what if our supplier savings come in
  faster than projected?" type questions.
* ``discount_rate_pct`` — hurdle rate used to compute NPV alongside
  the undiscounted breakeven. Defaults to the company's cost of
  capital from the financials.

Why not just slider-bind to ``ROIAgent._compute_j_curve`` directly?
------------------------------------------------------------------
That method reads the *raw* financials DataFrame plus the live KPI
engine output. The ROI page caches a single run's quarterly array; the
simulator re-projects from that cached output without re-running the
KPI engine. This keeps the page responsive and decouples "explore
scenarios" from "execute pipeline".
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WhatIfInputs:
    """Slider state captured by the ROI page.

    All percentages are in *percent units* (so ``25`` means +25%, not
    +2500%). Defaults to a no-op simulation so first render shows the
    baseline.
    """
    carbon_price_uplift_pct: float = 0.0
    capex_uplift_pct: float = 0.0
    benefit_uplift_pct: float = 0.0
    discount_rate_pct: float = 12.0


@dataclass
class WhatIfOutputs:
    """Result bundle the ROI page renders next to the live read.

    ``delta_iqs`` is the *change* in IQS from the baseline run, not the
    new absolute. Both are surfaced so the user can see "+5 vs base run"
    without doing the subtraction themselves.
    """
    j_curve: dict
    iqs: dict
    delta_iqs: float
    delta_breakeven_quarters: int | None
    cost_savings_total: float
    npv: float
    inputs: WhatIfInputs


def _parse_breakeven_index(period: str | None,
                           quarters: list[dict]) -> int | None:
    """Map a period string ("2024 Q3") back to its index in ``quarters``."""
    if not period:
        return None
    for i, q in enumerate(quarters):
        if q.get("period") == period:
            return i
    return None


def _recompute_iqs(roi_results: dict, *, new_roi_pct: float) -> tuple[dict, float]:
    """Recompute the Investment Quality Score with a new financial-ROI input.

    Mirrors the weights in ``agents/roi_agent.py::_investment_quality_score``
    so the simulator stays in sync with the agent. Returns ``(iqs_dict,
    delta_vs_baseline)``.
    """
    baseline_iqs = roi_results.get("investment_quality_score") or {}
    components = dict(baseline_iqs.get("components") or {})
    weights = dict(baseline_iqs.get("weights") or {
        "financial_roi": 0.25,
        "channel_performance": 0.25,
        "strategic_value": 0.20,
        "esg_momentum": 0.15,
        "risk_reduction": 0.15,
    })

    # Replace just the financial-ROI sub-score; everything else inherits
    # from the baseline run. ``min(100, max(0, roi*2))`` follows the
    # agent's compression curve (50% ROI = 100 score).
    new_fin_score = min(100.0, max(0.0, new_roi_pct * 2.0))
    components["financial_roi"] = round(new_fin_score, 1)

    composite = round(sum(
        components.get(k, 0) * weights.get(k, 0)
        for k in weights
    ), 1)
    grade = (
        "A+" if composite >= 90 else
        "A" if composite >= 80 else
        "B+" if composite >= 70 else
        "B" if composite >= 60 else
        "C" if composite >= 50 else "D"
    )
    new_iqs = {
        "score": composite,
        "grade": grade,
        "components": components,
        "weights": weights,
    }
    delta = round(composite - float(baseline_iqs.get("score") or 0), 1)
    return new_iqs, delta


def _net_present_value(quarterly_net: list[float], discount_rate_pct: float) -> float:
    """Standard NPV: sum(net_t / (1 + r/4)^t) over the quarter index.

    Quarter cadence means the per-period rate is ``rate/4`` not ``rate``.
    Discount rate of 0 returns the undiscounted sum so the slider's
    "what if money were free" extreme behaves intuitively.
    """
    if discount_rate_pct <= 0:
        return round(sum(quarterly_net), 2)
    r = discount_rate_pct / 100.0 / 4.0
    npv = 0.0
    for t, net in enumerate(quarterly_net, start=1):
        npv += net / ((1 + r) ** t)
    return round(npv, 2)


def simulate(roi_results: dict, inputs: WhatIfInputs) -> WhatIfOutputs:
    """Project a what-if scenario over an existing ROI run.

    All math is bounded: a 100x slider value can't flip the IQS to 9999
    because every component clamps at 100. The breakeven quarter is
    re-derived from the *adjusted* quarterly trajectory using the same
    "must go underwater first" rule the agent uses.
    """
    j_curve = roi_results.get("j_curve") or {}
    quarters = list(j_curve.get("quarters") or [])
    fin_roi = roi_results.get("financial_roi") or {}

    baseline_breakeven_idx = _parse_breakeven_index(
        j_curve.get("breakeven_quarter"), quarters,
    )

    # Apply uplift multipliers to each quarter
    capex_mul = 1.0 + (inputs.capex_uplift_pct / 100.0)
    benefit_mul = 1.0 + (inputs.benefit_uplift_pct / 100.0)
    # Carbon-price uplift contributes to cost savings as a one-time
    # additive shift across the full horizon. We approximate it by
    # boosting the benefit side of every quarter by a flat percentage
    # of the total carbon-tax-avoided baseline.
    cost_savings = (fin_roi.get("cost_savings") or {})
    carbon_baseline = float(cost_savings.get("carbon_tax_avoided") or 0)
    carbon_uplift_total = carbon_baseline * (inputs.carbon_price_uplift_pct / 100.0)
    per_quarter_carbon_lift = (carbon_uplift_total / max(1, len(quarters)))

    new_quarters: list[dict] = []
    cum_cost = 0.0
    cum_benefit = 0.0
    quarterly_net: list[float] = []
    for q in quarters:
        capex = float(q.get("quarterly_capex") or 0) * capex_mul
        benefit = (float(q.get("quarterly_benefit") or 0) * benefit_mul
                   + per_quarter_carbon_lift)
        cum_cost += capex
        cum_benefit += benefit
        net = cum_benefit - cum_cost
        quarterly_net.append(benefit - capex)
        new_quarters.append({
            "period": q.get("period"),
            "quarterly_capex": round(capex, 2),
            "cumulative_cost": round(cum_cost, 2),
            "quarterly_benefit": round(benefit, 2),
            "cumulative_benefit": round(cum_benefit, 2),
            "net_position": round(net, 2),
        })

    # Re-derive breakeven (same rule as the agent: must go underwater first)
    new_breakeven = None
    new_breakeven_idx = None
    went_underwater = False
    for i, q in enumerate(new_quarters):
        if q["cumulative_cost"] <= 0:
            continue
        if q["net_position"] < 0:
            went_underwater = True
            continue
        if went_underwater:
            new_breakeven = q["period"]
            new_breakeven_idx = i
            break

    delta_breakeven_q = None
    if baseline_breakeven_idx is not None and new_breakeven_idx is not None:
        delta_breakeven_q = new_breakeven_idx - baseline_breakeven_idx

    new_j_curve = {
        "quarters": new_quarters,
        "breakeven_quarter": new_breakeven,
        "total_invested": round(cum_cost, 2),
        "total_benefit": round(cum_benefit, 2),
        "net_position": round(cum_benefit - cum_cost, 2),
    }

    # New financial ROI: original cost savings adjusted for carbon-price
    # uplift, divided by the bumped capex base. Reuse the agent's
    # cumulative formula so the IQS sub-score stays comparable.
    base_capex = float(fin_roi.get("total_esg_capex") or 0)
    new_capex = base_capex * capex_mul
    base_savings_total = float((cost_savings or {}).get("total") or 0)
    new_savings_total = base_savings_total * benefit_mul + carbon_uplift_total
    new_roi_pct = (new_savings_total / new_capex * 100.0) if new_capex else 0.0
    new_iqs, delta_iqs = _recompute_iqs(roi_results, new_roi_pct=new_roi_pct)

    npv = _net_present_value(quarterly_net, inputs.discount_rate_pct)

    return WhatIfOutputs(
        j_curve=new_j_curve,
        iqs=new_iqs,
        delta_iqs=delta_iqs,
        delta_breakeven_quarters=delta_breakeven_q,
        cost_savings_total=round(new_savings_total, 2),
        npv=npv,
        inputs=inputs,
    )


__all__ = ["WhatIfInputs", "WhatIfOutputs", "simulate"]

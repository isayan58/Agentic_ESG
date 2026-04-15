"""Agent 9: ESG ROI Agent — Dual ROI framework (financial + strategic) with
Investment Quality Score.

Consumes KPI Engine outputs to quantify the financial return of ESG
initiatives and generate an ESG Investment Quality Score (0-100).

Hypothesis mapping:
  H1 (Growth) — ESG → Revenue / market share
  H2 (Profitability) — Emissions reduction → cost savings
  H5 (CapEx) — ESG-linked CapEx → ROA/ROIC
  H6 (J-Curve) — Short-term cost → long-term payback
"""
from __future__ import annotations

from datetime import datetime
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.data_access import get_dataset
from core.company_config import company_cfg
from core.kpi_engine import kpi_engine
from utils.data_processing import (
    load_financials, load_esg_metrics, load_emissions,
    load_energy, load_supply_chain, load_diversity,
)


class ROIAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="ESG ROI Agent",
            description="Quantifies financial and strategic ROI of ESG initiatives.",
        )

    def execute(self, **kwargs):
        self.log("Loading financial and ESG datasets")
        fin_df = get_dataset("financials", load_financials)
        esg_df = get_dataset("esg_metrics", load_esg_metrics)
        emissions_df = get_dataset("emissions", load_emissions)
        energy_df = get_dataset("energy", load_energy)
        sc_df = get_dataset("supply_chain", load_supply_chain)
        div_df = get_dataset("diversity", load_diversity)

        if fin_df.empty:
            return {"error": "No financial data available — upload sample_financials.csv"}

        # --- KPI Engine ---
        self.log("Running KPI Engine — 5 Value Creation Channels")
        kpi_results = kpi_engine.compute_all(
            fin_df, esg_df, emissions_df, energy_df, sc_df, div_df,
        )

        # --- Dual ROI ---
        financial_roi = self._compute_financial_roi(kpi_results, fin_df)
        strategic_roi = self._compute_strategic_roi(kpi_results, esg_df)

        # --- J-Curve ---
        j_curve = self._compute_j_curve(kpi_results, fin_df)

        # --- Investment Quality Score ---
        iqs = self._investment_quality_score(kpi_results, financial_roi, strategic_roi)

        # --- Narrative ---
        narrative = self._generate_narrative(kpi_results, financial_roi, strategic_roi, iqs)

        results = {
            "kpi_engine": kpi_results,
            "financial_roi": financial_roi,
            "strategic_roi": strategic_roi,
            "j_curve": j_curve,
            "investment_quality_score": iqs,
            "narrative": narrative,
            "generated_at": datetime.now().isoformat(),
        }

        state_manager.publish("roi_results", results, self.name)
        return results

    # ── Financial ROI ──────────────────────────────────────────────────────

    def _compute_financial_roi(self, kpi: dict, fin_df) -> dict:
        """Hard financial return from ESG spend."""
        fin = kpi.get("financial_summary", {})
        capex_curr = fin.get("esg_capex_current_fy", 0)
        capex_prev = fin.get("esg_capex_previous_fy", 0)
        total_capex = capex_curr + capex_prev

        # Cost savings from channels
        channels = {c["channel"]: c for c in kpi.get("value_channels", [])}

        # Estimate tangible returns
        cost_ch = channels.get("Cost", {})
        cost_metrics = {m["name"]: m["value"] for m in cost_ch.get("metrics", [])}
        saving_str = cost_metrics.get("Emission Reduction Savings", "0")
        emission_savings = _parse_number(saving_str)

        energy_cost = fin.get("energy_cost_latest", 0)
        energy_prev_approx = energy_cost * 1.08  # ~8% higher previous year
        energy_savings = round(energy_prev_approx - energy_cost, 2)

        carbon_tax_curr = fin.get("carbon_tax_exposure_latest", 0)
        # Estimate previous year carbon tax from trend
        carbon_tax_saving = round(carbon_tax_curr * 0.15, 2)  # ~15% avoided via reduction

        total_savings = round(emission_savings + energy_savings + carbon_tax_saving, 2)
        roi_pct = round((total_savings / total_capex) * 100, 1) if total_capex else 0

        # Revenue uplift from brand/ESG premium
        rev_growth = fin.get("revenue_growth_pct", 0)
        # Attribute ~20% of growth to ESG brand effect
        esg_revenue_uplift = round(
            fin.get("revenue_current_fy", 0) * (rev_growth / 100) * 0.20, 2
        )

        return {
            "total_esg_capex": round(total_capex, 2),
            "cost_savings": {
                "emission_reduction": emission_savings,
                "energy_efficiency": energy_savings,
                "carbon_tax_avoided": carbon_tax_saving,
                "total": total_savings,
            },
            "esg_revenue_uplift": esg_revenue_uplift,
            "net_financial_benefit": round(total_savings + esg_revenue_uplift, 2),
            "roi_pct": roi_pct,
            "payback_years": round(total_capex / total_savings, 1) if total_savings > 0 else None,
        }

    # ── Strategic ROI ──────────────────────────────────────────────────────

    def _compute_strategic_roi(self, kpi: dict, esg_df) -> dict:
        """Non-financial strategic returns from ESG initiatives."""
        fin = kpi.get("financial_summary", {})
        channels = {c["channel"]: c for c in kpi.get("value_channels", [])}

        # Risk reduction value
        risk_ch = channels.get("Risk", {})
        cost_of_capital = fin.get("cost_of_capital_latest", 12)
        coc_reduction = max(0, 12 - cost_of_capital)  # reduction from baseline ~12%
        market_cap = company_cfg.market_cap_local
        risk_value = round(market_cap * coc_reduction / 100, 2) if market_cap else 0

        # Human capital value
        hc_ch = channels.get("Human Capital", {})
        turnover = fin.get("employee_turnover_latest", 20)
        # Reduced turnover = ~30% of annual salary saved per retained employee
        turnover_savings = round(max(0, 20 - turnover) * company_cfg.employees * 0.03, 1)

        # Brand/reputation
        brand = fin.get("brand_value_index", 50)
        brand_premium = round((brand - 50) * 0.5, 1)  # points above 50 → premium

        # ESG rating trajectory
        rating_current = company_cfg.esg_rating_current
        rating_lift = "Positive" if kpi.get("composite_esg_financial_score", 0) > 60 else "Neutral"

        return {
            "risk_reduction_value": risk_value,
            "cost_of_capital_reduction_bps": round(coc_reduction * 100),
            "talent_retention_savings": turnover_savings,
            "brand_premium_score": brand_premium,
            "esg_rating_trajectory": rating_lift,
            "current_rating": rating_current,
            "channel_scores": {
                c["channel"]: c["score"] for c in kpi.get("value_channels", [])
            },
        }

    # ── J-Curve ────────────────────────────────────────────────────────────

    def _compute_j_curve(self, kpi: dict, fin_df) -> dict:
        """Model the ESG J-Curve: short-term costs → long-term payback.

        Returns quarterly CapEx (cost) vs cumulative benefit trajectory.
        """
        if fin_df.empty:
            return {"quarters": [], "breakeven_quarter": None}

        q_sorted = fin_df.sort_values(["year", "quarter"])
        quarters = []
        cum_cost = 0
        cum_benefit = 0

        for _, row in q_sorted.iterrows():
            capex = float(row.get("esg_linked_capex_inr_crores", 0))
            # Benefits: margin improvement + energy savings (proxied from trends)
            margin_benefit = max(0, float(row.get("ebitda_margin_pct", 20)) - 20) * \
                float(row.get("revenue_inr_crores", 0)) / 100
            energy_benefit = max(0, 30 - float(row.get("energy_cost_inr_crores", 30)))

            cum_cost += capex
            cum_benefit += (margin_benefit + energy_benefit)

            quarters.append({
                "period": f"{int(row['year'])} {row['quarter']}",
                "quarterly_capex": round(capex, 2),
                "cumulative_cost": round(cum_cost, 2),
                "quarterly_benefit": round(margin_benefit + energy_benefit, 2),
                "cumulative_benefit": round(cum_benefit, 2),
                "net_position": round(cum_benefit - cum_cost, 2),
            })

        # Find breakeven
        breakeven = None
        for i, q in enumerate(quarters):
            if q["net_position"] >= 0 and i > 0:
                breakeven = q["period"]
                break

        return {
            "quarters": quarters,
            "breakeven_quarter": breakeven,
            "total_invested": round(cum_cost, 2),
            "total_benefit": round(cum_benefit, 2),
            "net_position": round(cum_benefit - cum_cost, 2),
        }

    # ── Investment Quality Score ───────────────────────────────────────────

    def _investment_quality_score(self, kpi: dict, fin_roi: dict, strat_roi: dict) -> dict:
        """0-100 composite score measuring ESG investment effectiveness.

        Components (weighted):
          - Financial ROI (25%)
          - Channel scores average (25%)
          - Strategic value (20%)
          - ESG momentum — CAGR + rating trajectory (15%)
          - Risk reduction (15%)
        """
        # Financial ROI component (0-100)
        roi_pct = fin_roi.get("roi_pct", 0)
        fin_score = min(100, max(0, roi_pct * 2))  # 50% ROI → 100 score

        # Channel scores average
        channel_avg = kpi.get("composite_esg_financial_score", 50)

        # Strategic value
        brand_p = strat_roi.get("brand_premium_score", 0)
        coc_bps = strat_roi.get("cost_of_capital_reduction_bps", 0)
        strat_score = min(100, max(0, brand_p * 3 + coc_bps / 5))

        # Momentum
        cagr = kpi.get("cagr", {})
        capex_cagr = cagr.get("esg_capex_cagr", 0)
        rev_cagr = cagr.get("revenue_cagr", 0)
        momentum = min(100, max(0, (capex_cagr + rev_cagr) * 2))

        # Risk reduction
        risk_ch = next(
            (c for c in kpi.get("value_channels", []) if c["channel"] == "Risk"), {}
        )
        risk_score = risk_ch.get("score", 50) if isinstance(risk_ch, dict) else 50

        # Weighted composite
        iqs = round(
            fin_score * 0.25 +
            channel_avg * 0.25 +
            strat_score * 0.20 +
            momentum * 0.15 +
            risk_score * 0.15,
            1,
        )

        grade = (
            "A+" if iqs >= 90 else
            "A" if iqs >= 80 else
            "B+" if iqs >= 70 else
            "B" if iqs >= 60 else
            "C" if iqs >= 50 else "D"
        )

        return {
            "score": iqs,
            "grade": grade,
            "components": {
                "financial_roi": round(fin_score, 1),
                "channel_performance": round(channel_avg, 1),
                "strategic_value": round(strat_score, 1),
                "esg_momentum": round(momentum, 1),
                "risk_reduction": round(risk_score, 1),
            },
            "weights": {
                "financial_roi": 0.25,
                "channel_performance": 0.25,
                "strategic_value": 0.20,
                "esg_momentum": 0.15,
                "risk_reduction": 0.15,
            },
        }

    # ── AI Narrative ───────────────────────────────────────────────────────

    def _generate_narrative(self, kpi, fin_roi, strat_roi, iqs):
        prompt = (
            f"Write a 4-5 sentence ESG ROI executive briefing for {company_cfg.company_name}. "
            f"ESG Investment Quality Score: {iqs['score']}/100 (Grade: {iqs['grade']}). "
            f"Financial ROI: {fin_roi['roi_pct']}% on INR {fin_roi['total_esg_capex']} Cr invested. "
            f"Cost savings: INR {fin_roi['cost_savings']['total']} Cr. "
            f"Revenue uplift from ESG: INR {fin_roi['esg_revenue_uplift']} Cr. "
            f"Cost of capital reduction: {strat_roi['cost_of_capital_reduction_bps']} bps. "
            f"Rating trajectory: {strat_roi['esg_rating_trajectory']}. "
            f"Tone: confident, data-driven, suitable for board presentation."
        )
        return self.hf.generate_text(prompt)


def _parse_number(s: str) -> float:
    """Extract first number from a string like 'INR 1.2 Cr'."""
    import re
    m = re.search(r"[\d.]+", str(s))
    return float(m.group()) if m else 0.0

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

    def execute(self, orchestrator=None, **kwargs):
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

        # --- Peer Benchmarking (optional — only runs if peer data uploaded) ---
        peer_benchmarking = self._compute_peer_benchmarking(kpi_results, fin_df)

        # --- Narrative ---
        narrative = self._generate_narrative(kpi_results, financial_roi, strategic_roi, iqs)

        roi_recommendations = self._generate_roi_recommendations(kpi_results, financial_roi, strategic_roi, iqs)

        results = {
            "kpi_engine": kpi_results,
            "financial_roi": financial_roi,
            "strategic_roi": strategic_roi,
            "j_curve": j_curve,
            "investment_quality_score": iqs,
            "peer_benchmarking": peer_benchmarking,
            "narrative": narrative,
            "roi_recommendations": roi_recommendations,
            "generated_at": datetime.now().isoformat(),
        }

        # --- Post suggestions to the orchestrator's message board ---
        if orchestrator:
            self._post_suggestions(orchestrator, financial_roi, strategic_roi, iqs, j_curve)

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

        # Find breakeven — the J-Curve is "broken even" only after the
        # cumulative benefit climbs back to non-negative *after going
        # underwater*. The earlier check (`net_position >= 0 and i > 0`)
        # matched the all-zero pre-investment quarters where net_position
        # is trivially 0, so a 4-quarter run with no spend yet would
        # falsely report breakeven at the second quarter. Require both
        # (a) cumulative_cost > 0 (some investment has actually happened)
        # and (b) the position has been negative at some prior point.
        breakeven = None
        went_underwater = False
        for q in quarters:
            if q["cumulative_cost"] <= 0:
                # No investment yet — there is no J-curve to break even on.
                continue
            if q["net_position"] < 0:
                went_underwater = True
                continue
            # net_position >= 0 here, with non-zero cumulative_cost.
            if went_underwater:
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

    # ── Peer Benchmarking ──────────────────────────────────────────────────────

    def _compute_peer_benchmarking(self, kpi_results: dict, fin_df) -> dict:
        """Compare the company's metrics against uploaded sector peers.

        Reads from any available peer schema (peer_metrics > peer_benchmark >
        built from peer_financials + peer_esg).  Returns {"available": False}
        when no peer data has been uploaded.
        """
        import pandas as pd

        peer_metrics_df = get_dataset("peer_metrics")
        peer_bench_df   = get_dataset("peer_benchmark")
        peer_esg_df     = get_dataset("peer_esg")
        peer_fin_df     = get_dataset("peer_financials")

        if all(df.empty for df in [peer_metrics_df, peer_bench_df, peer_esg_df, peer_fin_df]):
            return {"available": False}

        # ── Build unified comparison frame ────────────────────────────────
        peers = pd.DataFrame()
        peer_source = "none"

        if not peer_metrics_df.empty:
            if {"esg_score", "ebitda_margin", "roa"} & set(peer_metrics_df.columns):
                if "year" in peer_metrics_df.columns:
                    latest = peer_metrics_df["year"].max()
                    peers = peer_metrics_df[peer_metrics_df["year"] == latest].copy()
                else:
                    peers = peer_metrics_df.copy()
                peer_source = "peer_metrics"

        if peers.empty and not peer_bench_df.empty:
            peers = peer_bench_df.rename(columns={
                "roa_avg":             "roa",
                "ebitda_margin_avg":   "ebitda_margin",
                "esg_capex_pct_avg":   "esg_capex_pct",
                "esg_score_avg":       "esg_score",
                "net_debt_ebitda_avg": "net_debt_to_ebitda",
                "asset_turnover_avg":  "asset_turnover",
            }).copy()
            peer_source = "peer_benchmark"

        if peers.empty and not peer_esg_df.empty:
            # Build from raw ESG (+ merge financials if available)
            peers = peer_esg_df.copy()
            if "year" in peers.columns:
                peers = peers[peers["year"] == peers["year"].max()].copy()
            if not peer_fin_df.empty:
                fin_l = peer_fin_df.copy()
                if "year" in fin_l.columns:
                    fin_l = fin_l[fin_l["year"] == fin_l["year"].max()]
                ccol = next((c for c in ["company", "Company"] if c in fin_l.columns), None)
                if ccol:
                    fin_l = fin_l.rename(columns={ccol: "company"})
                    if "ebitda" in fin_l.columns and "revenue" in fin_l.columns:
                        fin_l["ebitda_margin"] = (
                            fin_l["ebitda"] / fin_l["revenue"].replace(0, float("nan")) * 100
                        ).round(2)
                    if "net_profit" in fin_l.columns and "total_assets" in fin_l.columns:
                        fin_l["roa"] = (
                            fin_l["net_profit"] / fin_l["total_assets"].replace(0, float("nan")) * 100
                        ).round(2)
                    pcol = next((c for c in ["company", "Company"] if c in peers.columns), None)
                    if pcol:
                        peers = peers.rename(columns={pcol: "company"})
                    mcols = ["company"] + [c for c in ["ebitda_margin", "roa"] if c in fin_l.columns]
                    peers = peers.merge(fin_l[mcols], on="company", how="left")
            peer_source = "peer_esg"

        if peers.empty:
            return {"available": False, "reason": "No usable peer data"}

        # Normalise company column
        ccol = next((c for c in ["company", "Company"] if c in peers.columns), None)
        if ccol and ccol != "company":
            peers = peers.rename(columns={ccol: "company"})
        sector_col = next((c for c in ["sector", "Sector"] if c in peers.columns), None)

        # ── Company's own values ──────────────────────────────────────────
        fin_summary = kpi_results.get("financial_summary", {})
        company_esg_score     = self._derive_company_esg_score(kpi_results)
        company_ebitda_margin = float(fin_summary.get("ebitda_margin_latest", 0) or 0)
        company_roa           = float(fin_summary.get("roa_latest", 0) or 0)
        company_scope12_kt    = round(self._derive_company_scope12() / 1000, 1)

        metric_defs = [
            {"key": "esg_score",          "label": "ESG Score",            "unit": "/100", "company_value": company_esg_score,      "higher_is_better": True},
            {"key": "ebitda_margin",       "label": "EBITDA Margin",        "unit": "%",    "company_value": company_ebitda_margin,   "higher_is_better": True},
            {"key": "roa",                 "label": "Return on Assets",     "unit": "%",    "company_value": company_roa,             "higher_is_better": True},
            {"key": "scope1_2_emissions",  "label": "Scope 1+2 Emissions",  "unit": " kt",  "company_value": company_scope12_kt,      "higher_is_better": False},
        ]

        # ── Per-metric stats and percentile ranks ─────────────────────────
        benchmarks: dict = {}
        rankings:   list = []

        for mdef in metric_defs:
            k = mdef["key"]
            if k not in peers.columns:
                continue

            col_data = pd.to_numeric(peers[k], errors="coerce").dropna()
            if col_data.empty:
                continue

            # Normalise decimals → percentages for ratio columns
            if k in ("esg_capex_pct", "green_assets_pct") and col_data.max() <= 2.0:
                col_data = col_data * 100
            # Scope 1+2: convert peer tCO2e → ktCO2e if stored as large numbers
            if k == "scope1_2_emissions" and col_data.median() > 10_000:
                col_data = col_data / 1000

            p_median = round(float(col_data.median()), 2)
            p_mean   = round(float(col_data.mean()),   2)
            p_min    = round(float(col_data.min()),    2)
            p_max    = round(float(col_data.max()),    2)

            cv = mdef["company_value"] or 0
            n  = len(col_data)
            # Percentile: % of peers the company beats on this dimension
            beats = sum(1 for v in col_data if (v < cv if mdef["higher_is_better"] else v > cv))
            percentile = round(beats / n * 100) if n else None

            gap = round(cv - p_median, 2)
            if gap > 0:
                pos_label = f"+{gap} vs median ({'better' if mdef['higher_is_better'] else 'worse'})"
            elif gap < 0:
                pos_label = f"{gap} vs median ({'worse' if mdef['higher_is_better'] else 'better'})"
            else:
                pos_label = "At sector median"

            best = p_max if mdef["higher_is_better"] else p_min

            # Industry-standard comparison: attaches a fixed, source-
            # cited benchmark (SBTi, CRISIL median, etc.) alongside the
            # peer-derived median so users aren't solely anchored to
            # whatever peer set they happened to upload.
            try:
                from utils.industry_standards import compute_gap_vs_standard
                _overrides = getattr(company_cfg, "industry_benchmarks", None)
                industry_standard = compute_gap_vs_standard(
                    k, cv, _overrides,
                )
            except Exception:
                industry_standard = None

            benchmarks[k] = {
                "label":             mdef["label"],
                "unit":              mdef["unit"],
                "company_value":     cv,
                "peer_median":       p_median,
                "peer_mean":         p_mean,
                "peer_min":          p_min,
                "peer_max":          p_max,
                "sector_best":       best,
                "percentile":        percentile,
                "gap_vs_median":     gap,
                "position":          pos_label,
                "higher_is_better":  mdef["higher_is_better"],
                "industry_standard": industry_standard,
            }

            unit = mdef["unit"]
            rankings.append({
                "Metric":        mdef["label"],
                "Your Company":  f"{cv}{unit}",
                "Sector Median": f"{p_median}{unit}",
                "Sector Best":   f"{best}{unit}",
                "Percentile":    f"{percentile}th" if percentile is not None else "N/A",
                "vs Median":     pos_label,
            })

        # ── Full peer table for charting ──────────────────────────────────
        peer_table = []
        for _, row in peers.iterrows():
            entry = {"company": str(row.get("company", "Unknown"))}
            if sector_col:
                entry["sector"] = str(row.get(sector_col, ""))
            for mdef in metric_defs:
                k = mdef["key"]
                if k not in peers.columns:
                    continue
                raw = row.get(k)
                if raw is not None and str(raw) not in ("nan", "None", ""):
                    v = float(raw)
                    if k in ("esg_capex_pct", "green_assets_pct") and v <= 2.0:
                        v *= 100
                    if k == "scope1_2_emissions" and v > 10_000:
                        v /= 1000
                    entry[k] = round(v, 2)
            peer_table.append(entry)

        sectors_covered = []
        if sector_col:
            sectors_covered = peers[sector_col].dropna().unique().tolist()

        return {
            "available":       True,
            "peer_count":      len(peers),
            "peer_source":     peer_source,
            "sectors_covered": sectors_covered,
            "company_name":    company_cfg.company_name,
            "benchmarks":      benchmarks,
            "rankings":        rankings,
            "peer_table":      peer_table,
        }

    def _derive_company_esg_score(self, kpi_results: dict) -> float:
        """Approximate ESG score from esg_metrics status column."""
        from utils.data_processing import load_esg_metrics
        esg_df = get_dataset("esg_metrics", load_esg_metrics)
        if not esg_df.empty and "status" in esg_df.columns:
            total = int(esg_df["status"].notna().sum())
            if total:
                met = int((esg_df["status"] == "Met").sum())
                return round(40 + (met / total) * 48, 1)  # 100% met → ~88, 0% met → ~40
        return round(float(kpi_results.get("composite_esg_financial_score", 0) or 0), 1)

    def _derive_company_scope12(self) -> float:
        """Return Scope 1+2 tCO2e from carbon results in shared state."""
        carbon = state_manager.subscribe("carbon_results") or {}
        scope_curr = carbon.get("scope_totals_current", {})
        return float(scope_curr.get("Scope 1", 0) or 0) + float(scope_curr.get("Scope 2", 0) or 0)

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
        raw = self.hf.generate_text(prompt, agent="roi_agent")
        bullets = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return bullets if bullets else [raw.strip()]

    def _generate_roi_recommendations(self, kpi_results, financial_roi, strategic_roi, iqs):
        prompt = (
            f"You are an ESG ROI strategist. Provide 4 priority recommendations for improving ESG financial and strategic returns. "
            f"Financial ROI: {financial_roi.get('roi_pct', 0)}%. "
            f"Total ESG capex: {financial_roi.get('total_esg_capex', 0)}. "
            f"Net financial benefit: {financial_roi.get('net_financial_benefit', 0)}. "
            f"Investment Quality Score: {iqs.get('score', 0)}/100. "
            f"Current cost of capital reduction: {strategic_roi.get('cost_of_capital_reduction_bps', 0)} bps."
        )
        raw = self.hf.generate_text(prompt, max_tokens=260, agent="roi_agent")
        bullets = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return bullets if bullets else [raw.strip()]

    def _post_suggestions(self, orchestrator, financial_roi, strategic_roi, iqs, j_curve):
        """Post strategic suggestions to orchestrator's message board."""
        suggestions = []

        # High ROI opportunity
        if financial_roi.get("roi_pct", 0) > 50:
            suggestions.append(f"High ROI detected ({financial_roi['roi_pct']}%) — Consider scaling ESG initiatives")
        
        # Strong investment quality
        if iqs.get("score", 0) > 75:
            suggestions.append(f"Strong IQS ({iqs['score']}/100, {iqs['grade']}) — Ready for stakeholder communication")
        
        # J-Curve inflection
        breakeven = j_curve.get("breakeven_quarter")
        if breakeven and "Q" in str(breakeven):
            suggestions.append(f"J-Curve breakeven at {breakeven} — Monitor payback trajectory closely")
        
        # Cost of capital benefit
        if strategic_roi.get("cost_of_capital_reduction_bps", 0) > 50:
            suggestions.append(f"Significant cost of capital reduction ({strategic_roi['cost_of_capital_reduction_bps']} bps) — Refinancing opportunity")
        
        if suggestions:
            message = f"ROI Agent insights: {'; '.join(suggestions)}"
            orchestrator.post_message("roi_agent", message)


def _parse_number(s: str) -> float:
    """Extract first number from a string like 'INR 1.2 Cr'."""
    import re
    m = re.search(r"[\d.]+", str(s))
    return float(m.group()) if m else 0.0

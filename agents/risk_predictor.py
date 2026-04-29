"""Agent 5: Risk Predictor — Climate risk forecasting, ESG rating prediction,
market regime detection, downside protection, and scenario analysis.

Hypothesis mapping:
  H3 — ESG outperformance is cyclical (market regime detection)
  H4 — ESG reduces downside risk (downside protection score)
"""
import pandas as pd
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.data_access import get_dataset
from core.company_config import company_cfg
from utils.data_processing import (
    load_esg_metrics, load_supply_chain, load_emissions, load_financials,
)


class RiskPredictorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Risk Predictor",
            description="Forecasts climate risks, predicts ESG ratings, and runs scenario analysis.",
        )

    def execute(self, **kwargs):
        self.log("Running risk analysis")
        metrics_df = get_dataset("esg_metrics", load_esg_metrics)
        supply_chain_df = get_dataset("supply_chain", load_supply_chain)
        emissions_df = get_dataset("emissions", load_emissions)
        financials_df = get_dataset("financials", load_financials)

        # Climate risk assessment
        climate_risks = self._assess_climate_risks(emissions_df, metrics_df)

        # ESG rating prediction (multi-framework)
        rating_prediction = self._predict_esg_rating(metrics_df)

        # Supplier risk analysis
        supplier_risks = self._analyze_supplier_risks(supply_chain_df)

        # Scenario analysis
        scenarios = self._run_scenario_analysis(emissions_df, metrics_df)

        # H3: Market regime detection
        market_regime = self._detect_market_regime(financials_df)

        # H4: Downside protection score
        downside_protection = self._compute_downside_protection(
            financials_df, metrics_df, climate_risks
        )

        # AI-generated risk narrative
        narrative = self._generate_risk_narrative(
            climate_risks, rating_prediction, supplier_risks
        )

        risk_recommendations = self._generate_risk_recommendations(
            climate_risks, rating_prediction, supplier_risks, market_regime, downside_protection
        )

        results = {
            "climate_risks": climate_risks,
            "rating_prediction": rating_prediction,
            "supplier_risks": supplier_risks,
            "scenarios": scenarios,
            "market_regime": market_regime,
            "downside_protection": downside_protection,
            "risk_recommendations": risk_recommendations,
            "narrative": narrative,
            "overall_risk_score": climate_risks["overall_score"],
        }

        state_manager.publish("risk_results", results, self.name)

        # Best-effort notification on a high-risk reading. Anything ≥70
        # crosses the "needs management attention" line in
        # ``_risk_level`` (see method below) so the threshold matches
        # what users already see colour-coded as red on the dashboard.
        try:
            self._maybe_notify_risk_breach(results)
        except Exception:  # noqa: BLE001 — never break the pipeline
            pass
        return results

    def _maybe_notify_risk_breach(self, results: dict) -> None:
        """Emit a `risk_threshold_breached` event when overall risk ≥ 70."""
        overall = float(results.get("overall_risk_score") or 0)
        if overall < 70:
            return
        try:
            from utils.notifications import Event, notify
        except Exception:  # pragma: no cover
            return

        owner = None
        actor = None
        try:
            import streamlit as st
            user = (st.session_state.get("user") or {}) if hasattr(st, "session_state") else {}
            owner = (user.get("org_id") or "").strip() or None
            actor = (user.get("username") or "").strip() or None
        except Exception:
            owner = None
        import os
        owner = owner or os.getenv("ESG_DEFAULT_ORG") or None
        if not owner:
            return

        notify(
            Event(
                type="risk_threshold_breached",
                title=f"Risk score crossed threshold: {overall}/100",
                summary=(
                    f"The Risk Predictor reported an overall climate risk "
                    f"score of {overall}/100, which is at or above the "
                    "70-point management-attention threshold. Open the "
                    "Risk Predictor page to review category-level drivers."
                ),
                severity="critical" if overall >= 85 else "warning",
                actor=actor,
                payload={"overall_risk_score": overall},
            ),
            owner=owner,
        )

    def _assess_climate_risks(self, emissions_df, metrics_df):
        sr = company_cfg.sector_risk
        rw = company_cfg.risk_weights

        # Physical risks (sector-specific base)
        physical_risk = sr.physical_risk

        # Transition risks (regulatory, market, technology)
        transition_risk = sr.transition_risk_base
        regulatory_data = state_manager.subscribe("regulatory_results")
        if regulatory_data:
            compliance = regulatory_data.get("overall_compliance", sr.compliance_baseline)
            transition_risk = max(20, 100 - compliance)

        # Emission trajectory risk
        emission_risk = sr.emission_risk_base
        if not emissions_df.empty:
            totals_by_year = emissions_df.groupby("year")["emissions_tco2e"].sum()
            if len(totals_by_year) >= 2:
                years = sorted(totals_by_year.index)
                latest = totals_by_year[years[-1]]
                prev = totals_by_year[years[-2]]
                if latest > prev:
                    emission_risk = min(sr.emission_risk_max,
                                        sr.emission_risk_midpoint + (latest - prev) / prev * 100)
                else:
                    emission_risk = max(sr.emission_risk_min,
                                        sr.emission_risk_midpoint - (prev - latest) / prev * 100)

        overall = round(
            physical_risk * rw.physical +
            transition_risk * rw.transition +
            emission_risk * rw.emission, 1
        )

        risk_items = [
            {"category": "Physical Risk", "score": physical_risk,
             "level": self._risk_level(physical_risk),
             "details": sr.physical_risk_detail},
            {"category": "Transition Risk", "score": transition_risk,
             "level": self._risk_level(transition_risk),
             "details": "Regulatory changes and market expectations"},
            {"category": "Emission Trajectory", "score": emission_risk,
             "level": self._risk_level(emission_risk),
             "details": "Based on year-over-year emissions trend analysis"},
            {"category": "Reputational Risk", "score": sr.reputational_risk,
             "level": self._risk_level(sr.reputational_risk),
             "details": sr.reputational_detail},
            {"category": "Supply Chain Climate Risk", "score": sr.supply_chain_risk,
             "level": self._risk_level(sr.supply_chain_risk),
             "details": sr.supply_chain_detail},
        ]

        return {
            "overall_score": overall,
            "overall_level": self._risk_level(overall),
            "physical_risk": physical_risk,
            "transition_risk": transition_risk,
            "emission_risk": emission_risk,
            "risk_items": risk_items,
        }

    def _predict_esg_rating(self, metrics_df):
        t = company_cfg.thresholds
        sr = company_cfg.sector_risk

        if metrics_df.empty:
            return {
                "current": company_cfg.esg_rating_current,
                "predicted": company_cfg.esg_rating_target or "N/A",
                "confidence": 65,
            }

        met_count = (metrics_df["status"] == "Met").sum()
        total = len(metrics_df)
        met_pct = met_count / total * 100 if total > 0 else 0

        # Pillar scores
        pillar_scores = {}
        for pillar in ["Environmental", "Social", "Governance"]:
            pdf = metrics_df[metrics_df["pillar"] == pillar]
            if not pdf.empty:
                p_met = (pdf["status"] == "Met").sum()
                pillar_scores[pillar] = round(p_met / len(pdf) * 100, 1)

        # Rating prediction logic (thresholds from config)
        if met_pct >= t.rating_a:
            predicted = "A"
        elif met_pct >= t.rating_a_minus:
            predicted = "A-"
        elif met_pct >= t.rating_bbb_plus:
            predicted = "BBB+"
        elif met_pct >= t.rating_bbb:
            predicted = "BBB"
        else:
            predicted = "BB+"

        # Multi-agency rating predictions (MSCI, Sustainalytics, CDP-style)
        multi_ratings = self._multi_agency_ratings(met_pct, pillar_scores)

        return {
            "current": company_cfg.esg_rating_current,
            "predicted": predicted,
            "confidence": round(min(sr.confidence_cap, met_pct + sr.confidence_boost), 1),
            "pillar_scores": pillar_scores,
            "metrics_met_pct": round(met_pct, 1),
            "multi_agency_ratings": multi_ratings,
            "improvement_areas": self._identify_improvement_areas(metrics_df),
        }

    def _identify_improvement_areas(self, metrics_df):
        areas = []
        not_met = metrics_df[metrics_df["status"] == "Not Met"]
        current_col = f"value_{company_cfg.current_fy}" if company_cfg.current_fy else "value_2024"
        target_col = f"target_{company_cfg.current_fy}" if company_cfg.current_fy else "target_2024"

        for _, row in not_met.iterrows():
            areas.append({
                "metric": row["metric_name"],
                "pillar": row["pillar"],
                "current": row.get(current_col, row.get("value_2024", "N/A")),
                "target": row.get(target_col, row.get("target_2024", "N/A")),
            })
        return areas

    def _analyze_supplier_risks(self, supply_chain_df):
        if supply_chain_df.empty:
            return {"high_risk_count": 0, "suppliers": []}

        high_risk = supply_chain_df[supply_chain_df["risk_rating"] == "High"]
        overdue = supply_chain_df[supply_chain_df["audit_status"] == "Overdue"]

        supplier_details = []
        for _, row in high_risk.iterrows():
            supplier_details.append({
                "name": row["supplier_name"],
                "country": row["country"],
                "esg_score": row["esg_score"],
                "emissions": row["emission_contribution_tco2e"],
                "risk_factors": row["key_risk_factors"],
                "audit_status": row["audit_status"],
            })

        return {
            "high_risk_count": len(high_risk),
            "overdue_audits": len(overdue),
            "total_suppliers": len(supply_chain_df),
            "avg_esg_score": round(supply_chain_df["esg_score"].mean(), 1),
            "suppliers": supplier_details,
        }

    def _run_scenario_analysis(self, emissions_df, metrics_df):
        if emissions_df.empty:
            return {}

        current_fy = company_cfg.current_fy
        if current_fy and current_fy in emissions_df["year"].values:
            base_total = emissions_df[emissions_df["year"] == current_fy]["emissions_tco2e"].sum()
        else:
            base_total = emissions_df.groupby("year")["emissions_tco2e"].sum().iloc[-1]

        sc = company_cfg.scenarios
        scenarios = {
            "best_case": {
                "name": "Accelerated Transition",
                "description": "Aggressive decarbonization, 100% renewable, supplier engagement",
                "emission_reduction_pct": sc.best_reduction_pct,
                "projected_emissions": round(base_total * (1 - sc.best_reduction_pct / 100), 0),
                "projected_rating": sc.best_rating,
                "investment_required": sc.best_investment,
                "timeline": sc.best_timeline,
            },
            "base_case": {
                "name": "Current Trajectory",
                "description": "Maintain current improvement rate, planned initiatives",
                "emission_reduction_pct": sc.base_reduction_pct,
                "projected_emissions": round(base_total * (1 - sc.base_reduction_pct / 100), 0),
                "projected_rating": sc.base_rating,
                "investment_required": sc.base_investment,
                "timeline": sc.base_timeline,
            },
            "worst_case": {
                "name": "Stalled Progress",
                "description": "Regulatory delays, supply chain disruption, budget cuts",
                "emission_reduction_pct": sc.worst_reduction_pct,
                "projected_emissions": round(base_total * (1 - sc.worst_reduction_pct / 100), 0),
                "projected_rating": sc.worst_rating,
                "investment_required": sc.worst_investment,
                "timeline": sc.worst_timeline,
            },
        }
        return scenarios

    def _generate_risk_narrative(self, climate_risks, rating_prediction, supplier_risks):
        prompt = (
            f"Generate a risk assessment narrative for {company_cfg.company_name}'s ESG report. "
            f"Sector: {company_cfg.sector}. "
            f"Overall risk score: {climate_risks['overall_score']}/100 ({climate_risks['overall_level']}). "
            f"Physical risk: {climate_risks['physical_risk']}, "
            f"Transition risk: {climate_risks['transition_risk']}. "
            f"Current ESG rating: {rating_prediction['current']}, "
            f"Predicted: {rating_prediction['predicted']}. "
            f"High-risk suppliers: {supplier_risks['high_risk_count']}/{supplier_risks.get('total_suppliers', 0)}. "
            f"Provide key insights and recommendations."
        )
        raw = self.hf.generate_text(prompt, agent="risk_predictor")
        bullets = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return bullets if bullets else [raw.strip()]

    def _generate_risk_recommendations(self, climate_risks, rating_prediction, supplier_risks, market_regime, downside_protection):
        prompt = (
            f"You are an ESG risk strategist. Provide 4 prioritized recommendations for {company_cfg.company_name} "
            f"based on climate risk, rating prediction, supplier risks, market regime, and downside protection. "
            f"Overall risk score: {climate_risks['overall_score']}/100 ({climate_risks['overall_level']}). "
            f"Predicted ESG rating: {rating_prediction['predicted']}. "
            f"High-risk suppliers: {supplier_risks.get('high_risk_count', 0)}. "
            f"Market regime: {market_regime.get('regime', 'Unknown')}. "
            f"Downside protection score: {downside_protection.get('score', 0)}."
        )
        raw = self.hf.generate_text(prompt, max_tokens=260, agent="risk_predictor")
        bullets = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return bullets if bullets else [raw.strip()]

    def _multi_agency_ratings(self, met_pct, pillar_scores):
        """Predict ratings across MSCI, Sustainalytics, and CDP-style scales."""
        env_score = pillar_scores.get("Environmental", 50)
        soc_score = pillar_scores.get("Social", 50)
        gov_score = pillar_scores.get("Governance", 50)

        # MSCI-style (AAA to CCC)
        if met_pct >= 90:
            msci = "AA"
        elif met_pct >= 80:
            msci = "A"
        elif met_pct >= 70:
            msci = "BBB"
        elif met_pct >= 60:
            msci = "BB"
        else:
            msci = "B"

        # Sustainalytics-style (lower = better, 0-40+ risk score)
        sust_risk = round(max(5, 50 - met_pct * 0.45), 1)
        if sust_risk < 10:
            sust_category = "Negligible"
        elif sust_risk < 20:
            sust_category = "Low"
        elif sust_risk < 30:
            sust_category = "Medium"
        elif sust_risk < 40:
            sust_category = "High"
        else:
            sust_category = "Severe"

        # CDP-style (A to D-, focused on environmental)
        if env_score >= 85:
            cdp = "A"
        elif env_score >= 70:
            cdp = "A-"
        elif env_score >= 55:
            cdp = "B"
        elif env_score >= 40:
            cdp = "B-"
        else:
            cdp = "C"

        return {
            "msci": {"rating": msci, "basis": "Overall ESG performance"},
            "sustainalytics": {
                "risk_score": sust_risk,
                "category": sust_category,
                "basis": "Unmanaged ESG risk exposure",
            },
            "cdp": {"score": cdp, "basis": "Environmental disclosure & action"},
        }

    def _detect_market_regime(self, fin_df):
        """H3: Detect current market regime and ESG performance context.

        Market regimes:
          - Bull: rising revenue + expanding margins → ESG premium intact
          - Bear/Stress: declining metrics → ESG as defensive shield
          - Transition: mixed signals → ESG differentiation opportunity
        """
        if fin_df.empty or len(fin_df) < 4:
            return {
                "regime": "Unknown",
                "confidence": 0,
                "esg_context": "Insufficient data",
            }

        q = fin_df.sort_values(["year", "quarter"])
        recent_4 = q.tail(4)

        rev_trend = recent_4["revenue_inr_crores"].pct_change().mean()
        margin_trend = recent_4["ebitda_margin_pct"].diff().mean()
        pe_trend = recent_4["pe_ratio"].diff().mean()
        volatility = recent_4["revenue_inr_crores"].pct_change().std()

        # Classify regime
        if rev_trend > 0.01 and margin_trend > 0:
            regime = "Bull"
            esg_context = (
                "ESG premium is priced in — investors reward sustainability leaders. "
                "Focus on growth channel and brand differentiation."
            )
            confidence = min(90, 60 + rev_trend * 1000)
        elif rev_trend < -0.005 or margin_trend < -0.5:
            regime = "Stress"
            esg_context = (
                "ESG acts as a defensive shield — companies with strong governance "
                "and low carbon exposure show better downside protection."
            )
            confidence = min(85, 60 + abs(rev_trend) * 1000)
        else:
            regime = "Transition"
            esg_context = (
                "Mixed market signals — ESG differentiation is a competitive advantage. "
                "Focus on risk reduction and cost efficiency channels."
            )
            confidence = 55

        return {
            "regime": regime,
            "confidence": round(confidence, 1),
            "esg_context": esg_context,
            "indicators": {
                "revenue_trend_pct": round(rev_trend * 100, 2),
                "margin_trend_bps": round(margin_trend * 100, 1),
                "pe_trend": round(pe_trend, 2),
                "revenue_volatility": round(volatility * 100, 2),
            },
        }

    def _compute_downside_protection(self, fin_df, metrics_df, climate_risks):
        """H4: Compute downside protection score — how well ESG shields
        against negative shocks.

        Higher score = better protection.  Components:
          - Governance strength (board oversight, compliance)
          - Financial resilience (low leverage, stable margins)
          - ESG momentum (improving trajectory reduces tail risk)
          - Climate risk mitigation (lower exposure = better shield)
        """
        # Governance strength (0-100)
        gov_score = 50.0
        if not metrics_df.empty:
            gov = metrics_df[metrics_df["pillar"] == "Governance"]
            if not gov.empty:
                gov_score = round((gov["status"] == "Met").sum() / len(gov) * 100, 1)

        # Financial resilience
        fin_resilience = 50.0
        if not fin_df.empty:
            latest = fin_df.sort_values(["year", "quarter"]).iloc[-1]
            de = float(latest.get("debt_equity_ratio", 0.5))
            margin = float(latest.get("ebitda_margin_pct", 20))
            # Lower D/E and higher margin = more resilient
            fin_resilience = min(100, max(0, (1 - de) * 50 + margin * 2))

        # ESG momentum (are metrics improving?)
        esg_momentum = 50.0
        if not metrics_df.empty:
            met_pct = (metrics_df["status"] == "Met").sum() / len(metrics_df) * 100
            esg_momentum = min(100, met_pct * 1.2)

        # Climate risk inverse (lower risk = better protection)
        overall_risk = climate_risks.get("overall_score", 50)
        climate_shield = max(0, 100 - overall_risk)

        # Weighted composite
        dps = round(
            gov_score * 0.30 +
            fin_resilience * 0.25 +
            esg_momentum * 0.25 +
            climate_shield * 0.20,
            1,
        )

        level = "Strong" if dps >= 70 else ("Moderate" if dps >= 50 else "Weak")

        return {
            "score": dps,
            "level": level,
            "components": {
                "governance_strength": round(gov_score, 1),
                "financial_resilience": round(fin_resilience, 1),
                "esg_momentum": round(esg_momentum, 1),
                "climate_risk_shield": round(climate_shield, 1),
            },
            "interpretation": (
                f"Downside protection is {level.lower()}. "
                f"{'Governance and financial resilience provide a solid buffer.' if dps >= 70 else 'Consider strengthening governance and reducing leverage to improve downside protection.'}"
            ),
        }

    def _risk_level(self, score):
        t = company_cfg.thresholds
        if score < t.risk_low:
            return "Low"
        elif score < t.risk_medium:
            return "Medium"
        return "High"

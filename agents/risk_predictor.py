"""Agent 5: Risk Predictor — Climate risk forecasting, ESG rating prediction, scenario analysis."""
import pandas as pd
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.company_config import company_cfg
from utils.data_processing import load_esg_metrics, load_supply_chain, load_emissions


class RiskPredictorAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Risk Predictor",
            description="Forecasts climate risks, predicts ESG ratings, and runs scenario analysis.",
        )

    def execute(self, **kwargs):
        self.log("Running risk analysis")
        metrics_df = load_esg_metrics()
        supply_chain_df = load_supply_chain()
        emissions_df = load_emissions()

        # Climate risk assessment
        climate_risks = self._assess_climate_risks(emissions_df, metrics_df)

        # ESG rating prediction
        rating_prediction = self._predict_esg_rating(metrics_df)

        # Supplier risk analysis
        supplier_risks = self._analyze_supplier_risks(supply_chain_df)

        # Scenario analysis
        scenarios = self._run_scenario_analysis(emissions_df, metrics_df)

        # AI-generated risk narrative
        narrative = self._generate_risk_narrative(
            climate_risks, rating_prediction, supplier_risks
        )

        results = {
            "climate_risks": climate_risks,
            "rating_prediction": rating_prediction,
            "supplier_risks": supplier_risks,
            "scenarios": scenarios,
            "narrative": narrative,
            "overall_risk_score": climate_risks["overall_score"],
        }

        state_manager.publish("risk_results", results, self.name)
        return results

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

        return {
            "current": company_cfg.esg_rating_current,
            "predicted": predicted,
            "confidence": round(min(sr.confidence_cap, met_pct + sr.confidence_boost), 1),
            "pillar_scores": pillar_scores,
            "metrics_met_pct": round(met_pct, 1),
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
        return self.hf.generate_text(prompt)

    def _risk_level(self, score):
        t = company_cfg.thresholds
        if score < t.risk_low:
            return "Low"
        elif score < t.risk_medium:
            return "Medium"
        return "High"

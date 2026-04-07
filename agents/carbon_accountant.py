"""Agent 3: Carbon Accountant — Scope 1/2/3 emissions tracking and analysis."""
import pandas as pd
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.company_config import company_cfg
from utils.data_processing import (
    load_emissions, load_supply_chain, load_energy,
    compute_scope_totals, compute_quarterly_trends,
)


class CarbonAccountantAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Carbon Accountant",
            description="Tracks Scope 1, 2, and 3 emissions with supply chain hotspot detection.",
        )

    def execute(self, **kwargs):
        self.log("Loading emissions data")
        emissions_df = load_emissions()
        supply_chain_df = load_supply_chain()
        energy_df = load_energy()

        if emissions_df.empty:
            return {"error": "No emissions data available"}

        # Determine reporting years from config (with fallback to data)
        current_fy = company_cfg.current_fy
        previous_fy = company_cfg.previous_fy
        if not current_fy and "year" in emissions_df.columns:
            years = sorted(emissions_df["year"].unique())
            current_fy = years[-1] if years else 0
            previous_fy = years[-2] if len(years) >= 2 else 0

        # Scope totals for current and previous FY
        scope_totals_current = compute_scope_totals(emissions_df, year=current_fy)
        scope_totals_previous = compute_scope_totals(emissions_df, year=previous_fy)

        # Quarterly trends
        quarterly_trends = compute_quarterly_trends(emissions_df)

        # Category breakdown for current FY
        category_breakdown = (
            emissions_df[emissions_df["year"] == current_fy]
            .groupby(["scope", "category"])["emissions_tco2e"]
            .sum()
            .reset_index()
            .to_dict("records")
        ) if current_fy else []

        # YoY change
        total_current = sum(scope_totals_current.values())
        total_previous = sum(scope_totals_previous.values())
        yoy_change = round((total_current - total_previous) / total_previous * 100, 1) if total_previous else 0

        # Supply chain hotspots (Scope 3 X-Ray)
        hotspots = self._identify_hotspots(supply_chain_df)

        # Carbon intensity (per $M revenue)
        rev_current = company_cfg.revenue("current")
        rev_previous = company_cfg.revenue("previous")
        carbon_intensity = round(total_current / rev_current, 1) if rev_current else 0
        carbon_intensity_prev = round(total_previous / rev_previous, 1) if rev_previous else 0

        # Energy mix analysis
        energy_analysis = self._analyze_energy(energy_df, current_fy)

        # AI narrative
        narrative = self._generate_narrative(
            scope_totals_current, yoy_change, hotspots, carbon_intensity
        )

        results = {
            "scope_totals_current": scope_totals_current,
            "scope_totals_previous": scope_totals_previous,
            "total_emissions_current": round(total_current, 1),
            "total_emissions_previous": round(total_previous, 1),
            "yoy_change_pct": yoy_change,
            "quarterly_trends": quarterly_trends.to_dict("records"),
            "category_breakdown": category_breakdown,
            "hotspots": hotspots,
            "carbon_intensity": carbon_intensity,
            "carbon_intensity_prev": carbon_intensity_prev,
            "energy_analysis": energy_analysis,
            "narrative": narrative,
            "reporting_year": current_fy,
        }

        state_manager.publish("carbon_results", results, self.name)
        return results

    def _identify_hotspots(self, supply_chain_df):
        if supply_chain_df.empty:
            return []

        hotspots = []
        high_risk = supply_chain_df[supply_chain_df["risk_rating"] == "High"].sort_values(
            "emission_contribution_tco2e", ascending=False
        )
        for _, row in high_risk.head(5).iterrows():
            hotspots.append({
                "supplier": row["supplier_name"],
                "country": row["country"],
                "sector": row["sector"],
                "emissions": row["emission_contribution_tco2e"],
                "esg_score": row["esg_score"],
                "risk_factors": row["key_risk_factors"],
            })
        return hotspots

    def _analyze_energy(self, energy_df, current_fy):
        if energy_df.empty:
            return {}

        df_fy = energy_df[energy_df["year"] == current_fy] if current_fy else energy_df
        if df_fy.empty:
            df_fy = energy_df  # fallback to all data

        total_mwh = df_fy["consumption_mwh"].sum()
        renewable_mwh = df_fy[df_fy["renewable"] == "Yes"]["consumption_mwh"].sum()
        renewable_pct = round(renewable_mwh / total_mwh * 100, 1) if total_mwh else 0

        by_source = df_fy.groupby("energy_source")["consumption_mwh"].sum().to_dict()

        return {
            "total_mwh": round(total_mwh, 1),
            "renewable_pct": renewable_pct,
            "by_source": by_source,
        }

    def _generate_narrative(self, scope_totals, yoy_change, hotspots, carbon_intensity):
        hotspot_names = ", ".join(h["supplier"] for h in hotspots[:3]) if hotspots else "none identified"
        prompt = (
            f"Generate a carbon accounting narrative for {company_cfg.company_name} "
            f"({company_cfg.sector} sector). "
            f"Scope 1: {scope_totals.get('Scope 1', 0):.0f} tCO2e, "
            f"Scope 2: {scope_totals.get('Scope 2', 0):.0f} tCO2e, "
            f"Scope 3: {scope_totals.get('Scope 3', 0):.0f} tCO2e. "
            f"Year-over-year change: {yoy_change}%. "
            f"Carbon intensity: {carbon_intensity} tCO2e per $M revenue. "
            f"Top supply chain hotspots: {hotspot_names}. "
            f"Provide analysis and key insights."
        )
        return self.hf.generate_text(prompt)

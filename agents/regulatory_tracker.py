"""Agent 2: Regulatory Tracker — Monitors ESG frameworks and performs gap analysis."""
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from utils.data_processing import load_regulatory_frameworks, load_esg_metrics


# Mapping from data field names to metric IDs in our sample data
DATA_FIELD_MAPPING = {
    "emissions_scope1": ["E01", "E02"],
    "emissions_scope2": ["E01", "E02"],
    "emissions_scope3": ["E02"],
    "emissions_all_scopes": ["E01", "E02"],
    "energy_consumption": ["E10"],
    "energy_intensity": ["E01"],
    "renewable_energy": ["E03"],
    "renewable_energy_pct": ["E03"],
    "water_consumption": ["E04"],
    "water_recycling": ["E05"],
    "waste_generated": ["E06"],
    "waste_recycled": ["E07"],
    "hazardous_waste": ["E08"],
    "biodiversity_impact": ["E09"],
    "land_use": ["E09"],
    "ltifr": ["S06"],
    "safety_training": ["S07"],
    "employee_wellbeing": ["S01", "S02"],
    "diversity": ["S03", "S04"],
    "pay_equity": ["S05"],
    "gender_diversity": ["S03", "S04"],
    "board_diversity": ["G02"],
    "training_hours": ["S07"],
    "anti_corruption": ["G04"],
    "anti_corruption_training": ["G04"],
    "whistleblower": ["G05"],
    "csr_spending": ["S08"],
    "beneficiaries": ["S09"],
    "hr_training": ["S10"],
    "data_privacy": ["G07"],
    "data_breaches": ["G07"],
    "board_governance": ["G01", "G02", "G03"],
    "supplier_audits": ["S12"],
    "supplier_env_audits": ["S12"],
    "supplier_social_audits": ["S12"],
    "supply_chain_emissions": ["E02"],
    "supply_chain_labor": ["S12"],
    "engagement_score": ["S02"],
    "new_hires": ["S01"],
    "turnover": ["S02"],
    "voluntary_turnover": ["S02"],
    "involuntary_turnover": ["S02"],
    "climate_targets": ["E01", "E02"],
}


class RegulatoryTrackerAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Regulatory Tracker",
            description="Monitors global ESG frameworks and performs compliance gap analysis.",
        )

    def execute(self, **kwargs):
        self.log("Loading regulatory frameworks")
        frameworks_data = load_regulatory_frameworks()
        metrics_df = load_esg_metrics()

        if not frameworks_data or "frameworks" not in frameworks_data:
            return {"error": "No regulatory framework data available"}

        available_metrics = set(metrics_df["metric_id"].tolist()) if not metrics_df.empty else set()

        framework_results = {}
        for fw_name, fw_data in frameworks_data["frameworks"].items():
            result = self._analyze_framework(fw_name, fw_data, available_metrics)
            framework_results[fw_name] = result
            self.log(f"{fw_name}: {result['compliance_pct']}% compliant "
                     f"({result['covered']}/{result['total']} requirements)")

        # Generate AI-powered gap analysis narrative
        gap_narrative = self._generate_gap_narrative(framework_results)

        # Compute overall compliance
        all_pcts = [r["compliance_pct"] for r in framework_results.values()]
        overall_compliance = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else 0

        results = {
            "framework_results": framework_results,
            "overall_compliance": overall_compliance,
            "gap_narrative": gap_narrative,
            "frameworks_analyzed": len(framework_results),
        }

        state_manager.publish("regulatory_results", results, self.name)
        return results

    def _analyze_framework(self, fw_name, fw_data, available_metrics):
        requirements = fw_data.get("requirements", [])
        covered = 0
        partial = 0
        gaps = []

        for req in requirements:
            data_fields = req.get("data_fields", [])
            mapped_metrics = set()
            for field in data_fields:
                mapped_metrics.update(DATA_FIELD_MAPPING.get(field, []))

            if not mapped_metrics:
                gaps.append({
                    "requirement_id": req["id"],
                    "requirement": req["requirement"],
                    "status": "missing",
                    "priority": req.get("priority", "medium"),
                    "reason": "No data mapping available",
                })
            elif mapped_metrics & available_metrics:
                overlap = len(mapped_metrics & available_metrics)
                if overlap == len(mapped_metrics):
                    covered += 1
                else:
                    partial += 1
                    gaps.append({
                        "requirement_id": req["id"],
                        "requirement": req["requirement"],
                        "status": "partial",
                        "priority": req.get("priority", "medium"),
                        "reason": f"Only {overlap}/{len(mapped_metrics)} data fields available",
                    })
            else:
                gaps.append({
                    "requirement_id": req["id"],
                    "requirement": req["requirement"],
                    "status": "missing",
                    "priority": req.get("priority", "medium"),
                    "reason": "Required data not found in available metrics",
                })

        total = len(requirements)
        compliance_pct = round((covered + partial * 0.5) / total * 100, 1) if total > 0 else 0

        return {
            "full_name": fw_data.get("full_name", fw_name),
            "mandatory": fw_data.get("mandatory", False),
            "total": total,
            "covered": covered,
            "partial": partial,
            "missing": total - covered - partial,
            "compliance_pct": compliance_pct,
            "gaps": gaps,
        }

    def _generate_gap_narrative(self, framework_results):
        critical_gaps = []
        for fw_name, result in framework_results.items():
            for gap in result.get("gaps", []):
                if gap["priority"] == "critical":
                    critical_gaps.append(f"{fw_name}: {gap['requirement']} ({gap['status']})")

        prompt = (
            f"Generate a concise ESG regulatory gap analysis summary. "
            f"Frameworks analyzed: {', '.join(framework_results.keys())}. "
            f"Critical gaps found: {'; '.join(critical_gaps[:5]) if critical_gaps else 'None'}. "
            f"Provide 2-3 key recommendations for improving compliance."
        )
        return self.hf.generate_text(prompt)

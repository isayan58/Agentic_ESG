"""Agent 2: Regulatory Tracker — Monitors ESG frameworks and performs gap analysis."""
import threading
import json
from datetime import datetime, timedelta
from core.base_agent import BaseAgent
from core.channels import Channel
from core.state_manager import state_manager
from core.data_access import get_dataset
from core.company_config import company_cfg
from utils.data_processing import load_regulatory_frameworks, load_esg_metrics


# Mapping from framework data_field names to metric IDs in esg_metrics.
#
# The numbering follows the canonical metric-ID taxonomy in DATA_MODEL.md §9
# (E01–E25, S01–S25, G01–G25). New entries below close the 45 framework gaps
# previously reporting "No data mapping available" — particularly the SOX,
# SEC-Climate, CSRD-DM, and CSRD-E3 governance/compliance fields.
DATA_FIELD_MAPPING = {
    # ── Climate & emissions ──
    "emissions_scope1":          ["E01"],
    "emissions_scope2":          ["E01"],
    "emissions_scope3":          ["E02"],
    "emissions_all_scopes":      ["E01", "E02"],
    "supply_chain_emissions":    ["E02"],
    "climate_targets":           ["E01", "E02"],
    "emissions_assurance":       ["E25", "G14"],
    "transition_plan":           ["E14", "E15", "G10"],

    # ── Energy ──
    "energy_consumption":        ["E10"],
    "energy_intensity":          ["E22"],
    "renewable_energy":          ["E03"],
    "renewable_energy_pct":      ["E03"],
    "energy_strategy":           ["E03", "E10", "G10"],
    "grid_electricity_pct":      ["E21"],

    # ── Water ──
    "water_consumption":         ["E04"],
    "water_recycling":           ["E05"],
    "water_pollution":           ["E12"],
    "water_discharge":           ["E12"],
    "water_stress":              ["E24"],

    # ── Waste & circularity ──
    "waste_generated":           ["E06"],
    "waste_recycled":            ["E07"],
    "hazardous_waste":           ["E08"],

    # ── Biodiversity & land ──
    "biodiversity_impact":       ["E09"],
    "land_use":                  ["E09"],

    # ── Pollution (CSRD-E3) ──
    "air_pollution":             ["E11"],

    # ── Climate-financial (SEC-CLIM SX-14, IFRS S2) ──
    "financial_climate_impact":  ["E14", "E15", "E16"],
    "severe_weather_costs":      ["E15", "E17"],
    "material_events_disclosure":["E16", "G18"],

    # ── Sourcing ──
    "product_sustainability":    ["E19", "S25"],

    # ── Workforce & DEI ──
    "ltifr":                     ["S06"],
    "safety_training":           ["S07"],
    "employee_wellbeing":        ["S01", "S19"],
    "diversity":                 ["S03", "S04"],
    "pay_equity":                ["S05"],
    "gender_diversity":          ["S03", "S04"],
    "racial_diversity":          ["S03"],
    "board_diversity":           ["G02"],
    "training_hours":            ["S07", "S10"],
    "engagement_score":          ["S19"],
    "new_hires":                 ["S01"],
    "turnover":                  ["S02"],
    "voluntary_turnover":        ["S02"],
    "involuntary_turnover":      ["S02"],
    "skill_development":         ["S24"],
    "benefits":                  ["S20", "S19"],
    "hr_assessment":             ["S14"],
    "incidents":                 ["S06", "S22", "S23"],

    # ── Human rights & community ──
    "csr_spending":              ["S08"],
    "beneficiaries":             ["S09"],
    "community_impact":          ["S08", "S09"],
    "hr_training":               ["S10", "S14"],
    "indigenous_rights":         ["S17"],
    "stakeholder_engagement":    ["G13"],

    # ── Customer / product ──
    "consumer_complaints":       ["S15"],
    "product_safety":            ["S16"],

    # ── Privacy & cyber ──
    "data_privacy":              ["G07"],
    "data_breaches":             ["G07", "G18"],
    "gdpr_compliance":           ["G07"],
    "pii_records":               ["G07"],
    "privacy_policy":            ["G07"],

    # ── Board & ethics ──
    "board_governance":          ["G01", "G02", "G03"],
    "anti_corruption":           ["G04"],
    "anti_corruption_training":  ["G04"],
    "whistleblower":             ["G05"],
    "corruption_incidents":      ["G17"],
    "lobbying":                  ["G16"],
    "policy_advocacy":           ["G16"],
    "ethical_ai_revenue":        ["G18", "G07"],

    # ── SOX / ICFR ──
    "icfr_assessment":           ["G06"],
    "internal_controls":         ["G06", "G25"],
    "control_deficiencies":      ["G06"],
    "ceo_cfo_certification":     ["G08"],
    "disclosure_controls":       ["G19"],
    "document_retention":        ["G20"],
    "audit_trail":               ["G24"],

    # ── Climate governance (TCFD / IFRS S2 / SEC-CLIM 1501-1502) ──
    "climate_gov_structure":     ["G09"],
    "climate_strategy":          ["G10"],
    "climate_risk_assessment":   ["G11"],
    "climate_risk_process":      ["G11"],

    # ── Materiality (CSRD-DM) ──
    "materiality_assessment":    ["G12"],

    # ── Supply chain risk ──
    "supplier_audits":           ["S12"],
    "supplier_env_audits":       ["S12"],
    "supplier_social_audits":    ["S12"],
    "supplier_env_screening":    ["S12"],
    "supplier_social_screening": ["S12"],
    "supplier_dependency":       ["S12"],
    "supply_risk":               ["S12", "G21"],
    "supply_chain_labor":        ["S12", "S14"],
}


class RegulatoryTrackerAgent(BaseAgent):
    output_channel = Channel.REGULATORY

    def __init__(self):
        super().__init__(
            name="Regulatory Tracker",
            description="Monitors global ESG frameworks and performs compliance gap analysis.",
        )
        self.frameworks_cache = None
        self.last_updated = None
        self.update_interval_hours = 24
        self.background_thread = None
        self.running = True
        self._start_background_updater()

    def _start_background_updater(self):
        """Start a background thread that updates regulatory data every 24 hours."""
        def background_update():
            while self.running:
                try:
                    # Wait for 24 hours or until stopped
                    for _ in range(self.update_interval_hours * 60):
                        if not self.running:
                            break
                        threading.Event().wait(60)  # Check every minute
                    
                    if self.running:
                        self.log("Auto-updating regulatory frameworks from external sources...")
                        self._fetch_and_update_frameworks()
                except Exception as e:
                    self.log(f"Error in background updater: {str(e)}")
        
        self.background_thread = threading.Thread(target=background_update, daemon=True)
        self.background_thread.start()

    def _fetch_and_update_frameworks(self):
        """Fetch regulatory data from external sources and update cache."""
        try:
            # Simulate fetching from external sources (news APIs, regulatory databases, etc.)
            external_updates = self._fetch_external_regulatory_data()
            
            if external_updates:
                # Load current frameworks
                current_frameworks = load_regulatory_frameworks()
                
                # Merge external updates with current frameworks
                updated_frameworks = self._merge_framework_updates(current_frameworks, external_updates)
                
                # Cache the updated frameworks
                self.frameworks_cache = updated_frameworks
                self.last_updated = datetime.now().isoformat()
                
                self.log(f"Regulatory frameworks updated at {self.last_updated}. Found {len(external_updates)} updates.")
        except Exception as e:
            self.log(f"Failed to update regulatory frameworks: {str(e)}")

    def _fetch_external_regulatory_data(self):
        """Fetch regulatory updates from external sources."""
        # Simulated external data sources:
        # - SEC/SEBI regulatory announcements
        # - EU taxonomy updates
        # - GRI standards changes
        # - CSRD deadline updates
        # - Industry-specific regulations
        
        external_updates = {
            "new_requirements": [],
            "updated_frameworks": [],
            "deadline_changes": [],
            "relevant_news": [],
        }
        
        # Example: Check for CSRD deadline changes (in real implementation, call actual APIs)
        csrd_update = {
            "framework": "CSRD",
            "type": "deadline_change",
            "description": "CSRD Phase-in timeline updated for large companies",
            "date": datetime.now().isoformat(),
            "impact": "high",
            "action_required": "Review reporting timeline requirements",
        }
        external_updates["deadline_changes"].append(csrd_update)
        
        # Example: Check for new GRI standards
        gri_update = {
            "framework": "GRI",
            "type": "new_standard",
            "description": "New GRI Standard 418 on Customer Privacy released",
            "date": datetime.now().isoformat(),
            "impact": "medium",
            "action_required": "Assess relevance to company operations",
        }
        external_updates["new_requirements"].append(gri_update)
        
        return external_updates

    def _merge_framework_updates(self, current_frameworks, external_updates):
        """Merge external regulatory updates with current frameworks."""
        if not current_frameworks or "frameworks" not in current_frameworks:
            return current_frameworks
        
        updated = current_frameworks.copy()
        
        # Add metadata about external updates
        if "external_updates" not in updated:
            updated["external_updates"] = []
        
        updated["external_updates"].extend(external_updates.get("deadline_changes", []))
        updated["external_updates"].extend(external_updates.get("new_requirements", []))
        updated["last_external_update"] = datetime.now().isoformat()
        
        return updated

    def stop(self):
        """Stop the background updater."""
        self.running = False
        if self.background_thread:
            self.background_thread.join(timeout=5)

    def execute(self, orchestrator=None, **kwargs):
        self.log("Loading regulatory frameworks from disk (live)")
        # Always reload from disk so updates applied via "Global Framework
        # Updates" are reflected immediately in the next compliance analysis.
        frameworks_data = load_regulatory_frameworks()
        self.last_updated = datetime.now().isoformat()

        # Preserve any in-memory external_updates metadata that the background
        # thread has accumulated (these are not persisted to disk).
        if self.frameworks_cache:
            cached_ext = self.frameworks_cache.get("external_updates") or []
            if cached_ext:
                merged = list(frameworks_data.get("external_updates") or [])
                seen = {u.get("description") for u in merged}
                for u in cached_ext:
                    if u.get("description") not in seen:
                        merged.append(u)
                frameworks_data["external_updates"] = merged
            if self.frameworks_cache.get("last_external_update"):
                frameworks_data.setdefault(
                    "last_external_update",
                    self.frameworks_cache["last_external_update"],
                )
        self.frameworks_cache = frameworks_data
        
        metrics_df = get_dataset("esg_metrics", load_esg_metrics)

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
        reporter_profile = self._classify_reporter_profile(framework_results)

        # Compute overall compliance
        all_pcts = [r["compliance_pct"] for r in framework_results.values()]
        overall_compliance = round(sum(all_pcts) / len(all_pcts), 1) if all_pcts else 0

        # Extract external updates if available
        external_updates = frameworks_data.get("external_updates", [])
        
        regulatory_action_plan = self._generate_regulatory_action_plan(framework_results)

        results = {
            "framework_results": framework_results,
            "overall_compliance": overall_compliance,
            "gap_narrative": gap_narrative,
            "regulatory_action_plan": regulatory_action_plan,
            "reporter_profile": reporter_profile,
            "frameworks_analyzed": len(framework_results),
            "external_updates": external_updates,
            "frameworks_last_updated": frameworks_data.get("last_external_update"),
        }

        # Post regulatory updates to orchestrator's message board
        if orchestrator and external_updates:
            self._post_regulatory_alerts(orchestrator, external_updates)

        return results

    def _post_regulatory_alerts(self, orchestrator, external_updates):
        """Post regulatory alerts to orchestrator's message board for planner awareness."""
        alerts = []
        for update in external_updates:
            alerts.append(f"{update.get('framework')}: {update.get('description')} (Impact: {update.get('impact')})")
        
        if alerts:
            message = f"Regulatory updates detected: {'; '.join(alerts[:3])}"
            orchestrator.post_message("regulatory_tracker", message)

    def _analyze_framework(self, fw_name, fw_data, available_metrics):
        requirements = fw_data.get("requirements", [])
        covered = 0
        partial = 0
        gaps = []

        for req in requirements:
            data_fields = req.get("data_fields", [])
            # Split fields by whether they're satisfied by at least one of
            # the currently-available metric IDs. ``missing_fields`` is
            # what the Regulatory Tracker UI surfaces as "add this data to
            # close the gap" — it's the list the gap-fill helper pages
            # read from ``utils.gap_suggestions``.
            missing_fields = []
            covered_fields = []
            all_required_metrics = set()
            for field in data_fields:
                mapped_for_field = set(DATA_FIELD_MAPPING.get(field, []))
                all_required_metrics.update(mapped_for_field)
                if not mapped_for_field:
                    # Field has no mapping → we can't verify coverage, so
                    # treat it as missing for the purpose of user-facing
                    # suggestions.
                    missing_fields.append(field)
                elif mapped_for_field & available_metrics:
                    covered_fields.append(field)
                else:
                    missing_fields.append(field)

            if not all_required_metrics:
                gaps.append({
                    "requirement_id": req["id"],
                    "requirement": req["requirement"],
                    "status": "missing",
                    "priority": req.get("priority", "medium"),
                    "reason": "No data mapping available",
                    "data_fields": list(data_fields),
                    "missing_fields": list(data_fields),
                    "covered_fields": [],
                })
            elif all_required_metrics & available_metrics:
                overlap = len(all_required_metrics & available_metrics)
                if overlap == len(all_required_metrics):
                    covered += 1
                else:
                    partial += 1
                    gaps.append({
                        "requirement_id": req["id"],
                        "requirement": req["requirement"],
                        "status": "partial",
                        "priority": req.get("priority", "medium"),
                        "reason": f"Only {overlap}/{len(all_required_metrics)} data fields available",
                        "data_fields": list(data_fields),
                        "missing_fields": missing_fields,
                        "covered_fields": covered_fields,
                    })
            else:
                gaps.append({
                    "requirement_id": req["id"],
                    "requirement": req["requirement"],
                    "status": "missing",
                    "priority": req.get("priority", "medium"),
                    "reason": "Required data not found in available metrics",
                    "data_fields": list(data_fields),
                    "missing_fields": missing_fields or list(data_fields),
                    "covered_fields": covered_fields,
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
        return self.hf.generate_text(prompt, agent="regulatory_tracker")

    def _classify_reporter_profile(self, framework_results):
        """Classify the company's reporting posture for regulatory context."""
        mandatory_frameworks = [
            name for name, result in framework_results.items()
            if result.get("mandatory")
        ]
        adopted = set(company_cfg.frameworks_adopted)

        is_listed_india = any(ex in {"BSE", "NSE"} for ex in company_cfg.listed_exchanges)
        mandatory_due_to_listing = is_listed_india and "BRSR" in adopted

        if mandatory_due_to_listing or mandatory_frameworks:
            reporter_type = "Mandatory Reporter"
            rationale = (
                "Listed-entity posture and adopted mandatory frameworks indicate "
                "a mandatory ESG reporting baseline."
            )
        else:
            reporter_type = "Voluntary Reporter"
            rationale = (
                "Current framework posture looks primarily voluntary, with optional "
                "alignment used for market positioning and readiness."
            )

        return {
            "classification": reporter_type,
            "mandatory_frameworks": mandatory_frameworks,
            "voluntary_frameworks": [
                name for name in framework_results if name not in mandatory_frameworks
            ],
            "listed_entity": is_listed_india,
            "rationale": rationale,
        }

    def _generate_regulatory_action_plan(self, framework_results):
        prompt = (
            f"You are an ESG regulatory advisor. Based on the framework gap analysis, "
            f"create a prioritized action plan with 4 recommendations for closing the most important compliance gaps. "
            f"Frameworks: {', '.join(framework_results.keys())}. "
            f"Provide each item as a short bullet with the target audience and expected impact."
        )
        raw = self.hf.generate_text(prompt, max_tokens=260, agent="regulatory_tracker")
        lines = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return lines if lines else [raw.strip()]

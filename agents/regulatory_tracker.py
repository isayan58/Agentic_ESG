"""Agent 2: Regulatory Tracker — Monitors ESG frameworks and performs gap analysis."""
import threading
import json
from datetime import datetime, timedelta
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.data_access import get_dataset
from core.company_config import company_cfg
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
        self.log("Loading regulatory frameworks")
        # Use cached frameworks if available, otherwise load fresh
        if self.frameworks_cache:
            frameworks_data = self.frameworks_cache
            self.log(f"Using cached regulatory frameworks (last updated: {self.last_updated})")
        else:
            frameworks_data = load_regulatory_frameworks()
            self.frameworks_cache = frameworks_data
            self.last_updated = datetime.now().isoformat()
        
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

        state_manager.publish("regulatory_results", results, self.name)
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
        return self.hf.generate_text(prompt)

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
        raw = self.hf.generate_text(prompt, max_tokens=260)
        lines = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return lines if lines else [raw.strip()]

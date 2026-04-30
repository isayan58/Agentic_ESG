"""Agent 7: Action Agent — Generates prioritized recommendations from ESG insights."""
from datetime import datetime, timedelta
from core.base_agent import BaseAgent
from core.channels import Channel
from core.state_manager import state_manager
from core.company_config import company_cfg


class ActionAgent(BaseAgent):
    output_channel = Channel.ACTION

    def __init__(self):
        super().__init__(
            name="Action Agent",
            description="Generates prioritized, actionable ESG recommendations with timelines.",
        )

    def execute(self, **kwargs):
        self.log("Generating action recommendations")

        # Gather insights from other agents
        risk_results = state_manager.subscribe(Channel.RISK) or {}
        audit_results = state_manager.subscribe(Channel.AUDIT) or {}
        carbon_results = state_manager.subscribe(Channel.CARBON) or {}
        regulatory_results = state_manager.subscribe(Channel.REGULATORY) or {}
        roi_results = state_manager.subscribe(Channel.ROI) or {}

        # Generate recommendations from each source
        actions = []
        actions.extend(self._actions_from_risks(risk_results))
        actions.extend(self._actions_from_audit(audit_results))
        actions.extend(self._actions_from_carbon(carbon_results))
        actions.extend(self._actions_from_regulatory(regulatory_results))

        # Remove duplicates and sort by priority
        actions = self._deduplicate_and_rank(actions)
        actions = self._apply_implementation_friction(
            actions, risk_results, carbon_results, regulatory_results, roi_results
        )

        # Generate AI-enhanced descriptions
        for action in actions:
            action["detailed_description"] = self._enhance_description(action)

        targets = self._generate_targets(
            actions, risk_results, audit_results, carbon_results, regulatory_results, roi_results
        )

        # Compute summary statistics
        cost_unit = company_cfg.currency_unit
        summary = {
            "total_actions": len(actions),
            "critical": sum(1 for a in actions if a["priority"] == "Critical"),
            "high": sum(1 for a in actions if a["priority"] == "High"),
            "medium": sum(1 for a in actions if a["priority"] == "Medium"),
            "low": sum(1 for a in actions if a["priority"] == "Low"),
            "total_investment": sum(a.get("estimated_cost", 0) for a in actions),
            "adjusted_investment": round(sum(a.get("adjusted_cost", a.get("estimated_cost", 0)) for a in actions), 2),
            "net_value": round(sum(a.get("net_value", 0) for a in actions), 2),
            "avg_friction_score": round(
                sum(a.get("implementation_friction_score", 0) for a in actions) / len(actions), 1
            ) if actions else 0,
            "cost_unit": cost_unit,
        }

        results = {
            "actions": actions,
            "targets": targets,
            "summary": summary,
            "roadmap_narrative": self._generate_roadmap_narrative(actions, summary),
        }

        return results

    def _actions_from_risks(self, risk_results):
        actions = []
        supplier_risks = risk_results.get("supplier_risks", {})
        ac = company_cfg.action_costs
        t = company_cfg.thresholds

        if supplier_risks.get("high_risk_count", 0) > 0:
            actions.append({
                "action": "Implement supplier ESG engagement program",
                "category": "Supply Chain",
                "priority": "Critical",
                "source": "Risk Predictor",
                "duration_weeks": ac.supplier_engagement_weeks,
                "estimated_cost": ac.supplier_engagement_cost,
                "impact": "Reduce supply chain risk exposure by 40%",
                "kpi": "Supplier ESG score improvement",
            })

        if supplier_risks.get("overdue_audits", 0) > 0:
            actions.append({
                "action": "Complete overdue supplier audits",
                "category": "Supply Chain",
                "priority": "High",
                "source": "Risk Predictor",
                "duration_weeks": ac.overdue_audit_weeks,
                "estimated_cost": ac.overdue_audit_cost,
                "impact": "Close audit gaps for regulatory readiness",
                "kpi": "Audit completion rate",
            })

        climate_risks = risk_results.get("climate_risks", {})
        if climate_risks.get("transition_risk", 0) > t.transition_risk_trigger:
            actions.append({
                "action": "Accelerate transition risk mitigation strategy",
                "category": "Climate",
                "priority": "High",
                "source": "Risk Predictor",
                "duration_weeks": ac.transition_risk_weeks,
                "estimated_cost": ac.transition_risk_cost,
                "impact": "Reduce transition risk score by 20 points",
                "kpi": "Transition risk score",
            })

        return actions

    def _actions_from_audit(self, audit_results):
        actions = []
        checklist = audit_results.get("compliance_checklist", [])
        ac = company_cfg.action_costs
        t = company_cfg.thresholds

        for item in checklist:
            if item.get("status") == "Fail":
                actions.append({
                    "action": f"Remediate: {item.get('requirement', 'Unknown')}",
                    "category": "Compliance",
                    "priority": "Critical",
                    "source": "Audit Agent",
                    "duration_weeks": ac.compliance_remediation_weeks,
                    "estimated_cost": ac.compliance_remediation_cost,
                    "impact": f"Achieve compliance for {item.get('framework', 'General')}",
                    "kpi": "Compliance score",
                })

        readiness = audit_results.get("readiness_score", {})
        if readiness.get("evidence", 0) < t.evidence_score_trigger:
            actions.append({
                "action": "Strengthen evidence documentation and data traceability",
                "category": "Audit Readiness",
                "priority": "Medium",
                "source": "Audit Agent",
                "duration_weeks": ac.evidence_documentation_weeks,
                "estimated_cost": ac.evidence_documentation_cost,
                "impact": "Improve evidence score to 90%+",
                "kpi": "Evidence verifiability rate",
            })

        return actions

    def _actions_from_carbon(self, carbon_results):
        actions = []
        yoy = carbon_results.get("yoy_change_pct", 0)
        ac = company_cfg.action_costs
        t = company_cfg.thresholds

        if yoy > t.yoy_reduction_insufficient:
            actions.append({
                "action": "Increase renewable energy procurement to 60%",
                "category": "Emissions",
                "priority": "High",
                "source": "Carbon Accountant",
                "duration_weeks": ac.renewable_energy_weeks,
                "estimated_cost": ac.renewable_energy_cost,
                "impact": "Reduce Scope 2 emissions by 25%",
                "kpi": "Renewable energy percentage",
            })

        hotspots = carbon_results.get("hotspots", [])
        if hotspots:
            actions.append({
                "action": "Engage top 5 emission-intensive suppliers in reduction programs",
                "category": "Scope 3",
                "priority": "High",
                "source": "Carbon Accountant",
                "duration_weeks": ac.scope3_supplier_weeks,
                "estimated_cost": ac.scope3_supplier_cost,
                "impact": "Target 15% Scope 3 reduction from key suppliers",
                "kpi": "Scope 3 emissions from top suppliers",
            })

        energy = carbon_results.get("energy_analysis", {})
        if energy.get("renewable_pct", 0) < t.renewable_low_trigger:
            office = company_cfg.primary_office()
            actions.append({
                "action": f"Install additional solar capacity at {office}",
                "category": "Energy",
                "priority": "Medium",
                "source": "Carbon Accountant",
                "duration_weeks": ac.solar_installation_weeks,
                "estimated_cost": ac.solar_installation_cost,
                "impact": "Add solar capacity, reduce grid dependency",
                "kpi": "Solar generation capacity (kW)",
            })

        return actions

    def _actions_from_regulatory(self, regulatory_results):
        actions = []
        framework_results = regulatory_results.get("framework_results", {})
        ac = company_cfg.action_costs

        for fw_name, fw_result in framework_results.items():
            critical_gaps = [
                g for g in fw_result.get("gaps", []) if g.get("priority") == "critical"
            ]
            if critical_gaps:
                actions.append({
                    "action": f"Address critical {fw_name} compliance gaps ({len(critical_gaps)} items)",
                    "category": "Regulatory",
                    "priority": "Critical",
                    "source": "Regulatory Tracker",
                    "duration_weeks": ac.regulatory_gap_weeks,
                    "estimated_cost": ac.regulatory_gap_cost,
                    "impact": f"Close {len(critical_gaps)} critical gaps in {fw_name}",
                    "kpi": f"{fw_name} compliance percentage",
                })

        return actions

    def _deduplicate_and_rank(self, actions):
        seen = set()
        unique = []
        for a in actions:
            key = a["action"][:50]
            if key not in seen:
                seen.add(key)
                unique.append(a)

        priority_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        unique.sort(key=lambda x: priority_order.get(x.get("priority", "Low"), 3))

        # Add sequential IDs and timelines
        start = datetime.now()
        for i, action in enumerate(unique):
            action["id"] = f"ACT-{i+1:03d}"
            action["start_date"] = (start + timedelta(weeks=i * 2)).strftime("%Y-%m-%d")
            end = start + timedelta(weeks=i * 2 + action.get("duration_weeks", 4))
            action["end_date"] = end.strftime("%Y-%m-%d")

        return unique

    def _apply_implementation_friction(self, actions, risk_results, carbon_results,
                                       regulatory_results, roi_results):
        """Add realistic execution friction, transaction cost, and net ROI."""
        regime = risk_results.get("market_regime", {}).get("regime", "Transition")
        current_revenue = company_cfg.revenue_local("current") or 1
        roi_anchor = roi_results.get("financial_roi", {}).get("net_financial_benefit", 0)
        risk_anchor = risk_results.get("downside_protection", {}).get("score", 50)

        regime_adj = {"Bull": 0, "Transition": 2, "Stress": 5}.get(regime, 2)
        category_adj = {
            "Compliance": 4,
            "Regulatory": 5,
            "Supply Chain": 6,
            "Climate": 4,
            "Emissions": 4,
            "Scope 3": 6,
            "Energy": 5,
            "Audit Readiness": 2,
        }

        for action in actions:
            base_cost = float(action.get("estimated_cost", 0))
            duration = float(action.get("duration_weeks", 4))
            friction_pct = (
                6
                + duration * 0.35
                + category_adj.get(action.get("category", ""), 3)
                + regime_adj
            )
            transaction_cost = round(base_cost * friction_pct / 100, 2)
            adjusted_cost = round(base_cost + transaction_cost, 2)

            benefit_multiplier = {
                "Compliance": 1.15,
                "Regulatory": 1.20,
                "Supply Chain": 1.35,
                "Climate": 1.30,
                "Emissions": 1.25,
                "Scope 3": 1.30,
                "Energy": 1.28,
                "Audit Readiness": 1.10,
            }.get(action.get("category", ""), 1.15)
            anchor_share = max(0, roi_anchor * 0.08)
            gross_benefit = round(max(base_cost * benefit_multiplier, base_cost + anchor_share), 2)
            net_value = round(gross_benefit - adjusted_cost, 2)
            net_roi_pct = round((net_value / adjusted_cost) * 100, 1) if adjusted_cost else 0

            spend_ratio_pct = adjusted_cost / current_revenue * 100
            liquidity_risk = (
                "High" if spend_ratio_pct > 4 else
                "Medium" if spend_ratio_pct > 2 else
                "Low"
            )
            friction_score = min(
                100,
                round(
                    friction_pct * 2
                    + (10 if liquidity_risk == "High" else 5 if liquidity_risk == "Medium" else 0)
                    + max(0, 60 - risk_anchor) * 0.2,
                    1,
                ),
            )

            action["transaction_cost"] = transaction_cost
            action["adjusted_cost"] = adjusted_cost
            action["estimated_benefit"] = gross_benefit
            action["net_value"] = net_value
            action["net_roi_pct"] = net_roi_pct
            action["liquidity_risk"] = liquidity_risk
            action["implementation_friction_score"] = friction_score
            action["recommended_execution_mode"] = (
                "Phased rollout" if friction_score >= 60 or liquidity_risk != "Low"
                else "Accelerated rollout"
            )

        return actions

    def _generate_targets(self, actions, risk_results, audit_results, carbon_results,
                          regulatory_results, roi_results):
        """Convert analysis outputs into explicit target recommendations."""
        targets = []
        current_year = company_cfg.current_fy or datetime.now().year

        renewable_pct = carbon_results.get("energy_analysis", {}).get("renewable_pct")
        if renewable_pct is not None:
            targets.append({
                "metric": "Renewable Energy Share",
                "current": renewable_pct,
                "target": round(max(renewable_pct + 10, 60), 1),
                "unit": "%",
                "deadline": f"{current_year + 1}-12-31",
                "owner": "Facilities & Sustainability",
                "linked_actions": [a["id"] for a in actions if a.get("category") in {"Energy", "Emissions"}][:2],
            })

        compliance = regulatory_results.get("overall_compliance")
        if compliance is not None:
            targets.append({
                "metric": "Overall Regulatory Compliance",
                "current": compliance,
                "target": round(min(100, max(compliance + 8, 90)), 1),
                "unit": "%",
                "deadline": f"{current_year + 1}-09-30",
                "owner": "Compliance Office",
                "linked_actions": [a["id"] for a in actions if a.get("category") in {"Compliance", "Regulatory"}][:3],
            })

        evidence = audit_results.get("readiness_score", {}).get("evidence")
        if evidence is not None:
            targets.append({
                "metric": "Evidence Verifiability",
                "current": evidence,
                "target": round(min(100, max(evidence + 10, 90)), 1),
                "unit": "%",
                "deadline": f"{current_year + 1}-06-30",
                "owner": "Internal Audit",
                "linked_actions": [a["id"] for a in actions if a.get("category") == "Audit Readiness"][:2],
            })

        supplier_risks = risk_results.get("supplier_risks", {})
        if supplier_risks:
            high_risk = supplier_risks.get("high_risk_count", 0)
            targets.append({
                "metric": "High-Risk Suppliers",
                "current": high_risk,
                "target": max(0, high_risk - 2),
                "unit": "count",
                "deadline": f"{current_year + 1}-12-31",
                "owner": "Procurement",
                "linked_actions": [a["id"] for a in actions if a.get("category") in {"Supply Chain", "Scope 3"}][:2],
            })

        iqs = roi_results.get("investment_quality_score", {})
        if iqs:
            current_score = iqs.get("score", 0)
            targets.append({
                "metric": "ESG Investment Quality Score",
                "current": current_score,
                "target": round(min(100, max(current_score + 8, 75)), 1),
                "unit": "score",
                "deadline": f"{current_year + 1}-12-31",
                "owner": "CFO & Sustainability Office",
                "linked_actions": [a["id"] for a in actions[:3]],
            })

        return targets

    def _enhance_description(self, action):
        prompt = (
            f"Write a 2-sentence implementation description for this ESG action item: "
            f"'{action['action']}'. Category: {action['category']}. "
            f"Expected impact: {action.get('impact', 'N/A')}. "
            f"Duration: {action.get('duration_weeks', 4)} weeks. "
            f"Net ROI after friction: {action.get('net_roi_pct', 'N/A')}%."
        )
        return self.hf.generate_text(prompt, max_tokens=100, agent="action_item")

    def _generate_roadmap_narrative(self, actions, summary):
        cost_unit = summary.get("cost_unit", company_cfg.currency_unit)
        prompt = (
            f"Generate a brief implementation roadmap summary for {company_cfg.company_name}. "
            f"Total actions: {summary['total_actions']}. "
            f"Critical: {summary['critical']}, High: {summary['high']}. "
            f"Total estimated investment: {summary['total_investment']} ({cost_unit}). "
            f"Top priorities: {', '.join(a['action'] for a in actions[:3])}. "
            f"Provide a strategic overview in 3-4 sentences."
        )
        return self.hf.generate_text(prompt, agent="action_agent")

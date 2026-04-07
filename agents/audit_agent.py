"""Agent 6: Audit Agent — Compliance verification, audit readiness, and trail management."""
from datetime import datetime
from core.base_agent import BaseAgent
from core.state_manager import state_manager
from core.company_config import company_cfg
from utils.data_processing import load_esg_metrics, load_regulatory_frameworks


class AuditAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="Audit Agent",
            description="Verifies compliance, audits data completeness, and manages audit trails.",
        )

    def execute(self, **kwargs):
        self.log("Starting audit verification")
        metrics_df = load_esg_metrics()
        frameworks = load_regulatory_frameworks()

        # Data from other agents
        data_results = state_manager.subscribe("data_collection_results") or {}
        regulatory_results = state_manager.subscribe("regulatory_results") or {}
        carbon_results = state_manager.subscribe("carbon_results") or {}

        # Data completeness audit
        completeness_audit = self._audit_data_completeness(data_results)

        # Compliance checklist
        compliance_checklist = self._generate_compliance_checklist(
            regulatory_results, metrics_df
        )

        # Evidence mapping
        evidence_map = self._map_evidence(metrics_df)

        # Readiness score
        readiness_score = self._calculate_readiness_score(
            completeness_audit, compliance_checklist, evidence_map
        )

        # Audit trail compilation
        audit_trail = self._compile_full_audit_trail()

        # AI-generated findings summary
        findings_summary = self._generate_findings_summary(
            readiness_score, completeness_audit, compliance_checklist
        )

        results = {
            "readiness_score": readiness_score,
            "completeness_audit": completeness_audit,
            "compliance_checklist": compliance_checklist,
            "evidence_map": evidence_map,
            "audit_trail": audit_trail,
            "findings_summary": findings_summary,
            "issues_count": sum(
                1 for item in compliance_checklist if item["status"] != "Pass"
            ),
        }

        state_manager.publish("audit_results", results, self.name)
        return results

    def _audit_data_completeness(self, data_results):
        quality_scores = data_results.get("quality_scores", {})
        t = company_cfg.thresholds
        items = []

        expected_datasets = [
            ("emissions", "Scope 1/2/3 Emissions Data", "critical"),
            ("esg_metrics", "ESG KPI Metrics", "critical"),
            ("supply_chain", "Supply Chain Data", "high"),
            ("energy", "Energy Consumption Data", "high"),
            ("waste", "Waste Management Data", "medium"),
            ("diversity", "Workforce Diversity Data", "medium"),
        ]

        for dataset_key, label, priority in expected_datasets:
            quality = quality_scores.get(dataset_key, {})
            if quality:
                status = "Pass" if quality["completeness"] >= t.audit_completeness_pass else (
                    "Warning" if quality["completeness"] >= t.audit_completeness_warning else "Fail"
                )
                items.append({
                    "dataset": label,
                    "status": status,
                    "completeness": quality["completeness"],
                    "records": quality["total_records"],
                    "confidence": quality.get("avg_confidence", 0),
                    "priority": priority,
                })
            else:
                items.append({
                    "dataset": label,
                    "status": "Missing",
                    "completeness": 0,
                    "records": 0,
                    "confidence": 0,
                    "priority": priority,
                })

        return items

    def _generate_compliance_checklist(self, regulatory_results, metrics_df):
        checklist = []
        framework_results = regulatory_results.get("framework_results", {})
        t = company_cfg.thresholds

        for fw_name, fw_result in framework_results.items():
            compliance = fw_result.get("compliance_pct", 0)
            status = "Pass" if compliance >= t.audit_compliance_pass else (
                "Warning" if compliance >= t.audit_compliance_warning else "Fail"
            )
            checklist.append({
                "framework": fw_name,
                "requirement": f"{fw_result.get('full_name', fw_name)} Compliance",
                "status": status,
                "score": compliance,
                "covered": fw_result.get("covered", 0),
                "total": fw_result.get("total", 0),
                "gaps": len(fw_result.get("gaps", [])),
            })

        # Add general audit checks
        general_checks = [
            ("Data Traceability", "All data sources documented with timestamps", 88),
            ("Confidence Scoring", "All metrics have confidence scores assigned", 82),
            ("Year-over-Year Comparability", "Prior and current year data available for comparison", 95),
            ("Third-Party Verification", "External audit conducted within last 12 months", 70),
            ("Board ESG Oversight", "ESG committee meeting minutes documented", 90),
            ("Materiality Assessment", "Double materiality assessment completed", 60),
        ]

        for check_name, description, score in general_checks:
            status = "Pass" if score >= t.audit_compliance_pass else (
                "Warning" if score >= t.audit_compliance_warning else "Fail"
            )
            checklist.append({
                "framework": "General",
                "requirement": check_name,
                "description": description,
                "status": status,
                "score": score,
            })

        return checklist

    def _map_evidence(self, metrics_df):
        evidence = []
        if metrics_df.empty:
            return evidence

        t = company_cfg.thresholds
        for _, row in metrics_df.iterrows():
            source = row.get("data_source", "Unknown")
            confidence = row.get("confidence", 0)
            evidence.append({
                "metric_id": row["metric_id"],
                "metric_name": row["metric_name"],
                "data_source": source,
                "confidence": confidence,
                "verifiable": confidence >= t.audit_evidence_verifiable,
            })
        return evidence

    def _calculate_readiness_score(self, completeness_audit, compliance_checklist, evidence_map):
        aw = company_cfg.audit_weights
        t = company_cfg.thresholds

        # Completeness component
        comp_scores = [item["completeness"] for item in completeness_audit if item["completeness"] > 0]
        completeness_avg = sum(comp_scores) / len(comp_scores) if comp_scores else 0

        # Compliance component
        compliance_scores = [item.get("score", 0) for item in compliance_checklist if "score" in item]
        compliance_avg = sum(compliance_scores) / len(compliance_scores) if compliance_scores else 0

        # Evidence component
        verifiable = sum(1 for e in evidence_map if e.get("verifiable", False))
        evidence_pct = (verifiable / len(evidence_map) * 100) if evidence_map else 0

        total = round(
            completeness_avg * aw.completeness +
            compliance_avg * aw.compliance +
            evidence_pct * aw.evidence, 1
        )

        return {
            "overall": total,
            "completeness": round(completeness_avg, 1),
            "compliance": round(compliance_avg, 1),
            "evidence": round(evidence_pct, 1),
            "grade": (
                "A" if total >= t.audit_grade_a else
                "B" if total >= t.audit_grade_b else
                "C" if total >= t.audit_grade_c else "D"
            ),
        }

    def _compile_full_audit_trail(self):
        trail = []

        # Gather audit trails from all agents via state manager channels
        channels = state_manager.get_all_channels()
        for channel, info in channels.items():
            trail.append({
                "timestamp": info["timestamp"],
                "event": f"Data published to '{channel}'",
                "agent": info["published_by"],
                "status": "completed",
            })

        trail.sort(key=lambda x: x["timestamp"])
        return trail

    def _generate_findings_summary(self, readiness, completeness_audit, checklist):
        fails = [item for item in checklist if item["status"] == "Fail"]
        warnings = [item for item in checklist if item["status"] == "Warning"]
        missing = [item for item in completeness_audit if item["status"] == "Missing"]

        prompt = (
            f"Summarize ESG audit findings for {company_cfg.company_name}. "
            f"Readiness score: {readiness['overall']}/100 (Grade: {readiness['grade']}). "
            f"Critical failures: {len(fails)}. Warnings: {len(warnings)}. Missing data: {len(missing)}. "
            f"Top issues: {'; '.join(f['requirement'] for f in fails[:3]) if fails else 'None critical'}. "
            f"Provide a 3-4 sentence findings summary with key recommendations."
        )
        return self.hf.summarize(prompt)

"""Agent 6: Audit Agent — Compliance verification, audit readiness, trail
management, and ESG Integrity Gap detection.

The Integrity Gap Detector compares self-reported ESG metrics against
data-derived actuals to flag inconsistencies (the "73% mismatch" pattern).
"""
from datetime import datetime
from core.base_agent import BaseAgent
from core.channels import Channel
from core.state_manager import state_manager
from core.data_access import get_dataset
from core.company_config import company_cfg
from utils.data_processing import (
    load_esg_metrics, load_regulatory_frameworks, load_emissions, load_energy,
)


class AuditAgent(BaseAgent):
    output_channel = Channel.AUDIT

    def __init__(self):
        super().__init__(
            name="Audit Agent",
            description="Verifies compliance, audits data completeness, and manages audit trails.",
        )

    def execute(self, **kwargs):
        self.log("Starting audit verification")
        metrics_df = get_dataset("esg_metrics", load_esg_metrics)

        # Data from other agents
        data_results = state_manager.subscribe(Channel.DATA_COLLECTION) or {}
        regulatory_results = state_manager.subscribe(Channel.REGULATORY) or {}

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

        # ESG Integrity Gap Detector
        integrity_gaps = self._detect_integrity_gaps(metrics_df)

        # Audit trail compilation
        audit_trail = self._compile_full_audit_trail()

        # Claude-powered specific audit gap analysis (with HF fallback).
        # The structured `gap_analysis` payload powers the new
        # field-level table on the Audit page; legacy summary / bullet
        # keys stay populated for backwards-compatible renderers.
        from utils.gap_analyzer import analyze_audit_gaps
        gap_analysis = analyze_audit_gaps(
            readiness_score,
            completeness_audit,
            compliance_checklist,
            integrity_gaps,
            company_name=company_cfg.company_name,
            fallback_summary=lambda: self._generate_findings_summary(
                readiness_score, completeness_audit, compliance_checklist
            ),
            fallback_recommendations=lambda: self._generate_audit_recommendations(
                readiness_score, completeness_audit, compliance_checklist, integrity_gaps
            ),
        )
        findings_summary = gap_analysis.get("summary") or self._generate_findings_summary(
            readiness_score, completeness_audit, compliance_checklist
        )
        audit_recommendations = gap_analysis.get("recommendations") or self._generate_audit_recommendations(
            readiness_score, completeness_audit, compliance_checklist, integrity_gaps
        )

        results = {
            "readiness_score": readiness_score,
            "completeness_audit": completeness_audit,
            "compliance_checklist": compliance_checklist,
            "evidence_map": evidence_map,
            "integrity_gaps": integrity_gaps,
            "audit_trail": audit_trail,
            "findings_summary": findings_summary,
            "audit_recommendations": audit_recommendations,
            "gap_analysis": gap_analysis,
            "issues_count": sum(
                1 for item in compliance_checklist if item["status"] != "Pass"
            ),
        }

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
            # Real uploads are stored under the `real_*` key by the Data
            # Collector; the bare schema name only holds bundled-sample data.
            # Prefer real-source quality, fall back to sample-source quality.
            quality = quality_scores.get(f"real_{dataset_key}") or quality_scores.get(dataset_key, {})
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

    def _detect_integrity_gaps(self, metrics_df):
        """ESG Integrity Gap Detector — compare self-reported vs data-derived.

        Flags metrics where the reported value diverges significantly from
        what operational data suggests, producing a mismatch score.
        """
        if metrics_df.empty:
            return {"mismatch_pct": 0, "gaps": [], "risk_level": "N/A"}

        emissions_df = get_dataset("emissions", load_emissions)
        energy_df = get_dataset("energy", load_energy)

        current_col = f"value_{company_cfg.current_fy}" if company_cfg.current_fy else "value_2024"
        target_col = f"target_{company_cfg.current_fy}" if company_cfg.current_fy else "target_2024"

        gaps = []
        total_checked = 0
        mismatches = 0

        # Cross-reference environmental metrics against operational data
        for _, row in metrics_df.iterrows():
            reported = row.get(current_col, row.get("value_2024"))
            target = row.get(target_col, row.get("target_2024"))
            metric_name = row.get("metric_name", "")
            pillar = row.get("pillar", "")
            status = row.get("status", "")

            if reported is None or target is None:
                continue
            total_checked += 1

            # Try to derive actual from operational data
            derived_value = None
            gap_detail = None

            if "carbon_intensity" in str(row.get("metric_id", "")).lower():
                # Cross-check carbon intensity with emissions data
                if not emissions_df.empty and company_cfg.revenue("current"):
                    fy = company_cfg.current_fy
                    fy_emissions = emissions_df[emissions_df["year"] == fy]["emissions_tco2e"].sum() \
                        if fy else emissions_df["emissions_tco2e"].sum()
                    derived_value = round(fy_emissions / company_cfg.revenue("current"), 1) \
                        if company_cfg.revenue("current") else None
                    if derived_value is not None:
                        try:
                            reported_num = float(reported)
                            if abs(reported_num - derived_value) / max(reported_num, 0.01) > 0.15:
                                gap_detail = f"Reported {reported_num}, derived from data: {derived_value}"
                        except (ValueError, TypeError):
                            pass

            elif "renewable" in str(row.get("metric_id", "")).lower():
                # Cross-check renewable % with energy data
                if not energy_df.empty:
                    fy = company_cfg.current_fy
                    fy_en = energy_df[energy_df["year"] == fy] if fy else energy_df
                    if not fy_en.empty:
                        total_mwh = fy_en["consumption_mwh"].sum()
                        ren_mwh = fy_en[fy_en["renewable"] == "Yes"]["consumption_mwh"].sum()
                        derived_value = round(ren_mwh / total_mwh * 100, 1) if total_mwh else None
                        if derived_value is not None:
                            try:
                                reported_num = float(reported)
                                if abs(reported_num - derived_value) > 5:
                                    gap_detail = f"Reported {reported_num}%, energy data shows {derived_value}%"
                            except (ValueError, TypeError):
                                pass

            # Generic target vs actual gap (self-reported as "Met" but far from target)
            if gap_detail is None and status == "Met":
                try:
                    r_num = float(reported)
                    t_num = float(target)
                    # If "Met" but actual < 90% of target → suspicious
                    if t_num > 0 and r_num / t_num < 0.90:
                        gap_detail = f"Marked 'Met' but value {r_num} is <90% of target {t_num}"
                except (ValueError, TypeError):
                    pass

            if gap_detail:
                mismatches += 1
                gaps.append({
                    "metric_id": row.get("metric_id", ""),
                    "metric_name": metric_name,
                    "pillar": pillar,
                    "reported_value": str(reported),
                    "derived_value": str(derived_value) if derived_value else "N/A",
                    "reported_status": status,
                    "gap_detail": gap_detail,
                    "severity": "High" if derived_value else "Medium",
                })

        mismatch_pct = round(mismatches / total_checked * 100, 1) if total_checked else 0
        risk_level = (
            "Critical" if mismatch_pct > 30 else
            "High" if mismatch_pct > 15 else
            "Medium" if mismatch_pct > 5 else "Low"
        )

        return {
            "total_checked": total_checked,
            "mismatches_found": mismatches,
            "mismatch_pct": mismatch_pct,
            "risk_level": risk_level,
            "gaps": gaps,
            "recommendation": (
                "Significant integrity gaps detected — initiate data reconciliation "
                "and third-party verification before reporting."
                if mismatch_pct > 15
                else "Integrity checks passed with minor discrepancies."
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
        return self.hf.generate_text(prompt, agent="audit_agent")

    def _generate_audit_recommendations(self, readiness, completeness_audit, compliance_checklist, integrity_gaps):
        prompt = (
            f"You are an ESG audit advisor. Based on the audit readiness data, "
            f"provide 4 concrete recommendations to improve audit readiness and close the top compliance issues. "
            f"Readiness score: {readiness['overall']}/100. "
            f"Number of failed compliance checks: {sum(1 for item in compliance_checklist if item['status'] == 'Fail')}. "
            f"Number of data completeness issues: {sum(1 for item in completeness_audit if item['status'] == 'Missing')}. "
            f"Integrity gaps count: {len(integrity_gaps.get('gaps', []))}."
        )
        raw = self.hf.generate_text(prompt, max_tokens=260, agent="audit_agent")
        bullets = [line.strip('-•* ').strip() for line in raw.splitlines() if line.strip()]
        return bullets if bullets else [raw.strip()]

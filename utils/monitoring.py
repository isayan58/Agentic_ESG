"""24/7 Always-On Monitoring — Simulates continuous ESG intelligence."""
from datetime import datetime, timedelta
import random
import json


class MonitoringEngine:
    """Simulates a 24/7 always-on monitoring system for ESG data streams."""

    def __init__(self):
        self.is_running = False
        self.alerts = []
        self.data_streams = {
            "emissions_tracker": {"status": "active", "last_reading": None, "frequency": "hourly"},
            "energy_monitor": {"status": "active", "last_reading": None, "frequency": "real-time"},
            "regulatory_scanner": {"status": "active", "last_reading": None, "frequency": "daily"},
            "supplier_risk_feed": {"status": "active", "last_reading": None, "frequency": "6-hourly"},
            "iot_sensor_stream": {"status": "active", "last_reading": None, "frequency": "real-time"},
            "news_sentiment": {"status": "active", "last_reading": None, "frequency": "hourly"},
        }
        self.uptime_hours = 0
        self.events_processed = 0

    def start(self):
        self.is_running = True
        self._simulate_activity()
        return {"status": "Monitoring started", "streams": len(self.data_streams)}

    def stop(self):
        self.is_running = False
        return {"status": "Monitoring stopped"}

    def _simulate_activity(self):
        """Simulate realistic monitoring activity and alerts."""
        random.seed(datetime.now().microsecond)
        now = datetime.now()

        # Update stream readings
        for stream_name, stream in self.data_streams.items():
            stream["last_reading"] = (now - timedelta(minutes=random.randint(1, 30))).isoformat()
            stream["status"] = random.choices(["active", "active", "active", "warning"], weights=[85, 5, 5, 5])[0]

        # Generate realistic alerts
        alert_templates = [
            {
                "type": "data_quality",
                "severity": "warning",
                "source": "emissions_tracker",
                "message": "Scope 3 supplier data confidence dropped below 60% for 3 suppliers",
                "action_required": True,
            },
            {
                "type": "regulatory",
                "severity": "info",
                "source": "regulatory_scanner",
                "message": "SEBI updated BRSR Core framework — new disclosure requirements for FY2025",
                "action_required": True,
            },
            {
                "type": "anomaly",
                "severity": "warning",
                "source": "energy_monitor",
                "message": "Electricity consumption 18% above baseline at Mumbai HQ (HVAC anomaly detected)",
                "action_required": True,
            },
            {
                "type": "compliance",
                "severity": "critical",
                "source": "regulatory_scanner",
                "message": "CSRD double materiality assessment deadline approaching (45 days remaining)",
                "action_required": True,
            },
            {
                "type": "supplier",
                "severity": "warning",
                "source": "supplier_risk_feed",
                "message": "TechParts Global (Tier 1) reported environmental violation in Shenzhen facility",
                "action_required": True,
            },
            {
                "type": "positive",
                "severity": "info",
                "source": "emissions_tracker",
                "message": "Monthly Scope 2 emissions decreased 8% vs. previous month — solar generation up",
                "action_required": False,
            },
            {
                "type": "data_quality",
                "severity": "info",
                "source": "iot_sensor_stream",
                "message": "IoT sensor calibration completed for Bangalore office — water meters verified",
                "action_required": False,
            },
            {
                "type": "rating",
                "severity": "info",
                "source": "news_sentiment",
                "message": "MSCI ESG rating review scheduled for next quarter — current trajectory positive",
                "action_required": False,
            },
            {
                "type": "supplier",
                "severity": "critical",
                "source": "supplier_risk_feed",
                "message": "RawMaterials Inc (Tier 2) audit overdue by 90+ days — escalation required",
                "action_required": True,
            },
            {
                "type": "anomaly",
                "severity": "warning",
                "source": "iot_sensor_stream",
                "message": "Water consumption spike detected at Mumbai HQ — possible leak in B-wing",
                "action_required": True,
            },
        ]

        # Pick 5-8 recent alerts
        num_alerts = random.randint(5, 8)
        selected = random.sample(alert_templates, min(num_alerts, len(alert_templates)))

        self.alerts = []
        for i, alert in enumerate(selected):
            alert["timestamp"] = (now - timedelta(hours=random.randint(1, 72))).isoformat()
            alert["id"] = f"ALERT-{i+1:04d}"
            alert["acknowledged"] = random.choice([True, False]) if not alert["action_required"] else False
            self.alerts.append(alert)

        self.alerts.sort(key=lambda x: x["timestamp"], reverse=True)

        # Simulate uptime
        self.uptime_hours = random.randint(720, 2160)  # 1-3 months
        self.events_processed = self.uptime_hours * random.randint(80, 200)

    def get_dashboard_data(self):
        if not self.is_running:
            self.start()

        critical_alerts = sum(1 for a in self.alerts if a["severity"] == "critical")
        warning_alerts = sum(1 for a in self.alerts if a["severity"] == "warning")
        active_streams = sum(1 for s in self.data_streams.values() if s["status"] == "active")

        return {
            "is_running": self.is_running,
            "uptime_hours": self.uptime_hours,
            "uptime_days": round(self.uptime_hours / 24, 1),
            "events_processed": self.events_processed,
            "active_streams": active_streams,
            "total_streams": len(self.data_streams),
            "streams": self.data_streams,
            "alerts": self.alerts,
            "critical_alerts": critical_alerts,
            "warning_alerts": warning_alerts,
            "health": "healthy" if critical_alerts == 0 else ("degraded" if critical_alerts < 2 else "critical"),
        }


class RegulatoryAutoUpdater:
    """Simulates automatic regulatory framework update detection within 24 hours."""

    def __init__(self):
        self.update_log = []
        self._generate_update_history()

    def _generate_update_history(self):
        now = datetime.now()
        updates = [
            {
                "framework": "BRSR",
                "update_type": "Amendment",
                "description": "SEBI expanded BRSR Core with new value chain disclosure requirements",
                "detected_at": (now - timedelta(hours=8)).isoformat(),
                "response_time_hours": 8,
                "status": "integrated",
                "impact": "medium",
                "changes": ["New Scope 3 Category 1 disclosure", "Supplier ESG scoring mandate", "Water stress area reporting"],
            },
            {
                "framework": "CSRD",
                "update_type": "New Standard",
                "description": "EFRAG published sector-specific ESRS for IT & Telecom",
                "detected_at": (now - timedelta(hours=18)).isoformat(),
                "response_time_hours": 18,
                "status": "analyzing",
                "impact": "high",
                "changes": ["Data center energy efficiency metrics", "Digital waste reporting", "AI ethics disclosure"],
            },
            {
                "framework": "GRI",
                "update_type": "Revision",
                "description": "GRI 303 (Water) updated with enhanced water stress methodology",
                "detected_at": (now - timedelta(days=3)).isoformat(),
                "response_time_hours": 12,
                "status": "integrated",
                "impact": "low",
                "changes": ["New water stress classification", "Watershed-level reporting"],
            },
            {
                "framework": "SASB",
                "update_type": "Guidance",
                "description": "ISSB/SASB convergence guidance for technology sector published",
                "detected_at": (now - timedelta(days=5)).isoformat(),
                "response_time_hours": 22,
                "status": "integrated",
                "impact": "medium",
                "changes": ["Aligned metrics with IFRS S1/S2", "Updated materiality mapping"],
            },
            {
                "framework": "EU Taxonomy",
                "update_type": "New Regulation",
                "description": "EU Taxonomy Delegated Act — new technical screening criteria for ICT",
                "detected_at": (now - timedelta(days=7)).isoformat(),
                "response_time_hours": 16,
                "status": "integrated",
                "impact": "high",
                "changes": ["Substantial contribution criteria for IT services", "DNSH assessment requirements"],
            },
        ]
        self.update_log = updates

    def check_for_updates(self):
        return {
            "total_updates": len(self.update_log),
            "pending": sum(1 for u in self.update_log if u["status"] == "analyzing"),
            "integrated": sum(1 for u in self.update_log if u["status"] == "integrated"),
            "avg_response_hours": round(
                sum(u["response_time_hours"] for u in self.update_log) / len(self.update_log), 1
            ),
            "within_24h": all(u["response_time_hours"] <= 24 for u in self.update_log),
            "updates": self.update_log,
        }


# Singletons
monitoring_engine = MonitoringEngine()
regulatory_updater = RegulatoryAutoUpdater()

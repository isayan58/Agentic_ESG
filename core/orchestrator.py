"""Agent orchestrator — manages dependency graph and pipeline execution."""
from agents.data_collector import DataCollectorAgent
from agents.regulatory_tracker import RegulatoryTrackerAgent
from agents.carbon_accountant import CarbonAccountantAgent
from agents.report_generator import ReportGeneratorAgent
from agents.risk_predictor import RiskPredictorAgent
from agents.audit_agent import AuditAgent
from agents.action_agent import ActionAgent
from agents.stakeholder_agent import StakeholderAgent


# Execution order based on dependency graph
PIPELINE_ORDER = [
    ("data_collector", DataCollectorAgent, []),
    ("regulatory_tracker", RegulatoryTrackerAgent, ["data_collector"]),
    ("carbon_accountant", CarbonAccountantAgent, ["data_collector"]),
    ("risk_predictor", RiskPredictorAgent, ["data_collector", "regulatory_tracker"]),
    ("audit_agent", AuditAgent, ["data_collector", "regulatory_tracker", "carbon_accountant"]),
    ("report_generator", ReportGeneratorAgent, ["audit_agent", "carbon_accountant", "risk_predictor"]),
    ("action_agent", ActionAgent, ["risk_predictor", "audit_agent", "report_generator"]),
    ("stakeholder_agent", StakeholderAgent, ["action_agent", "report_generator"]),
]


class Orchestrator:
    """Manages the execution of all 8 ESG CoPilot agents."""

    def __init__(self):
        self.agents = {}
        self.execution_log = []

        for key, agent_cls, _ in PIPELINE_ORDER:
            self.agents[key] = agent_cls()

    def run_full_pipeline(self, progress_callback=None):
        """Execute all agents in dependency order."""
        results = {}

        for i, (key, _, deps) in enumerate(PIPELINE_ORDER):
            agent = self.agents[key]

            if progress_callback:
                progress_callback(key, "running", i + 1, len(PIPELINE_ORDER))

            agent_results = agent.run()
            results[key] = agent_results

            status = "completed" if agent.status == "completed" else "error"
            self.execution_log.append({
                "agent": key,
                "status": status,
                "step": i + 1,
            })

            if progress_callback:
                progress_callback(key, status, i + 1, len(PIPELINE_ORDER))

        return results

    def run_single_agent(self, agent_key, **kwargs):
        """Execute a single agent."""
        if agent_key not in self.agents:
            return {"error": f"Unknown agent: {agent_key}"}
        return self.agents[agent_key].run(**kwargs)

    def get_agent_statuses(self):
        """Get status of all agents."""
        return {key: agent.get_status_dict() for key, agent in self.agents.items()}

    def get_agent(self, key):
        return self.agents.get(key)

"""Agent orchestrator — dispatches a Claude Opus 4.7 tool-use loop over the
nine ESG domain agents.

Planning is delegated to :mod:`core.agent_loop`, which exposes each domain
agent's ``execute()`` as an Anthropic tool. Claude decides which tools to
call (sequential or parallel), respects the dependency graph baked into the
tool descriptions, and stops when the goal is satisfied. Calculations stay
deterministic — only orchestration decisions are LLM-driven.
"""
from agents.action_agent import ActionAgent
from agents.audit_agent import AuditAgent
from agents.carbon_accountant import CarbonAccountantAgent
from agents.data_collector import DataCollectorAgent
from agents.report_generator import ReportGeneratorAgent
from agents.regulatory_tracker import RegulatoryTrackerAgent
from agents.risk_predictor import RiskPredictorAgent
from agents.roi_agent import ROIAgent
from agents.stakeholder_agent import StakeholderAgent
from core.agent_loop import AnthropicAgentLoop


# Dependency graph — surfaced to Claude through tool descriptions so it can
# plan parallel calls correctly. The orchestrator also enforces it at
# tool-execution time, so a hallucinated out-of-order call is rejected.
PIPELINE_ORDER = [
    ("data_collector", DataCollectorAgent, []),
    ("regulatory_tracker", RegulatoryTrackerAgent, ["data_collector"]),
    ("carbon_accountant", CarbonAccountantAgent, ["data_collector"]),
    ("risk_predictor", RiskPredictorAgent, ["data_collector", "regulatory_tracker"]),
    ("audit_agent", AuditAgent, ["data_collector", "regulatory_tracker", "carbon_accountant"]),
    ("roi_agent", ROIAgent, ["data_collector", "carbon_accountant", "risk_predictor"]),
    ("report_generator", ReportGeneratorAgent, ["audit_agent", "carbon_accountant", "risk_predictor", "roi_agent"]),
    ("action_agent", ActionAgent, ["risk_predictor", "audit_agent", "report_generator", "roi_agent"]),
    ("stakeholder_agent", StakeholderAgent, ["action_agent", "report_generator", "roi_agent"]),
]

DEFAULT_AUTONOMOUS_GOAL = (
    "Prepare the company for ESG reporting and investor readiness through a complete ESG analytics pipeline."
)
MAX_AGENT_LOOP_ITERATIONS = 20


class Orchestrator:
    """Dispatches the agentic Claude tool-use loop over ESG domain agents."""

    def __init__(self):
        self.agents = {}
        self.execution_log = []
        self.planning_log = []
        self.message_board = {}

        for key, agent_cls, _ in PIPELINE_ORDER:
            self.agents[key] = agent_cls()

        self.agent_dependencies = {key: deps for key, _, deps in PIPELINE_ORDER}
        self.agent_order = [key for key, _, _ in PIPELINE_ORDER]
        self.agent_descriptions = {
            key: self.agents[key].description for key, _, _ in PIPELINE_ORDER
        }
        self._loop = None  # constructed lazily so importing this module
                           # never requires ANTHROPIC_API_KEY to be set

    def _get_loop(self):
        if self._loop is None:
            self._loop = AnthropicAgentLoop(self)
        return self._loop

    def run_full_pipeline(self, progress_callback=None, data_collector_kwargs=None,
                          user_goal=None, max_steps=MAX_AGENT_LOOP_ITERATIONS):
        """Execute the pipeline as a Claude-driven tool-use loop."""
        goal = user_goal or DEFAULT_AUTONOMOUS_GOAL
        return self.run_autonomous_pipeline(
            goal,
            progress_callback=progress_callback,
            data_collector_kwargs=data_collector_kwargs,
            max_steps=max_steps,
        )

    def run_autonomous_pipeline(self, goal, progress_callback=None,
                                data_collector_kwargs=None,
                                max_steps=MAX_AGENT_LOOP_ITERATIONS):
        results = {}
        self.execution_log = []
        self.planning_log = []

        try:
            self._get_loop().run(
                goal=goal,
                results=results,
                data_collector_kwargs=data_collector_kwargs,
                progress_callback=progress_callback,
                max_iterations=max_steps,
            )
        except Exception as exc:
            self.execution_log.append({
                "agent": "planner",
                "status": "error",
                "details": f"Agent loop failed: {exc}",
            })
            self.planning_log.append({
                "step": len(self.planning_log) + 1,
                "agent": "planner",
                "reason": f"Agent loop failed: {exc}",
                "error": str(exc),
            })

        return {"planning": self.planning_log, **results}

    def _can_run_agent(self, agent_key, results):
        if agent_key not in self.agents:
            return False
        for dep in self.agent_dependencies.get(agent_key, []):
            dep_results = results.get(dep)
            if dep_results is None or "error" in dep_results:
                return False
        return True

    def run_single_agent(self, agent_key, **kwargs):
        """Execute a single agent without the planning loop."""
        if agent_key not in self.agents:
            return {"error": f"Unknown agent: {agent_key}"}
        return self.agents[agent_key].run(**kwargs)

    def get_agent_statuses(self):
        return {key: agent.get_status_dict() for key, agent in self.agents.items()}

    def post_message(self, agent_key, message):
        """Allow agents to post messages for inter-agent communication."""
        self.message_board[agent_key] = message

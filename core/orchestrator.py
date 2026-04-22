"""Agent orchestrator — manages dependency graph and LLM-driven pipeline execution."""
import json
import re

from agents.action_agent import ActionAgent
from agents.audit_agent import AuditAgent
from agents.carbon_accountant import CarbonAccountantAgent
from agents.data_collector import DataCollectorAgent
from agents.report_generator import ReportGeneratorAgent
from agents.regulatory_tracker import RegulatoryTrackerAgent
from agents.risk_predictor import RiskPredictorAgent
from agents.roi_agent import ROIAgent
from agents.stakeholder_agent import StakeholderAgent
from core.hf_client import hf_client


# Execution order based on dependency graph
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
MAX_AUTONOMOUS_PLANNER_STEPS = 8


class Orchestrator:
    """Manages the execution of ESG CoPilot agents."""

    def __init__(self):
        self.agents = {}
        self.execution_log = []
        self.planning_log = []
        self.hf = hf_client

        for key, agent_cls, _ in PIPELINE_ORDER:
            self.agents[key] = agent_cls()

        self.agent_dependencies = {
            key: deps for key, _, deps in PIPELINE_ORDER
        }
        self.agent_order = [key for key, _, _ in PIPELINE_ORDER]
        self.agent_descriptions = {
            key: self.agents[key].description for key, _, _ in PIPELINE_ORDER
        }

    def run_full_pipeline(self, progress_callback=None, data_collector_kwargs=None,
                          user_goal=None, max_steps=MAX_AUTONOMOUS_PLANNER_STEPS):
        """Execute the pipeline with an LLM-driven planning loop.

        The LLM observes the goal, the available agents, and intermediate results,
        then decides which agent to run next or whether the pipeline is complete.
        """
        goal = user_goal or self.DEFAULT_AUTONOMOUS_GOAL
        return self.run_autonomous_pipeline(
            goal,
            progress_callback=progress_callback,
            data_collector_kwargs=data_collector_kwargs,
            max_steps=max_steps,
        )

    def run_autonomous_pipeline(self, goal, progress_callback=None,
                                data_collector_kwargs=None, max_steps=MAX_AUTONOMOUS_PLANNER_STEPS):
        results = {}
        self.execution_log = []
        self.planning_log = []

        for step in range(max_steps):
            plan_step = self._plan_next_step(goal, results)
            self.planning_log.append(plan_step)

            if plan_step["action"] == "stop":
                self.execution_log.append({
                    "agent": "planner",
                    "status": "stopped",
                    "step": step + 1,
                    "details": plan_step.get("reason", "Goal achieved or no further actions needed."),
                })
                break

            agent_key = plan_step["agent"]
            if not self._can_run_agent(agent_key, results):
                plan_step = self._fallback_plan(results, reason="Planned agent was invalid or dependencies were not met.")
                self.planning_log[-1] = plan_step
                if plan_step["action"] == "stop":
                    self.execution_log.append({
                        "agent": "planner",
                        "status": "stopped",
                        "step": step + 1,
                        "details": plan_step.get("reason", "Goal achieved or no further actions needed."),
                    })
                    break
                agent_key = plan_step["agent"]

            if progress_callback:
                progress_callback(agent_key, "running", step + 1, len(self.agent_order))
            run_kwargs = data_collector_kwargs if (agent_key == "data_collector" and data_collector_kwargs) else {}
            agent_results = self.agents[agent_key].run(**run_kwargs)
            results[agent_key] = agent_results

            status = "completed" if self.agents[agent_key].status == "completed" else "error"
            self.execution_log.append({
                "agent": agent_key,
                "status": status,
                "step": step + 1,
            })

            if progress_callback:
                progress_callback(agent_key, status, step + 1, len(self.agent_order))

            if status == "error":
                break

        return {"planning": self.planning_log, **results}

    def _plan_next_step(self, goal, results):
        prompt = self._build_planner_prompt(goal, results)
        plan_text = self.hf.generate_text(prompt)
        plan = self._parse_planner_response(plan_text)
        if self._is_valid_plan(plan, results):
            return plan
        return self._fallback_plan(results, reason="Planner output invalid or unparseable.")

    def _build_planner_prompt(self, goal, results):
        completed = [key for key in self.agent_order if key in results]
        available = [key for key in self.agent_order if key not in results and self._can_run_agent(key, results)]
        dependency_lines = [f"- {key}: depends on {', '.join(deps) or 'nothing'}" for key, deps in self.agent_dependencies.items()]
        agent_lines = [f"- {key}: {self.agent_descriptions[key]}" for key in self.agent_order]

        prompt = (
            f"You are an autonomous ESG orchestration agent. Your goal is: {goal}\n\n"
            "Available agents and their descriptions:\n"
            + "\n".join(agent_lines)
            + "\n\nDependencies:\n"
            + "\n".join(dependency_lines)
            + "\n\nCurrent pipeline state:\n"
            f"Completed agents: {completed or ['none']}\n"
            f"Next available agents: {available or ['none']}\n\n"
            "Decide the next action for the pipeline. You may run one agent at a time, "
            "or STOP if the goal is already satisfied. Only choose agents whose dependencies "
            "have already completed, and do not rerun agents that already completed successfully."
            "\n\nRespond using JSON only with the following shape:\n"
            "{\"action\":\"run_agent\",\"agent\":\"<agent_key>\",\"reason\":\"<why>\"} or "
            "{\"action\":\"stop\",\"reason\":\"<why>\"}"
        )
        return prompt

    def _parse_planner_response(self, text):
        if not isinstance(text, str):
            return {}
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}

    def _is_valid_plan(self, plan, results):
        if not isinstance(plan, dict):
            return False
        action = plan.get("action")
        if action == "stop":
            return True
        if action != "run_agent":
            return False
        agent = plan.get("agent")
        return agent in self.agents and self._can_run_agent(agent, results)

    def _fallback_plan(self, results, reason=None):
        available = self._available_next_agents(results)
        if available:
            return {
                "action": "run_agent",
                "agent": available[0],
                "reason": reason or "Fallback to static DAG ordering.",
            }
        return {
            "action": "stop",
            "reason": reason or "No further agents can run.",
        }

    def _available_next_agents(self, results):
        return [key for key in self.agent_order if key not in results and self._can_run_agent(key, results)]

    def _can_run_agent(self, agent_key, results):
        if agent_key not in self.agents:
            return False
        deps = self.agent_dependencies.get(agent_key, [])
        for dep in deps:
            dep_results = results.get(dep)
            if dep_results is None or "error" in dep_results:
                return False
        return True

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

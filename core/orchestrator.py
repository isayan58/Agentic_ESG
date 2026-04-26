"""Agent orchestrator — dispatches a Claude Opus 4.7 tool-use loop over the
nine ESG domain agents.

Planning is delegated to :mod:`core.agent_loop`, which exposes each domain
agent's ``execute()`` as an Anthropic tool. Claude decides which tools to
call (sequential or parallel), respects the dependency graph baked into the
tool descriptions, and stops when the goal is satisfied. Calculations stay
deterministic — only orchestration decisions are LLM-driven.

Incremental runs
----------------
The orchestrator memoises each agent's result inside the live process,
keyed on a fingerprint of its dependency inputs. When the user clicks
*Run* a second time without changing data or upstream agents, the loop
short-circuits any agent whose dep-fingerprint matches its prior run and
returns the cached result. Force-full mode clears the cache before the
next run.
"""
import hashlib
import json

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

        # Incremental-run memo: per-agent dep fingerprint → cached result.
        # Stays valid for the life of the orchestrator instance (one
        # signed-in user's Streamlit session). Cleared by
        # ``invalidate_incremental_cache()``.
        self._incremental_cache: dict[str, tuple[str, dict]] = {}
        # Tally of agents reused on the most recent run, for the UI's
        # "Reused N cached agents" status line.
        self._last_cache_hits: list[str] = []

        for key, agent_cls, _ in PIPELINE_ORDER:
            agent = agent_cls()
            # Pin the canonical orchestrator key as the agent's telemetry
            # identifier. Overrides the slug-from-name fallback so the ROI
            # agent records under "roi_agent" (not "esg_roi_agent").
            agent.telemetry_key = key
            # Re-hydrate now that we know the real key — catches any prior
            # persisted state written under this key in a previous session.
            try:
                agent._hydrate_from_telemetry()
            except Exception:
                pass
            self.agents[key] = agent

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
                          user_goal=None, max_steps=MAX_AGENT_LOOP_ITERATIONS,
                          enforce_complete=True):
        """Execute the pipeline as a Claude-driven tool-use loop.

        With ``enforce_complete=True`` (default), any agent the LLM
        planner skipped is run afterwards in dependency order — so
        callers that say "run the full pipeline" actually get all 9
        agents in the result, not whatever subset Claude decided was
        sufficient for the goal. The featured ROI card on the ESG
        Command Center page relies on this guarantee to refresh on
        every Run.
        """
        goal = user_goal or DEFAULT_AUTONOMOUS_GOAL
        results = self.run_autonomous_pipeline(
            goal,
            progress_callback=progress_callback,
            data_collector_kwargs=data_collector_kwargs,
            max_steps=max_steps,
        )
        if enforce_complete:
            self._ensure_complete(
                results,
                data_collector_kwargs=data_collector_kwargs,
                progress_callback=progress_callback,
            )
        return results

    def run_autonomous_pipeline(self, goal, progress_callback=None,
                                data_collector_kwargs=None,
                                max_steps=MAX_AGENT_LOOP_ITERATIONS):
        results = {}
        self.execution_log = []
        self.planning_log = []
        self._last_cache_hits = []

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

    def _ensure_complete(self, results, data_collector_kwargs=None,
                         progress_callback=None) -> None:
        """Run any agents the LLM planner left out of ``results``.

        Mutates ``results`` in place. Walks ``agent_order`` once so a
        downstream agent (e.g. ``roi_agent``) gets a chance to run after
        its upstream prerequisites are filled in by an earlier pass of
        this loop. Errored agents are *not* re-run automatically — that
        would mask transient failures the user should see and react to.

        Each fill-in run is fingerprinted into the incremental cache so
        the next ``Run`` button click correctly short-circuits when
        nothing has changed.
        """
        for agent_key in self.agent_order:
            existing = results.get(agent_key)
            if isinstance(existing, dict) and "error" not in existing:
                continue
            if existing is not None:
                # Errored result — leave it. The user needs to see the
                # error, not have us silently retry and possibly mask it.
                continue
            if not self._can_run_agent(agent_key, results):
                continue
            run_kwargs = (data_collector_kwargs or {}) if agent_key == "data_collector" else {}
            if progress_callback:
                progress_callback(agent_key, "running", 0, len(self.agent_order))
            try:
                agent_result = self.agents[agent_key].run(
                    orchestrator=self, **run_kwargs,
                )
            except Exception as exc:  # noqa: BLE001
                self.execution_log.append({
                    "agent": agent_key, "status": "error",
                    "details": f"ensure_complete fill-in failed: {exc}",
                })
                continue
            results[agent_key] = agent_result
            self.execution_log.append({
                "agent": agent_key,
                "status": ("completed"
                           if self.agents[agent_key].status == "completed"
                           else "error"),
                "details": "Filled in by ensure_complete (skipped by planner).",
            })
            if (isinstance(agent_result, dict)
                    and "error" not in agent_result):
                # Keep the incremental cache honest so a follow-up Run
                # short-circuits when inputs haven't changed.
                dep_fp = self.compute_dep_fingerprint(
                    agent_key, results,
                    data_collector_kwargs=data_collector_kwargs,
                )
                self.store_incremental_cache(agent_key, dep_fp, agent_result)
            if progress_callback:
                progress_callback(
                    agent_key, self.agents[agent_key].status or "completed",
                    0, len(self.agent_order),
                )

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

    # ── Incremental-run cache ────────────────────────────────────────────
    def compute_dep_fingerprint(self, agent_key, results,
                                data_collector_kwargs=None) -> str:
        """Stable fingerprint of an agent's *inputs* — not its outputs.

        The fingerprint is what the loop hashes "what would change the
        next run's result" down to. For ``data_collector`` that's the
        connection-manager source signature (or the kwargs surface for
        tests with no manager). For every downstream agent it's the
        chain of upstream result-fingerprints — identical chain ⇒ same
        downstream output, so we can short-circuit.
        """
        if agent_key == "data_collector":
            cm = (data_collector_kwargs or {}).get("connection_manager")
            sources_sig = ""
            if cm is not None:
                try:
                    sources_sig = cm.sources_signature() or ""
                except AttributeError:
                    sources_sig = ""
                except Exception:
                    sources_sig = ""
            payload: dict = {
                "sources": sources_sig,
                "kwargs": sorted((data_collector_kwargs or {}).keys()),
            }
        else:
            deps = self.agent_dependencies.get(agent_key, [])
            payload = {dep: self._fingerprint_for(dep, results) for dep in deps}
        try:
            serialised = json.dumps(payload, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serialised = repr(payload)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]

    def _fingerprint_for(self, agent_key, results) -> str:
        """Return the fingerprint of ``agent_key``'s most recent result.

        Falls back to a hash of the result dict when no entry exists in
        the incremental cache (e.g. when an upstream agent ran
        end-to-end this session for the first time).
        """
        cached = self._incremental_cache.get(agent_key)
        if cached is not None:
            return cached[0]
        result = results.get(agent_key)
        if result is None:
            return ""
        try:
            serialised = json.dumps(result, sort_keys=True, default=str)
        except (TypeError, ValueError):
            serialised = repr(result)
        return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]

    def lookup_incremental_cache(self, agent_key, dep_fingerprint):
        """Return ``(True, cached_result)`` if the cache hits, else ``(False, None)``.

        The first element is a boolean rather than ``cached_result is None`` so
        callers can distinguish "we have a cached empty dict" from "we have
        nothing".
        """
        entry = self._incremental_cache.get(agent_key)
        if entry is None:
            return False, None
        cached_fp, cached_result = entry
        if cached_fp == dep_fingerprint and dep_fingerprint:
            return True, cached_result
        return False, None

    def store_incremental_cache(self, agent_key, dep_fingerprint, result):
        """Memoise an agent's result under its dep fingerprint.

        Errored runs are *not* cached — we don't want a transient
        upstream failure to be reused on subsequent runs once the user
        fixes the cause.
        """
        if not dep_fingerprint:
            return
        if isinstance(result, dict) and "error" in result:
            return
        self._incremental_cache[agent_key] = (dep_fingerprint, result)

    def record_cache_hit(self, agent_key) -> None:
        """Record a per-run cache hit so the UI can summarise reuse."""
        self._last_cache_hits.append(agent_key)

    def invalidate_incremental_cache(self) -> None:
        """Drop every memoised result. Use before a "force full re-run"."""
        self._incremental_cache.clear()
        self._last_cache_hits = []

    def cache_hits_last_run(self) -> list[str]:
        """List of agent keys reused from cache on the most recent run."""
        return list(self._last_cache_hits)

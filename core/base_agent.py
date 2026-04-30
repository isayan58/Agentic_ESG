"""Abstract base class for all ESG Pilot agents."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import ClassVar

from core.hf_client import hf_client
from utils import agent_telemetry


class BaseAgent(ABC):
    """Base class that all ESG Pilot agents inherit from.

    Subclasses set ``output_channel`` to the ``core.channels.Channel`` they
    publish their final result on. ``run()`` then publishes for them, so
    ``execute()`` stays a pure compute step that just returns a dict —
    easier to unit-test and harder to accidentally couple to global state.
    Mid-execute side channels (e.g. data_collector's per-schema feeds) stay
    inline; ``output_channel`` only covers the canonical end-of-run result.
    """

    # Subclasses override this to opt into auto-publish. ``None`` means
    # the agent doesn't have a single canonical output channel and is
    # expected to manage any publishing itself (or none at all).
    output_channel: ClassVar[str | None] = None

    def __init__(self, name, description):
        self.name = name
        self.description = description
        self.hf = hf_client
        self.status = "idle"  # idle, running, completed, error
        self.last_run = None
        self.started_at = None
        self.finished_at = None
        self.runtime_seconds = None
        self.last_error = None
        self.run_count = 0
        self.results = {}
        self.audit_trail = []

        # Stable key for telemetry persistence. The orchestrator overrides
        # this per registered agent; slugified-name is the fallback for ad-
        # hoc agents constructed outside the orchestrator.
        self.telemetry_key = agent_telemetry.slugify(name)

        # Hydrate last-known state from the persistent store so a fresh
        # Streamlit session shows "Last run: 2h ago" instead of "Never".
        self._hydrate_from_telemetry()

    # -- Telemetry plumbing ------------------------------------------------
    def _hydrate_from_telemetry(self) -> None:
        try:
            rec = agent_telemetry.get(self.telemetry_key)
        except Exception:
            rec = None
        if not rec:
            return
        # Keep in-memory status as "idle" on fresh load — if the last
        # persisted run was still "running", something died mid-flight;
        # showing it as running would lie to the user.
        last_status = (rec.get("status") or "").lower()
        if last_status in ("completed", "error"):
            self.status = last_status
        self.last_run = rec.get("last_run") or self.last_run
        self.runtime_seconds = rec.get("runtime_seconds") or self.runtime_seconds
        self.last_error = rec.get("last_error") or self.last_error
        self.run_count = int(rec.get("run_count") or 0)

    def _persist_snapshot(self, *, append_history: bool) -> None:
        """Best-effort persistence — never let telemetry IO break a run."""
        try:
            agent_telemetry.record(
                self.telemetry_key,
                {
                    "name": self.name,
                    "status": self.status,
                    "last_run": self.last_run,
                    "started_at": self.started_at.isoformat() if self.started_at else None,
                    "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                    "runtime_seconds": self.runtime_seconds,
                    "last_error": self.last_error,
                    "run_count": self.run_count,
                },
                append_history=append_history,
            )
        except Exception:
            # Telemetry must never crash the pipeline.
            pass

    def log(self, message, level="info"):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "level": level,
            "message": message,
        }
        self.audit_trail.append(entry)
        # Keep the trail bounded so long-running sessions stay light.
        if len(self.audit_trail) > 200:
            self.audit_trail = self.audit_trail[-200:]

    def run(self, **kwargs):
        self.status = "running"
        self.started_at = datetime.now()
        self.last_error = None
        self.log(f"{self.name} started execution")
        # Persist the "running" state up front so a fresh Streamlit session
        # loading during the run sees "RUNNING" rather than stale data.
        self._persist_snapshot(append_history=False)
        try:
            self.results = self.execute(**kwargs)
            self.status = "completed"
            self.finished_at = datetime.now()
            self.runtime_seconds = (self.finished_at - self.started_at).total_seconds()
            self.last_run = self.finished_at.isoformat()
            self.run_count += 1
            self.log(f"{self.name} completed in {self.runtime_seconds:.2f}s", level="success")
        except Exception as e:
            self.status = "error"
            self.finished_at = datetime.now()
            self.runtime_seconds = (self.finished_at - self.started_at).total_seconds()
            self.last_run = self.finished_at.isoformat()
            self.last_error = str(e)
            self.run_count += 1
            self.log(f"{self.name} failed: {e}", level="error")
            self.results = {"error": str(e)}
        # Terminal state → append a history row so the UI can plot trends.
        self._persist_snapshot(append_history=True)
        # Auto-publish the canonical output for completed runs. Skipped on
        # error so subscribers never see a {"error": ...} sentinel that
        # used to be a real result. Lazy import to dodge import cycles
        # during early bootstrap.
        if self.status == "completed" and self.output_channel:
            try:
                from core.state_manager import state_manager
                state_manager.publish(self.output_channel, self.results, self.name)
            except Exception:
                # Publish IO must never crash the run.
                pass
        return self.results

    @abstractmethod
    def execute(self, **kwargs):
        """Execute the agent's core logic. Must return a dict of results."""
        pass

    def get_status_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "last_run": self.last_run,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "runtime_seconds": self.runtime_seconds,
            "last_error": self.last_error,
            "run_count": self.run_count,
            "has_results": bool(self.results),
            "audit_tail": self.audit_trail[-5:],
        }

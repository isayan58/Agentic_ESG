"""Abstract base class for all ESG CoPilot agents."""
from abc import ABC, abstractmethod
from datetime import datetime
from core.hf_client import hf_client


class BaseAgent(ABC):
    """Base class that all ESG CoPilot agents inherit from."""

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
            self.last_error = str(e)
            self.log(f"{self.name} failed: {e}", level="error")
            self.results = {"error": str(e)}
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

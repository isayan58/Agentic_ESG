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
        self.results = {}
        self.audit_trail = []

    def log(self, message):
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": self.name,
            "message": message,
        }
        self.audit_trail.append(entry)

    def run(self, **kwargs):
        self.status = "running"
        self.log(f"{self.name} started execution")
        try:
            self.results = self.execute(**kwargs)
            self.status = "completed"
            self.last_run = datetime.now().isoformat()
            self.log(f"{self.name} completed successfully")
        except Exception as e:
            self.status = "error"
            self.log(f"{self.name} failed: {str(e)}")
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
            "has_results": bool(self.results),
        }

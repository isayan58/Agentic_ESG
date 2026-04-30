"""Structured per-run state object for the orchestrator.

The legacy pipeline carries state via three loosely-coordinated stores:

- ``StateManager`` — pub/sub channels keyed by user (see core.state_manager).
- ``Orchestrator.results`` — a flat ``{agent_key: result_dict}`` collected
  by the agent loop.
- ``streamlit.session_state`` — UI-side caches sprinkled across pages.

That works, but a debug session means correlating three places. ``RunState``
is the structured envelope we hand to a background-job runner (Step 7) and
will eventually persist to disk (Step 9). For now it sits alongside the
existing channels — opt in where useful, don't force a full rewrite.

Identity, status, and error fields are typed; the ``inputs`` and ``outputs``
maps stay loosely typed because every agent has its own result schema and
formalizing nine of them is out of scope for this step.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


RunStatus = Literal["created", "running", "completed", "error", "budget_exceeded"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentError(BaseModel):
    """One failure recorded during a run.

    Kept small and serializable so persisting the whole RunState is cheap.
    """
    agent: str
    message: str
    timestamp: str = Field(default_factory=_now_iso)


class RunState(BaseModel):
    """One pipeline run, scoped to one user and one company.

    Mutable: agents call ``record_output`` / ``record_error`` to mutate
    in-place. ``model_dump()`` serializes for the job runner (Step 7) or
    persistence layer (Step 9).
    """
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    company_id: str | None = None

    status: RunStatus = "created"
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    errors: list[AgentError] = Field(default_factory=list)

    created_at: str = Field(default_factory=_now_iso)
    started_at: str | None = None
    finished_at: str | None = None

    # ── Mutators ───────────────────────────────────────────────────────────
    def mark_running(self) -> None:
        self.status = "running"
        self.started_at = _now_iso()

    def mark_completed(self) -> None:
        self.status = "completed"
        self.finished_at = _now_iso()

    def mark_error(self) -> None:
        self.status = "error"
        self.finished_at = _now_iso()

    def record_output(self, channel: str, value: Any) -> None:
        """Store an agent's result on a channel.

        Channel names should come from ``core.channels.Channel`` to avoid
        typos, but plain strings are accepted for the dynamic dataset
        channels published by the data collector.
        """
        self.outputs[str(channel)] = value

    def get_output(self, channel: str, default: Any = None) -> Any:
        return self.outputs.get(str(channel), default)

    def record_error(self, agent: str, message: str) -> None:
        self.errors.append(AgentError(agent=agent, message=message))

    def has_errors(self) -> bool:
        return bool(self.errors)

"""Approval workflow: state machine + reviewer queue + SLA tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

STATES = ("draft", "in_review", "approved", "rejected", "changes_requested")

_TRANSITIONS: dict[str, dict[str, str]] = {
    "draft": {"submit": "in_review"},
    "in_review": {"approve": "approved", "reject": "rejected",
                  "request_changes": "changes_requested"},
    "rejected": {"resubmit": "in_review"},
    "changes_requested": {"resubmit": "in_review"},
    "approved": {},
}


class WorkflowError(Exception):
    """Raised on illegal transitions or missing rationale."""


@dataclass
class Review:
    doc_id: str
    reviewer: str
    decision: str
    rationale: str
    at: str


@dataclass
class WorkflowInstance:
    doc_id: str
    workflow: str
    state: str = "draft"
    history: list[Review] = field(default_factory=list)
    submitted_at: str | None = None
    sla_hours: float = 48.0


class WorkflowEngine:
    def __init__(self) -> None:
        self._instances: dict[str, WorkflowInstance] = {}

    def submit(self, doc_id: str, workflow: str = "approval",
               sla_hours: float = 48.0) -> WorkflowInstance:
        inst = self._instances.get(doc_id)
        if inst is None:
            inst = WorkflowInstance(doc_id=doc_id, workflow=workflow,
                                    sla_hours=sla_hours)
            self._instances[doc_id] = inst
        self._move(inst, "submit", reviewer="system", rationale="submitted")
        inst.submitted_at = datetime.now(timezone.utc).isoformat()
        return inst

    def review(self, doc_id: str, decision: str, reviewer: str,
               rationale: str = "") -> WorkflowInstance:
        """decision: approve | reject | request_changes. Rejections and
        change requests require a rationale."""
        if decision not in ("approve", "reject", "request_changes"):
            raise WorkflowError(f"unknown decision '{decision}'")
        if decision in ("reject", "request_changes") and not rationale.strip():
            raise WorkflowError(
                f"decision '{decision}' requires a rationale")
        inst = self._get(doc_id)
        self._move(inst, decision, reviewer=reviewer, rationale=rationale)
        return inst

    def resubmit(self, doc_id: str) -> WorkflowInstance:
        inst = self._get(doc_id)
        self._move(inst, "resubmit", reviewer="system",
                   rationale="resubmitted after changes")
        return inst

    def state(self, doc_id: str) -> str:
        return self._get(doc_id).state

    def sla_status(self, doc_id: str,
                   now: datetime | None = None) -> dict:
        """Hours elapsed vs SLA for an in-review document."""
        inst = self._get(doc_id)
        if inst.submitted_at is None or inst.state != "in_review":
            return {"state": inst.state, "breached": False,
                    "elapsed_hours": 0.0}
        submitted = datetime.fromisoformat(inst.submitted_at)
        now = now or datetime.now(timezone.utc)
        elapsed = (now - submitted).total_seconds() / 3600.0
        return {"state": inst.state, "breached": elapsed > inst.sla_hours,
                "elapsed_hours": round(elapsed, 2),
                "sla_hours": inst.sla_hours}

    def queue(self) -> list[str]:
        """Doc IDs currently awaiting review."""
        return sorted(d for d, i in self._instances.items()
                      if i.state == "in_review")

    def _move(self, inst: WorkflowInstance, action: str, reviewer: str,
              rationale: str) -> None:
        allowed = _TRANSITIONS.get(inst.state, {})
        if action not in allowed:
            raise WorkflowError(
                f"cannot '{action}' from state '{inst.state}'")
        inst.state = allowed[action]
        inst.history.append(Review(
            doc_id=inst.doc_id, reviewer=reviewer, decision=action,
            rationale=rationale,
            at=datetime.now(timezone.utc).isoformat()))

    def _get(self, doc_id: str) -> WorkflowInstance:
        if doc_id not in self._instances:
            raise WorkflowError(f"no workflow for doc '{doc_id}'")
        return self._instances[doc_id]

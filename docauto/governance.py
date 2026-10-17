"""Information governance: retention policies, legal holds, disposition.

Retention policies are defined per doc_type. ``declare_record`` places a
legal hold that blocks deletion/editing. ``run_disposition`` destroys or
archives items whose retention has expired — always citing the policy.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class GovernanceError(Exception):
    """Raised when an operation conflicts with a record declaration."""


@dataclass
class RetentionPolicy:
    doc_type: str
    retention_days: int
    disposition: str  # "destroy" or "archive"

    def due(self, created_at: datetime, as_of: datetime) -> bool:
        return as_of >= created_at + timedelta(days=self.retention_days)


@dataclass
class DispositionRecord:
    doc_id: str
    action: str  # "destroyed" | "archived" | "skipped_record"
    policy: str
    at: str


class RetentionEngine:
    def __init__(self) -> None:
        self._policies: dict[str, RetentionPolicy] = {}
        self._declared: set[str] = set()
        self._created: dict[str, datetime] = {}
        self._types: dict[str, str] = {}
        self._log: list[DispositionRecord] = []

    def add_policy(self, policy: RetentionPolicy) -> None:
        self._policies[policy.doc_type] = policy

    def register(self, doc_id: str, doc_type: str,
                 created_at: datetime | None = None) -> None:
        self._types[doc_id] = doc_type
        self._created[doc_id] = created_at or datetime.now(timezone.utc)

    def declare_record(self, doc_id: str) -> None:
        """Place a legal hold: the document cannot be disposed or edited."""
        self._declared.add(doc_id)

    def release_record(self, doc_id: str) -> None:
        self._declared.discard(doc_id)

    def is_declared(self, doc_id: str) -> bool:
        return doc_id in self._declared

    def guard_edit(self, doc_id: str) -> None:
        if self.is_declared(doc_id):
            raise GovernanceError(
                f"doc '{doc_id}' is a declared record and cannot be edited")

    def run_disposition(self, as_of: datetime | None = None) -> list[DispositionRecord]:
        """Dispose of expired items. Declared records are always skipped."""
        now = as_of or datetime.now(timezone.utc)
        results: list[DispositionRecord] = []
        for doc_id, doc_type in list(self._types.items()):
            policy = self._policies.get(doc_type)
            if policy is None:
                continue
            if not policy.due(self._created[doc_id], now):
                continue
            if self.is_declared(doc_id):
                results.append(DispositionRecord(
                    doc_id=doc_id, action="skipped_record",
                    policy=policy.doc_type,
                    at=now.isoformat()))
                continue
            action = "destroyed" if policy.disposition == "destroy" else "archived"
            results.append(DispositionRecord(
                doc_id=doc_id, action=action, policy=policy.doc_type,
                at=now.isoformat()))
            # Remove from tracking — the document is gone from the store.
            del self._types[doc_id]
            del self._created[doc_id]
        self._log.extend(results)
        return results

    def disposition_log(self) -> list[DispositionRecord]:
        return list(self._log)

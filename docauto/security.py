"""Access control: RBAC over per-document ACLs, plus a hash-chained audit log.

Roles form a hierarchy: viewer < editor < manager < admin.
A document ACL maps role -> allowed actions; a user acts through their role.
Every access decision is recorded in the tamper-evident audit log.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

ROLE_RANK = {"viewer": 1, "editor": 2, "manager": 3, "admin": 4}
ACTIONS = {"read", "write", "delete", "share", "sign"}


class AccessDenied(Exception):
    """Raised when a user attempts an action their role/ACL does not allow."""


@dataclass
class AuditEntry:
    seq: int
    timestamp: str
    user: str
    role: str
    doc_id: str
    action: str
    allowed: bool
    reason: str
    prev_hash: str
    entry_hash: str


class AuditLog:
    """Hash-chained audit log. Each entry commits to the previous entry's
    hash, so tampering with any entry breaks the chain."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, user: str, role: str, doc_id: str, action: str,
               allowed: bool, reason: str) -> AuditEntry:
        prev_hash = self._entries[-1].entry_hash if self._entries else "GENESIS"
        body = json.dumps({
            "seq": len(self._entries),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user, "role": role, "doc_id": doc_id,
            "action": action, "allowed": allowed, "reason": reason,
            "prev_hash": prev_hash,
        }, sort_keys=True)
        entry_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        entry = AuditEntry(
            seq=len(self._entries),
            timestamp=json.loads(body)["timestamp"],
            user=user, role=role, doc_id=doc_id, action=action,
            allowed=allowed, reason=reason,
            prev_hash=prev_hash, entry_hash=entry_hash)
        self._entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        prev = "GENESIS"
        for i, entry in enumerate(self._entries):
            if entry.seq != i or entry.prev_hash != prev:
                return False
            body = json.dumps({
                "seq": entry.seq, "timestamp": entry.timestamp,
                "user": entry.user, "role": entry.role, "doc_id": entry.doc_id,
                "action": entry.action, "allowed": entry.allowed,
                "reason": entry.reason, "prev_hash": entry.prev_hash,
            }, sort_keys=True)
            if hashlib.sha256(body.encode("utf-8")).hexdigest() != entry.entry_hash:
                return False
            prev = entry.entry_hash
        return True

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)


class AccessControl:
    """RBAC with per-document ACLs. ``set_acl(doc_id, min_role)`` sets the
    minimum role required for each action on a document."""

    def __init__(self, audit: AuditLog | None = None) -> None:
        self._acls: dict[str, dict[str, str]] = {}
        self.audit = audit or AuditLog()

    def set_acl(self, doc_id: str, acl: dict[str, str]) -> None:
        for action, role in acl.items():
            if action not in ACTIONS:
                raise ValueError(f"unknown action '{action}'")
            if role not in ROLE_RANK:
                raise ValueError(f"unknown role '{role}'")
        self._acls[doc_id] = dict(acl)

    def check(self, user: str, role: str, doc_id: str, action: str) -> bool:
        """Return True if allowed; record the decision in the audit log.
        Raises AccessDenied with the reason when denied."""
        if role not in ROLE_RANK:
            raise ValueError(f"unknown role '{role}'")
        acl = self._acls.get(doc_id, {})
        required = acl.get(action, "admin")  # default-deny: unspecified = admin-only
        allowed = ROLE_RANK[role] >= ROLE_RANK[required]
        reason = (f"role '{role}' >= required '{required}' for '{action}'"
                  if allowed else
                  f"role '{role}' < required '{required}' for '{action}'")
        self.audit.record(user, role, doc_id, action, allowed, reason)
        if not allowed:
            raise AccessDenied(reason)
        return True

"""Document repository: ingest, check-in/check-out locking, immutable version history.

Every update creates a new immutable version — nothing is ever silently
overwritten. Document identity is a stable ID that survives updates.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone


class RepositoryError(Exception):
    """Raised for repository operations that violate identity or locking rules."""


@dataclass
class DocumentVersion:
    doc_id: str
    version: int
    content: str
    checksum: str
    created_by: str
    created_at: str
    comment: str = ""


@dataclass
class Document:
    doc_id: str
    versions: list = field(default_factory=list)
    checked_out_by: str | None = None

    @property
    def current(self) -> DocumentVersion:
        return self.versions[-1]


def _checksum(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DocumentStore:
    """Versioned document repository with pessimistic locking."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}

    def ingest(self, doc_id: str, content: str, metadata: dict, user: str,
               comment: str = "initial ingest") -> DocumentVersion:
        """Store a new document. Re-ingesting an existing ID is rejected —
        updates go through ``update()`` so history is preserved."""
        if doc_id in self._docs:
            raise RepositoryError(
                f"doc_id '{doc_id}' already exists — use update(), not ingest()")
        doc = Document(doc_id=doc_id)
        version = DocumentVersion(
            doc_id=doc_id, version=1, content=content,
            checksum=_checksum(content), created_by=user,
            created_at=_now(), comment=comment)
        doc.versions.append(version)
        self._docs[doc_id] = doc
        return version

    def update(self, doc_id: str, content: str, user: str,
               comment: str = "") -> DocumentVersion:
        """Create a new immutable version. Requires the document to be
        checked out by the same user (or not checked out at all)."""
        doc = self._get(doc_id)
        if doc.checked_out_by and doc.checked_out_by != user:
            raise RepositoryError(
                f"doc '{doc_id}' is checked out by {doc.checked_out_by}")
        version = DocumentVersion(
            doc_id=doc_id, version=len(doc.versions) + 1, content=content,
            checksum=_checksum(content), created_by=user,
            created_at=_now(), comment=comment)
        doc.versions.append(version)
        return version

    def checkout(self, doc_id: str, user: str) -> None:
        doc = self._get(doc_id)
        if doc.checked_out_by and doc.checked_out_by != user:
            raise RepositoryError(
                f"doc '{doc_id}' is already checked out by {doc.checked_out_by}")
        doc.checked_out_by = user

    def checkin(self, doc_id: str, user: str) -> None:
        doc = self._get(doc_id)
        if not doc.checked_out_by:
            raise RepositoryError(f"doc '{doc_id}' is not checked out")
        if doc.checked_out_by != user:
            raise RepositoryError(
                f"doc '{doc_id}' is checked out by {doc.checked_out_by}, "
                f"not {user}")
        doc.checked_out_by = None

    def version(self, doc_id: str) -> int:
        """Current version number."""
        return len(self._get(doc_id).versions)

    def get_version(self, doc_id: str, n: int) -> DocumentVersion:
        doc = self._get(doc_id)
        if n < 1 or n > len(doc.versions):
            raise RepositoryError(
                f"doc '{doc_id}' has no version {n}")
        return doc.versions[n - 1]

    def history(self, doc_id: str) -> list[DocumentVersion]:
        return list(self._get(doc_id).versions)

    def _get(self, doc_id: str) -> Document:
        if doc_id not in self._docs:
            raise RepositoryError(f"unknown doc_id '{doc_id}'")
        return self._docs[doc_id]

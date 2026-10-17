"""Metadata index: system metadata (read-only) + custom metadata.

System metadata is computed at ingest and can never be written by callers.
Custom metadata (department, doc_type, tags, ...) is queryable.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

SYSTEM_FIELDS = frozenset(
    {"created_by", "created_at", "size", "checksum", "doc_id"})


class MetadataError(Exception):
    """Raised when a caller attempts to write system metadata."""


@dataclass
class MetadataRecord:
    doc_id: str
    system: dict = field(default_factory=dict)
    custom: dict = field(default_factory=dict)

    def get(self, key: str):
        if key in self.system:
            return self.system[key]
        return self.custom.get(key)


class MetadataIndex:
    def __init__(self) -> None:
        self._records: dict[str, MetadataRecord] = {}

    def index(self, doc_id: str, content: str, user: str,
              custom: dict | None = None,
              created_at: str | None = None) -> MetadataRecord:
        """Build the metadata record. System fields are computed here and
        can never be supplied by the caller."""
        system = {
            "doc_id": doc_id,
            "created_by": user,
            "created_at": created_at or datetime.now(timezone.utc).isoformat(),
            "size": len(content.encode("utf-8")),
            "checksum": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }
        record = MetadataRecord(
            doc_id=doc_id, system=system, custom=dict(custom or {}))
        self._records[doc_id] = record
        return record

    def set_custom(self, doc_id: str, key: str, value) -> None:
        """Write custom metadata. System fields are rejected."""
        if key in SYSTEM_FIELDS:
            raise MetadataError(
                f"'{key}' is system metadata and is read-only")
        self._records[doc_id].custom[key] = value

    def get(self, doc_id: str) -> MetadataRecord:
        return self._records[doc_id]

    def query(self, **filters) -> list[str]:
        """Return doc_ids whose metadata (system or custom) matches all filters."""
        hits = []
        for doc_id, record in self._records.items():
            if all(record.get(k) == v for k, v in filters.items()):
                hits.append(doc_id)
        return sorted(hits)

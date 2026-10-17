"""Search with security trimming.

Results are filtered by the caller's RBAC permissions BEFORE return —
a denied document never appears in results, not even its title.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .security import AccessControl, AccessDenied


@dataclass
class SearchResult:
    doc_id: str
    snippet: str
    score: float
    matched_metadata: dict = field(default_factory=dict)


class SearchEngine:
    def __init__(self, access: AccessControl) -> None:
        self.access = access
        self._content: dict[str, str] = {}
        self._meta: dict[str, dict] = {}

    def index(self, doc_id: str, content: str, metadata: dict | None = None) -> None:
        self._content[doc_id] = content
        self._meta[doc_id] = dict(metadata or {})

    def search(self, query: str, user: str, role: str,
               limit: int = 10) -> list[SearchResult]:
        """Full-text + metadata search with security trimming applied first."""
        terms = [t.lower() for t in query.split() if t]
        if not terms:
            return []
        results: list[SearchResult] = []
        for doc_id, content in self._content.items():
            # Security trim: check read permission before touching the result.
            try:
                self.access.check(user, role, doc_id, "read")
            except AccessDenied:
                continue
            haystack = content.lower()
            meta_text = " ".join(str(v) for v in self._meta[doc_id].values()).lower()
            score = sum(haystack.count(t) * 2 + meta_text.count(t)
                        for t in terms)
            if score <= 0:
                continue
            snippet = self._snippet(content, terms)
            matched = {k: v for k, v in self._meta[doc_id].items()
                       if any(t in str(v).lower() for t in terms)}
            results.append(SearchResult(doc_id=doc_id, snippet=snippet,
                                        score=float(score),
                                        matched_metadata=matched))
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    @staticmethod
    def _snippet(content: str, terms: list[str], radius: int = 40) -> str:
        lowered = content.lower()
        for term in terms:
            idx = lowered.find(term)
            if idx >= 0:
                start = max(0, idx - radius)
                end = min(len(content), idx + len(term) + radius)
                return ("..." if start else "") + content[start:end] + \
                       ("..." if end < len(content) else "")
        return content[: 2 * radius]
